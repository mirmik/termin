#include "openxr_android_runtime_internal.hpp"

#if defined(TERMIN_OPENXR_HAS_HEADERS)
#if defined(__ANDROID__)
#include <dlfcn.h>
#endif
#endif

#include <array>
#include <atomic>
#include <chrono>
#include <cmath>
#include <cstdlib>
#include <filesystem>
#include <fstream>
#include <memory>
#include <span>
#include <stdexcept>
#include <thread>
#include <unordered_map>
#include <vector>

#include <components/mesh_component.hpp>
#include <tc_inspect_cpp.hpp>
#include <tcbase/tc_log.h>
#include <tcbase/trent/json.h>
#include <termin/bootstrap/bootstrap.hpp>
#include <termin/engine/engine_core.hpp>
#include <termin/entity/component_registry.hpp>
#include <termin/lighting/light_component.hpp>
#include <termin/render/execute_context.hpp>
#include <termin/render/mesh_renderer.hpp>
#include <termin/render/render_engine.hpp>
#include <termin/render/render_pipeline.hpp>
#include <termin/render/rendering_manager.hpp>
#include <termin/render/tc_pipeline_template.hpp>
#include <termin/render/ui_widget_pass.hpp>
#include <termin/runtime/runtime_package.hpp>
#include <termin/scene/tc_scene_render_ext.hpp>
#include <termin/tc_scene.hpp>
#include <termin/ui/ui_component.hpp>
#include <termin/xr/xr_origin_component.hpp>
#include <termin/xr/xr_thumbstick_locomotion_component.hpp>
#include <termin_collision/termin_collision.h>
#include <tgfx/tgfx_mesh_handle.hpp>
#include <tgfx2/i_command_list.hpp>
#include <tgfx2/builtin_shader_sources.hpp>
#include <tgfx2/render_context.hpp>
#include <tgfx2/render_state.hpp>
#include <tgfx2/vulkan/vulkan_render_device.hpp>
#include <tgfx2/graphics_host.hpp>

#include "openxr_math.hpp"

extern "C" {
void tc_inspect_kind_core_init(void);
#include <core/tc_component.h>
#include <core/tc_entity_pool.h>
#include <core/tc_entity_pool_registry.h>
#include <core/tc_scene_render_mount.h>
#include <core/tc_scene_render_state.h>
#include <inspect/tc_inspect_pass_adapter.h>
#include <render/tc_pass.h>
#include <render/tc_pipeline.h>
#include <render/tc_render_target.h>
#include <termin_scene/termin_scene.h>
#include <tgfx/resources/tc_mesh_registry.h>
#include <tgfx/resources/tc_primitive_mesh.h>
}

#if defined(__ANDROID__)
#include <android/log.h>
#endif

namespace termin::openxr {

namespace {

#if defined(TERMIN_OPENXR_HAS_HEADERS) && defined(__ANDROID__)

using namespace detail;

struct SmokeControl {
    std::atomic<bool> running{false};
    std::thread thread;
};

SmokeControl g_smoke;

struct ScenePrimitiveSmoke {
    termin::TcSceneRef scene;
    termin::Entity primitive;
    tgfx::BufferHandle vbo;
    tgfx::BufferHandle ebo;
    tgfx::ShaderHandle vertex_shader;
    tgfx::ShaderHandle fragment_shader;
    tgfx::PipelineHandle pipeline;
    uint32_t index_count = 0;
    bool initialized = false;

    bool init(tgfx::IRenderDevice &device, tgfx::PixelFormat color_format, uint32_t sample_count) {
        if (initialized) {
            return true;
        }

        termin::MeshComponent::register_type();

        scene = termin::TcSceneRef::create("OpenXR tc_scene smoke", "openxr-tc-scene-smoke");
        if (!scene.valid()) {
            log_error("tc_scene", "failed to create scene");
            return false;
        }

        primitive = scene.create_entity("tc_scene sphere");
        primitive.transform().set_local_position(termin::Vec3{0.0, 2.0, 0.0});

        auto *mesh_component = new termin::MeshComponent();
        const tc_mesh_handle mesh_handle = tc_primitive_unit_sphere();
        if (!tc_mesh_is_valid(mesh_handle) || !tc_mesh_ensure_loaded(mesh_handle)) {
            log_error("tc_scene", "failed to create/load unit sphere mesh");
            delete mesh_component;
            scene.destroy();
            scene = {};
            primitive = {};
            return false;
        }
        mesh_component->set_mesh(termin::TcMesh(mesh_handle));
        primitive.add_component(mesh_component);

        const tc_mesh *mesh = tc_mesh_get(mesh_handle);
        if (!mesh || !mesh->vertices || !mesh->indices || mesh->vertex_count == 0 || mesh->index_count == 0) {
            log_error("tc_scene", "unit sphere mesh has no CPU geometry");
            scene.destroy();
            scene = {};
            primitive = {};
            return false;
        }

        const tc_vertex_attrib *position_attr = tc_vertex_layout_find(&mesh->layout, "position");
        const tc_vertex_attrib *normal_attr = tc_vertex_layout_find(&mesh->layout, "normal");
        if (!position_attr || !normal_attr) {
            log_error("tc_scene", "unit sphere mesh is missing position/normal attributes");
            destroy();
            return false;
        }

        index_count = static_cast<uint32_t>(mesh->index_count);

        tgfx::BufferDesc vbo_desc{};
        vbo_desc.size = mesh->vertex_count * mesh->layout.stride;
        vbo_desc.usage = tgfx::BufferUsage::Vertex | tgfx::BufferUsage::CopyDst;
        vbo = device.create_buffer(vbo_desc);
        device.upload_buffer(vbo, std::span<const uint8_t>(reinterpret_cast<const uint8_t *>(mesh->vertices),
                                                           static_cast<size_t>(vbo_desc.size)));

        tgfx::BufferDesc ebo_desc{};
        ebo_desc.size = mesh->index_count * sizeof(uint32_t);
        ebo_desc.usage = tgfx::BufferUsage::Index | tgfx::BufferUsage::CopyDst;
        ebo = device.create_buffer(ebo_desc);
        device.upload_buffer(ebo, std::span<const uint8_t>(reinterpret_cast<const uint8_t *>(mesh->indices),
                                                           static_cast<size_t>(ebo_desc.size)));

        tgfx::ShaderDesc vs_desc{};
        vs_desc.stage = tgfx::ShaderStage::Vertex;
        vs_desc.bytecode.assign(kSmokeVertexSpv, kSmokeVertexSpv + kSmokeVertexSpvSize);
        vs_desc.debug_name = "openxr tc_scene sphere vs";
        vertex_shader = device.create_shader(vs_desc);

        tgfx::ShaderDesc fs_desc{};
        fs_desc.stage = tgfx::ShaderStage::Fragment;
        fs_desc.bytecode.assign(kSmokeFragmentSpv, kSmokeFragmentSpv + kSmokeFragmentSpvSize);
        fs_desc.debug_name = "openxr tc_scene sphere fs";
        fragment_shader = device.create_shader(fs_desc);

        tgfx::VertexBufferLayout vertex_layout{};
        vertex_layout.stride = static_cast<uint32_t>(mesh->layout.stride);
        vertex_layout.attributes.push_back(
            {0, tgfx::VertexFormat::Float3, static_cast<uint32_t>(position_attr->offset)});
        vertex_layout.attributes.push_back({1, tgfx::VertexFormat::Float3, static_cast<uint32_t>(normal_attr->offset)});

        tgfx::PipelineDesc pipeline_desc{};
        pipeline_desc.vertex_shader = vertex_shader;
        pipeline_desc.fragment_shader = fragment_shader;
        pipeline_desc.vertex_layouts.push_back(tgfx::make_vertex_layout_desc(vertex_layout));
        pipeline_desc.color_formats.push_back(color_format);
        pipeline_desc.depth_format = tgfx::PixelFormat::D32F;
        pipeline_desc.sample_count = sample_count;
        pipeline_desc.depth_stencil.depth_test = true;
        pipeline_desc.depth_stencil.depth_write = true;
        pipeline_desc.depth_stencil.depth_compare = tgfx::CompareOp::LessEqual;
        pipeline_desc.raster.cull = tgfx::CullMode::Back;
        pipeline = device.create_pipeline(pipeline_desc);

        initialized = true;
        __android_log_print(ANDROID_LOG_INFO, kLogTag, "tc_scene sphere ready: vertices=%zu indices=%zu stride=%u",
                            mesh->vertex_count, mesh->index_count, static_cast<unsigned>(mesh->layout.stride));
        return true;
    }

    void destroy(tgfx::IRenderDevice *device = nullptr) {
        if (device) {
            if (pipeline) {
                device->destroy(pipeline);
            }
            if (fragment_shader) {
                device->destroy(fragment_shader);
            }
            if (vertex_shader) {
                device->destroy(vertex_shader);
            }
            if (ebo) {
                device->destroy(ebo);
            }
            if (vbo) {
                device->destroy(vbo);
            }
        }
        pipeline = {};
        fragment_shader = {};
        vertex_shader = {};
        ebo = {};
        vbo = {};
        index_count = 0;
        initialized = false;

        if (scene.valid()) {
            scene.destroy();
        }
        scene = {};
        primitive = {};
    }
};

const tc_render_target_config *find_xr_render_target_config(termin::TcSceneRef scene) {
    tc_scene_render_mount *mount = tc_scene_render_mount_get(scene.handle());
    if (!mount) {
        return nullptr;
    }
    for (size_t i = 0; i < mount->render_target_config_count; ++i) {
        const tc_render_target_config &config = mount->render_target_configs[i];
        tc_render_target_kind kind = TC_RENDER_TARGET_TEXTURE_2D;
        if (config.kind && tc_render_target_kind_from_string(config.kind, &kind) &&
            kind == TC_RENDER_TARGET_XR_STEREO && config.enabled) {
            return &config;
        }
    }
    return nullptr;
}

termin::XrOriginComponent *xr_origin_component_from_entity_uuid(termin::TcSceneRef scene, const char *uuid) {
    if (!uuid || uuid[0] == '\0') {
        return nullptr;
    }
    tc_entity_pool *pool = tc_scene_entity_pool(scene.handle());
    if (!pool) {
        return nullptr;
    }
    tc_entity_id entity_id = tc_entity_pool_find_by_uuid(pool, uuid);
    if (!tc_entity_id_valid(entity_id)) {
        return nullptr;
    }
    tc_entity_pool_handle pool_handle = tc_entity_pool_registry_find(pool);
    termin::Entity entity(tc_entity_handle_make(pool_handle, entity_id));
    tc_component *raw = entity.get_component_by_type_name("XrOriginComponent");
    if (!raw) {
        return nullptr;
    }
    termin::CxxComponent *cxx = termin::CxxComponent::from_tc(raw);
    return dynamic_cast<termin::XrOriginComponent *>(cxx);
}

termin::XrOriginComponent *find_first_runtime_xr_origin(termin::TcSceneRef scene) {
    tc_component *raw = tc_scene_first_component_of_type(scene.handle(), "XrOriginComponent");
    if (!raw) {
        return nullptr;
    }
    termin::CxxComponent *cxx = termin::CxxComponent::from_tc(raw);
    return dynamic_cast<termin::XrOriginComponent *>(cxx);
}

termin::XrOriginComponent *resolve_runtime_xr_origin(termin::TcSceneRef scene,
                                                     const tc_render_target_config *xr_config) {
    if (xr_config) {
        const char *target_name = xr_config->name ? xr_config->name : "XRStereoTarget";
        if (!xr_config->xr_origin_uuid || xr_config->xr_origin_uuid[0] == '\0') {
            tc_log_error("[OpenXR scene] xr_stereo render target '%s' has no xr_origin_uuid", target_name);
            return nullptr;
        }
        termin::XrOriginComponent *xr_origin = xr_origin_component_from_entity_uuid(scene, xr_config->xr_origin_uuid);
        if (!xr_origin) {
            tc_log_error("[OpenXR scene] xr_stereo render target '%s' xr_origin_uuid "
                         "'%s' does not resolve to XrOriginComponent",
                         target_name, xr_config->xr_origin_uuid);
            return nullptr;
        }
        return xr_origin;
    }

    tc_log(TC_LOG_WARN, "[OpenXR scene] no xr_stereo render target config found; "
                        "using first XrOriginComponent");
    return find_first_runtime_xr_origin(scene);
}

void register_openxr_scene_runtime() {
    static bool registered = false;
    if (registered) {
        return;
    }
    registered = true;

    termin::bootstrap::bootstrap_runtime();
}

struct OpenXRRuntimeScene {
    struct MultiviewFrame {
        tgfx::TextureHandle color_texture;
        uint32_t width = 0;
        uint32_t height = 0;
        tgfx::PixelFormat color_format = tgfx::PixelFormat::Undefined;
        std::array<XrView, 2> views{};
        bool valid = false;
    };

    std::unique_ptr<termin::EngineCore> engine;
    termin::runtime::RuntimePackageLoadResult package;
    termin::TcSceneRef scene;
    termin::RenderPipeline pipeline;
    tc_render_target_handle xr_render_target = TC_RENDER_TARGET_HANDLE_INVALID;
    termin::XrOriginComponent *xr_origin = nullptr;
    termin::Mat44 origin_from_xr_reference = termin::Mat44::identity();
    MultiviewFrame active_multiview_frame;
    bool reference_alignment_initialized = false;
    bool stereo_contract_logged = false;
    bool ready = false;

    void reset_reference_alignment() {
        origin_from_xr_reference = termin::Mat44::identity();
        reference_alignment_initialized = false;
    }

    bool update_reference_alignment(const XrView &view, XrViewStateFlags view_state_flags) {
        if (reference_alignment_initialized) {
            return true;
        }
        if (!xr_origin) {
            return false;
        }

        if (xr_origin->reference_alignment == termin::XrReferenceAlignment::StageAxes) {
            origin_from_xr_reference = termin::Mat44::identity();
            reference_alignment_initialized = true;
            tc_log_info("[OpenXR scene] XR reference alignment initialized "
                        "mode=stage_axes yaw_degrees=0");
            return true;
        }

        if ((view_state_flags & XR_VIEW_STATE_ORIENTATION_VALID_BIT) == 0) {
            return false;
        }

        termin::Vec3 forward =
            xr_direction_to_scene_direction(rotate_xr_vector(view.pose.orientation, XrVector3f{0.0f, 0.0f, -1.0f}));
        forward.z = 0.0;
        const double len = forward.norm();
        if (len < 1e-6) {
            tc_log_warn("[OpenXR scene] cannot initialize XR reference alignment: "
                        "head forward is vertical");
            return false;
        }
        forward = forward / len;

        const double yaw = std::atan2(forward.x, forward.y);
        origin_from_xr_reference = termin::Mat44::rotation_axis_angle(termin::Vec3{0.0, 0.0, 1.0}, yaw);
        reference_alignment_initialized = true;

        constexpr double kRadToDeg = 180.0 / 3.14159265358979323846;
        tc_log_info("[OpenXR scene] XR reference alignment initialized "
                    "mode=initial_head_yaw "
                    "yaw_degrees=%.3f initial_forward=(%.3f, %.3f, %.3f)",
                    yaw * kRadToDeg, forward.x, forward.y, forward.z);
        return true;
    }

    void install_runtime_pipeline_factory() {
        engine->rendering_manager.set_pipeline_factory([](const std::string &key) -> tc_pipeline_handle {
            const tc_pipeline_template_handle template_handle =
                tc_pipeline_template_find(key.c_str());
            if (tc_pipeline_template_handle_is_invalid(template_handle)) {
                tc_log_error(
                    "[OpenXR scene] compiled runtime pipeline template '%s' was not found",
                    key.c_str());
                return TC_PIPELINE_HANDLE_INVALID;
            }

            try {
                termin::TcPipelineTemplate pipeline_template(template_handle);
                const tc_pipeline_template* definition = pipeline_template.get();
                tc_log_info(
                    "[OpenXR scene] runtime pipeline template '%s' model=%d handle=(%u,%u)",
                    key.c_str(),
                    definition ? static_cast<int>(definition->execution_model) : -1,
                    template_handle.index,
                    template_handle.generation);
                termin::RenderPipeline compiled(pipeline_template);
                if (!compiled.is_valid()) {
                    tc_log_error("[OpenXR scene] failed to instantiate runtime pipeline '%s'", key.c_str());
                    return TC_PIPELINE_HANDLE_INVALID;
                }
                compiled.set_name(key);
                const tc_pipeline_handle handle = compiled.handle();
                const tc_pipeline_template_handle instance_template =
                    tc_pipeline_get_template(handle);
                const tc_pipeline_template* instance_definition =
                    tc_pipeline_template_get(instance_template);
                tc_log_info(
                    "[OpenXR scene] instantiated compiled runtime pipeline '%s' passes=%zu "
                    "model=%d template=(%u,%u)",
                    key.c_str(), compiled.pass_count(),
                    instance_definition
                        ? static_cast<int>(instance_definition->execution_model)
                        : -1,
                    instance_template.index,
                    instance_template.generation);
                return handle;
            } catch (const std::exception &e) {
                tc_log_error(
                    "[OpenXR scene] runtime pipeline '%s' instantiation failed: %s",
                    key.c_str(), e.what());
                return TC_PIPELINE_HANDLE_INVALID;
            }
        });
    }

    bool load(const std::string &asset_root, tgfx::GraphicsHost &graphics_host) {
        if (ready) {
            return true;
        }
        if (asset_root.empty()) {
            log_error("OpenXR scene", "asset_root is empty");
            tc_log_error("[OpenXR scene] asset_root is empty");
            return false;
        }

        register_openxr_scene_runtime();

        const char *required_components[] = {
            "MeshComponent",  "MeshRenderer",     "UIComponent",      "XrOriginComponent",
            "XrThumbstickLocomotionComponent", "XrTrackedPoseComponent",
            "XrGrabInteractableComponent", "XrDirectGrabInteractorComponent",
            "ColliderComponent", "PhysicsWorldComponent", "RigidBodyComponent",
            "LightComponent", "UnknownComponent",
        };
        for (const char *name : required_components) {
            if (!tc_component_registry_has(name)) {
                log_error("OpenXR scene", (std::string("required component is not registered: ") + name).c_str());
                tc_log_error("[OpenXR scene] required component is not registered: %s", name);
                return false;
            }
        }

        const std::filesystem::path manifest_path = std::filesystem::path(asset_root) / "manifest.json";
        if (!std::filesystem::is_regular_file(manifest_path)) {
            log_error("OpenXR scene", (std::string("runtime manifest not found at ") + manifest_path.string()).c_str());
            tc_log_error("[OpenXR scene] runtime manifest not found at '%s'", manifest_path.c_str());
            return false;
        }

        const std::filesystem::path ui_font_path =
            std::filesystem::path(asset_root) / "fonts" / "DroidSans.ttf";
        if (!std::filesystem::is_regular_file(ui_font_path)) {
            log_error("OpenXR scene", "packaged native UI font is missing");
            tc_log_error("[OpenXR scene] packaged native UI font not found at '%s'",
                         ui_font_path.c_str());
            return false;
        }
        if (setenv("TERMIN_UI_FONT", ui_font_path.c_str(), 1) != 0) {
            log_error("OpenXR scene", "failed to configure native UI font");
            tc_log_error("[OpenXR scene] failed to set TERMIN_UI_FONT='%s'",
                         ui_font_path.c_str());
            return false;
        }

        tgfx::set_builtin_shader_root(nullptr);
        engine = std::make_unique<termin::EngineCore>();
        termin::RenderEngine *render_engine =
            engine->rendering_manager.render_engine();
        if (!render_engine) {
            log_error("OpenXR scene", "render engine is unavailable");
            tc_log_error("[OpenXR scene] render engine is unavailable");
            engine.reset();
            return false;
        }
        try {
            render_engine->set_graphics_host(graphics_host);
        } catch (const std::exception &e) {
            log_error("OpenXR scene graphics host", e.what());
            tc_log_error("[OpenXR scene] failed to install graphics host: %s", e.what());
            engine.reset();
            return false;
        }
        termin::runtime::RuntimePackageLoader loader;
        termin::runtime::RuntimePackageLoadOptions load_options;
        load_options.scene_extensions = termin::default_scene_extension_ids();
        package = loader.load(asset_root, load_options);
        if (!package.ok || !package.scene.valid()) {
            log_error("OpenXR scene", (std::string("runtime package load failed: ") + package.message).c_str());
            tc_log_error("[OpenXR scene] runtime package load failed: %s", package.message.c_str());
            package.destroy();
            engine.reset();
            return false;
        }
        tgfx::set_builtin_shader_root(package.shader_runtime.builtin_shader_root.c_str());
        render_engine->configure_shader_artifacts(
            package.shader_runtime.artifact_root,
            package.shader_runtime.cache_root,
            package.shader_runtime.compiler_path,
            package.shader_runtime.dev_compile_enabled
        );

        const tc_render_target_config *xr_config = find_xr_render_target_config(package.scene);
        install_runtime_pipeline_factory();
        xr_origin = resolve_runtime_xr_origin(package.scene, xr_config);
        if (!xr_origin) {
            log_error("OpenXR scene", "runtime package loaded but has no XR camera origin");
            tc_log_error("[OpenXR scene] runtime package loaded but has no XR camera origin");
            package.destroy();
            engine.reset();
            return false;
        }
        reset_reference_alignment();

        scene = package.scene;
        if (!engine->rendering_manager.attach_scene_render_targets(scene.handle())) {
            log_error("OpenXR scene", "failed to restore scene render targets");
            tc_log_error("[OpenXR scene] failed to restore scene render targets");
            package.destroy();
            engine.reset();
            return false;
        }

        const std::string xr_target_name = choose_xr_render_target_name(xr_config);
        xr_render_target = engine->rendering_manager.topology().find_render_target(
            scene.handle(), xr_target_name);
        if (!tc_render_target_handle_valid(xr_render_target)) {
            log_error("OpenXR scene", "scene has no restored XR render target");
            tc_log_error("[OpenXR scene] restored XR render target '%s' was not found",
                         xr_target_name.c_str());
            engine->rendering_manager.detach_scene_full(scene.handle());
            package.destroy();
            engine.reset();
            return false;
        }
        pipeline = termin::RenderPipeline(tc_render_target_get_pipeline(xr_render_target));
        if (!pipeline.is_valid() || pipeline.pass_count() == 0) {
            log_error("OpenXR scene", "failed to create render pipeline");
            tc_log_error("[OpenXR scene] failed to create render pipeline");
            engine->rendering_manager.detach_scene_full(scene.handle());
            pipeline = {};
            xr_render_target = TC_RENDER_TARGET_HANDLE_INVALID;
            package.destroy();
            engine.reset();
            return false;
        }
        const tc_pipeline_template* pipeline_template =
            tc_pipeline_template_get(pipeline.template_handle());
        if (!pipeline_template ||
            pipeline_template->execution_model != TC_PIPELINE_EXECUTION_XR_MULTIVIEW) {
            tc_log_error(
                "[OpenXR scene] xr_stereo pipeline model mismatch: model=%d "
                "template=(%u,%u)",
                pipeline_template
                    ? static_cast<int>(pipeline_template->execution_model)
                    : -1,
                pipeline.template_handle().index,
                pipeline.template_handle().generation);
            log_error("OpenXR scene", "xr_stereo requires an xr_multiview pipeline");
            tc_log_error(
                "[OpenXR scene] xr_stereo target rejected non-xr_multiview pipeline");
            engine->rendering_manager.detach_scene_full(scene.handle());
            pipeline = {};
            xr_render_target = TC_RENDER_TARGET_HANDLE_INVALID;
            package.destroy();
            engine.reset();
            return false;
        }

        register_context_provider();
        ready = true;
        __android_log_print(ANDROID_LOG_INFO, kLogTag, "OpenXR runtime scene loaded root='%s' entities=%zu passes=%zu",
                            asset_root.c_str(), scene.entity_count(), pipeline.pass_count());
        return true;
    }

    std::string choose_xr_render_target_name(const tc_render_target_config *config) const {
        if (config && config->name && config->name[0] != '\0') {
            return config->name;
        }
        return "XRStereoTarget";
    }

    void create_xr_render_target() {
        const tc_render_target_config *config = find_xr_render_target_config(scene);
        const std::string name = choose_xr_render_target_name(config);
        xr_render_target = tc_render_target_new(name.c_str());
        tc_render_target_set_kind(xr_render_target, TC_RENDER_TARGET_XR_STEREO);
        tc_render_target_set_scene(xr_render_target, scene.handle());
        tc_render_target_set_xr_origin(xr_render_target, xr_origin ? xr_origin->c_component() : nullptr);
        tc_render_target_set_pipeline(xr_render_target, pipeline.handle());
        tc_render_target_set_enabled(xr_render_target, true);
        if (config) {
            tc_render_target_set_layer_mask(xr_render_target, config->layer_mask);
            tc_render_target_set_clear_color_enabled(xr_render_target, config->clear_color);
            tc_render_target_set_clear_color_value(xr_render_target, config->clear_color_value[0],
                                                   config->clear_color_value[1], config->clear_color_value[2],
                                                   config->clear_color_value[3]);
            tc_render_target_set_clear_depth_enabled(xr_render_target, config->clear_depth);
            tc_render_target_set_clear_depth_value(xr_render_target, config->clear_depth_value);
        } else {
            tc_render_target_set_clear_color_enabled(xr_render_target, true);
            tc_render_target_set_clear_color_value(xr_render_target, 0.015f, 0.018f, 0.024f, 1.0f);
            tc_render_target_set_clear_depth_enabled(xr_render_target, true);
            tc_render_target_set_clear_depth_value(xr_render_target, 1.0f);
        }
        engine->rendering_manager.register_managed_render_target(xr_render_target);
    }

    void register_context_provider() {
        engine->rendering_manager.set_render_target_context_provider(
            TC_RENDER_TARGET_XR_STEREO, [this](termin::RenderingManager &, tc_render_target_handle render_target,
                                               const std::string &base_context_name, tc_entity_handle internal_entities,
                                               std::unordered_map<std::string, termin::RenderTargetContext> &contexts,
                                               std::string &default_context_name) {
                return build_active_eye_context(render_target, base_context_name, internal_entities, contexts,
                                                default_context_name);
            });
    }

    bool build_active_eye_context(tc_render_target_handle render_target, const std::string &base_context_name,
                                  tc_entity_handle internal_entities,
                                  std::unordered_map<std::string, termin::RenderTargetContext> &contexts,
                                  std::string &default_context_name) {
        if (!tc_render_target_handle_eq(render_target, xr_render_target)) {
            return false;
        }
        if (!active_multiview_frame.valid || !xr_origin) {
            return false;
        }

        const MultiviewFrame &frame = active_multiview_frame;
        const std::string name = base_context_name.empty()
            ? "XRStereoTarget" : base_context_name;

        termin::RenderTargetContext target;
        target.name = name;
        target.render_rect = termin::Rect2i{0, 0, static_cast<int>(frame.width), static_cast<int>(frame.height)};
        target.internal_entities = internal_entities;
        target.output_color_tex = frame.color_texture;
        target.output_color_format = frame.color_format;
        target.external_textures["XR_MULTIVIEW_TARGET"] = frame.color_texture;
        target.output_depth_format = tgfx::PixelFormat::D32F;
        target.clear_color_enabled = tc_render_target_get_clear_color_enabled(render_target);
        tc_render_target_get_clear_color_value(render_target, target.clear_color);
        target.clear_depth_enabled = tc_render_target_get_clear_depth_enabled(render_target);
        target.clear_depth = tc_render_target_get_clear_depth_value(render_target);
        const termin::GeneralTransform3 origin_transform =
            xr_origin->entity().transform();
        termin::Pose3 origin_pose3(
            origin_transform.global_rotation(),
            origin_transform.global_position());
        // XrOriginComponent uses engine authoring axes: +X right, +Y forward,
        // +Z up. OpenXR reference poses are first converted from +X right, +Y
        // up, -Z forward into that engine basis, then optionally yaw-aligned
        // under the origin by XrOriginComponent::reference_alignment.
        termin::Mat44 scene_to_origin = origin_pose3.inverse().as_mat44();
        termin::Mat44 scene_from_origin = scene_to_origin.inverse();
        termin::Mat44 reference_to_origin = origin_from_xr_reference.inverse();
        termin::StereoRenderViews stereo;
        termin::RenderCamera* cameras[2] = {&stereo.left, &stereo.right};
        for (uint32_t eye = 0; eye < 2; ++eye) {
            const XrView& xr_view = frame.views[eye];
            termin::RenderCamera& camera = *cameras[eye];
            termin::Vec3 eye_position_in_reference =
                xr_position_to_scene_position(xr_view.pose.position);
            termin::Vec3 eye_position_in_origin =
                origin_from_xr_reference.transform_point(eye_position_in_reference);
            camera.view = make_xr_to_scene_matrix() *
                          mat44_from_float_array(make_view_matrix_from_xr_pose(xr_view.pose)) *
                          make_scene_to_xr_matrix() * reference_to_origin * scene_to_origin;
            camera.projection = make_engine_projection_from_xr_fov(
                xr_view.fov, static_cast<float>(xr_origin->near_clip),
                static_cast<float>(xr_origin->far_clip));
            camera.position = scene_from_origin.transform_point(eye_position_in_origin);
            camera.near_clip = xr_origin->near_clip;
            camera.far_clip = xr_origin->far_clip;
        }
        if (!stereo_contract_logged) {
            const termin::Vec3 baseline = stereo.right.position - stereo.left.position;
            tc_log_info(
                "[OpenXR scene] stereo views: left_pos=(%.6f,%.6f,%.6f) "
                "right_pos=(%.6f,%.6f,%.6f) baseline=%.6f",
                stereo.left.position.x, stereo.left.position.y, stereo.left.position.z,
                stereo.right.position.x, stereo.right.position.y, stereo.right.position.z,
                baseline.norm());
            for (uint32_t eye = 0; eye < 2; ++eye) {
                const XrView& xr_view = frame.views[eye];
                const termin::RenderCamera& camera = *cameras[eye];
                tc_log_info(
                    "[OpenXR scene] eye[%u]: xr_pose=(%.6f,%.6f,%.6f) "
                    "fov=(%.6f,%.6f,%.6f,%.6f) "
                    "projection=(%.6f,%.6f,%.6f,%.6f,%.6f,%.6f,%.6f)",
                    eye,
                    xr_view.pose.position.x, xr_view.pose.position.y,
                    xr_view.pose.position.z,
                    xr_view.fov.angleLeft, xr_view.fov.angleRight,
                    xr_view.fov.angleDown, xr_view.fov.angleUp,
                    camera.projection(0, 0), camera.projection(1, 0),
                    camera.projection(2, 1), camera.projection(1, 1),
                    camera.projection(1, 2), camera.projection(3, 2),
                    camera.projection(1, 3));
            }
            stereo_contract_logged = true;
        }
        target.stereo_views = stereo;
        target.camera = stereo.left;
        target.camera.position = (stereo.left.position + stereo.right.position) * 0.5;
        target.layer_mask = xr_origin->layer_mask & tc_render_target_get_layer_mask(render_target);

        contexts.emplace(name, std::move(target));
        default_context_name = name;
        return true;
    }

    void render_multiview(
        tgfx::TextureHandle color_texture,
        uint32_t width,
        uint32_t height,
        tgfx::PixelFormat color_format,
        const std::vector<XrView>& views) {
        if (!ready || !engine || !xr_origin) {
            return;
        }
        if (!tc_render_target_handle_valid(xr_render_target)) {
            tc_log_error("[OpenXR scene] XR render target is unavailable");
            return;
        }

        if (views.size() != 2) {
            tc_log_error("[OpenXR scene] multiview rendering requires exactly two views");
            return;
        }
        active_multiview_frame.color_texture = color_texture;
        active_multiview_frame.width = width;
        active_multiview_frame.height = height;
        active_multiview_frame.color_format = color_format;
        active_multiview_frame.views[0] = views[0];
        active_multiview_frame.views[1] = views[1];
        active_multiview_frame.valid = true;
        engine->rendering_manager.render_render_target_tree_offscreen(xr_render_target);
        active_multiview_frame.valid = false;
    }

    void update(double dt) {
        if (!ready || !scene.valid()) {
            return;
        }
        scene.update(dt);
    }

    bool begin_render_frame() {
        if (!ready || !engine) {
            return false;
        }
        termin::RenderEngine *render_engine = engine->rendering_manager.render_engine();
        if (!render_engine) {
            tc_log_error("[OpenXR scene] render engine is unavailable");
            return false;
        }
        render_engine->ensure_tgfx2();
        tgfx::RenderContext2 *ctx = render_engine->tgfx2_ctx();
        if (!ctx) {
            tc_log_error("[OpenXR scene] tgfx2 render context is unavailable");
            return false;
        }
        if (ctx->in_frame()) {
            return false;
        }
        ctx->begin_frame();
        return true;
    }

    void end_render_frame() {
        if (!ready || !engine) {
            return;
        }
        termin::RenderEngine *render_engine = engine->rendering_manager.render_engine();
        if (!render_engine) {
            tc_log_error("[OpenXR scene] render engine is unavailable while ending frame");
            return;
        }
        tgfx::RenderContext2 *ctx = render_engine->tgfx2_ctx();
        if (!ctx) {
            tc_log_error("[OpenXR scene] tgfx2 render context is unavailable while "
                         "ending frame");
            return;
        }
        if (!ctx->in_frame()) {
            tc_log_error("[OpenXR scene] tgfx2 render frame was not open while ending frame");
            return;
        }
        ctx->end_frame();
    }

    void destroy() {
        active_multiview_frame = {};
        if (engine) {
            engine->rendering_manager.clear_render_target_context_provider(TC_RENDER_TARGET_XR_STEREO);
            if (scene.valid()) {
                engine->rendering_manager.detach_scene_full(scene.handle());
            }
        }
        xr_render_target = TC_RENDER_TARGET_HANDLE_INVALID;
        // Scene render targets own their pipeline instances and detach_scene_full
        // destroyed them above. RenderPipeline is only the non-owning XR view.
        pipeline = {};
        xr_origin = nullptr;
        package.destroy();
        scene = {};
        tgfx::set_builtin_shader_root(nullptr);
        engine.reset();
        ready = false;
    }
};
void smoke_thread_main(void *java_vm, void *activity_or_context, std::string asset_root) {
    install_android_tc_log_callback_once();
    log_info("OpenXR color smoke thread start");

    OpenXRDispatch xr{};
    void *loader = dlopen("libopenxr_loader.so", RTLD_NOW | RTLD_LOCAL);
    if (!loader) {
        log_error("dlopen", dlerror());
        g_smoke.running.store(false);
        return;
    }

    xr.get_instance_proc_addr = reinterpret_cast<PFN_xrGetInstanceProcAddr>(dlsym(loader, "xrGetInstanceProcAddr"));
    if (!xr.get_instance_proc_addr) {
        log_error("dlsym", "xrGetInstanceProcAddr not found");
        g_smoke.running.store(false);
        return;
    }

    if (!load_instance_proc(xr, XR_NULL_HANDLE, "xrInitializeLoaderKHR",
                            reinterpret_cast<PFN_xrVoidFunction *>(&xr.initialize_loader))) {
        g_smoke.running.store(false);
        return;
    }
    if (!load_instance_proc(xr, XR_NULL_HANDLE, "xrEnumerateInstanceExtensionProperties",
                            reinterpret_cast<PFN_xrVoidFunction *>(&xr.enumerate_instance_extension_properties))) {
        g_smoke.running.store(false);
        return;
    }

    XrLoaderInitInfoAndroidKHR loader_init{};
    loader_init.type = XR_TYPE_LOADER_INIT_INFO_ANDROID_KHR;
    loader_init.applicationVM = java_vm;
    loader_init.applicationContext = activity_or_context;
    XrResult result = xr.initialize_loader(reinterpret_cast<const XrLoaderInitInfoBaseHeaderKHR *>(&loader_init));
    if (XR_FAILED(result)) {
        log_error("xrInitializeLoaderKHR", "loader initialization failed");
        g_smoke.running.store(false);
        return;
    }

    std::vector<const char *> enabled_extensions = {
        XR_KHR_ANDROID_CREATE_INSTANCE_EXTENSION_NAME,
        XR_KHR_VULKAN_ENABLE_EXTENSION_NAME,
    };
    const bool display_refresh_rate_available =
        openxr_instance_extension_available(xr, XR_FB_DISPLAY_REFRESH_RATE_EXTENSION_NAME);
    if (display_refresh_rate_available) {
        enabled_extensions.push_back(XR_FB_DISPLAY_REFRESH_RATE_EXTENSION_NAME);
        __android_log_print(ANDROID_LOG_INFO, kLogTag, "OpenXR extension enabled: %s",
                            XR_FB_DISPLAY_REFRESH_RATE_EXTENSION_NAME);
    } else {
        __android_log_print(ANDROID_LOG_INFO, kLogTag, "OpenXR extension unavailable: %s",
                            XR_FB_DISPLAY_REFRESH_RATE_EXTENSION_NAME);
    }

    XrInstanceCreateInfoAndroidKHR android_create_info{};
    android_create_info.type = XR_TYPE_INSTANCE_CREATE_INFO_ANDROID_KHR;
    android_create_info.applicationVM = java_vm;
    android_create_info.applicationActivity = activity_or_context;

    XrInstanceCreateInfo instance_create_info{};
    instance_create_info.type = XR_TYPE_INSTANCE_CREATE_INFO;
    instance_create_info.next = &android_create_info;
    std::strncpy(instance_create_info.applicationInfo.applicationName, "Termin OpenXR Color Smoke",
                 XR_MAX_APPLICATION_NAME_SIZE - 1);
    std::strncpy(instance_create_info.applicationInfo.engineName, "Termin", XR_MAX_ENGINE_NAME_SIZE - 1);
    instance_create_info.applicationInfo.applicationVersion = 1;
    instance_create_info.applicationInfo.engineVersion = 1;
    instance_create_info.applicationInfo.apiVersion = XR_CURRENT_API_VERSION;
    instance_create_info.enabledExtensionCount = static_cast<uint32_t>(enabled_extensions.size());
    instance_create_info.enabledExtensionNames = enabled_extensions.data();

    if (!load_instance_proc(xr, XR_NULL_HANDLE, "xrCreateInstance",
                            reinterpret_cast<PFN_xrVoidFunction *>(&xr.create_instance))) {
        g_smoke.running.store(false);
        return;
    }

    XrInstance instance = XR_NULL_HANDLE;
    result = xr.create_instance(&instance_create_info, &instance);
    if (XR_FAILED(result) || instance == XR_NULL_HANDLE) {
        __android_log_print(ANDROID_LOG_ERROR, kLogTag, "xrCreateInstance failed: %d", result);
        g_smoke.running.store(false);
        return;
    }

    load_instance_proc(xr, instance, "xrDestroyInstance", reinterpret_cast<PFN_xrVoidFunction *>(&xr.destroy_instance));
    load_instance_proc(xr, instance, "xrGetSystem", reinterpret_cast<PFN_xrVoidFunction *>(&xr.get_system));
    load_instance_proc(xr, instance, "xrCreateSession", reinterpret_cast<PFN_xrVoidFunction *>(&xr.create_session));
    load_instance_proc(xr, instance, "xrDestroySession", reinterpret_cast<PFN_xrVoidFunction *>(&xr.destroy_session));
    load_instance_proc(xr, instance, "xrCreateReferenceSpace",
                       reinterpret_cast<PFN_xrVoidFunction *>(&xr.create_reference_space));
    load_instance_proc(xr, instance, "xrCreateActionSpace",
                       reinterpret_cast<PFN_xrVoidFunction *>(&xr.create_action_space));
    load_instance_proc(xr, instance, "xrDestroySpace", reinterpret_cast<PFN_xrVoidFunction *>(&xr.destroy_space));
    load_instance_proc(xr, instance, "xrLocateSpace", reinterpret_cast<PFN_xrVoidFunction *>(&xr.locate_space));
    load_instance_proc(xr, instance, "xrEnumerateViewConfigurationViews",
                       reinterpret_cast<PFN_xrVoidFunction *>(&xr.enumerate_view_configuration_views));
    load_instance_proc(xr, instance, "xrEnumerateEnvironmentBlendModes",
                       reinterpret_cast<PFN_xrVoidFunction *>(&xr.enumerate_environment_blend_modes));
    load_instance_proc(xr, instance, "xrEnumerateSwapchainFormats",
                       reinterpret_cast<PFN_xrVoidFunction *>(&xr.enumerate_swapchain_formats));
    load_instance_proc(xr, instance, "xrCreateSwapchain", reinterpret_cast<PFN_xrVoidFunction *>(&xr.create_swapchain));
    load_instance_proc(xr, instance, "xrDestroySwapchain",
                       reinterpret_cast<PFN_xrVoidFunction *>(&xr.destroy_swapchain));
    load_instance_proc(xr, instance, "xrEnumerateSwapchainImages",
                       reinterpret_cast<PFN_xrVoidFunction *>(&xr.enumerate_swapchain_images));
    load_instance_proc(xr, instance, "xrAcquireSwapchainImage",
                       reinterpret_cast<PFN_xrVoidFunction *>(&xr.acquire_swapchain_image));
    load_instance_proc(xr, instance, "xrWaitSwapchainImage",
                       reinterpret_cast<PFN_xrVoidFunction *>(&xr.wait_swapchain_image));
    load_instance_proc(xr, instance, "xrReleaseSwapchainImage",
                       reinterpret_cast<PFN_xrVoidFunction *>(&xr.release_swapchain_image));
    load_instance_proc(xr, instance, "xrPollEvent", reinterpret_cast<PFN_xrVoidFunction *>(&xr.poll_event));
    load_instance_proc(xr, instance, "xrBeginSession", reinterpret_cast<PFN_xrVoidFunction *>(&xr.begin_session));
    load_instance_proc(xr, instance, "xrEndSession", reinterpret_cast<PFN_xrVoidFunction *>(&xr.end_session));
    load_instance_proc(xr, instance, "xrWaitFrame", reinterpret_cast<PFN_xrVoidFunction *>(&xr.wait_frame));
    load_instance_proc(xr, instance, "xrBeginFrame", reinterpret_cast<PFN_xrVoidFunction *>(&xr.begin_frame));
    load_instance_proc(xr, instance, "xrEndFrame", reinterpret_cast<PFN_xrVoidFunction *>(&xr.end_frame));
    load_instance_proc(xr, instance, "xrLocateViews", reinterpret_cast<PFN_xrVoidFunction *>(&xr.locate_views));
    load_instance_proc(xr, instance, "xrStringToPath", reinterpret_cast<PFN_xrVoidFunction *>(&xr.string_to_path));
    load_instance_proc(xr, instance, "xrCreateActionSet",
                       reinterpret_cast<PFN_xrVoidFunction *>(&xr.create_action_set));
    load_instance_proc(xr, instance, "xrDestroyActionSet",
                       reinterpret_cast<PFN_xrVoidFunction *>(&xr.destroy_action_set));
    load_instance_proc(xr, instance, "xrCreateAction", reinterpret_cast<PFN_xrVoidFunction *>(&xr.create_action));
    load_instance_proc(xr, instance, "xrDestroyAction", reinterpret_cast<PFN_xrVoidFunction *>(&xr.destroy_action));
    load_instance_proc(xr, instance, "xrSuggestInteractionProfileBindings",
                       reinterpret_cast<PFN_xrVoidFunction *>(&xr.suggest_interaction_profile_bindings));
    load_instance_proc(xr, instance, "xrAttachSessionActionSets",
                       reinterpret_cast<PFN_xrVoidFunction *>(&xr.attach_session_action_sets));
    load_instance_proc(xr, instance, "xrSyncActions", reinterpret_cast<PFN_xrVoidFunction *>(&xr.sync_actions));
    load_instance_proc(xr, instance, "xrGetActionStateVector2f",
                       reinterpret_cast<PFN_xrVoidFunction *>(&xr.get_action_state_vector2f));
    load_instance_proc(xr, instance, "xrGetActionStateFloat",
                       reinterpret_cast<PFN_xrVoidFunction *>(&xr.get_action_state_float));
    load_instance_proc(xr, instance, "xrGetActionStatePose",
                       reinterpret_cast<PFN_xrVoidFunction *>(&xr.get_action_state_pose));
    load_instance_proc(xr, instance, "xrGetVulkanInstanceExtensionsKHR",
                       reinterpret_cast<PFN_xrVoidFunction *>(&xr.get_vulkan_instance_extensions));
    load_instance_proc(xr, instance, "xrGetVulkanDeviceExtensionsKHR",
                       reinterpret_cast<PFN_xrVoidFunction *>(&xr.get_vulkan_device_extensions));
    load_instance_proc(xr, instance, "xrGetVulkanGraphicsDeviceKHR",
                       reinterpret_cast<PFN_xrVoidFunction *>(&xr.get_vulkan_graphics_device));
    load_instance_proc(xr, instance, "xrGetVulkanGraphicsRequirementsKHR",
                       reinterpret_cast<PFN_xrVoidFunction *>(&xr.get_vulkan_requirements));
    if (display_refresh_rate_available) {
        load_instance_proc(xr, instance, "xrEnumerateDisplayRefreshRatesFB",
                           reinterpret_cast<PFN_xrVoidFunction *>(&xr.enumerate_display_refresh_rates));
        load_instance_proc(xr, instance, "xrGetDisplayRefreshRateFB",
                           reinterpret_cast<PFN_xrVoidFunction *>(&xr.get_display_refresh_rate));
        load_instance_proc(xr, instance, "xrRequestDisplayRefreshRateFB",
                           reinterpret_cast<PFN_xrVoidFunction *>(&xr.request_display_refresh_rate));
    }

    XrSystemGetInfo system_info{};
    system_info.type = XR_TYPE_SYSTEM_GET_INFO;
    system_info.formFactor = XR_FORM_FACTOR_HEAD_MOUNTED_DISPLAY;
    XrSystemId system_id = XR_NULL_SYSTEM_ID;
    result = xr.get_system(instance, &system_info, &system_id);
    if (XR_FAILED(result) || system_id == XR_NULL_SYSTEM_ID) {
        __android_log_print(ANDROID_LOG_ERROR, kLogTag, "xrGetSystem failed: %d", result);
        xr.destroy_instance(instance);
        g_smoke.running.store(false);
        return;
    }

    XrGraphicsRequirementsVulkanKHR vulkan_requirements{};
    vulkan_requirements.type = XR_TYPE_GRAPHICS_REQUIREMENTS_VULKAN_KHR;
    result = xr.get_vulkan_requirements(instance, system_id, &vulkan_requirements);
    if (XR_FAILED(result)) {
        __android_log_print(ANDROID_LOG_ERROR, kLogTag, "xrGetVulkanGraphicsRequirementsKHR failed: %d", result);
        xr.destroy_instance(instance);
        g_smoke.running.store(false);
        return;
    }

    std::vector<std::string> instance_extension_storage;
    std::vector<std::string> device_extension_storage;
    if (!query_openxr_vulkan_extensions(xr.get_vulkan_instance_extensions, instance, system_id,
                                        instance_extension_storage) ||
        !query_openxr_vulkan_extensions(xr.get_vulkan_device_extensions, instance, system_id,
                                        device_extension_storage)) {
        xr.destroy_instance(instance);
        g_smoke.running.store(false);
        return;
    }
    std::vector<const char *> instance_extensions = extension_cstrs(instance_extension_storage);
    std::vector<const char *> device_extensions = extension_cstrs(device_extension_storage);

    std::unique_ptr<tgfx::GraphicsHost> graphics_host;
    tgfx::VulkanRenderDevice* render_device = nullptr;
    try {
        tgfx::VulkanDeviceCreateInfo device_info{};
        device_info.enable_validation = false;
        XrVersion requested_vulkan_version = XR_MAKE_VERSION(1, 1, 0);
        if (vulkan_requirements.maxApiVersionSupported < requested_vulkan_version) {
            throw std::runtime_error(
                "OpenXR runtime does not support Vulkan 1.1 required for multiview");
        }
        if (vulkan_requirements.minApiVersionSupported > requested_vulkan_version) {
            requested_vulkan_version = vulkan_requirements.minApiVersionSupported;
        }
        device_info.api_version = VK_MAKE_API_VERSION(
            0,
            XR_VERSION_MAJOR(requested_vulkan_version),
            XR_VERSION_MINOR(requested_vulkan_version),
            XR_VERSION_PATCH(requested_vulkan_version));
        device_info.instance_extensions = instance_extensions;
        device_info.device_extensions = device_extensions;
        device_info.physical_device_selector = [&](VkInstance vk_instance) -> VkPhysicalDevice {
            VkPhysicalDevice physical_device = VK_NULL_HANDLE;
            XrResult select_result = xr.get_vulkan_graphics_device(instance, system_id, vk_instance, &physical_device);
            if (XR_FAILED(select_result)) {
                __android_log_print(ANDROID_LOG_ERROR, kLogTag, "xrGetVulkanGraphicsDeviceKHR failed: %d",
                                    select_result);
                return VK_NULL_HANDLE;
            }
            return physical_device;
        };
        auto owned_device = std::make_unique<tgfx::VulkanRenderDevice>(device_info);
        const tgfx::BackendCapabilities capabilities = owned_device->capabilities();
        if (!capabilities.supports_texture_arrays ||
            !capabilities.supports_multiview ||
            capabilities.max_multiview_views < 2) {
            throw std::runtime_error(
                "Vulkan device does not satisfy the two-view multiview contract");
        }
        render_device = owned_device.get();
        graphics_host = tgfx::GraphicsHost::adopt_application_device(
            std::move(owned_device));
    } catch (const std::exception &e) {
        log_error("tgfx2 Vulkan", e.what());
        xr.destroy_instance(instance);
        g_smoke.running.store(false);
        return;
    }

    auto release_render_device = [&]() {
        if (!graphics_host) {
            return;
        }
        graphics_host.reset();
        render_device = nullptr;
    };

    XrGraphicsBindingVulkanKHR graphics_binding{};
    graphics_binding.type = XR_TYPE_GRAPHICS_BINDING_VULKAN_KHR;
    graphics_binding.instance = render_device->instance();
    graphics_binding.physicalDevice = render_device->physical_device();
    graphics_binding.device = render_device->device();
    graphics_binding.queueFamilyIndex = render_device->graphics_queue_family();
    graphics_binding.queueIndex = 0;

    XrSessionCreateInfo session_create_info{};
    session_create_info.type = XR_TYPE_SESSION_CREATE_INFO;
    session_create_info.next = &graphics_binding;
    session_create_info.systemId = system_id;

    XrSession session = XR_NULL_HANDLE;
    result = xr.create_session(instance, &session_create_info, &session);
    if (XR_FAILED(result) || session == XR_NULL_HANDLE) {
        __android_log_print(ANDROID_LOG_ERROR, kLogTag, "xrCreateSession failed: %d", result);
        release_render_device();
        xr.destroy_instance(instance);
        g_smoke.running.store(false);
        return;
    }
    configure_display_refresh_rate(xr, session);

    OpenXRRuntimeScene runtime_scene;
    const bool runtime_scene_requested = !asset_root.empty();
    const bool runtime_scene_ready =
        runtime_scene_requested && runtime_scene.load(asset_root, *graphics_host);

    XrReferenceSpaceCreateInfo space_create_info{};
    space_create_info.type = XR_TYPE_REFERENCE_SPACE_CREATE_INFO;
    space_create_info.referenceSpaceType =
        runtime_scene_ready && runtime_scene.xr_origin &&
                runtime_scene.xr_origin->reference_space == termin::XrReferenceSpace::Stage
            ? XR_REFERENCE_SPACE_TYPE_STAGE
            : XR_REFERENCE_SPACE_TYPE_LOCAL;
    space_create_info.poseInReferenceSpace.orientation.w = 1.0f;
    XrSpace app_space = XR_NULL_HANDLE;
    result = xr.create_reference_space(session, &space_create_info, &app_space);
    if (XR_FAILED(result)) {
        __android_log_print(ANDROID_LOG_ERROR, kLogTag, "xrCreateReferenceSpace failed: %d", result);
    }

    uint32_t view_count = 0;
    xr.enumerate_view_configuration_views(instance, system_id, XR_VIEW_CONFIGURATION_TYPE_PRIMARY_STEREO, 0,
                                          &view_count, nullptr);
    std::vector<XrViewConfigurationView> view_configs(view_count);
    for (XrViewConfigurationView &view_config : view_configs) {
        view_config.type = XR_TYPE_VIEW_CONFIGURATION_VIEW;
    }
    xr.enumerate_view_configuration_views(instance, system_id, XR_VIEW_CONFIGURATION_TYPE_PRIMARY_STEREO, view_count,
                                          &view_count, view_configs.data());
    if (view_count != 2) {
        log_error("OpenXR", "explicit multiview path requires exactly two primary stereo views");
        runtime_scene.destroy();
        if (app_space != XR_NULL_HANDLE) {
            xr.destroy_space(app_space);
        }
        xr.destroy_session(session);
        release_render_device();
        xr.destroy_instance(instance);
        g_smoke.running.store(false);
        return;
    }

    uint32_t blend_count = 0;
    xr.enumerate_environment_blend_modes(instance, system_id, XR_VIEW_CONFIGURATION_TYPE_PRIMARY_STEREO, 0,
                                         &blend_count, nullptr);
    std::vector<XrEnvironmentBlendMode> blend_modes(blend_count);
    xr.enumerate_environment_blend_modes(instance, system_id, XR_VIEW_CONFIGURATION_TYPE_PRIMARY_STEREO, blend_count,
                                         &blend_count, blend_modes.data());
    XrEnvironmentBlendMode blend_mode = blend_count > 0 ? blend_modes[0] : XR_ENVIRONMENT_BLEND_MODE_OPAQUE;

    uint32_t format_count = 0;
    xr.enumerate_swapchain_formats(session, 0, &format_count, nullptr);
    std::vector<int64_t> formats(format_count);
    xr.enumerate_swapchain_formats(session, format_count, &format_count, formats.data());
    int64_t color_format = choose_vulkan_swapchain_format(formats);
    tgfx::PixelFormat tgfx_color_format = pixel_format_from_vk_format(static_cast<VkFormat>(color_format));
    if (tgfx_color_format == tgfx::PixelFormat::Undefined) {
        __android_log_print(ANDROID_LOG_ERROR, kLogTag, "unsupported Vulkan swapchain format: 0x%llx",
                            static_cast<long long>(color_format));
        runtime_scene.destroy();
        if (app_space != XR_NULL_HANDLE) {
            xr.destroy_space(app_space);
        }
        xr.destroy_session(session);
        release_render_device();
        xr.destroy_instance(instance);
        g_smoke.running.store(false);
        return;
    }
    __android_log_print(ANDROID_LOG_INFO, kLogTag, "OpenXR smoke color format: 0x%llx",
                        static_cast<long long>(color_format));

    XrSwapchainCreateInfo swapchain_create_info{};
    swapchain_create_info.type = XR_TYPE_SWAPCHAIN_CREATE_INFO;
    swapchain_create_info.usageFlags = XR_SWAPCHAIN_USAGE_COLOR_ATTACHMENT_BIT | XR_SWAPCHAIN_USAGE_TRANSFER_DST_BIT;
    swapchain_create_info.format = color_format;
    // MSAA belongs to the explicit internal graph resources. The XR image is
    // the single-sample, two-layer tonemap destination.
    swapchain_create_info.sampleCount = 1;
    swapchain_create_info.width = view_configs[0].recommendedImageRectWidth;
    swapchain_create_info.height = view_configs[0].recommendedImageRectHeight;
    swapchain_create_info.faceCount = 1;
    swapchain_create_info.arraySize = 2;
    swapchain_create_info.mipCount = 1;
    __android_log_print(ANDROID_LOG_INFO, kLogTag,
                        "OpenXR swapchain: views=%u size=%ux%u samples=%u "
                        "recommendedSamples=%u maxSamples=%u",
                        view_count, swapchain_create_info.width, swapchain_create_info.height,
                        swapchain_create_info.sampleCount, view_configs[0].recommendedSwapchainSampleCount,
                        view_configs[0].maxSwapchainSampleCount);

    XrSwapchain color_swapchain = XR_NULL_HANDLE;
    std::vector<XrSwapchainImageVulkanKHR> swapchain_images;
    std::vector<tgfx::TextureHandle> swapchain_textures;
    tgfx::TextureDesc color_desc{};
    color_desc.width = swapchain_create_info.width;
    color_desc.height = swapchain_create_info.height;
    color_desc.mip_levels = 1;
    color_desc.sample_count = swapchain_create_info.sampleCount;
    color_desc.array_layers = 2;
    color_desc.format = tgfx_color_format;
    color_desc.usage = tgfx::TextureUsage::ColorAttachment | tgfx::TextureUsage::CopySrc | tgfx::TextureUsage::CopyDst;
    {
        result = xr.create_swapchain(session, &swapchain_create_info, &color_swapchain);
        if (XR_FAILED(result) || color_swapchain == XR_NULL_HANDLE) {
            __android_log_print(ANDROID_LOG_ERROR, kLogTag, "xrCreateSwapchain failed: %d", result);
            runtime_scene.destroy();
            if (app_space != XR_NULL_HANDLE) {
                xr.destroy_space(app_space);
            }
            xr.destroy_session(session);
            release_render_device();
            xr.destroy_instance(instance);
            g_smoke.running.store(false);
            return;
        }

        uint32_t image_count = 0;
        xr.enumerate_swapchain_images(color_swapchain, 0, &image_count, nullptr);
        swapchain_images.resize(image_count);
        for (XrSwapchainImageVulkanKHR &image : swapchain_images) {
            image.type = XR_TYPE_SWAPCHAIN_IMAGE_VULKAN_KHR;
        }
        xr.enumerate_swapchain_images(color_swapchain, image_count, &image_count,
                                      reinterpret_cast<XrSwapchainImageBaseHeader *>(swapchain_images.data()));
        swapchain_textures.reserve(image_count);
        for (const XrSwapchainImageVulkanKHR &image : swapchain_images) {
            swapchain_textures.push_back(
                render_device->register_external_texture(reinterpret_cast<uintptr_t>(image.image), color_desc));
        }
    }

    if (runtime_scene_requested && !runtime_scene_ready) {
        __android_log_print(ANDROID_LOG_ERROR, kLogTag,
                            "OpenXR runtime scene is not ready; rendering clear frames only");
    }

    XrControllerActions controller_actions;
    if (controller_actions.init(xr, instance)) {
        controller_actions.attach(session);
    } else {
        tc_log_error("[OpenXR input] XR controller actions are disabled");
    }

    std::vector<XrView> views(view_count);
    for (XrView &view : views) {
        view.type = XR_TYPE_VIEW;
    }
    std::vector<XrCompositionLayerProjectionView> layer_views(view_count);
    for (XrCompositionLayerProjectionView &layer_view : layer_views) {
        layer_view.type = XR_TYPE_COMPOSITION_LAYER_PROJECTION_VIEW;
    }
    bool session_running = false;
    XrSessionState current_session_state = XR_SESSION_STATE_UNKNOWN;
    uint64_t frame_index = 0;
    using FrameClock = std::chrono::steady_clock;
    auto fps_window_start = FrameClock::now();
    XrTime fps_window_first_display_time = 0;
    XrTime fps_window_last_display_time = 0;
    uint64_t fps_window_frames = 0;
    uint64_t fps_window_rendered_frames = 0;
    uint64_t fps_window_should_skip_frames = 0;
    double fps_window_wait_frame_ms = 0.0;
    double fps_window_wait_frame_min_ms = -1.0;
    double fps_window_wait_frame_max_ms = 0.0;
    double fps_window_swapchain_wait_ms = 0.0;
    double fps_window_render_ms = 0.0;
    double fps_window_frame_cpu_ms = 0.0;
    double fps_window_predicted_period_ms = 0.0;
    double fps_window_predicted_delta_ms = 0.0;
    double fps_window_predicted_delta_min_ms = -1.0;
    double fps_window_predicted_delta_max_ms = 0.0;
    uint64_t fps_window_predicted_delta_count = 0;
    XrTime last_predicted_display_time = 0;
    auto millis_between = [](FrameClock::time_point begin, FrameClock::time_point end) {
        return std::chrono::duration<double, std::milli>(end - begin).count();
    };
    auto xr_duration_to_ms = [](XrDuration duration) { return static_cast<double>(duration) * 1e-6; };

    log_info("OpenXR color smoke loop ready");
    while (g_smoke.running.load()) {
        const auto frame_cpu_start = FrameClock::now();
        double frame_wait_frame_ms = 0.0;
        double frame_swapchain_wait_ms = 0.0;
        double frame_render_ms = 0.0;
        bool frame_rendered = false;

        XrEventDataBuffer event{};
        event.type = XR_TYPE_EVENT_DATA_BUFFER;
        while (xr.poll_event(instance, &event) == XR_SUCCESS) {
            if (event.type == XR_TYPE_EVENT_DATA_SESSION_STATE_CHANGED) {
                const auto *state_event = reinterpret_cast<const XrEventDataSessionStateChanged *>(&event);
                current_session_state = state_event->state;
                __android_log_print(ANDROID_LOG_INFO, kLogTag, "session state: %s",
                                    session_state_name(state_event->state));
                if (state_event->state == XR_SESSION_STATE_READY) {
                    XrSessionBeginInfo begin_info{};
                    begin_info.type = XR_TYPE_SESSION_BEGIN_INFO;
                    begin_info.primaryViewConfigurationType = XR_VIEW_CONFIGURATION_TYPE_PRIMARY_STEREO;
                    result = xr.begin_session(session, &begin_info);
                    session_running = XR_SUCCEEDED(result);
                    __android_log_print(ANDROID_LOG_INFO, kLogTag, "xrBeginSession result=%d", result);
                } else if (state_event->state == XR_SESSION_STATE_STOPPING) {
                    if (session_running) {
                        xr.end_session(session);
                    }
                    session_running = false;
                } else if (state_event->state == XR_SESSION_STATE_EXITING ||
                           state_event->state == XR_SESSION_STATE_LOSS_PENDING) {
                    g_smoke.running.store(false);
                }
            }
            event = {};
            event.type = XR_TYPE_EVENT_DATA_BUFFER;
        }

        if (!session_running || app_space == XR_NULL_HANDLE) {
            std::this_thread::sleep_for(std::chrono::milliseconds(10));
            continue;
        }

        XrFrameWaitInfo wait_info{};
        wait_info.type = XR_TYPE_FRAME_WAIT_INFO;
        XrFrameState frame_state{};
        frame_state.type = XR_TYPE_FRAME_STATE;
        const auto wait_frame_begin = FrameClock::now();
        result = xr.wait_frame(session, &wait_info, &frame_state);
        frame_wait_frame_ms = millis_between(wait_frame_begin, FrameClock::now());
        if (fps_window_wait_frame_min_ms < 0.0 || frame_wait_frame_ms < fps_window_wait_frame_min_ms) {
            fps_window_wait_frame_min_ms = frame_wait_frame_ms;
        }
        if (frame_wait_frame_ms > fps_window_wait_frame_max_ms) {
            fps_window_wait_frame_max_ms = frame_wait_frame_ms;
        }
        if (XR_FAILED(result)) {
            __android_log_print(ANDROID_LOG_ERROR, kLogTag, "xrWaitFrame failed: %d", result);
            continue;
        }

        fps_window_predicted_period_ms += xr_duration_to_ms(frame_state.predictedDisplayPeriod);
        if (last_predicted_display_time != 0 && frame_state.predictedDisplayTime > last_predicted_display_time) {
            const double predicted_delta_ms =
                static_cast<double>(frame_state.predictedDisplayTime - last_predicted_display_time) * 1e-6;
            fps_window_predicted_delta_ms += predicted_delta_ms;
            ++fps_window_predicted_delta_count;
            if (fps_window_predicted_delta_min_ms < 0.0 || predicted_delta_ms < fps_window_predicted_delta_min_ms) {
                fps_window_predicted_delta_min_ms = predicted_delta_ms;
            }
            if (predicted_delta_ms > fps_window_predicted_delta_max_ms) {
                fps_window_predicted_delta_max_ms = predicted_delta_ms;
            }
        }
        last_predicted_display_time = frame_state.predictedDisplayTime;

        XrFrameBeginInfo begin_frame_info{};
        begin_frame_info.type = XR_TYPE_FRAME_BEGIN_INFO;
        result = xr.begin_frame(session, &begin_frame_info);
        if (XR_FAILED(result)) {
            __android_log_print(ANDROID_LOG_ERROR, kLogTag, "xrBeginFrame failed: %d", result);
            continue;
        }

        XrCompositionLayerBaseHeader *layers[1] = {};
        uint32_t layer_count = 0;
        XrCompositionLayerProjection projection_layer{};
        projection_layer.type = XR_TYPE_COMPOSITION_LAYER_PROJECTION;
        projection_layer.space = app_space;
        projection_layer.viewCount = view_count;
        projection_layer.views = layer_views.data();

        if (frame_state.shouldRender) {
            XrViewLocateInfo locate_info{};
            locate_info.type = XR_TYPE_VIEW_LOCATE_INFO;
            locate_info.viewConfigurationType = XR_VIEW_CONFIGURATION_TYPE_PRIMARY_STEREO;
            locate_info.displayTime = frame_state.predictedDisplayTime;
            locate_info.space = app_space;
            XrViewState view_state{};
            view_state.type = XR_TYPE_VIEW_STATE;
            uint32_t located_view_count = 0;
            result = xr.locate_views(session, &locate_info, &view_state, view_count, &located_view_count, views.data());
            if (XR_SUCCEEDED(result) && located_view_count == view_count) {
                const bool head_orientation_valid =
                    (view_state.viewStateFlags & XR_VIEW_STATE_ORIENTATION_VALID_BIT) != 0;
                if (located_view_count > 0) {
                    if (runtime_scene_ready) {
                        runtime_scene.update_reference_alignment(views[0], view_state.viewStateFlags);
                    }
                    controller_actions.update_head_axes(views[0],
                                                        runtime_scene_ready ? runtime_scene.origin_from_xr_reference
                                                                            : termin::Mat44::identity(),
                                                        head_orientation_valid);
                }
                controller_actions.sync(
                    session, app_space, frame_state.predictedDisplayTime,
                    runtime_scene_ready ? runtime_scene.origin_from_xr_reference : termin::Mat44::identity(),
                    frame_index);
                if (runtime_scene_ready) {
                    const double frame_dt =
                        std::max(1e-6, static_cast<double>(frame_state.predictedDisplayPeriod) * 1e-9);
                    runtime_scene.update(frame_dt);
                }

                const bool runtime_scene_frame_open = runtime_scene_ready && runtime_scene.begin_render_frame();
                uint32_t image_index = 0;
                XrSwapchainImageAcquireInfo acquire_info{};
                acquire_info.type = XR_TYPE_SWAPCHAIN_IMAGE_ACQUIRE_INFO;
                result = xr.acquire_swapchain_image(color_swapchain, &acquire_info, &image_index);
                bool image_acquired = XR_SUCCEEDED(result);
                bool image_ready = image_acquired;
                if (!image_acquired) {
                    __android_log_print(ANDROID_LOG_ERROR, kLogTag,
                                        "xrAcquireSwapchainImage failed: %d", result);
                }

                if (image_acquired) {
                    XrSwapchainImageWaitInfo wait_swapchain_info{};
                    wait_swapchain_info.type = XR_TYPE_SWAPCHAIN_IMAGE_WAIT_INFO;
                    wait_swapchain_info.timeout = XR_INFINITE_DURATION;
                    const auto wait_swapchain_begin = FrameClock::now();
                    result = xr.wait_swapchain_image(color_swapchain, &wait_swapchain_info);
                    frame_swapchain_wait_ms +=
                        millis_between(wait_swapchain_begin, FrameClock::now());
                    if (XR_FAILED(result)) {
                        __android_log_print(ANDROID_LOG_ERROR, kLogTag,
                                            "xrWaitSwapchainImage failed: %d", result);
                        image_ready = false;
                    }
                }

                tgfx::TextureHandle color_texture{};
                if (image_ready) {
                    color_texture = swapchain_textures[image_index];
                    tgfx::ExternalTextureAccessDesc access;
                    access.state_after_wait =
                        tgfx::ExternalTextureState::ColorAttachment;
                    access.required_before_release =
                        tgfx::ExternalTextureState::ColorAttachment;
                    image_ready = render_device->begin_external_texture_access(
                        color_texture, access);
                }

                const auto render_begin = FrameClock::now();
                if (image_ready && runtime_scene_ready && runtime_scene_frame_open) {
                    runtime_scene.render_multiview(
                        color_texture, swapchain_create_info.width,
                        swapchain_create_info.height, tgfx_color_format, views);
                } else if (image_ready) {
                    if (runtime_scene_ready) {
                        tc_log_error("[OpenXR scene] render frame did not open; clearing XR target");
                    }
                    auto cmd = render_device->create_command_list();
                    cmd->begin();
                    tgfx::MultiviewRenderPassDesc pass{};
                    tgfx::ColorAttachmentDesc color_attachment{};
                    color_attachment.texture = color_texture;
                    color_attachment.load = tgfx::LoadOp::Clear;
                    color_attachment.store = tgfx::StoreOp::Store;
                    color_attachment.clear_color[0] = 0.015f;
                    color_attachment.clear_color[1] = 0.018f;
                    color_attachment.clear_color[2] = 0.024f;
                    color_attachment.clear_color[3] = 1.0f;
                    pass.colors.push_back(color_attachment);
                    pass.view_count = 2;
                    cmd->begin_multiview_render_pass(pass);
                    cmd->set_viewport(0, 0, static_cast<int>(swapchain_create_info.width),
                                      static_cast<int>(swapchain_create_info.height));
                    cmd->set_scissor(0, 0, static_cast<int>(swapchain_create_info.width),
                                     static_cast<int>(swapchain_create_info.height));
                    cmd->end_render_pass();
                    cmd->end();
                    render_device->submit(*cmd);
                }
                frame_render_ms += millis_between(render_begin, FrameClock::now());

                for (uint32_t eye = 0; eye < view_count; ++eye) {
                    layer_views[eye].pose = views[eye].pose;
                    layer_views[eye].fov = views[eye].fov;
                    layer_views[eye].subImage.swapchain = color_swapchain;
                    layer_views[eye].subImage.imageRect.offset = {0, 0};
                    layer_views[eye].subImage.imageRect.extent = {
                        static_cast<int32_t>(swapchain_create_info.width),
                        static_cast<int32_t>(swapchain_create_info.height)};
                    layer_views[eye].subImage.imageArrayIndex = eye;
                }

                if (runtime_scene_frame_open) {
                    const auto render_submit_begin = FrameClock::now();
                    runtime_scene.end_render_frame();
                    frame_render_ms += millis_between(render_submit_begin, FrameClock::now());
                }

                if (image_acquired) {
                    if (image_ready &&
                        !render_device->end_external_texture_access(color_texture)) {
                        tc_log_error("[OpenXR] external color texture failed release contract");
                        image_ready = false;
                    }
                    XrSwapchainImageReleaseInfo release_info{};
                    release_info.type = XR_TYPE_SWAPCHAIN_IMAGE_RELEASE_INFO;
                    result = xr.release_swapchain_image(color_swapchain, &release_info);
                    if (XR_FAILED(result)) {
                        __android_log_print(ANDROID_LOG_ERROR, kLogTag, "xrReleaseSwapchainImage failed: %d", result);
                    }
                }

                if (image_ready) {
                    layers[0] = reinterpret_cast<XrCompositionLayerBaseHeader *>(&projection_layer);
                    layer_count = 1;
                }
                ++frame_index;
                frame_rendered = image_ready;
            }
        } else {
            ++fps_window_should_skip_frames;
        }

        XrFrameEndInfo end_info{};
        end_info.type = XR_TYPE_FRAME_END_INFO;
        end_info.displayTime = frame_state.predictedDisplayTime;
        end_info.environmentBlendMode = blend_mode;
        end_info.layerCount = layer_count;
        end_info.layers = layer_count ? layers : nullptr;
        result = xr.end_frame(session, &end_info);
        if (XR_FAILED(result)) {
            __android_log_print(ANDROID_LOG_ERROR, kLogTag, "xrEndFrame failed: %d", result);
        }

        const auto frame_cpu_end = FrameClock::now();
        ++fps_window_frames;
        if (frame_rendered) {
            ++fps_window_rendered_frames;
        }
        if (fps_window_first_display_time == 0) {
            fps_window_first_display_time = frame_state.predictedDisplayTime;
        }
        fps_window_last_display_time = frame_state.predictedDisplayTime;
        fps_window_wait_frame_ms += frame_wait_frame_ms;
        fps_window_swapchain_wait_ms += frame_swapchain_wait_ms;
        fps_window_render_ms += frame_render_ms;
        fps_window_frame_cpu_ms += millis_between(frame_cpu_start, frame_cpu_end);

        const double wall_seconds = std::chrono::duration<double>(frame_cpu_end - fps_window_start).count();
        if (wall_seconds >= 2.0 && fps_window_frames > 0) {
            const double wall_fps = static_cast<double>(fps_window_frames) / wall_seconds;
            const double rendered_fps = static_cast<double>(fps_window_rendered_frames) / wall_seconds;
            double predicted_hz = 0.0;
            if (fps_window_last_display_time > fps_window_first_display_time) {
                const double predicted_seconds =
                    static_cast<double>(fps_window_last_display_time - fps_window_first_display_time) * 1e-9;
                if (predicted_seconds > 0.0) {
                    predicted_hz = static_cast<double>(fps_window_frames - 1) / predicted_seconds;
                }
            }
            const double inv_frames = 1.0 / static_cast<double>(fps_window_frames);
            const double inv_predicted_delta = fps_window_predicted_delta_count > 0
                                                   ? 1.0 / static_cast<double>(fps_window_predicted_delta_count)
                                                   : 0.0;
            __android_log_print(ANDROID_LOG_INFO, kLogTag,
                                "XR FPS: state=%s wall=%.1f rendered=%.1f predictedHz=%.1f "
                                "avgMs{frame=%.2f waitFrame=%.2f waitMin=%.2f waitMax=%.2f "
                                "swapWait=%.2f render=%.2f period=%.2f predDelta=%.2f "
                                "predDeltaMin=%.2f predDeltaMax=%.2f} "
                                "frames=%llu renderedFrames=%llu shouldSkip=%llu",
                                session_state_name(current_session_state), wall_fps, rendered_fps, predicted_hz,
                                fps_window_frame_cpu_ms * inv_frames, fps_window_wait_frame_ms * inv_frames,
                                fps_window_wait_frame_min_ms < 0.0 ? 0.0 : fps_window_wait_frame_min_ms,
                                fps_window_wait_frame_max_ms, fps_window_swapchain_wait_ms * inv_frames,
                                fps_window_render_ms * inv_frames, fps_window_predicted_period_ms * inv_frames,
                                fps_window_predicted_delta_ms * inv_predicted_delta,
                                fps_window_predicted_delta_min_ms < 0.0 ? 0.0 : fps_window_predicted_delta_min_ms,
                                fps_window_predicted_delta_max_ms, static_cast<unsigned long long>(fps_window_frames),
                                static_cast<unsigned long long>(fps_window_rendered_frames),
                                static_cast<unsigned long long>(fps_window_should_skip_frames));

            fps_window_start = frame_cpu_end;
            fps_window_first_display_time = 0;
            fps_window_last_display_time = 0;
            fps_window_frames = 0;
            fps_window_rendered_frames = 0;
            fps_window_should_skip_frames = 0;
            fps_window_wait_frame_ms = 0.0;
            fps_window_wait_frame_min_ms = -1.0;
            fps_window_wait_frame_max_ms = 0.0;
            fps_window_swapchain_wait_ms = 0.0;
            fps_window_render_ms = 0.0;
            fps_window_frame_cpu_ms = 0.0;
            fps_window_predicted_period_ms = 0.0;
            fps_window_predicted_delta_ms = 0.0;
            fps_window_predicted_delta_min_ms = -1.0;
            fps_window_predicted_delta_max_ms = 0.0;
            fps_window_predicted_delta_count = 0;
        }
    }

    if (session_running) {
        xr.end_session(session);
    }
    runtime_scene.destroy();
    for (tgfx::TextureHandle texture : swapchain_textures) {
        if (texture) {
            render_device->destroy(texture);
        }
    }
    render_device->wait_idle();
    if (color_swapchain != XR_NULL_HANDLE) {
        xr.destroy_swapchain(color_swapchain);
    }
    if (app_space != XR_NULL_HANDLE) {
        xr.destroy_space(app_space);
    }
    controller_actions.destroy();
    xr.destroy_session(session);
    release_render_device();
    xr.destroy_instance(instance);
    log_info("OpenXR color smoke thread stop");
}
#endif

} // namespace

namespace detail {

OpenXRAndroidStartResult start_android_scene_smoke_internal(void *java_vm, void *activity_or_context,
                                                            const char *asset_root) {
    OpenXRAndroidStartResult result{};
    result.stage = "unsupported";
    result.detail = "OpenXR color smoke is only available in Android builds with "
                    "OpenXR headers";

#if defined(TERMIN_OPENXR_HAS_HEADERS) && defined(__ANDROID__)
    install_android_tc_log_callback_once();
    if (!java_vm || !activity_or_context) {
        result.stage = "input";
        result.detail = "JavaVM or Android activity/context is null";
        log_error(result.stage, result.detail);
        return result;
    }
    if (g_smoke.running.exchange(true)) {
        result.started = true;
        result.stage = "already-running";
        result.detail = "OpenXR color smoke thread is already running";
        return result;
    }
    if (g_smoke.thread.joinable()) {
        g_smoke.thread.join();
    }
    try {
        g_smoke.thread =
            std::thread(smoke_thread_main, java_vm, activity_or_context, std::string(asset_root ? asset_root : ""));
    } catch (...) {
        g_smoke.running.store(false);
        result.stage = "thread";
        result.detail = "failed to create OpenXR color smoke thread";
        log_error(result.stage, result.detail);
        return result;
    }
    result.started = true;
    result.stage = "started";
    result.detail = "OpenXR color smoke thread started";
#else
    (void)java_vm;
    (void)activity_or_context;
    (void)asset_root;
#endif

    return result;
}

void stop_android_color_smoke_internal() {
#if defined(TERMIN_OPENXR_HAS_HEADERS) && defined(__ANDROID__)
    g_smoke.running.store(false);
    if (g_smoke.thread.joinable()) {
        g_smoke.thread.join();
    }
#endif
}

} // namespace detail

} // namespace termin::openxr
