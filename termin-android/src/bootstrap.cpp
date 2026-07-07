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

#include <inspect/tc_inspect_init.h>
#include <tc_inspect_cpp.hpp>
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
#include <termin/render/execute_context.hpp>
#include <termin/render/frame_pass.hpp>
#include <termin/render/render_engine.hpp>
#include <termin/render/render_pipeline.hpp>
#include <termin/render/rendering_manager.hpp>
#include <termin/render/tgfx2_bridge.hpp>
#include <termin/render/mesh_renderer.hpp>
#include <termin/runtime/runtime_package.hpp>
#include <termin/tc_scene.hpp>
#include <termin_collision/termin_collision.h>

extern "C" {
#include "core/tc_component.h"
#include "core/tc_scene_render_mount.h"
#include "core/tc_scene_render_state.h"
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

class UIWidgetPass final : public termin::CxxFramePass {
public:
    std::string input_res = "color";
    std::string output_res = "color+widgets";

    INSPECT_FIELD(UIWidgetPass, input_res, "Input Resource", "string")
    INSPECT_FIELD(UIWidgetPass, output_res, "Output Resource", "string")
    INSPECT_TYPE_METADATA(UIWidgetPass, graph, termin::make_pass_graph_metadata(
        {{"input_res", "fbo"}},
        {{"output_res", "fbo"}},
        {{"input_res", "output_res"}}
    ))

    UIWidgetPass() {
        pass_name_set("UIWidgets");
        link_to_type_registry("UIWidgetPass");
    }

    std::set<const char*> compute_reads() const override {
        return {input_res.c_str()};
    }

    std::set<const char*> compute_writes() const override {
        return {output_res.c_str()};
    }

    std::vector<std::pair<std::string, std::string>> get_inplace_aliases() const override {
        return {{input_res, output_res}};
    }

    void execute(termin::ExecuteContext& ctx) override {
        if (!ctx.ctx2) {
            tc_log_error("[UIWidgetPass/android] ctx2 is null");
            return;
        }
        auto in_it = ctx.tex2_reads.find(input_res);
        auto out_it = ctx.tex2_writes.find(output_res);
        if (in_it == ctx.tex2_reads.end() || !in_it->second ||
                out_it == ctx.tex2_writes.end() || !out_it->second) {
            tc_log_warn(
                "[UIWidgetPass/android] missing tgfx2 resources input='%s' output='%s'",
                input_res.c_str(),
                output_res.c_str()
            );
            return;
        }
        ctx.ctx2->blit(in_it->second, out_it->second);
    }
};

TC_REGISTER_FRAME_PASS(UIWidgetPass);

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
    termin::runtime::RuntimePackageLoadResult player_package;
    termin::TcSceneRef player_scene;
    termin::RenderPipeline player_pipeline;
    termin::CameraComponent* player_camera = nullptr;
    tgfx::TextureHandle player_color_target;
    tgfx::TextureHandle player_depth_target;
    uint32_t player_width = 0;
    uint32_t player_height = 0;
    uint32_t player_frame = 0;
    bool scene_extensions_registered = false;
#endif
};

std::mutex g_state_mutex;
AndroidBootstrapState g_state;

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
constexpr const char* kTcLogTag = "TerminTcLog";

int tc_log_android_priority(tc_log_level level) {
    switch (level) {
        case TC_LOG_DEBUG:
            return ANDROID_LOG_DEBUG;
        case TC_LOG_INFO:
            return ANDROID_LOG_INFO;
        case TC_LOG_WARN:
            return ANDROID_LOG_WARN;
        case TC_LOG_ERROR:
            return ANDROID_LOG_ERROR;
    }
    return ANDROID_LOG_INFO;
}

void tc_log_android_callback(tc_log_level level, const char* message) {
    __android_log_write(tc_log_android_priority(level), kTcLogTag, message ? message : "");
}

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

void register_android_scene_extensions_locked() {
#ifdef __ANDROID__
    if (g_state.scene_extensions_registered) {
        return;
    }

    tc_scene_render_mount_extension_init();
    tc_scene_render_state_extension_init();
    termin_collision_runtime_init();
    g_state.scene_extensions_registered = true;
    android_log_info("scene extensions registered");
    tc_log_info("termin_android: scene extensions registered");
#endif
}

#ifdef __ANDROID__
bool create_smoke_renderer_locked();
void destroy_smoke_renderer_locked();
bool resize_smoke_renderer_locked(uint32_t width, uint32_t height);

termin::CameraComponent* find_player_camera(termin::TcSceneRef scene) {
    tc_component* raw = tc_scene_first_component_of_type(scene.handle(), "CameraComponent");
    if (!raw) {
        return nullptr;
    }
    termin::CxxComponent* cxx = termin::CxxComponent::from_tc(raw);
    return dynamic_cast<termin::CameraComponent*>(cxx);
}

double value_to_double(const tc_value* value, double fallback = 0.0) {
    if (!value) {
        return fallback;
    }
    if (value->type == TC_VALUE_DOUBLE) {
        return value->data.d;
    }
    if (value->type == TC_VALUE_FLOAT) {
        return static_cast<double>(value->data.f);
    }
    if (value->type == TC_VALUE_INT) {
        return static_cast<double>(value->data.i);
    }
    return fallback;
}

void register_camera_runtime_fields(tc::InspectRegistry& inspect) {
    inspect.set_type_parent("CameraComponent", "CxxComponent");
    if (!inspect.find_field("CameraComponent", "near_clip")) {
        inspect.add<termin::CameraComponent, double>(
            "CameraComponent", &termin::CameraComponent::near_clip, "near_clip", "Near Clip", "double");
    }
    if (!inspect.find_field("CameraComponent", "far_clip")) {
        inspect.add<termin::CameraComponent, double>(
            "CameraComponent", &termin::CameraComponent::far_clip, "far_clip", "Far Clip", "double");
    }
    if (!inspect.find_field("CameraComponent", "ortho_size")) {
        inspect.add<termin::CameraComponent, double>(
            "CameraComponent", &termin::CameraComponent::ortho_size, "ortho_size", "Ortho Size", "double");
    }
    if (!inspect.find_field("CameraComponent", "fov_x_degrees")) {
        inspect.add_with_accessors<termin::CameraComponent, double>(
            "CameraComponent",
            "fov_x_degrees",
            "Horizontal FOV",
            "double",
            [](termin::CameraComponent* camera) { return camera ? camera->get_fov_x_degrees() : 0.0; },
            [](termin::CameraComponent* camera, double value) {
                if (camera) {
                    camera->set_fov_x_degrees(value);
                }
            }
        );
    }
    if (!inspect.find_field("CameraComponent", "fov_y_degrees")) {
        inspect.add_with_accessors<termin::CameraComponent, double>(
            "CameraComponent",
            "fov_y_degrees",
            "Vertical FOV",
            "double",
            [](termin::CameraComponent* camera) { return camera ? camera->get_fov_y_degrees() : 0.0; },
            [](termin::CameraComponent* camera, double value) {
                if (camera) {
                    camera->set_fov_y_degrees(value);
                }
            }
        );
    }
    if (!inspect.find_field("CameraComponent", "fov_mode")) {
        tc::InspectFieldInfo info;
        info.type_name = "CameraComponent";
        info.path = "fov_mode";
        info.label = "FOV Mode";
        info.kind = "string";
        info.getter = [](void* obj) -> tc_value {
            return tc_value_string(static_cast<termin::CameraComponent*>(obj)->get_fov_mode_str().c_str());
        };
        info.setter = [](void* obj, tc_value value, void*) {
            auto* camera = static_cast<termin::CameraComponent*>(obj);
            if (camera && value.type == TC_VALUE_STRING && value.data.s) {
                camera->set_fov_mode_str(value.data.s);
            }
        };
        inspect.add_field_with_choices("CameraComponent", std::move(info));
    }
    if (!inspect.find_field("CameraComponent", "layer_mask")) {
        tc::InspectFieldInfo info;
        info.type_name = "CameraComponent";
        info.path = "layer_mask";
        info.label = "Layers";
        info.kind = "layer_mask";
        info.getter = [](void* obj) -> tc_value {
            auto* camera = static_cast<termin::CameraComponent*>(obj);
            char buf[32];
            snprintf(buf, sizeof(buf), "0x%llx", static_cast<unsigned long long>(camera->layer_mask));
            return tc_value_string(buf);
        };
        info.setter = [](void* obj, tc_value value, void*) {
            auto* camera = static_cast<termin::CameraComponent*>(obj);
            if (!camera) {
                return;
            }
            if (value.type == TC_VALUE_STRING && value.data.s) {
                camera->layer_mask = strtoull(value.data.s, nullptr, 0);
            } else if (value.type == TC_VALUE_INT) {
                camera->layer_mask = static_cast<uint64_t>(value.data.i);
            }
        };
        inspect.add_field_with_choices("CameraComponent", std::move(info));
    }
}

void register_light_runtime_fields(tc::InspectRegistry& inspect) {
    inspect.set_type_parent("LightComponent", "CxxComponent");
    if (!inspect.find_field("LightComponent", "light_type")) {
        tc::InspectFieldInfo info;
        info.type_name = "LightComponent";
        info.path = "light_type";
        info.label = "Light Type";
        info.kind = "string";
        info.getter = [](void* obj) -> tc_value {
            return tc_value_string(static_cast<termin::LightComponent*>(obj)->get_light_type_str().c_str());
        };
        info.setter = [](void* obj, tc_value value, void*) {
            auto* light = static_cast<termin::LightComponent*>(obj);
            if (light && value.type == TC_VALUE_STRING && value.data.s) {
                light->set_light_type_str(value.data.s);
            }
        };
        inspect.add_field_with_choices("LightComponent", std::move(info));
    }
    if (!inspect.find_field("LightComponent", "color")) {
        tc::InspectFieldInfo info;
        info.type_name = "LightComponent";
        info.path = "color";
        info.label = "Color";
        info.kind = "color";
        info.getter = [](void* obj) -> tc_value {
            auto* light = static_cast<termin::LightComponent*>(obj);
            tc_value list = tc_value_list_new();
            tc_value_list_push(&list, tc_value_double(light->color.x));
            tc_value_list_push(&list, tc_value_double(light->color.y));
            tc_value_list_push(&list, tc_value_double(light->color.z));
            return list;
        };
        info.setter = [](void* obj, tc_value value, void*) {
            auto* light = static_cast<termin::LightComponent*>(obj);
            if (light && value.type == TC_VALUE_LIST && tc_value_list_size(&value) >= 3) {
                light->color = termin::Vec3(
                    value_to_double(tc_value_list_get(&value, 0), 1.0),
                    value_to_double(tc_value_list_get(&value, 1), 1.0),
                    value_to_double(tc_value_list_get(&value, 2), 1.0)
                );
            }
        };
        inspect.add_field_with_choices("LightComponent", std::move(info));
    }
    if (!inspect.find_field("LightComponent", "intensity")) {
        inspect.add<termin::LightComponent, double>(
            "LightComponent", &termin::LightComponent::intensity, "intensity", "Intensity", "double");
    }
}

void register_android_runtime_inspect_fields() {
    static bool registered = false;
    if (registered) {
        return;
    }
    registered = true;

    tc_inspect_kind_core_init();
    tc::KindRegistryCpp::instance();
    termin::MeshComponent::register_type();

    auto& inspect = tc::InspectRegistry::instance();
    inspect.set_type_parent("MeshRenderer", "Component");
    if (!inspect.find_field("MeshRenderer", "material")) {
        inspect.add<termin::MeshRenderer, termin::TcMaterial>(
            "MeshRenderer", &termin::MeshRenderer::material, "material", "Material", "tc_material");
    }
    if (!inspect.find_field("MeshRenderer", "cast_shadow")) {
        inspect.add<termin::MeshRenderer, bool>(
            "MeshRenderer", &termin::MeshRenderer::cast_shadow, "cast_shadow", "Cast Shadow", "bool");
    }
    if (!inspect.find_field("MeshRenderer", "mesh_offset_enabled")) {
        inspect.add<termin::MeshRenderer, bool>(
            "MeshRenderer", &termin::MeshRenderer::mesh_offset_enabled, "mesh_offset_enabled", "Mesh Offset", "bool");
    }
    if (!inspect.find_field("MeshRenderer", "mesh_offset_position")) {
        inspect.add<termin::MeshRenderer, tc_vec3>(
            "MeshRenderer", &termin::MeshRenderer::mesh_offset_position, "mesh_offset_position", "Offset Position", "vec3");
    }
    if (!inspect.find_field("MeshRenderer", "mesh_offset_euler")) {
        inspect.add<termin::MeshRenderer, tc_vec3>(
            "MeshRenderer", &termin::MeshRenderer::mesh_offset_euler, "mesh_offset_euler", "Offset Rotation", "vec3");
    }
    if (!inspect.find_field("MeshRenderer", "mesh_offset_scale")) {
        inspect.add<termin::MeshRenderer, tc_vec3>(
            "MeshRenderer", &termin::MeshRenderer::mesh_offset_scale, "mesh_offset_scale", "Offset Scale", "vec3");
    }
    if (!inspect.find_field("MeshRenderer", "_override_material")) {
        inspect.add_with_accessors<termin::MeshRenderer, bool>(
            "MeshRenderer",
            "_override_material",
            "Override Material",
            "bool",
            [](termin::MeshRenderer* renderer) { return renderer ? renderer->override_material() : false; },
            [](termin::MeshRenderer* renderer, bool value) {
                if (renderer) {
                    renderer->set_override_material(value);
                }
            }
        );
    }
    if (!inspect.find_field("MeshRenderer", "_overridden_material_data")) {
        tc::InspectFieldInfo info;
        info.type_name = "MeshRenderer";
        info.path = "_overridden_material_data";
        info.label = "";
        info.kind = "";
        info.is_inspectable = false;
        info.is_serializable = true;
        info.getter = [](void* obj) -> tc_value {
            return static_cast<termin::MeshRenderer*>(obj)->get_override_data();
        };
        info.setter = [](void* obj, tc_value value, void*) {
            static_cast<termin::MeshRenderer*>(obj)->set_override_data(&value);
        };
        inspect.add_serializable_field("MeshRenderer", std::move(info));
    }

    register_camera_runtime_fields(inspect);
    register_light_runtime_fields(inspect);

    tc_log_info(
        "termin_android_player: runtime inspect fields registered mesh=%zu renderer=%zu camera=%zu light=%zu",
        tc_inspect_field_count("MeshComponent"),
        tc_inspect_field_count("MeshRenderer"),
        tc_inspect_field_count("CameraComponent"),
        tc_inspect_field_count("LightComponent")
    );
}

bool ensure_android_scene_pipeline_locked() {
    if (g_state.player_pipeline.is_valid()) {
        return true;
    }

    tc_pipeline_handle pipeline_handle =
        g_state.player_engine
            ? g_state.player_engine->rendering_manager.create_pipeline("Default")
            : termin::RenderingManager::make_default_pipeline();
    if (!tc_pipeline_handle_valid(pipeline_handle)) {
        android_log_error("player: failed to create Default render pipeline");
        return false;
    }
    g_state.player_pipeline = termin::RenderPipeline(pipeline_handle);
    android_log_info(
        "player: Default render pipeline created passes=%zu",
        g_state.player_pipeline.pass_count()
    );
    return true;
}

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
        g_state.player_scene = termin::TcSceneRef();
    }
    g_state.player_package = termin::runtime::RuntimePackageLoadResult();
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
        register_android_scene_extensions_locked();
        g_state.player_engine = std::make_unique<termin::EngineCore>();
    }

    register_android_runtime_inspect_fields();

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

    if (g_state.asset_root.empty()) {
        android_log_error("player: asset_root is empty; runtime package cannot be loaded");
        tc_log_error("termin_android_player: asset_root is empty; runtime package cannot be loaded");
        return false;
    }

    const std::filesystem::path manifest_path =
        std::filesystem::path(g_state.asset_root) / "manifest.json";
    if (!std::filesystem::is_regular_file(manifest_path)) {
        android_log_error("player: runtime manifest not found at '%s'", manifest_path.c_str());
        tc_log_error("termin_android_player: runtime manifest not found at '%s'", manifest_path.c_str());
        return false;
    }

    termin::runtime::RuntimePackageLoader loader;
    g_state.player_package = loader.load(g_state.asset_root);
    if (!g_state.player_package.ok || !g_state.player_package.scene.valid()) {
        android_log_error("player: runtime package load failed: %s", g_state.player_package.message.c_str());
        tc_log_error("termin_android_player: runtime package load failed: %s", g_state.player_package.message.c_str());
        g_state.player_package = termin::runtime::RuntimePackageLoadResult();
        return false;
    }

    termin::CameraComponent* camera = find_player_camera(g_state.player_package.scene);
    if (!camera) {
        android_log_error("player: runtime package loaded but has no CameraComponent");
        tc_log_error("termin_android_player: runtime package loaded but has no CameraComponent");
        g_state.player_package.scene.destroy();
        g_state.player_package = termin::runtime::RuntimePackageLoadResult();
        return false;
    }
    if (!ensure_android_scene_pipeline_locked()) {
        g_state.player_package.scene.destroy();
        g_state.player_package = termin::runtime::RuntimePackageLoadResult();
        return false;
    }
    g_state.player_scene = g_state.player_package.scene;
    g_state.player_camera = camera;
    android_log_info(
        "player: runtime package loaded entities=%zu pipeline_passes=%zu",
        g_state.player_scene.entity_count(),
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
        target.render_rect = termin::Rect2i{
            0,
            0,
            static_cast<int>(g_state.player_width),
            static_cast<int>(g_state.player_height)
        };
        target.output_color_tex = g_state.player_color_target;
        target.output_depth_tex = g_state.player_depth_target;
        target.clear_color_enabled = true;
        target.clear_color[0] = 0.0f;
        target.clear_color[1] = 0.0f;
        target.clear_color[2] = 0.0f;
        target.clear_color[3] = 1.0f;
        target.clear_depth_enabled = true;
        target.clear_depth = 1.0f;
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
            resize_smoke_renderer_locked(
                static_cast<uint32_t>(g_state.surface_width),
                static_cast<uint32_t>(g_state.surface_height)
            );
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
    if (g_state.smoke_device) {
        android_log_info("smoke: destroy renderer");
        try {
            g_state.smoke_device->wait_idle();
            destroy_player_scene_locked();
            destroy_smoke_resources_locked();
        } catch (const std::exception& e) {
            android_log_error("smoke: destroy failed: %s", e.what());
            tc_log_error("termin_android_smoke: destroy failed: %s", e.what());
        }
    } else {
        destroy_player_scene_locked();
    }
    g_state.smoke_device.reset();
    reset_smoke_resources_locked();
    g_state.smoke_width = 0;
    g_state.smoke_height = 0;
    g_state.smoke_frame = 0;
    tgfx2_interop_set_device(nullptr);
#endif
}

#ifdef __ANDROID__
bool resize_smoke_renderer_locked(uint32_t width, uint32_t height) {
    if (!g_state.smoke_device || !g_state.smoke_device->swapchain()) {
        return false;
    }
    if (width == 0 || height == 0) {
        android_log_error("smoke: invalid resize %ux%u", width, height);
        tc_log_error("termin_android_smoke: invalid resize %ux%u", width, height);
        destroy_smoke_renderer_locked();
        return false;
    }

    try {
        android_log_info("smoke: recreate swapchain size=%ux%u", width, height);
        tc_log_info("termin_android_smoke: recreate swapchain size=%ux%u", width, height);
        g_state.smoke_device->swapchain()->recreate(width, height);
        g_state.smoke_width = g_state.smoke_device->swapchain()->width();
        g_state.smoke_height = g_state.smoke_device->swapchain()->height();
        destroy_player_targets_locked();
        android_log_info(
            "smoke: swapchain recreated %ux%u images=%u",
            g_state.smoke_width,
            g_state.smoke_height,
            g_state.smoke_device->swapchain()->image_count()
        );
        tc_log_info(
            "termin_android_smoke: swapchain recreated %ux%u images=%u",
            g_state.smoke_width,
            g_state.smoke_height,
            g_state.smoke_device->swapchain()->image_count()
        );
        return true;
    } catch (const std::exception& e) {
        android_log_error("smoke: swapchain recreate failed: %s", e.what());
        tc_log_error("termin_android_smoke: swapchain recreate failed: %s", e.what());
        destroy_smoke_renderer_locked();
        return false;
    }
}
#endif

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
#ifdef __ANDROID__
    tc_log_set_callback(tc_log_android_callback);
    tc_log_set_level(TC_LOG_DEBUG);
#endif
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
#ifdef __ANDROID__
    if (g_state.scene_extensions_registered) {
        termin_collision_runtime_shutdown();
        g_state.scene_extensions_registered = false;
    }
#endif
    android_log_info("shutdown");
    tc_log_info("termin_android_shutdown");
#ifdef __ANDROID__
    tc_log_set_callback(nullptr);
#endif
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
    if (size_changed && g_state.smoke_device) {
        if (width <= 0 || height <= 0) {
            android_log_error(
                "surface_changed: invalid resize %dx%d",
                static_cast<int>(width),
                static_cast<int>(height)
            );
            tc_log_error(
                "termin_android_on_surface_changed: invalid resize %dx%d",
                static_cast<int>(width),
                static_cast<int>(height)
            );
            destroy_smoke_renderer_locked();
            return;
        }
        resize_smoke_renderer_locked(
            static_cast<uint32_t>(width),
            static_cast<uint32_t>(height)
        );
    }
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
