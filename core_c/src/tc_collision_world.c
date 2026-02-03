// tc_collision_world.c - Collision world allocator registry
// Stores function pointers registered by entity_lib (C++ side)
#include "../include/tc_collision_world.h"
#include "../include/tc_log.h"
#include <stddef.h>

// Registered allocator functions (set by entity_lib)
static tc_collision_world_alloc_fn g_alloc_fn = NULL;
static tc_collision_world_free_fn g_free_fn = NULL;

void tc_collision_world_set_allocator(
    tc_collision_world_alloc_fn alloc_fn,
    tc_collision_world_free_fn free_fn
) {
    g_alloc_fn = alloc_fn;
    g_free_fn = free_fn;
}

tc_collision_world* tc_collision_world_new(void) {
    if (!g_alloc_fn) {
        tc_log(TC_LOG_WARN, "tc_collision_world_new: allocator not registered");
        return NULL;
    }
    return g_alloc_fn();
}

void tc_collision_world_free(tc_collision_world* cw) {
    if (!g_free_fn) {
        tc_log(TC_LOG_WARN, "tc_collision_world_free: deallocator not registered");
        return;
    }
    if (cw) {
        g_free_fn(cw);
    }
}
