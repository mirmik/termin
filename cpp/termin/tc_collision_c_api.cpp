/**
 * @file tc_collision_c_api.cpp
 * @brief C API implementation for CollisionWorld.
 *
 * This file implements the C API defined in tc_collision.h.
 * It's built as part of termin.dll (C++ library) because collision
 * detection requires the C++ CollisionWorld class.
 */

#include "collision/collision_world.hpp"
#include "colliders/attached_collider.hpp"
#include "../../core_c/include/tc_collision.h"
#include "../../core_c/include/tc_scene.h"
#include <vector>

using namespace termin;
using namespace termin::collision;

// Static storage for manifolds returned to C
static std::vector<tc_contact_manifold> s_cached_manifolds;
static size_t s_cached_manifold_count = 0;

// ============================================================================
// Internal helper functions
// ============================================================================

static size_t detect_and_cache_contacts(void* cw) {
    if (!cw) {
        s_cached_manifolds.clear();
        s_cached_manifold_count = 0;
        return 0;
    }

    auto* world = static_cast<CollisionWorld*>(cw);

    // Detect collisions
    auto manifolds = world->detect_contacts();

    // Convert to C structs
    s_cached_manifolds.clear();
    s_cached_manifolds.reserve(manifolds.size());

    for (const auto& m : manifolds) {
        tc_contact_manifold cm = {};

        // Get entity IDs from AttachedCollider if available
        if (auto* attached_a = dynamic_cast<colliders::AttachedCollider*>(m.collider_a)) {
            cm.entity_a = attached_a->owner_entity_id();
        } else {
            cm.entity_a = TC_ENTITY_ID_INVALID;
        }

        if (auto* attached_b = dynamic_cast<colliders::AttachedCollider*>(m.collider_b)) {
            cm.entity_b = attached_b->owner_entity_id();
        } else {
            cm.entity_b = TC_ENTITY_ID_INVALID;
        }

        // Normal
        cm.normal[0] = m.normal.x;
        cm.normal[1] = m.normal.y;
        cm.normal[2] = m.normal.z;

        // Contact points
        cm.point_count = m.point_count;
        for (int i = 0; i < cm.point_count && i < 4; ++i) {
            const auto& p = m.points[i];
            cm.points[i].position[0] = p.position.x;
            cm.points[i].position[1] = p.position.y;
            cm.points[i].position[2] = p.position.z;
            cm.points[i].penetration = p.penetration;
        }

        s_cached_manifolds.push_back(cm);
    }

    s_cached_manifold_count = s_cached_manifolds.size();
    return s_cached_manifold_count;
}

// ============================================================================
// C API Implementation (tc_collision.h)
// Note: Using explicit __declspec(dllexport) because TC_API is defined for
// termin_core.dll, but these functions are in termin.dll
// ============================================================================

#ifdef _WIN32
#define COLLISION_API __declspec(dllexport)
#else
#define COLLISION_API __attribute__((visibility("default")))
#endif

extern "C" {

COLLISION_API void tc_scene_collision_update(tc_scene_handle scene) {
    void* cw = tc_scene_get_collision_world(scene);
    if (!cw) return;

    auto* world = static_cast<CollisionWorld*>(cw);
    world->update_all();
}

COLLISION_API int tc_scene_has_collisions(tc_scene_handle scene) {
    void* cw = tc_scene_get_collision_world(scene);
    if (!cw) return 0;

    size_t count = detect_and_cache_contacts(cw);
    return count > 0 ? 1 : 0;
}

COLLISION_API size_t tc_scene_collision_count(tc_scene_handle scene) {
    (void)scene;  // The count is from the last detect call
    return s_cached_manifold_count;
}

COLLISION_API tc_contact_manifold* tc_scene_detect_collisions(tc_scene_handle scene, size_t* out_count) {
    if (out_count) *out_count = 0;

    void* cw = tc_scene_get_collision_world(scene);
    if (!cw) return nullptr;

    size_t count = detect_and_cache_contacts(cw);

    if (out_count) *out_count = count;
    return s_cached_manifolds.empty() ? nullptr : s_cached_manifolds.data();
}

COLLISION_API tc_contact_manifold* tc_scene_get_collision(tc_scene_handle scene, size_t index) {
    (void)scene;
    if (index >= s_cached_manifold_count) return nullptr;
    return &s_cached_manifolds[index];
}

} // extern "C"
