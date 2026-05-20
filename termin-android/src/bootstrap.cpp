#include "termin/android/bootstrap.h"

#include <mutex>
#include <memory>
#include <string>
#include <stdexcept>
#include <cstdarg>
#include <cstdint>
#include <cstring>
#include <cmath>
#include <fstream>
#include <vector>
#include <filesystem>

#ifdef __ANDROID__
#include <android/log.h>
#endif

#include <tcbase/tc_log.h>
#include <tgfx2/tc_shader_bridge.hpp>
#include <tgfx/tgfx2_interop.h>
#include <tgfx/tgfx_material_handle.hpp>
#include <tgfx/tgfx_mesh_handle.hpp>
#include <termin/camera/camera_component.hpp>
#include <termin/camera/render_camera_utils.hpp>
#include <termin/engine/engine_core.hpp>
#include <termin/entity/component_registry.hpp>
#include <termin/lighting/light_component.hpp>
#include <termin/render/drawable.hpp>
#include <termin/render/execute_context.hpp>
#include <termin/render/frame_pass.hpp>
#include <termin/render/render_engine.hpp>
#include <termin/render/render_pipeline.hpp>
#include <termin/render/tgfx2_bridge.hpp>
#include <termin/render/mesh_renderer.hpp>
#include <termin/tc_scene.hpp>

extern "C" {
#include "core/tc_component.h"
#include "core/tc_scene_drawable.h"
#include "render/tc_pipeline.h"
}

#ifdef __ANDROID__
#ifndef VK_USE_PLATFORM_ANDROID_KHR
#define VK_USE_PLATFORM_ANDROID_KHR
#endif
#include <vulkan/vulkan.h>
#include <vulkan/vulkan_android.h>
#include <tgfx2/descriptors.hpp>
#include <tgfx2/i_command_list.hpp>
#include <tgfx2/render_context.hpp>
#include <tgfx2/vulkan/vulkan_render_device.hpp>
#include <tgfx2/vulkan/vulkan_swapchain.hpp>
#endif

namespace {

constexpr const char* kAndroidSceneShaderUuid = "termin-android-scene-color";

constexpr const char* kAndroidSceneVertexSource = R"GLSL(
#version 450

layout(push_constant) uniform PushConstants {
    mat4 u_mvp;
} pc;

layout(location = 0) in vec3 in_pos;
layout(location = 1) in vec3 in_color;
layout(location = 0) out vec3 v_color;

void main() {
    v_color = in_color;
    gl_Position = pc.u_mvp * vec4(in_pos, 1.0);
}
)GLSL";

constexpr const char* kAndroidSceneFragmentSource = R"GLSL(
#version 450

layout(location = 0) in vec3 v_color;
layout(location = 0) out vec4 out_color;

void main() {
    out_color = vec4(v_color, 1.0);
}
)GLSL";

class AndroidScenePass final : public termin::CxxFramePass {
public:
    std::string output_res = "OUTPUT";

    AndroidScenePass() {
        pass_name_set("AndroidScenePass");
    }

    std::set<const char*> compute_writes() const override {
        return {output_res.c_str()};
    }

    void execute(termin::ExecuteContext& ctx) override;
};

struct AndroidSceneDrawCall {
    termin::Entity entity;
    tc_component* component = nullptr;
    tc_material_phase* phase = nullptr;
    tc_shader_handle final_shader = tc_shader_handle_invalid();
    int geometry_id = 0;
};

struct AndroidSceneCollectData {
    std::vector<AndroidSceneDrawCall>* calls = nullptr;
    const char* phase_mark = "opaque";
};

bool collect_android_scene_draw_call(tc_component* component, void* user_data) {
    auto* data = static_cast<AndroidSceneCollectData*>(user_data);
    if (!component || !data || !data->calls) {
        return true;
    }

    const char* phase_mark = data->phase_mark ? data->phase_mark : "";
    if (phase_mark[0] != '\0' && !tc_component_has_phase(component, phase_mark)) {
        return true;
    }

    void* draws_ptr = tc_component_get_geometry_draws(component, phase_mark);
    if (!draws_ptr) {
        return true;
    }

    auto* draws = static_cast<std::vector<termin::GeometryDrawCall>*>(draws_ptr);
    for (const termin::GeometryDrawCall& draw : *draws) {
        if (!draw.phase) {
            continue;
        }
        tc_shader_handle final_shader = tc_component_override_shader(
            component,
            phase_mark,
            draw.geometry_id,
            draw.phase->shader
        );
        data->calls->push_back(AndroidSceneDrawCall{
            termin::Entity(component->owner),
            component,
            draw.phase,
            final_shader,
            draw.geometry_id
        });
    }

    return true;
}

struct AndroidBootstrapState {
    std::string app_data_dir;
    std::string asset_root;
    std::string native_lib_dir;
    ANativeWindow* window = nullptr;
    int32_t surface_width = 0;
    int32_t surface_height = 0;
    bool initialized = false;
#ifdef __ANDROID__
    std::unique_ptr<tgfx::VulkanRenderDevice> smoke_device;
    tgfx::ShaderHandle smoke_vertex_shader;
    tgfx::ShaderHandle smoke_fragment_shader;
    tgfx::PipelineHandle smoke_pipeline;
    tgfx::BufferHandle smoke_vertex_buffer;
    tgfx::BufferHandle smoke_index_buffer;
    tgfx::TextureHandle smoke_render_target;
    tgfx::TextureHandle smoke_depth_target;
    uint32_t smoke_width = 0;
    uint32_t smoke_height = 0;
    uint32_t smoke_frame = 0;
    bool smoke_create_failed = false;
    std::unique_ptr<termin::EngineCore> player_engine;
    termin::TcSceneRef player_scene;
    termin::RenderPipeline player_pipeline;
    termin::CameraComponent* player_camera = nullptr;
    tgfx::TextureHandle player_color_target;
    tgfx::TextureHandle player_depth_target;
    uint32_t player_width = 0;
    uint32_t player_height = 0;
    uint32_t player_frame = 0;
#endif
};

std::mutex g_state_mutex;
AndroidBootstrapState g_state;

void AndroidScenePass::execute(termin::ExecuteContext& ctx) {
    if (!ctx.ctx2) {
        tc_log_error("AndroidScenePass: ctx2 is null");
        return;
    }
    if (!ctx.scene.valid()) {
        tc_log_error("AndroidScenePass: scene is invalid");
        return;
    }
    if (!ctx.camera) {
        tc_log_error("AndroidScenePass: camera is missing");
        return;
    }

    auto color_it = ctx.tex2_writes.find(output_res);
    if (color_it == ctx.tex2_writes.end() || !color_it->second) {
        tc_log_error("AndroidScenePass: output texture '%s' is missing", output_res.c_str());
        return;
    }

    tgfx::TextureHandle color = color_it->second;
    tgfx::TextureHandle depth;
    auto depth_it = ctx.tex2_depth_writes.find(output_res);
    if (depth_it != ctx.tex2_depth_writes.end()) {
        depth = depth_it->second;
    }

    auto& ctx2 = *ctx.ctx2;
    auto& device = ctx2.device();

    const float clear_color[4] = {0.02f, 0.025f, 0.035f, 1.0f};
    ctx2.begin_pass(color, depth, clear_color, 1.0f, true);
    ctx2.set_viewport(0, 0, ctx.render_rect.width, ctx.render_rect.height);
    ctx2.set_depth_test(true);
    ctx2.set_depth_write(true);
    ctx2.set_blend(false);
    ctx2.set_cull(tgfx::CullMode::Back);
    ctx2.set_polygon_mode(tgfx::PolygonMode::Fill);

    std::vector<AndroidSceneDrawCall> calls;
    AndroidSceneCollectData collect{&calls, "opaque"};
    tc_scene_foreach_drawable(
        ctx.scene.handle(),
        collect_android_scene_draw_call,
        &collect,
        TC_SCENE_FILTER_NONE,
        ctx.layer_mask
    );

    const termin::Mat44f view = ctx.camera->get_view_matrix().to_float();
    const termin::Mat44f projection = ctx.camera->get_projection_matrix().to_float();

    for (const AndroidSceneDrawCall& call : calls) {
        if (!call.phase || tc_shader_handle_is_invalid(call.final_shader)) {
            continue;
        }

        auto* raw_shader = tc_shader_get(call.final_shader);
        if (!raw_shader) {
            continue;
        }

        tgfx::ShaderHandle vs;
        tgfx::ShaderHandle fs;
        if (!termin::tc_shader_ensure_tgfx2(raw_shader, &device, &vs, &fs)) {
            tc_log_error(
                "AndroidScenePass: tc_shader_ensure_tgfx2 failed for '%s'",
                raw_shader->name ? raw_shader->name : raw_shader->uuid
            );
            continue;
        }

        termin::Drawable* drawable = nullptr;
        if (tc_component_get_drawable_vtable(call.component) ==
            &termin::Drawable::cxx_drawable_vtable()) {
            drawable = static_cast<termin::Drawable*>(
                tc_component_get_drawable_userdata(call.component));
        }
        if (!drawable) {
            continue;
        }

        tc_mesh* mesh = drawable->get_mesh_for_phase("opaque", call.geometry_id);
        if (!mesh) {
            continue;
        }

        ctx2.bind_shader(vs, fs);

        const termin::Mat44f model = drawable->get_model_matrix(call.entity);
        const termin::Mat44f mvp = projection * view * model;
        struct PushConstants {
            float u_mvp[16];
        } push{};
        std::memcpy(push.u_mvp, mvp.data, sizeof(push.u_mvp));
        ctx2.set_push_constants(&push, sizeof(push));

        termin::draw_tc_mesh(ctx2, mesh, {0, 1});
    }

    ctx2.end_pass();
}

std::string infer_shader_artifact_root(const std::string& asset_root) {
    if (asset_root.empty()) {
        return "";
    }

    std::filesystem::path build_assets = std::filesystem::path(asset_root) / "assets";
    if (std::filesystem::is_directory(build_assets / "shaders" / "vulkan")) {
        return build_assets.string();
    }
    return asset_root;
}

#ifdef __ANDROID__
constexpr const char* kAndroidLogTag = "TerminAndroid";

void android_log_info(const char* fmt, ...) {
    va_list args;
    va_start(args, fmt);
    __android_log_vprint(ANDROID_LOG_INFO, kAndroidLogTag, fmt, args);
    va_end(args);
}

void android_log_error(const char* fmt, ...) {
    va_list args;
    va_start(args, fmt);
    __android_log_vprint(ANDROID_LOG_ERROR, kAndroidLogTag, fmt, args);
    va_end(args);
}
#else
void android_log_info(const char*, ...) {}
void android_log_error(const char*, ...) {}
#endif

#ifdef __ANDROID__
bool create_smoke_renderer_locked();
void destroy_smoke_renderer_locked();

void reset_smoke_resources_locked() {
    g_state.smoke_vertex_shader = {};
    g_state.smoke_fragment_shader = {};
    g_state.smoke_pipeline = {};
    g_state.smoke_vertex_buffer = {};
    g_state.smoke_index_buffer = {};
    g_state.smoke_render_target = {};
    g_state.smoke_depth_target = {};
}

void reset_player_resources_locked() {
    g_state.player_color_target = {};
    g_state.player_depth_target = {};
    g_state.player_width = 0;
    g_state.player_height = 0;
}

void destroy_player_targets_locked() {
    if (!g_state.smoke_device) {
        reset_player_resources_locked();
        return;
    }

    auto& device = *g_state.smoke_device;
    if (g_state.player_color_target) {
        device.destroy(g_state.player_color_target);
    }
    if (g_state.player_depth_target) {
        device.destroy(g_state.player_depth_target);
    }
    reset_player_resources_locked();
}

void destroy_player_scene_locked() {
    destroy_player_targets_locked();
    if (g_state.player_pipeline.is_valid()) {
        g_state.player_pipeline.destroy();
    }
    if (g_state.player_scene.valid()) {
        g_state.player_scene.destroy();
    }
    g_state.player_camera = nullptr;
    g_state.player_engine.reset();
    g_state.player_frame = 0;
}

void destroy_smoke_resources_locked() {
    if (!g_state.smoke_device) {
        reset_smoke_resources_locked();
        return;
    }

    auto& device = *g_state.smoke_device;
    if (g_state.smoke_pipeline) {
        device.destroy(g_state.smoke_pipeline);
    }
    if (g_state.smoke_index_buffer) {
        device.destroy(g_state.smoke_index_buffer);
    }
    if (g_state.smoke_vertex_buffer) {
        device.destroy(g_state.smoke_vertex_buffer);
    }
    if (g_state.smoke_render_target) {
        device.destroy(g_state.smoke_render_target);
    }
    if (g_state.smoke_depth_target) {
        device.destroy(g_state.smoke_depth_target);
    }
    if (g_state.smoke_fragment_shader) {
        device.destroy(g_state.smoke_fragment_shader);
    }
    if (g_state.smoke_vertex_shader) {
        device.destroy(g_state.smoke_vertex_shader);
    }
    reset_smoke_resources_locked();
}

#if 0
std::vector<uint8_t> read_asset_file_locked(const char* relative_path) {
    std::string path = g_state.asset_root;
    if (!path.empty() && path.back() != '/') {
        path.push_back('/');
    }
    path += relative_path;

    std::ifstream in(path, std::ios::binary);
    if (!in) {
        throw std::runtime_error("failed to open asset file: " + path);
    }
    in.seekg(0, std::ios::end);
    std::streamoff size = in.tellg();
    if (size <= 0) {
        throw std::runtime_error("asset file is empty: " + path);
    }
    in.seekg(0, std::ios::beg);

    std::vector<uint8_t> bytes(static_cast<size_t>(size));
    in.read(reinterpret_cast<char*>(bytes.data()), size);
    if (!in) {
        throw std::runtime_error("failed to read asset file: " + path);
    }
    android_log_info("smoke: loaded shader asset '%s' bytes=%zu", path.c_str(), bytes.size());
    return bytes;
}

struct Mat4 {
    float v[16] = {};
};

Mat4 mat4_identity() {
    Mat4 out;
    out.v[0] = 1.0f;
    out.v[5] = 1.0f;
    out.v[10] = 1.0f;
    out.v[15] = 1.0f;
    return out;
}

Mat4 mat4_mul(const Mat4& a, const Mat4& b) {
    Mat4 out;
    for (int col = 0; col < 4; ++col) {
        for (int row = 0; row < 4; ++row) {
            float sum = 0.0f;
            for (int k = 0; k < 4; ++k) {
                sum += a.v[k * 4 + row] * b.v[col * 4 + k];
            }
            out.v[col * 4 + row] = sum;
        }
    }
    return out;
}

Mat4 mat4_translation(float x, float y, float z) {
    Mat4 out = mat4_identity();
    out.v[12] = x;
    out.v[13] = y;
    out.v[14] = z;
    return out;
}

Mat4 mat4_rotation_x(float radians) {
    Mat4 out = mat4_identity();
    float c = std::cos(radians);
    float s = std::sin(radians);
    out.v[5] = c;
    out.v[6] = s;
    out.v[9] = -s;
    out.v[10] = c;
    return out;
}

Mat4 mat4_rotation_y(float radians) {
    Mat4 out = mat4_identity();
    float c = std::cos(radians);
    float s = std::sin(radians);
    out.v[0] = c;
    out.v[2] = -s;
    out.v[8] = s;
    out.v[10] = c;
    return out;
}

Mat4 mat4_perspective(float fovy_radians, float aspect, float near_z, float far_z) {
    Mat4 out;
    float f = 1.0f / std::tan(fovy_radians * 0.5f);
    out.v[0] = f / aspect;
    out.v[5] = -f;
    out.v[10] = far_z / (near_z - far_z);
    out.v[11] = -1.0f;
    out.v[14] = (far_z * near_z) / (near_z - far_z);
    return out;
}

Mat4 smoke_mvp_locked() {
    constexpr float kPi = 3.14159265358979323846f;
    float aspect = 1.0f;
    if (g_state.smoke_height != 0) {
        aspect = static_cast<float>(g_state.smoke_width) / static_cast<float>(g_state.smoke_height);
    }
    float t = static_cast<float>(g_state.smoke_frame) * 0.016f;
    Mat4 projection = mat4_perspective(55.0f * kPi / 180.0f, aspect, 0.1f, 20.0f);
    Mat4 view = mat4_translation(0.0f, 0.0f, -3.0f);
    Mat4 model = mat4_mul(mat4_rotation_y(t), mat4_rotation_x(t * 0.67f));
    return mat4_mul(projection, mat4_mul(view, model));
}

bool create_smoke_mesh_resources_locked() {
    if (!g_state.smoke_device) {
        android_log_error("smoke: cannot create mesh resources without Vulkan device");
        tc_log_error("termin_android_smoke: cannot create mesh resources without Vulkan device");
        return false;
    }
    if (g_state.smoke_width == 0 || g_state.smoke_height == 0) {
        android_log_error("smoke: cannot create mesh resources for empty swapchain");
        tc_log_error("termin_android_smoke: cannot create mesh resources for empty swapchain");
        return false;
    }

    auto& device = *g_state.smoke_device;

    tgfx::ShaderDesc vs_desc;
    vs_desc.stage = tgfx::ShaderStage::Vertex;
    vs_desc.debug_name = "android_smoke_cube_vs";
    vs_desc.bytecode = read_asset_file_locked("shaders/android_smoke_cube.vert.spv");
    g_state.smoke_vertex_shader = device.create_shader(vs_desc);

    tgfx::ShaderDesc fs_desc;
    fs_desc.stage = tgfx::ShaderStage::Fragment;
    fs_desc.debug_name = "android_smoke_cube_fs";
    fs_desc.bytecode = read_asset_file_locked("shaders/android_smoke_cube.frag.spv");
    g_state.smoke_fragment_shader = device.create_shader(fs_desc);

    tgfx::TextureDesc rt_desc;
    rt_desc.width = g_state.smoke_width;
    rt_desc.height = g_state.smoke_height;
    rt_desc.format = tgfx::PixelFormat::RGBA8_UNorm;
    rt_desc.usage = tgfx::TextureUsage::ColorAttachment |
                    tgfx::TextureUsage::CopySrc |
                    tgfx::TextureUsage::Sampled;
    g_state.smoke_render_target = device.create_texture(rt_desc);

    tgfx::TextureDesc depth_desc;
    depth_desc.width = g_state.smoke_width;
    depth_desc.height = g_state.smoke_height;
    depth_desc.format = tgfx::PixelFormat::D32F;
    depth_desc.usage = tgfx::TextureUsage::DepthStencilAttachment;
    g_state.smoke_depth_target = device.create_texture(depth_desc);

    tgfx::PipelineDesc pipeline_desc;
    pipeline_desc.vertex_shader = g_state.smoke_vertex_shader;
    pipeline_desc.fragment_shader = g_state.smoke_fragment_shader;
    pipeline_desc.topology = tgfx::PrimitiveTopology::TriangleList;
    pipeline_desc.depth_stencil.depth_test = true;
    pipeline_desc.depth_stencil.depth_write = true;
    pipeline_desc.depth_stencil.depth_compare = tgfx::CompareOp::Less;
    pipeline_desc.raster.cull = tgfx::CullMode::None;
    pipeline_desc.color_formats = {tgfx::PixelFormat::RGBA8_UNorm};
    pipeline_desc.depth_format = tgfx::PixelFormat::D32F;

    tgfx::VertexBufferLayout layout;
    layout.stride = 6 * sizeof(float);
    layout.attributes = {
        {0, tgfx::VertexFormat::Float3, 0},
        {1, tgfx::VertexFormat::Float3, 3 * sizeof(float)},
    };
    pipeline_desc.vertex_layouts.push_back(layout);
    g_state.smoke_pipeline = device.create_pipeline(pipeline_desc);

    const float vertices[] = {
        -0.55f, -0.55f, -0.55f,  0.95f, 0.10f, 0.10f,
         0.55f, -0.55f, -0.55f,  0.95f, 0.70f, 0.10f,
         0.55f,  0.55f, -0.55f,  0.95f, 0.95f, 0.10f,
        -0.55f,  0.55f, -0.55f,  0.15f, 0.85f, 0.20f,
        -0.55f, -0.55f,  0.55f,  0.10f, 0.70f, 0.95f,
         0.55f, -0.55f,  0.55f,  0.25f, 0.25f, 1.00f,
         0.55f,  0.55f,  0.55f,  0.90f, 0.20f, 0.95f,
        -0.55f,  0.55f,  0.55f,  0.80f, 0.80f, 1.00f,
    };
    tgfx::BufferDesc vb_desc;
    vb_desc.size = sizeof(vertices);
    vb_desc.usage = tgfx::BufferUsage::Vertex;
    vb_desc.cpu_visible = true;
    g_state.smoke_vertex_buffer = device.create_buffer(vb_desc);
    device.upload_buffer(
        g_state.smoke_vertex_buffer,
        {reinterpret_cast<const uint8_t*>(vertices), sizeof(vertices)}
    );

    const uint32_t indices[] = {
        4, 5, 6,  4, 6, 7,
        1, 0, 3,  1, 3, 2,
        0, 4, 7,  0, 7, 3,
        5, 1, 2,  5, 2, 6,
        3, 7, 6,  3, 6, 2,
        0, 1, 5,  0, 5, 4,
    };
    tgfx::BufferDesc ib_desc;
    ib_desc.size = sizeof(indices);
    ib_desc.usage = tgfx::BufferUsage::Index;
    ib_desc.cpu_visible = true;
    g_state.smoke_index_buffer = device.create_buffer(ib_desc);
    device.upload_buffer(
        g_state.smoke_index_buffer,
        {reinterpret_cast<const uint8_t*>(indices), sizeof(indices)}
    );

    android_log_info(
        "smoke: cube resources created rt=%ux%u vs=%u fs=%u pipeline=%u vb=%u ib=%u",
        g_state.smoke_width,
        g_state.smoke_height,
        g_state.smoke_vertex_shader.id,
        g_state.smoke_fragment_shader.id,
        g_state.smoke_pipeline.id,
        g_state.smoke_vertex_buffer.id,
        g_state.smoke_index_buffer.id
    );
    tc_log_info(
        "termin_android_smoke: cube resources created rt=%ux%u pipeline=%u",
        g_state.smoke_width,
        g_state.smoke_height,
        g_state.smoke_pipeline.id
    );
    return true;
}
#endif
#endif

bool ensure_player_targets_locked() {
#ifdef __ANDROID__
    if (!g_state.smoke_device) {
        android_log_error("player: cannot create render targets without Vulkan device");
        return false;
    }
    if (g_state.smoke_width == 0 || g_state.smoke_height == 0) {
        android_log_error("player: cannot create render targets for empty swapchain");
        return false;
    }
    if (g_state.player_color_target &&
        g_state.player_depth_target &&
        g_state.player_width == g_state.smoke_width &&
        g_state.player_height == g_state.smoke_height) {
        return true;
    }

    destroy_player_targets_locked();

    auto& device = *g_state.smoke_device;

    tgfx::TextureDesc color_desc;
    color_desc.width = g_state.smoke_width;
    color_desc.height = g_state.smoke_height;
    color_desc.format = tgfx::PixelFormat::RGBA8_UNorm;
    color_desc.usage = tgfx::TextureUsage::ColorAttachment |
                       tgfx::TextureUsage::CopySrc |
                       tgfx::TextureUsage::CopyDst |
                       tgfx::TextureUsage::Sampled;
    g_state.player_color_target = device.create_texture(color_desc);

    tgfx::TextureDesc depth_desc;
    depth_desc.width = g_state.smoke_width;
    depth_desc.height = g_state.smoke_height;
    depth_desc.format = tgfx::PixelFormat::D32F;
    depth_desc.usage = tgfx::TextureUsage::DepthStencilAttachment |
                       tgfx::TextureUsage::CopySrc |
                       tgfx::TextureUsage::Sampled;
    g_state.player_depth_target = device.create_texture(depth_desc);

    if (!g_state.player_color_target || !g_state.player_depth_target) {
        android_log_error("player: failed to create render target textures");
        destroy_player_targets_locked();
        return false;
    }

    g_state.player_width = g_state.smoke_width;
    g_state.player_height = g_state.smoke_height;
    android_log_info("player: render targets created %ux%u", g_state.player_width, g_state.player_height);
    return true;
#else
    return false;
#endif
}

bool ensure_player_scene_locked() {
#ifdef __ANDROID__
    if (g_state.player_scene.valid() && g_state.player_pipeline.is_valid() && g_state.player_camera) {
        return true;
    }

    if (!g_state.player_engine) {
        g_state.player_engine = std::make_unique<termin::EngineCore>();
    }

    const char* required_components[] = {
        "MeshComponent",
        "MeshRenderer",
        "CameraComponent",
        "LightComponent",
        "UnknownComponent",
    };
    for (const char* name : required_components) {
        if (!tc_component_registry_has(name)) {
            android_log_error("player: required component is not registered: %s", name);
            tc_log_error("termin_android_player: required component is not registered: %s", name);
            return false;
        }
    }

    termin::TcShader shader = termin::TcShader::get_or_create(kAndroidSceneShaderUuid);
    if (!shader.is_valid() ||
        !shader.set_sources(
            kAndroidSceneVertexSource,
            kAndroidSceneFragmentSource,
            "",
            "AndroidSceneColor",
            "termin-android/generated")) {
        android_log_error("player: failed to create scene shader");
        return false;
    }

    termin::TcMaterial material =
        termin::TcMaterial::create("AndroidSceneMaterial", "termin-android-scene-material");
    if (!material.is_valid()) {
        android_log_error("player: failed to create scene material");
        return false;
    }
    material.clear_phases();
    if (!material.add_phase(shader, "opaque", 0)) {
        android_log_error("player: failed to add material phase");
        return false;
    }

    struct Vertex {
        float position[3];
        float color[3];
    };
    const Vertex vertices[] = {
        {{-1.0f, 0.0f, -0.8f}, {0.0f, 1.0f, 0.15f}},
        {{ 1.0f, 0.0f, -0.8f}, {0.1f, 0.35f, 1.0f}},
        {{ 0.0f, 0.0f,  1.0f}, {1.0f, 0.1f, 0.05f}},
    };
    const uint32_t indices[] = {0, 1, 2};
    tc_vertex_layout layout;
    tc_vertex_layout_init(&layout);
    tc_vertex_layout_add(&layout, "position", 3, TC_ATTRIB_FLOAT32, 0);
    tc_vertex_layout_add(&layout, "color", 3, TC_ATTRIB_FLOAT32, 1);

    termin::TcMesh mesh = termin::TcMesh::from_interleaved(
        vertices,
        3,
        indices,
        3,
        layout,
        "AndroidSceneTriangle",
        "termin-android-scene-triangle",
        TC_DRAW_TRIANGLES
    );
    if (!mesh.is_valid()) {
        android_log_error("player: failed to create triangle mesh");
        return false;
    }

    g_state.player_scene = termin::TcSceneRef::create("android-player-scene");
    if (!g_state.player_scene.valid()) {
        android_log_error("player: failed to create tc_scene");
        return false;
    }

    termin::Entity triangle = g_state.player_scene.create_entity("Triangle");
    auto* mesh_component = new termin::MeshComponent();
    mesh_component->set_mesh(mesh);
    triangle.add_component(mesh_component);
    auto* mesh_renderer = new termin::MeshRenderer();
    mesh_renderer->set_mesh(mesh);
    mesh_renderer->set_material(material);
    triangle.add_component(mesh_renderer);

    termin::Entity camera_entity = g_state.player_scene.create_entity("MainCamera");
    double camera_pos[3] = {0.0, -3.2, 0.0};
    camera_entity.set_local_position(camera_pos);
    auto* camera = new termin::CameraComponent();
    camera->near_clip = 0.1;
    camera->far_clip = 50.0;
    camera->set_fov_y_degrees(55.0);
    camera->set_aspect(
        g_state.smoke_height == 0
            ? 1.0
            : static_cast<double>(g_state.smoke_width) / static_cast<double>(g_state.smoke_height)
    );
    camera_entity.add_component(camera);
    g_state.player_camera = camera;

    termin::Entity light_entity = g_state.player_scene.create_entity("KeyLight");
    auto* light = new termin::LightComponent();
    light_entity.add_component(light);

    tc_pipeline_handle pipeline_handle = tc_pipeline_create("AndroidScenePipeline");
    if (!tc_pipeline_handle_valid(pipeline_handle)) {
        android_log_error("player: failed to create render pipeline");
        return false;
    }
    g_state.player_pipeline = termin::RenderPipeline(pipeline_handle);
    auto* pass = new AndroidScenePass();
    g_state.player_pipeline.add_pass(pass->tc_pass_ptr());

    android_log_info(
        "player: tc_scene created entities=%zu mesh_vertices=%zu pipeline_passes=%zu",
        g_state.player_scene.entity_count(),
        mesh.vertex_count(),
        g_state.player_pipeline.pass_count()
    );
    return true;
#else
    return false;
#endif
}

int render_player_frame_locked() {
#ifdef __ANDROID__
    if (!g_state.smoke_device) {
        if (!create_smoke_renderer_locked()) {
            return 0;
        }
    }
    if (!ensure_player_scene_locked() || !ensure_player_targets_locked()) {
        return 0;
    }

    try {
        g_state.player_camera->set_aspect(
            g_state.player_height == 0
                ? 1.0
                : static_cast<double>(g_state.player_width) / static_cast<double>(g_state.player_height)
        );

        termin::RenderEngine* engine = g_state.player_engine->rendering_manager.render_engine();
        if (!engine) {
            android_log_error("player: RenderEngine is unavailable");
            return 0;
        }

        termin::RenderTargetContext target;
        target.name = "Main";
        target.render_rect = termin::Rect4i{
            0,
            0,
            static_cast<int>(g_state.player_width),
            static_cast<int>(g_state.player_height)
        };
        target.output_color_tex = g_state.player_color_target;
        target.output_depth_tex = g_state.player_depth_target;
        target.clear_color_enabled = false;
        target.clear_depth_enabled = false;
        target.camera = termin::make_render_camera(
            *g_state.player_camera,
            target.render_rect.height == 0
                ? 1.0
                : static_cast<double>(target.render_rect.width) /
                  static_cast<double>(target.render_rect.height)
        );

        std::unordered_map<std::string, termin::RenderTargetContext> targets;
        targets.emplace(target.name, target);
        std::vector<termin::Light> lights;

        engine->render_scene_pipeline_offscreen(
            g_state.player_pipeline,
            g_state.player_scene.handle(),
            targets,
            lights,
            target.name
        );

        bool recreate = g_state.smoke_device->swapchain()->compose_and_present(
            g_state.player_color_target);
        ++g_state.player_frame;
        if (recreate || g_state.player_frame == 1 || g_state.player_frame % 60 == 0) {
            android_log_info(
                "player: rendered tc_scene frame=%u recreate=%d",
                g_state.player_frame,
                recreate ? 1 : 0
            );
        }
        if (recreate) {
            destroy_smoke_renderer_locked();
        }
        return 1;
    } catch (const std::exception& e) {
        android_log_error("player: render failed: %s", e.what());
        tc_log_error("termin_android_player: render failed: %s", e.what());
        destroy_smoke_renderer_locked();
        return 0;
    }
#else
    return 0;
#endif
}

void destroy_smoke_renderer_locked() {
#ifdef __ANDROID__
    destroy_player_scene_locked();
    if (g_state.smoke_device) {
        android_log_info("smoke: destroy renderer");
        try {
            destroy_smoke_resources_locked();
            g_state.smoke_device->wait_idle();
        } catch (const std::exception& e) {
            android_log_error("smoke: destroy failed: %s", e.what());
            tc_log_error("termin_android_smoke: destroy failed: %s", e.what());
        }
    }
    g_state.smoke_device.reset();
    reset_smoke_resources_locked();
    g_state.smoke_width = 0;
    g_state.smoke_height = 0;
    g_state.smoke_frame = 0;
    tgfx2_interop_set_device(nullptr);
#endif
}

void release_window_locked() {
    destroy_smoke_renderer_locked();
#ifdef __ANDROID__
    if (g_state.window) {
        ANativeWindow_release(g_state.window);
    }
#endif
    g_state.window = nullptr;
    g_state.surface_width = 0;
    g_state.surface_height = 0;
#ifdef __ANDROID__
    g_state.smoke_create_failed = false;
#endif
}

#ifdef __ANDROID__
bool create_smoke_renderer_locked() {
    if (g_state.smoke_create_failed) {
        android_log_info("smoke: create skipped after earlier failure on this surface");
        return false;
    }
    if (!g_state.window) {
        android_log_error("smoke: cannot create renderer without ANativeWindow");
        tc_log_error("termin_android_smoke: cannot create renderer without ANativeWindow");
        return false;
    }
    if (g_state.surface_width <= 0 || g_state.surface_height <= 0) {
        android_log_error(
            "smoke: invalid surface size %dx%d",
            static_cast<int>(g_state.surface_width),
            static_cast<int>(g_state.surface_height)
        );
        tc_log_error(
            "termin_android_smoke: invalid surface size %dx%d",
            static_cast<int>(g_state.surface_width),
            static_cast<int>(g_state.surface_height)
        );
        return false;
    }

    destroy_smoke_renderer_locked();

    try {
        android_log_info(
            "smoke: create Vulkan renderer for surface=%p size=%dx%d",
            static_cast<void*>(g_state.window),
            static_cast<int>(g_state.surface_width),
            static_cast<int>(g_state.surface_height)
        );
        tgfx::VulkanDeviceCreateInfo info{};
        info.enable_validation = false;
        info.instance_extensions = {
            VK_KHR_SURFACE_EXTENSION_NAME,
            VK_KHR_ANDROID_SURFACE_EXTENSION_NAME,
        };
        info.swapchain_width = static_cast<uint32_t>(g_state.surface_width);
        info.swapchain_height = static_cast<uint32_t>(g_state.surface_height);
        ANativeWindow* window = g_state.window;
        info.surface_factory = [window](VkInstance instance) -> VkSurfaceKHR {
            VkAndroidSurfaceCreateInfoKHR ci{};
            ci.sType = VK_STRUCTURE_TYPE_ANDROID_SURFACE_CREATE_INFO_KHR;
            ci.window = window;
            VkSurfaceKHR surface = VK_NULL_HANDLE;
            VkResult result = vkCreateAndroidSurfaceKHR(instance, &ci, nullptr, &surface);
            if (result != VK_SUCCESS) {
                android_log_error(
                    "smoke: vkCreateAndroidSurfaceKHR failed result=%d",
                    static_cast<int>(result)
                );
                tc_log_error(
                    "termin_android_smoke: vkCreateAndroidSurfaceKHR failed result=%d",
                    static_cast<int>(result)
                );
                return VK_NULL_HANDLE;
            }
            return surface;
        };

        g_state.smoke_device = std::make_unique<tgfx::VulkanRenderDevice>(info);
        tgfx2_interop_set_device(g_state.smoke_device.get());
        tgfx2_gpu_ops_register();

        g_state.smoke_width = g_state.smoke_device->swapchain()->width();
        g_state.smoke_height = g_state.smoke_device->swapchain()->height();

        android_log_info(
            "smoke: Vulkan renderer created swapchain=%ux%u images=%u",
            g_state.smoke_width,
            g_state.smoke_height,
            g_state.smoke_device->swapchain()->image_count()
        );
        tc_log_info(
            "termin_android_smoke: Vulkan renderer created swapchain=%ux%u images=%u",
            g_state.smoke_width,
            g_state.smoke_height,
            g_state.smoke_device->swapchain()->image_count()
        );
        return true;
    } catch (const std::exception& e) {
        android_log_error("smoke: create failed: %s", e.what());
        tc_log_error("termin_android_smoke: create failed: %s", e.what());
        destroy_smoke_renderer_locked();
        g_state.smoke_create_failed = true;
        return false;
    }
}

int render_smoke_frame_locked() {
    return render_player_frame_locked();
}
#endif

} // namespace

extern "C" int termin_android_initialize(const termin_android_config* config) {
    std::lock_guard<std::mutex> lock(g_state_mutex);
    if (!config) {
        android_log_error("initialize: config is NULL");
        tc_log_error("termin_android_initialize: config is NULL");
        return 0;
    }

    g_state.app_data_dir = config->app_data_dir ? config->app_data_dir : "";
    g_state.asset_root = config->asset_root ? config->asset_root : "";
    g_state.native_lib_dir = config->native_lib_dir ? config->native_lib_dir : "";
    g_state.initialized = true;

    std::string shader_artifact_root = infer_shader_artifact_root(g_state.asset_root);
    termin::tgfx2_set_shader_artifact_root(
        shader_artifact_root.empty() ? nullptr : shader_artifact_root.c_str());
    std::filesystem::path scene_vertex_spv =
        std::filesystem::path(shader_artifact_root) / "shaders" / "vulkan" /
        (std::string(kAndroidSceneShaderUuid) + ".vert.spv");
    std::filesystem::path scene_fragment_spv =
        std::filesystem::path(shader_artifact_root) / "shaders" / "vulkan" /
        (std::string(kAndroidSceneShaderUuid) + ".frag.spv");
    if (!std::filesystem::is_regular_file(scene_vertex_spv) ||
        !std::filesystem::is_regular_file(scene_fragment_spv)) {
        android_log_error(
            "initialize: missing Android scene shader artifacts: vert='%s' exists=%d frag='%s' exists=%d",
            scene_vertex_spv.string().c_str(),
            std::filesystem::is_regular_file(scene_vertex_spv) ? 1 : 0,
            scene_fragment_spv.string().c_str(),
            std::filesystem::is_regular_file(scene_fragment_spv) ? 1 : 0
        );
    }

    android_log_info(
        "initialize: app_data_dir='%s', asset_root='%s', shader_artifact_root='%s', native_lib_dir='%s'",
        g_state.app_data_dir.c_str(),
        g_state.asset_root.c_str(),
        shader_artifact_root.c_str(),
        g_state.native_lib_dir.c_str()
    );
    tc_log_info(
        "termin_android_initialize: app_data_dir='%s', asset_root='%s', shader_artifact_root='%s', native_lib_dir='%s'",
        g_state.app_data_dir.c_str(),
        g_state.asset_root.c_str(),
        shader_artifact_root.c_str(),
        g_state.native_lib_dir.c_str()
    );
    return 1;
}

extern "C" void termin_android_shutdown(void) {
    std::lock_guard<std::mutex> lock(g_state_mutex);
    release_window_locked();
    g_state.app_data_dir.clear();
    g_state.asset_root.clear();
    g_state.native_lib_dir.clear();
    g_state.initialized = false;
    termin::tgfx2_set_shader_artifact_root(nullptr);
    android_log_info("shutdown");
    tc_log_info("termin_android_shutdown");
}

extern "C" void termin_android_set_shader_artifact_root(const char* root) {
    std::lock_guard<std::mutex> lock(g_state_mutex);
    g_state.asset_root = root ? root : "";
    termin::tgfx2_set_shader_artifact_root(g_state.asset_root.c_str());
    tc_log_info("termin_android_set_shader_artifact_root: '%s'", g_state.asset_root.c_str());
}

extern "C" const char* termin_android_get_shader_artifact_root(void) {
    return termin::tgfx2_get_shader_artifact_root();
}

extern "C" void termin_android_on_surface_created(ANativeWindow* window) {
    std::lock_guard<std::mutex> lock(g_state_mutex);
    release_window_locked();
    if (!window) {
        android_log_error("surface_created: window is NULL");
        tc_log_error("termin_android_on_surface_created: window is NULL");
        return;
    }

#ifdef __ANDROID__
    ANativeWindow_acquire(window);
    g_state.surface_width = ANativeWindow_getWidth(window);
    g_state.surface_height = ANativeWindow_getHeight(window);
#endif
    g_state.window = window;
#ifdef __ANDROID__
    g_state.smoke_create_failed = false;
#endif
    android_log_info(
        "surface_created: window=%p size=%dx%d; waiting for surfaceChanged before render",
        static_cast<void*>(window),
        static_cast<int>(g_state.surface_width),
        static_cast<int>(g_state.surface_height)
    );
    tc_log_info(
        "termin_android_on_surface_created: window=%p size=%dx%d",
        static_cast<void*>(window),
        static_cast<int>(g_state.surface_width),
        static_cast<int>(g_state.surface_height)
    );
}

extern "C" void termin_android_on_surface_changed(int32_t width, int32_t height) {
    std::lock_guard<std::mutex> lock(g_state_mutex);
    bool size_changed = g_state.surface_width != width || g_state.surface_height != height;
    g_state.surface_width = width;
    g_state.surface_height = height;
    android_log_info(
        "surface_changed: size=%dx%d size_changed=%d",
        static_cast<int>(width),
        static_cast<int>(height),
        size_changed ? 1 : 0
    );
    tc_log_info(
        "termin_android_on_surface_changed: size=%dx%d",
        static_cast<int>(width),
        static_cast<int>(height)
    );
    if (size_changed) {
        destroy_smoke_renderer_locked();
    }
    render_smoke_frame_locked();
}

extern "C" void termin_android_on_surface_destroyed(void) {
    std::lock_guard<std::mutex> lock(g_state_mutex);
    release_window_locked();
    android_log_info("surface_destroyed");
    tc_log_info("termin_android_on_surface_destroyed");
}

extern "C" int termin_android_render_frame(void) {
    std::lock_guard<std::mutex> lock(g_state_mutex);
#ifdef __ANDROID__
    return render_smoke_frame_locked();
#else
    tc_log_error("termin_android_render_frame: only supported on Android");
    return 0;
#endif
}

extern "C" int termin_android_smoke_render(void) {
    return termin_android_render_frame();
}

extern "C" ANativeWindow* termin_android_native_window(void) {
    std::lock_guard<std::mutex> lock(g_state_mutex);
    return g_state.window;
}

extern "C" int32_t termin_android_surface_width(void) {
    std::lock_guard<std::mutex> lock(g_state_mutex);
    return g_state.surface_width;
}

extern "C" int32_t termin_android_surface_height(void) {
    std::lock_guard<std::mutex> lock(g_state_mutex);
    return g_state.surface_height;
}
