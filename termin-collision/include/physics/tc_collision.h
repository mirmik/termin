#pragma once
/**
 * @file tc_collision.h
 * @brief C API for collision detection.
 *
 * Provides functions for collision detection using the CollisionWorld.
 */

#include "tc_types.h"
#include "core/tc_scene.h"
#include "termin_collision/termin_collision.h"

#ifdef __cplusplus
extern "C" {
#endif

// ============================================================================
// Collision World Operations (via scene)
// ============================================================================

typedef enum tc_collision_broad_phase_mode {
    TC_COLLISION_BROAD_PHASE_BVH = 0,
    TC_COLLISION_BROAD_PHASE_NAIVE = 1,
} tc_collision_broad_phase_mode;

/**
 * Update all collider positions in the collision world.
 * Call this after kinematic components have been updated.
 *
 * @param scene Scene handle containing the collision world
 */
TERMIN_COLLISION_API void tc_scene_collision_update(tc_scene_handle scene);

/**
 * Select pair generation strategy used by scene collision detection.
 *
 * @param scene Scene handle containing the collision world
 * @param mode One of tc_collision_broad_phase_mode values
 */
TERMIN_COLLISION_API void tc_scene_collision_set_broad_phase_mode(tc_scene_handle scene, int mode);

/**
 * Get current scene collision pair generation strategy.
 *
 * @param scene Scene handle containing the collision world
 * @return One of tc_collision_broad_phase_mode values, or BVH if scene/world is invalid
 */
TERMIN_COLLISION_API int tc_scene_collision_get_broad_phase_mode(tc_scene_handle scene);

/**
 * Check if there are any collisions in the scene.
 *
 * @param scene Scene handle
 * @return Non-zero if there are collisions, 0 otherwise
 */
TERMIN_COLLISION_API int tc_scene_has_collisions(tc_scene_handle scene);

/**
 * Get the number of collision pairs detected.
 *
 * @param scene Scene handle
 * @return Number of collision pairs (ContactManifolds)
 */
TERMIN_COLLISION_API size_t tc_scene_collision_count(tc_scene_handle scene);

// ============================================================================
// Contact Manifold Access
// ============================================================================

/**
 * Contact point data structure.
 */
typedef struct tc_contact_point {
    double position[3];      // Contact position in world space
    double penetration;      // Penetration depth (negative = penetrating)
} tc_contact_point;

/**
 * Contact manifold data - information about a collision pair.
 */
typedef struct tc_contact_manifold {
    tc_entity_id entity_a;   // First entity involved
    tc_entity_id entity_b;   // Second entity involved
    double normal[3];        // Contact normal (from A to B)
    int point_count;         // Number of contact points
    tc_contact_point points[4]; // Contact points (max 4)
} tc_contact_manifold;

/**
 * Detect all collisions and get manifolds.
 * The returned array is valid until the next call to this function.
 *
 * @param scene Scene handle
 * @param out_count Output: number of manifolds
 * @return Pointer to array of manifolds (internal storage, do not free)
 */
TERMIN_COLLISION_API tc_contact_manifold* tc_scene_detect_collisions(tc_scene_handle scene, size_t* out_count);

/**
 * Get collision manifold at index.
 *
 * @param scene Scene handle
 * @param index Manifold index (0 to count-1)
 * @return Pointer to manifold or NULL if invalid index
 */
TERMIN_COLLISION_API tc_contact_manifold* tc_scene_get_collision(tc_scene_handle scene, size_t index);

#ifdef __cplusplus
}
#endif
