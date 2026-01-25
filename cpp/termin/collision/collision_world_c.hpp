// collision_world_c.hpp - C API for CollisionWorld
#pragma once

#ifdef __cplusplus
extern "C" {
#endif

// Create a new CollisionWorld
void* tc_collision_world_create(void);

// Destroy a CollisionWorld
void tc_collision_world_destroy(void* cw);

// Get number of colliders in the world
int tc_collision_world_size(void* cw);

#ifdef __cplusplus
}
#endif
