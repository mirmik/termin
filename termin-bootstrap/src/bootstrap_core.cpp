#include <termin/bootstrap/bootstrap.hpp>
#include <termin/bootstrap/bootstrap_c.h>

#include <components/components_collision_bootstrap.hpp>
#include <components/components_kinematic_bootstrap.hpp>
#include <components/components_mesh_bootstrap.hpp>
#include <termin/entity/unknown_component.hpp>
#include <termin/foliage/components_bootstrap.hpp>
#include <termin/render/components_bootstrap.hpp>
#include <termin/render/builtin_passes.hpp>
#include <termin/render_passes/bootstrap.hpp>
#include <termin/render/skeleton_components_bootstrap.hpp>
#include <termin/entity/component.hpp>
#include <termin/entity/entity.hpp>
#include <termin/inspect/tc_kind_cpp_ext.hpp>
#include <termin/navmesh/tc_navmesh_handle.hpp>
#include <termin/prefab/prefab_instance_state.hpp>
#include <termin/skeleton/tc_skeleton_handle.hpp>
#include <termin/voxels/tc_voxel_grid_handle.hpp>
#include <tcbase/tc_string.h>
#include <tgfx/tgfx_material_handle.hpp>
#include <tgfx/tgfx_mesh_handle.hpp>

#ifdef TERMIN_BOOTSTRAP_HAS_ANIMATION
#include <termin/animation/tc_animation_handle.hpp>
#endif
#ifdef TERMIN_BOOTSTRAP_HAS_ANIMATION_COMPONENTS
#include <termin/animation/components_bootstrap.hpp>
#endif
#ifdef TERMIN_BOOTSTRAP_HAS_NAVMESH_COMPONENTS
#include <termin/navmesh/components_bootstrap.hpp>
#endif

extern "C" {
#include <core/tc_component.h>
#include <core/tc_entity_pool_registry.h>
#include <core/tc_scene_extension.h>
#include <core/tc_scene_pool.h>
#include <core/tc_scene_render_mount.h>
#include <core/tc_scene_render_state.h>
#include <inspect/tc_inspect_component_adapter.h>
#include <inspect/tc_inspect.h>
#include <inspect/tc_inspect_init.h>
#include <inspect/tc_kind.h>
#include <inspect/tc_inspect_pass_adapter.h>
#include <render/tc_pass.h>
#include <render/tc_pipeline_pool.h>
#include <resources/tc_skeleton_registry.h>
#include <termin_collision/termin_collision.h>
#include <tgfx/resources/tc_material_registry.h>
#include <tgfx/resources/tc_mesh_registry.h>
#include <tgfx/resources/tc_shader_registry.h>
#include <tgfx/resources/tc_texture_registry.h>
#ifdef TERMIN_BOOTSTRAP_HAS_ANIMATION
#include <resources/tc_animation_registry.h>
#endif
}

namespace {

bool g_c_runtime_initialized = false;

} // namespace

namespace termin::bootstrap {
void reset_python_bootstrap_state();

namespace {

struct BootstrapState {
    bool mesh_registered = false;
    bool material_registered = false;
    bool skeleton_registered = false;
    bool animation_registered = false;
    bool voxel_grid_registered = false;
    bool navmesh_registered = false;
    bool entity_registered = false;
    bool inspect_initialized = false;
    bool builtin_components_registered = false;
    bool builtin_passes_registered = false;
};

BootstrapState g_bootstrap_state;

void reset_bootstrap_state() {
    g_bootstrap_state = {};
}

template<typename H>
void register_once(const char* kind_name, bool& registered) {
    if (registered) {
        return;
    }
    tc::register_cpp_handle_kind<H>(kind_name);
    registered = true;
}

} // namespace
} // namespace termin::bootstrap

extern "C" {

void tc_init(void) {
    if (g_c_runtime_initialized) {
        return;
    }

    tc_mesh_init();
    tc_texture_init();
    tc_shader_init();
    tc_skeleton_init();
#ifdef TERMIN_BOOTSTRAP_HAS_ANIMATION
    tc_animation_init();
#endif
    tc_material_init();
    tc_entity_pool_registry_init();
    tc_scene_pool_init();
    tc_scene_ext_registry_init();
    g_c_runtime_initialized = true;
}

void tc_shutdown(void) {
    if (!g_c_runtime_initialized) {
        return;
    }

    tc_scene_pool_shutdown();
    // Scene shutdown unregisters and destroys scene-owned pools first.  The
    // registry then owns only standalone (or otherwise unmounted) pools.
    tc_entity_pool_registry_shutdown();
    tc_pipeline_pool_shutdown();
    tc_material_shutdown();
#ifdef TERMIN_BOOTSTRAP_HAS_ANIMATION
    tc_animation_shutdown();
#endif
    tc_skeleton_shutdown();
    tc_shader_shutdown();
    tc_texture_shutdown();
    tc_mesh_shutdown();
    tc_component_registry_cleanup();
    tc_pass_registry_cleanup();
    tc_inspect_cleanup();
    // Runtime type records own inspect/widget facets and keep their names,
    // owners and parents as interned strings.  They must not survive the
    // intern pool that backs those pointers.  Component and pass cleanup run
    // first so their facet destructors can still reach their native
    // registries; the remaining domain-neutral records are then released as
    // one shutdown boundary.
    tc_runtime_type_registry_clear();
    tc::reset_kind_registry_cpp();
    tc_kind_cleanup();
    tc_scene_ext_registry_shutdown();
    tc_intern_cleanup();

    g_c_runtime_initialized = false;
    termin::bootstrap::reset_bootstrap_state();
    termin::bootstrap::reset_python_bootstrap_state();
}

} // extern "C"

namespace termin::bootstrap {

void register_runtime_kinds(const RuntimeKindOptions& options) {
    if (options.mesh) {
        register_once<TcMesh>("tc_mesh", g_bootstrap_state.mesh_registered);
    }
    if (options.material) {
        register_once<TcMaterial>("tc_material", g_bootstrap_state.material_registered);
    }
    if (options.skeleton) {
        register_once<TcSkeleton>("tc_skeleton", g_bootstrap_state.skeleton_registered);
    }
    if (options.animation) {
#ifdef TERMIN_BOOTSTRAP_HAS_ANIMATION
        register_once<animation::TcAnimationClip>("tc_animation_clip", g_bootstrap_state.animation_registered);
#else
        (void)g_bootstrap_state.animation_registered;
#endif
    }
    if (options.voxel_grid) {
        register_once<voxels::TcVoxelGrid>("voxel_grid_handle", g_bootstrap_state.voxel_grid_registered);
    }
    if (options.navmesh) {
        register_once<TcNavMesh>("navmesh_handle", g_bootstrap_state.navmesh_registered);
    }
    if (options.entity) {
        register_once<Entity>("entity", g_bootstrap_state.entity_registered);
    }
}

void register_scene_extensions(const SceneExtensionOptions& options) {
    if (options.render_mount) {
        tc_scene_render_mount_extension_init();
    }
    if (options.render_state) {
        tc_scene_render_state_extension_init();
    }
    if (options.collision_world) {
        termin_collision_runtime_init();
    }
}

void init_inspect_adapters() {
    if (g_bootstrap_state.inspect_initialized) {
        return;
    }
    tc_inspect_kind_core_init();
    tc_inspect_component_adapter_init();
    register_component_base_inspect_fields();
    tc_inspect_pass_adapter_init();
    tc_inspect_python_adapter_init();
    g_bootstrap_state.inspect_initialized = true;
}

void register_builtin_component_types() {
    if (g_bootstrap_state.builtin_components_registered) {
        return;
    }

    register_builtin_scene_component_types();
    prefab::register_prefab_component_types();
    register_builtin_mesh_component_types();
    register_builtin_collision_component_types();
    register_builtin_kinematic_component_types();
    register_builtin_skeleton_component_types();
    register_builtin_render_component_types();
    register_builtin_foliage_component_types();
#ifdef TERMIN_BOOTSTRAP_HAS_NAVMESH_COMPONENTS
    register_builtin_navmesh_component_types();
#endif
#ifdef TERMIN_BOOTSTRAP_HAS_ANIMATION_COMPONENTS
    termin::animation::register_builtin_animation_component_types();
#endif
    g_bootstrap_state.builtin_components_registered = true;
}

void register_builtin_pass_types() {
    if (g_bootstrap_state.builtin_passes_registered) {
        return;
    }
    register_builtin_render_pass_types();
    register_builtin_render_component_pass_types();
    register_builtin_render_passes();
    g_bootstrap_state.builtin_passes_registered = true;
}

void bootstrap_runtime() {
    tc_init();
    init_inspect_adapters();
    register_runtime_kinds();
    register_builtin_component_types();
    register_builtin_pass_types();
    register_scene_extensions();
}

void bootstrap_player() {
    bootstrap_runtime();
    init_python_inspect_adapters();
    init_python_render_passes();
    init_python_kind_handlers();
    init_pointer_extractors();
    init_python_component_callbacks();
}

void bootstrap_editor() {
    bootstrap_player();
}

void shutdown_runtime() {
    tc_shutdown();
}

} // namespace termin::bootstrap
