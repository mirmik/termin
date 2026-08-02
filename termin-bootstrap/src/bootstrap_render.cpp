#include <termin/bootstrap/bootstrap.hpp>
#include <termin/bootstrap/bootstrap_c.h>

#include <components/components_mesh_bootstrap.hpp>
#include <termin/entity/entity.hpp>
#include <termin/entity/unknown_component.hpp>
#include <termin/inspect/tc_kind_cpp_ext.hpp>
#include <termin/materials/surface_contract_registry.h>
#include <termin/render/builtin_passes.hpp>
#include <termin/render/components_bootstrap.hpp>
#include <termin/render_passes/bootstrap.hpp>
#include <tcbase/tc_log.h>

#include <tgfx/tgfx_material_handle.hpp>
#include <tgfx/tgfx_mesh_handle.hpp>

extern "C" {
#include <core/tc_entity_pool_registry.h>
#include <core/tc_scene_pool.h>
#include <core/tc_scene_render_mount.h>
#include <core/tc_scene_render_state.h>
#include <inspect/tc_inspect.h>
#include <inspect/tc_inspect_component_adapter.h>
#include <inspect/tc_inspect_init.h>
#include <inspect/tc_inspect_pass_adapter.h>
#include <inspect/tc_kind.h>
#include <render/tc_display_pool.h>
#include <render/tc_pass.h>
#include <render/tc_pipeline_pool.h>
#include <render/tc_pipeline_template_registry.h>
#include <resources/tc_skeleton_registry.h>
#include <termin_scene/internal/tc_scene_extension_registry.h>
#include <tgfx/resources/tc_material_registry.h>
#include <tgfx/resources/tc_mesh_registry.h>
#include <tgfx/resources/tc_shader_program_registry.h>
#include <tgfx/resources/tc_shader_registry.h>
#include <tgfx/resources/tc_texture_registry.h>
}

namespace {

bool g_runtime_initialized = false;
bool g_inspect_initialized = false;
bool g_kinds_registered = false;
bool g_scene_components_registered = false;
bool g_components_registered = false;
bool g_passes_registered = false;
bool g_extensions_registered = false;

void log_unavailable(const char* feature) {
    tc_log_error("[termin-bootstrap] render-only build does not provide %s", feature);
}

} // namespace

namespace termin::bootstrap {

void reset_python_bootstrap_state();

void register_runtime_kinds(const RuntimeKindOptions& options) {
    if (!g_kinds_registered) {
        if (options.mesh) tc::register_cpp_handle_kind<TcMesh>("tc_mesh");
        if (options.material) tc::register_cpp_handle_kind<TcMaterial>("tc_material");
        if (options.entity) tc::register_cpp_handle_kind<Entity>("entity");
        g_kinds_registered = true;
    }
    if (options.skeleton || options.animation || options.voxel_grid ||
            options.navmesh || options.ui_document) {
        log_unavailable("non-render runtime handle kinds");
    }
}

void register_scene_extensions(const SceneExtensionOptions& options) {
    if (options.render_mount) tc_scene_render_mount_extension_init();
    if (options.render_state) tc_scene_render_state_extension_init();
    if (options.collision_world) log_unavailable("collision scene extensions");
    g_extensions_registered = true;
}

void init_inspect_adapters() {
    if (g_inspect_initialized) return;
    tc_inspect_kind_core_init();
    tc_inspect_component_adapter_init();
    tc_inspect_pass_adapter_init();
    tc_inspect_python_adapter_init();
    g_inspect_initialized = true;
}

void register_builtin_pass_types() {
    if (g_passes_registered) return;
    register_builtin_render_pass_types();
    register_builtin_render_component_pass_types();
    register_builtin_render_passes();
    g_passes_registered = true;
}

void bootstrap_runtime() {
    bootstrap_runtime(RuntimeBootstrapProfile::Render);
}

void bootstrap_runtime(RuntimeBootstrapProfile profile) {
    if (profile == RuntimeBootstrapProfile::Full) {
        log_unavailable("the full runtime bootstrap profile");
        return;
    }
    tc_init();
    init_inspect_adapters();
    if (profile == RuntimeBootstrapProfile::Minimal) {
        RuntimeKindOptions kinds;
        kinds.mesh = false;
        kinds.material = false;
        kinds.skeleton = false;
        kinds.animation = false;
        kinds.voxel_grid = false;
        kinds.navmesh = false;
        kinds.ui_document = false;
        register_runtime_kinds(kinds);
        if (!g_scene_components_registered) {
            register_builtin_scene_component_types();
            g_scene_components_registered = true;
        }
        return;
    }
    RuntimeKindOptions kinds;
    kinds.skeleton = false;
    kinds.animation = false;
    kinds.voxel_grid = false;
    kinds.navmesh = false;
    kinds.ui_document = false;
    register_runtime_kinds(kinds);
    if (!g_components_registered) {
        if (!g_scene_components_registered) {
            register_builtin_scene_component_types();
            g_scene_components_registered = true;
        }
        register_builtin_mesh_component_types();
        register_builtin_render_component_types();
        g_components_registered = true;
    }
    register_builtin_pass_types();
    if (!g_extensions_registered) {
        SceneExtensionOptions extensions;
        extensions.collision_world = false;
        register_scene_extensions(extensions);
    }
}

void bootstrap_player() { bootstrap_runtime(RuntimeBootstrapProfile::Render); }
void bootstrap_editor() { log_unavailable("the editor bootstrap profile"); }

void shutdown_runtime() { tc_shutdown(); }

} // namespace termin::bootstrap

extern "C" {

void tc_init(void) {
    if (g_runtime_initialized) return;
    tc_mesh_init();
    tc_texture_init();
    tc_shader_init();
    tc_shader_program_init();
    tc_skeleton_init();
    tc_material_init();
    if (!tc_surface_contract_registry_register_builtins()) {
        tc_log_error("[termin-bootstrap] failed to register material surface contracts");
    }
    tc_pipeline_template_init();
    tc_pipeline_pool_init();
    tc_display_pool_init();
    tc_entity_pool_registry_init();
    tc_scene_pool_init();
    tc_scene_ext_registry_init();
    g_runtime_initialized = true;
}

void tc_bootstrap_runtime(void) {
    termin::bootstrap::bootstrap_runtime(
        termin::bootstrap::RuntimeBootstrapProfile::Render);
}

void tc_shutdown(void) {
    if (!g_runtime_initialized) return;
    tc_scene_pool_shutdown();
    tc_entity_pool_registry_shutdown();
    tc_display_pool_shutdown();
    tc_pipeline_pool_shutdown();
    tc_pipeline_template_shutdown();
    tc_material_shutdown();
    tc_skeleton_shutdown();
    tc_shader_program_shutdown();
    tc_shader_shutdown();
    tc_texture_shutdown();
    tc_mesh_shutdown();
    tc_component_registry_cleanup();
    tc_pass_registry_cleanup();
    tc_inspect_cleanup();
    tc_runtime_type_registry_clear();
    tc::reset_kind_registry_cpp();
    tc_kind_cleanup();
    tc_scene_ext_registry_shutdown();
    tc_intern_cleanup();
    g_runtime_initialized = false;
    g_inspect_initialized = false;
    g_kinds_registered = false;
    g_scene_components_registered = false;
    g_components_registered = false;
    g_passes_registered = false;
    g_extensions_registered = false;
    termin::bootstrap::reset_python_bootstrap_state();
}

} // extern "C"
