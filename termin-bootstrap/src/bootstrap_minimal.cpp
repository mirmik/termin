#include <termin/bootstrap/bootstrap.hpp>
#include <termin/bootstrap/bootstrap_c.h>

#include <tcbase/tc_log.h>
#include <tcbase/tc_string.h>
#include <termin/entity/entity.hpp>
#include <termin/entity/unknown_component.hpp>
#include <termin/inspect/tc_kind_cpp_ext.hpp>

extern "C" {
#include <core/tc_entity_pool_registry.h>
#include <core/tc_scene_pool.h>
#include <inspect/tc_inspect.h>
#include <inspect/tc_inspect_component_adapter.h>
#include <inspect/tc_inspect_init.h>
#include <inspect/tc_kind.h>
#include <termin_scene/internal/tc_scene_extension_registry.h>
}

namespace {

    bool g_runtime_initialized = false;
    bool g_inspect_initialized = false;
    bool g_entity_kind_registered = false;
    bool g_scene_components_registered = false;

    void log_unavailable(const char* feature) {
        tc_log_error("[termin-bootstrap] minimal-only build does not provide %s", feature);
    }

} // namespace

namespace termin::bootstrap {

    void reset_python_bootstrap_state();

    void register_runtime_kinds(const RuntimeKindOptions& options) {
        if (options.entity && !g_entity_kind_registered) {
            tc::register_cpp_handle_kind<Entity>("entity");
            g_entity_kind_registered = true;
        }
        if (options.mesh || options.material || options.skeleton || options.animation || options.voxel_grid ||
            options.navmesh || options.ui_document) {
            log_unavailable("non-core runtime handle kinds");
        }
    }

    void register_scene_extensions(const SceneExtensionOptions& options) {
        if (options.render_mount || options.render_state || options.collision_world) {
            log_unavailable("render/collision scene extensions");
        }
    }

    void init_inspect_adapters() {
        if (g_inspect_initialized) {
            return;
        }
        tc_inspect_kind_core_init();
        tc_inspect_component_adapter_init();
        tc_inspect_python_adapter_init();
        g_inspect_initialized = true;
    }

    void register_builtin_pass_types() {
        log_unavailable("built-in render pass types");
    }

    void bootstrap_runtime() {
        bootstrap_runtime(RuntimeBootstrapProfile::Minimal);
    }

    void bootstrap_runtime(RuntimeBootstrapProfile profile) {
        if (profile == RuntimeBootstrapProfile::Full) {
            log_unavailable("the full runtime bootstrap profile");
            return;
        }
        tc_init();
        init_inspect_adapters();
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
    }

    void bootstrap_player() {
        log_unavailable("player bootstrap");
    }

    void bootstrap_editor() {
        log_unavailable("editor bootstrap");
    }

    void shutdown_runtime() {
        tc_shutdown();
    }

} // namespace termin::bootstrap

extern "C" {

void tc_init(void) {
    if (g_runtime_initialized) {
        return;
    }
    tc_entity_pool_registry_init();
    tc_scene_pool_init();
    tc_scene_ext_registry_init();
    g_runtime_initialized = true;
}

void tc_bootstrap_runtime(void) {
    termin::bootstrap::bootstrap_runtime(termin::bootstrap::RuntimeBootstrapProfile::Minimal);
}

void tc_shutdown(void) {
    if (!g_runtime_initialized) {
        return;
    }
    tc_scene_pool_shutdown();
    tc_entity_pool_registry_shutdown();
    tc_component_registry_cleanup();
    tc_inspect_cleanup();
    tc_runtime_type_registry_clear();
    tc::reset_kind_registry_cpp();
    tc_kind_cleanup();
    tc_scene_ext_registry_shutdown();
    tc_intern_cleanup();
    g_runtime_initialized = false;
    g_inspect_initialized = false;
    g_entity_kind_registered = false;
    g_scene_components_registered = false;
    termin::bootstrap::reset_python_bootstrap_state();
}

} // extern "C"
