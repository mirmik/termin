#include <termin/bootstrap/bootstrap.hpp>

#include <termin/entity/component.hpp>
#include <termin/entity/entity.hpp>
#include <termin/inspect/tc_kind_cpp_ext.hpp>
#include <termin/navmesh/tc_navmesh_handle.hpp>
#include <termin/skeleton/tc_skeleton_handle.hpp>
#include <termin/voxels/tc_voxel_grid_handle.hpp>
#include <tgfx/tgfx_material_handle.hpp>
#include <tgfx/tgfx_mesh_handle.hpp>

#ifdef TERMIN_BOOTSTRAP_HAS_ANIMATION
#include <termin/animation/tc_animation_handle.hpp>
#endif

extern "C" {
#include <core/tc_scene_render_mount.h>
#include <core/tc_scene_render_state.h>
#include <inspect/tc_inspect_component_adapter.h>
#include <inspect/tc_inspect_init.h>
#include <inspect/tc_inspect_pass_adapter.h>
#include <termin_collision/termin_collision.h>
}

namespace termin::bootstrap {
namespace {

template<typename H>
void register_once(const char* kind_name, bool& registered) {
    if (registered) {
        return;
    }
    tc::register_cpp_handle_kind<H>(kind_name);
    registered = true;
}

} // namespace

void register_runtime_kinds(const RuntimeKindOptions& options) {
    static bool mesh_registered = false;
    static bool material_registered = false;
    static bool skeleton_registered = false;
    static bool animation_registered = false;
    static bool voxel_grid_registered = false;
    static bool navmesh_registered = false;
    static bool entity_registered = false;

    if (options.mesh) {
        register_once<TcMesh>("tc_mesh", mesh_registered);
    }
    if (options.material) {
        register_once<TcMaterial>("tc_material", material_registered);
    }
    if (options.skeleton) {
        register_once<TcSkeleton>("tc_skeleton", skeleton_registered);
    }
    if (options.animation) {
#ifdef TERMIN_BOOTSTRAP_HAS_ANIMATION
        register_once<animation::TcAnimationClip>("tc_animation_clip", animation_registered);
#else
        (void)animation_registered;
#endif
    }
    if (options.voxel_grid) {
        register_once<voxels::TcVoxelGrid>("voxel_grid_handle", voxel_grid_registered);
    }
    if (options.navmesh) {
        register_once<TcNavMesh>("navmesh_handle", navmesh_registered);
    }
    if (options.entity) {
        register_once<Entity>("entity", entity_registered);
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
    static bool initialized = false;
    if (initialized) {
        return;
    }
    tc_inspect_kind_core_init();
    tc_inspect_component_adapter_init();
    register_component_base_inspect_fields();
    tc_inspect_pass_adapter_init();
    tc_inspect_python_adapter_init();
    initialized = true;
}

void bootstrap_runtime() {
    init_inspect_adapters();
    register_runtime_kinds();
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

} // namespace termin::bootstrap
