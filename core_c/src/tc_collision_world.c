// tc_collision_world.c - Collision world allocator registry
// Stores function pointers registered by entity_lib (C++ side)
#include "physics/tc_collision_world.h"
#include "core/tc_scene_extension.h"
#include <stdlib.h>
#include <tcbase/tc_log.h>
#include <stddef.h>

// Registered collision-world allocator functions (set by entity_lib)
static tc_collision_world_alloc_fn s_collision_world_alloc_fn = NULL;
static tc_collision_world_free_fn s_collision_world_free_fn = NULL;

typedef struct tc_collision_world_ext_instance {
    tc_collision_world* world;
} tc_collision_world_ext_instance;

static void* collision_world_ext_create(tc_scene_handle scene, void* type_userdata) {
    (void)scene;
    (void)type_userdata;

    tc_collision_world_ext_instance* inst =
        (tc_collision_world_ext_instance*)calloc(1, sizeof(tc_collision_world_ext_instance));
    if (!inst) {
        tc_log_error("[tc_collision_world] failed to allocate extension instance");
        return NULL;
    }

    if (s_collision_world_alloc_fn) {
        inst->world = tc_collision_world_new();
        if (!inst->world) {
            free(inst);
            return NULL;
        }
    }

    return inst;
}

static void collision_world_ext_destroy(void* ext, void* type_userdata) {
    (void)type_userdata;
    if (!ext) return;

    tc_collision_world_ext_instance* inst = (tc_collision_world_ext_instance*)ext;
    if (inst->world) {
        tc_collision_world_free(inst->world);
        inst->world = NULL;
    }
    free(inst);
}

void tc_collision_world_extension_init(void) {
    if (tc_scene_ext_is_registered(TC_SCENE_EXT_TYPE_COLLISION_WORLD)) return;

    tc_scene_ext_vtable vtable = {
        .create = collision_world_ext_create,
        .destroy = collision_world_ext_destroy,
    };

    if (!tc_scene_ext_register(
            TC_SCENE_EXT_TYPE_COLLISION_WORLD,
            "collision_world",
            "collision_world",
            &vtable,
            NULL
        )) {
        tc_log_error("[tc_collision_world] failed to register collision_world extension type");
        return;
    }
}

void tc_collision_world_set_allocator(
    tc_collision_world_alloc_fn alloc_fn,
    tc_collision_world_free_fn free_fn
) {
    s_collision_world_alloc_fn = alloc_fn;
    s_collision_world_free_fn = free_fn;
}

tc_collision_world* tc_collision_world_new(void) {
    if (!s_collision_world_alloc_fn) {
        tc_log(TC_LOG_WARN, "tc_collision_world_new: allocator not registered");
        return NULL;
    }
    return s_collision_world_alloc_fn();
}

void tc_collision_world_free(tc_collision_world* cw) {
    if (!s_collision_world_free_fn) {
        tc_log(TC_LOG_WARN, "tc_collision_world_free: deallocator not registered");
        return;
    }
    if (cw) {
        s_collision_world_free_fn(cw);
    }
}

tc_collision_world* tc_collision_world_get_scene(tc_scene_handle scene) {
    tc_collision_world_ext_instance* inst =
        (tc_collision_world_ext_instance*)tc_scene_ext_get(scene, TC_SCENE_EXT_TYPE_COLLISION_WORLD);
    return inst ? inst->world : NULL;
}

bool tc_collision_world_set_scene(tc_scene_handle scene, tc_collision_world* cw) {
    if (!tc_scene_ext_has(scene, TC_SCENE_EXT_TYPE_COLLISION_WORLD)) {
        if (!tc_scene_ext_attach(scene, TC_SCENE_EXT_TYPE_COLLISION_WORLD)) {
            return false;
        }
    }

    tc_collision_world_ext_instance* inst =
        (tc_collision_world_ext_instance*)tc_scene_ext_get(scene, TC_SCENE_EXT_TYPE_COLLISION_WORLD);
    if (!inst) {
        return false;
    }

    if (inst->world && inst->world != cw) {
        tc_collision_world_free(inst->world);
    }
    inst->world = cw;
    return true;
}
