#include <termin/render/normal_pass.hpp>

#include <termin/camera/camera_component.hpp>
#include <termin/camera/render_camera_utils.hpp>
#include <termin/render/tgfx2_bridge.hpp>

#include <tgfx2/render_context.hpp>
#include <tgfx2/descriptors.hpp>
#include <tgfx2/enums.hpp>
#include <tgfx2/opengl/opengl_render_device.hpp>
#include <tgfx2/tc_shader_bridge.hpp>

#include <tgfx/resources/tc_shader_registry.h>
#include <core/tc_drawable_protocol.h>

#include <tcbase/tc_log.hpp>

#include <cstdlib>
#include <cstring>
#include <optional>
#include <span>

namespace termin {

namespace {

// PerFrame UBO (binding 0): view + projection. 128 bytes std140.
struct NormalPerFrameStd140 {
    float u_view[16];
    float u_projection[16];
};
static_assert(sizeof(NormalPerFrameStd140) == 128,
              "NormalPerFrameStd140 must be 2 * mat4");

// PushConstants (binding 14): per-object model matrix.
struct NormalPushStd140 {
    float u_model[16];
};
static_assert(sizeof(NormalPushStd140) == 64,
              "NormalPushStd140 must be exactly one mat4");

constexpr const char* NORMAL_PASS_VERT_UBO = R"(
#version 330 core
#extension GL_ARB_shading_language_420pack : require

layout(location = 0) in vec3 a_position;
layout(location = 1) in vec3 a_normal;
layout(location = 2) in vec2 a_texcoord;

layout(std140, binding = 0) uniform PerFrame {
    mat4 u_view;
    mat4 u_projection;
};

layout(std140, binding = 14) uniform PushConstants {
    mat4 u_model;
};

out vec3 v_world_normal;

void main() {
    mat3 normal_matrix = transpose(inverse(mat3(u_model)));
    v_world_normal = normalize(normal_matrix * a_normal);

    vec4 world_pos = u_model * vec4(a_position, 1.0);
    gl_Position = u_projection * u_view * world_pos;
}
)";

constexpr const char* NORMAL_PASS_FRAG_UBO = R"(
#version 330 core

in vec3 v_world_normal;
out vec4 FragColor;

void main() {
    vec3 encoded = normalize(v_world_normal) * 0.5 + 0.5;
    FragColor = vec4(encoded, 1.0);
}
)";

} // anonymous namespace

const char* NORMAL_PASS_VERT = R"(
#version 330 core

layout(location = 0) in vec3 a_position;
layout(location = 1) in vec3 a_normal;
layout(location = 2) in vec2 a_texcoord;

uniform mat4 u_model;
uniform mat4 u_view;
uniform mat4 u_projection;

out vec3 v_world_normal;

void main()
{
    mat3 normal_matrix = transpose(inverse(mat3(u_model)));
    v_world_normal = normalize(normal_matrix * a_normal);

    vec4 world_pos = u_model * vec4(a_position, 1.0);
    gl_Position = u_projection * u_view * world_pos;
}
)";

const char* NORMAL_PASS_FRAG = R"(
#version 330 core

in vec3 v_world_normal;
out vec4 FragColor;

void main()
{
    vec3 encoded = normalize(v_world_normal) * 0.5 + 0.5;
    FragColor = vec4(encoded, 1.0);
}
)";

void NormalPass::ensure_tgfx2_resources(tgfx::IRenderDevice& device) {
    if (device2_ == &device && normal_vs2_ && normal_fs2_ && per_frame_ubo_) {
        return;
    }
    if (device2_ && device2_ != &device) {
        release_tgfx2_resources();
    }
    device2_ = &device;

    tgfx::ShaderDesc vs_desc;
    vs_desc.stage = tgfx::ShaderStage::Vertex;
    vs_desc.source = NORMAL_PASS_VERT_UBO;
    normal_vs2_ = device.create_shader(vs_desc);

    tgfx::ShaderDesc fs_desc;
    fs_desc.stage = tgfx::ShaderStage::Fragment;
    fs_desc.source = NORMAL_PASS_FRAG_UBO;
    normal_fs2_ = device.create_shader(fs_desc);

    tgfx::BufferDesc ubo_desc;
    ubo_desc.size = sizeof(NormalPerFrameStd140);
    ubo_desc.usage = tgfx::BufferUsage::Uniform | tgfx::BufferUsage::CopyDst;
    per_frame_ubo_ = device.create_buffer(ubo_desc);
}

void NormalPass::release_tgfx2_resources() {
    if (!device2_) return;
    if (normal_vs2_) { device2_->destroy(normal_vs2_); normal_vs2_ = {}; }
    if (normal_fs2_) { device2_->destroy(normal_fs2_); normal_fs2_ = {}; }
    if (per_frame_ubo_) { device2_->destroy(per_frame_ubo_); per_frame_ubo_ = {}; }
    device2_ = nullptr;
}

// ----------------------------------------------------------------------------
// tgfx2 path — Stage 5.E.
// ----------------------------------------------------------------------------
void NormalPass::execute_with_data_tgfx2(
    ExecuteContext& ctx,
    const Rect4i& rect,
    tc_scene_handle scene,
    const Mat44f& view,
    const Mat44f& projection,
    uint64_t layer_mask
) {
    if (!ctx.ctx2) {
        tc::Log::error("NormalPass/tgfx2: ctx2 is null");
        return;
    }

    auto color_it = ctx.tex2_writes.find(output_res);
    if (color_it == ctx.tex2_writes.end() || !color_it->second) {
        tc::Log::error("NormalPass/tgfx2: missing tgfx2 color texture for '%s'",
                       output_res.c_str());
        return;
    }
    tgfx::TextureHandle color_tex2 = color_it->second;

    auto depth_it = ctx.tex2_depth_writes.find(output_res);
    tgfx::TextureHandle depth_tex2 =
        (depth_it != ctx.tex2_depth_writes.end()) ? depth_it->second : tgfx::TextureHandle{};

    auto* gl_dev = dynamic_cast<tgfx::OpenGLRenderDevice*>(&ctx.ctx2->device());
    if (!gl_dev) {
        tc::Log::error("NormalPass/tgfx2: device is not OpenGLRenderDevice");
        return;
    }

    ensure_tgfx2_resources(ctx.ctx2->device());

    TcShader& base_shader = get_shader();
    collect_draw_calls(scene, layer_mask, base_shader.handle);
    sort_draw_calls_by_shader();

    entity_names.clear();
    std::set<std::string> seen_entities;

    auto cc = clear_color();
    float clear_rgba[4] = {cc[0], cc[1], cc[2], cc[3]};

    ctx.ctx2->begin_pass(color_tex2, depth_tex2, clear_rgba, 1.0f, true);
    ctx.ctx2->set_viewport(0, 0, rect.width, rect.height);
    ctx.ctx2->set_depth_test(true);
    ctx.ctx2->set_depth_write(true);
    ctx.ctx2->set_blend(false);
    ctx.ctx2->set_cull(tgfx::CullMode::Back);
    ctx.ctx2->bind_shader(normal_vs2_, normal_fs2_);

    NormalPerFrameStd140 per_frame{};
    std::memcpy(per_frame.u_view, view.data, sizeof(float) * 16);
    std::memcpy(per_frame.u_projection, projection.data, sizeof(float) * 16);
    ctx.ctx2->device().upload_buffer(
        per_frame_ubo_,
        std::span<const uint8_t>(
            reinterpret_cast<const uint8_t*>(&per_frame),
            sizeof(per_frame)));
    ctx.ctx2->bind_uniform_buffer(0, per_frame_ubo_);

    const std::string& debug_symbol = get_debug_internal_point();

    for (const auto& dc : cached_draw_calls_) {
        Drawable* drawable = nullptr;
        if (tc_component_get_drawable_vtable(dc.component) == &Drawable::cxx_drawable_vtable()) {
            drawable = static_cast<Drawable*>(tc_component_get_drawable_userdata(dc.component));
        }
        if (!drawable) continue;

        tc_mesh* mesh = drawable->get_mesh_for_phase(phase_name(), dc.geometry_id);
        if (!mesh) continue;  // non-mesh drawables skipped

        Mat44f model = drawable->get_model_matrix(dc.entity);

        const char* name = dc.entity.name();
        if (name && seen_entities.insert(name).second) {
            entity_names.push_back(name);
        }

        bool override_is_base = tc_shader_handle_eq(dc.final_shader, base_shader.handle);

        Tgfx2MeshBinding bind = wrap_mesh_as_tgfx2(*gl_dev, mesh);
        if (bind.index_count == 0) continue;

        if (override_is_base) {
            NormalPushStd140 push{};
            std::memcpy(push.u_model, model.data, sizeof(float) * 16);
            ctx.ctx2->set_push_constants(&push, sizeof(push));

            ctx.ctx2->set_vertex_layout(bind.layout);
            ctx.ctx2->set_topology(bind.topology);
            ctx.ctx2->draw(bind.vertex_buffer, bind.index_buffer,
                           bind.index_count, bind.index_type);
        } else {
            // Shader override (skinning): compile via bridge, upload
            // u_model/u_view/u_projection via ctx2 transitional helpers.
            tc_shader* raw = tc_shader_get(dc.final_shader);
            if (!raw) {
                gl_dev->destroy(bind.vertex_buffer);
                gl_dev->destroy(bind.index_buffer);
                continue;
            }
            tgfx::ShaderHandle vs2, fs2;
            if (!tc_shader_ensure_tgfx2(raw, &ctx.ctx2->device(), &vs2, &fs2)) {
                gl_dev->destroy(bind.vertex_buffer);
                gl_dev->destroy(bind.index_buffer);
                continue;
            }
            ctx.ctx2->bind_shader(vs2, fs2);
            ctx.ctx2->set_vertex_layout(bind.layout);
            ctx.ctx2->set_topology(bind.topology);

            ctx.ctx2->set_uniform_mat4("u_view",       view.data,       false);
            ctx.ctx2->set_uniform_mat4("u_projection", projection.data, false);
            ctx.ctx2->set_uniform_mat4("u_model",      model.data,      false);

            drawable->upload_per_draw_uniforms_tgfx2(*ctx.ctx2, dc.geometry_id);

            ctx.ctx2->draw(bind.vertex_buffer, bind.index_buffer,
                           bind.index_count, bind.index_type);

            ctx.ctx2->bind_shader(normal_vs2_, normal_fs2_);
        }

        gl_dev->destroy(bind.vertex_buffer);
        gl_dev->destroy(bind.index_buffer);
    }

    ctx.ctx2->end_pass();
    // color_tex2/depth_tex2 are persistent FBOPool wrappers — do not destroy.
}

void NormalPass::execute(ExecuteContext& ctx) {
    tc_scene_handle scene = ctx.scene.handle();
    const RenderCamera* camera = ctx.camera;
    Rect4i rect = ctx.rect;
    std::optional<RenderCamera> named_camera_snapshot;

    if (!camera_name.empty()) {
        CameraComponent* named_camera = find_camera_by_name(scene, camera_name);
        if (!named_camera) {
            return;
        }
        named_camera_snapshot = make_render_camera(*named_camera);
        camera = &*named_camera_snapshot;
    }

    if (!camera) {
        return;
    }

    if (ctx.ctx2) {
        auto it = ctx.tex2_writes.find(output_res);
        if (it != ctx.tex2_writes.end() && it->second) {
            auto desc = ctx.ctx2->device().texture_desc(it->second);
            int w = static_cast<int>(desc.width);
            int h = static_cast<int>(desc.height);
            if (w > 0 && h > 0) {
                rect = Rect4i(0, 0, w, h);
                if (!camera_name.empty()) {
                    CameraComponent* named_camera = find_camera_by_name(scene, camera_name);
                    if (named_camera) {
                        named_camera_snapshot = make_render_camera(
                            *named_camera, static_cast<double>(w) / std::max(1, h));
                        camera = &*named_camera_snapshot;
                    }
                }
            }
        }
    }

    Mat44 view_d = camera->get_view_matrix();
    Mat44 proj_d = camera->get_projection_matrix();
    Mat44f view = view_d.to_float();
    Mat44f projection = proj_d.to_float();

    if (!ctx.ctx2) {
        tc::Log::error("[NormalPass] ctx.ctx2 is null — NormalPass is tgfx2-only");
        return;
    }

    execute_with_data_tgfx2(
        ctx,
        rect,
        scene,
        view,
        projection,
        ctx.layer_mask
    );
}

TC_REGISTER_FRAME_PASS_DERIVED(NormalPass, GeometryPassBase);

} // namespace termin
