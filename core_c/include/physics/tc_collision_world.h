// tc_collision_world.h - C API for collision world
// Implementation in cpp/termin/collision/collision_world_c.cpp
#ifndef TC_COLLISION_WORLD_H
#define TC_COLLISION_WORLD_H

#include "tc_types.h"

#ifdef __cplusplus
extern "C" {
#endif

// Opaque handle to collision world (C++ CollisionWorld*)
typedef void tc_collision_world;

// Function pointer types for collision world allocation
typedef tc_collision_world* (*tc_collision_world_alloc_fn)(void);
typedef void (*tc_collision_world_free_fn)(tc_collision_world* cw);

// Register collision world allocator/deallocator functions
// Called by entity_lib during initialization
TC_API void tc_collision_world_set_allocator(
    tc_collision_world_alloc_fn alloc_fn,
    tc_collision_world_free_fn free_fn
);

// Internal functions used by tc_scene.c (use registered allocators)
TC_API tc_collision_world* tc_collision_world_new(void);
TC_API void tc_collision_world_free(tc_collision_world* cw);

#ifdef __cplusplus
}
#endif

#endif // TC_COLLISION_WORLD_H
