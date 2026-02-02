// collision_world_c.cpp - C API implementation for CollisionWorld
#include "collision_world_c.hpp"
#include "collision_world.hpp"
#include "termin/colliders/attached_collider.hpp"
#include <vector>

using termin::collision::CollisionWorld;
using termin::collision::ContactManifold;

// Static storage for collision results (valid until next detect_contacts call)
static std::vector<tc_contact_manifold> s_manifold_storage;

extern "C" {

CW_API void* tc_collision_world_create(void) {
    return new CollisionWorld();
}

CW_API void tc_collision_world_destroy(void* cw) {
    delete static_cast<CollisionWorld*>(cw);
}

CW_API int tc_collision_world_size(void* cw) {
    if (!cw) return 0;
    return static_cast<int>(static_cast<CollisionWorld*>(cw)->size());
}

CW_API void tc_collision_world_update_all(void* cw) {
    if (!cw) return;
    static_cast<CollisionWorld*>(cw)->update_all();
}

CW_API size_t tc_collision_world_detect_contacts(void* cw, tc_contact_manifold** out_manifolds) {
    if (out_manifolds) *out_manifolds = nullptr;
    if (!cw) return 0;

    auto* world = static_cast<CollisionWorld*>(cw);
    auto cpp_manifolds = world->detect_contacts();

    // Clear and populate C manifold storage
    s_manifold_storage.clear();
    s_manifold_storage.reserve(cpp_manifolds.size());

    for (const auto& cpp_m : cpp_manifolds) {
        tc_contact_manifold c_manifold = {};

        // Get entity IDs from attached colliders
        if (auto* attached_a = dynamic_cast<termin::colliders::AttachedCollider*>(cpp_m.collider_a)) {
            c_manifold.entity_a = attached_a->owner_entity_id();
        }
        if (auto* attached_b = dynamic_cast<termin::colliders::AttachedCollider*>(cpp_m.collider_b)) {
            c_manifold.entity_b = attached_b->owner_entity_id();
        }

        // Copy normal
        c_manifold.normal[0] = cpp_m.normal.x;
        c_manifold.normal[1] = cpp_m.normal.y;
        c_manifold.normal[2] = cpp_m.normal.z;

        // Copy contact points
        c_manifold.point_count = cpp_m.point_count;
        for (int i = 0; i < cpp_m.point_count && i < 4; ++i) {
            const auto& cpp_pt = cpp_m.points[i];
            c_manifold.points[i].position[0] = cpp_pt.position.x;
            c_manifold.points[i].position[1] = cpp_pt.position.y;
            c_manifold.points[i].position[2] = cpp_pt.position.z;
            c_manifold.points[i].penetration = cpp_pt.penetration;
        }

        s_manifold_storage.push_back(c_manifold);
    }

    if (out_manifolds && !s_manifold_storage.empty()) {
        *out_manifolds = s_manifold_storage.data();
    }

    return s_manifold_storage.size();
}

}
