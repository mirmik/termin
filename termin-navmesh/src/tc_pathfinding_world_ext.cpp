#include <termin/navmesh/tc_pathfinding_world.h>

#include <termin/navmesh/pathfinding_world.hpp>

#include "core/tc_scene_extension.h"

#include <new>

#include <tcbase/tc_log.h>

namespace {

void* pathfinding_world_ext_create(tc_scene_handle scene, void* type_userdata) {
    (void)type_userdata;

    auto* world = new (std::nothrow) termin::PathfindingWorld();
    if (!world) {
        tc_log_error("[tc_pathfinding_world] failed to allocate PathfindingWorld");
        return nullptr;
    }

    world->set_scene(scene);
    world->rebuild_from_scene();
    return world;
}

void pathfinding_world_ext_destroy(void* ext, void* type_userdata) {
    (void)type_userdata;
    delete reinterpret_cast<termin::PathfindingWorld*>(ext);
}

} // namespace

extern "C" void tc_pathfinding_world_extension_init(void) {
    if (tc_scene_ext_is_registered(TC_SCENE_EXT_TYPE_PATHFINDING_WORLD)) {
        return;
    }

    tc_scene_ext_vtable vtable{};
    vtable.create = pathfinding_world_ext_create;
    vtable.destroy = pathfinding_world_ext_destroy;

    if (!tc_scene_ext_register(
            TC_SCENE_EXT_TYPE_PATHFINDING_WORLD,
            "pathfinding_world",
            "pathfinding_world",
            &vtable,
            nullptr)) {
        tc_log_error("[tc_pathfinding_world] failed to register pathfinding_world extension type");
    }
}

extern "C" tc_pathfinding_world* tc_pathfinding_world_get_scene(tc_scene_handle scene) {
    return reinterpret_cast<tc_pathfinding_world*>(
        tc_scene_ext_get(scene, TC_SCENE_EXT_TYPE_PATHFINDING_WORLD));
}

extern "C" tc_pathfinding_world* tc_pathfinding_world_ensure_scene(tc_scene_handle scene) {
    if (!tc_scene_handle_valid(scene)) {
        tc_log_warn("[tc_pathfinding_world] cannot ensure extension: scene handle is invalid");
        return nullptr;
    }

    if (!tc_scene_ext_has(scene, TC_SCENE_EXT_TYPE_PATHFINDING_WORLD)) {
        if (!tc_scene_ext_attach(scene, TC_SCENE_EXT_TYPE_PATHFINDING_WORLD)) {
            tc_log_error("[tc_pathfinding_world] failed to attach pathfinding_world extension");
            return nullptr;
        }
    }

    return tc_pathfinding_world_get_scene(scene);
}
