/**
 * @file tc_collision_c_api.cpp
 * @brief C API bridge for CollisionWorld.
 */

#include "collision/collision_world.hpp"
#include "colliders/attached_collider.hpp"
#include "../../core_c/include/tc_collision.h"
#include <vector>

using namespace termin;
using namespace termin::collision;

// Static storage for manifolds returned to C
static std::vector<tc_contact_manifold> s_cached_manifolds;

extern "C" {

void tc_collision_world_update_all(void* cw) {
    if (!cw) return;
    auto* world = static_cast<CollisionWorld*>(cw);
    world->update_all();
}

size_t tc_collision_world_detect_contacts(void* cw, tc_contact_manifold** out_manifolds) {
    if (!cw || !out_manifolds) {
        if (out_manifolds) *out_manifolds = nullptr;
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

        // Entity IDs are not directly available from Collider pointers
        // For now, we leave them as invalid (0xFFFFFFFF)
        // A future enhancement could add user_data to Collider or use a lookup table
        cm.entity_a = TC_ENTITY_ID_INVALID;
        cm.entity_b = TC_ENTITY_ID_INVALID;

        // Normal
        cm.normal[0] = m.normal.x;
        cm.normal[1] = m.normal.y;
        cm.normal[2] = m.normal.z;

        // Contact points
        cm.point_count = static_cast<int>(m.point_count());
        for (int i = 0; i < cm.point_count && i < 4; ++i) {
            const auto& p = m.points[i];
            cm.points[i].position[0] = p.position.x;
            cm.points[i].position[1] = p.position.y;
            cm.points[i].position[2] = p.position.z;
            cm.points[i].penetration = p.penetration;
        }

        s_cached_manifolds.push_back(cm);
    }

    *out_manifolds = s_cached_manifolds.empty() ? nullptr : s_cached_manifolds.data();
    return s_cached_manifolds.size();
}

} // extern "C"
