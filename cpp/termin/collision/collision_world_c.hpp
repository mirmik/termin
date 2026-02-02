// collision_world_c.hpp - C API for CollisionWorld
#pragma once

#include "tc_collision.h"  // For tc_contact_manifold

// Export macro for entity_lib.dll
#ifdef _WIN32
#define CW_API __declspec(dllexport)
#else
#define CW_API __attribute__((visibility("default")))
#endif

#ifdef __cplusplus
extern "C" {
#endif

// Create a new CollisionWorld
CW_API void* tc_collision_world_create(void);

// Destroy a CollisionWorld
CW_API void tc_collision_world_destroy(void* cw);

// Get number of colliders in the world
CW_API int tc_collision_world_size(void* cw);

// Update all collider poses in the collision world
CW_API void tc_collision_world_update_all(void* cw);

// Detect contacts and return manifolds
// Returns the number of manifolds detected
// out_manifolds receives a pointer to internal storage (valid until next call)
CW_API size_t tc_collision_world_detect_contacts(void* cw, tc_contact_manifold** out_manifolds);

#ifdef __cplusplus
}
#endif
