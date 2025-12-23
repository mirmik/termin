#pragma once

#include "termin/geom/vec3.hpp"
#include "termin/colliders/collider.hpp"
#include <array>
#include <cstdint>

namespace termin {
namespace collision {

using colliders::Collider;

/// Unique identifier for a contact point (for persistent contacts)
struct ContactID {
    uint32_t feature_a = 0;  // Feature on collider A (vertex/edge/face)
    uint32_t feature_b = 0;  // Feature on collider B

    bool operator==(const ContactID& other) const {
        return feature_a == other.feature_a && feature_b == other.feature_b;
    }

    bool operator!=(const ContactID& other) const {
        return !(*this == other);
    }
};

/// Single contact point within a manifold
struct ContactPoint {
    Vec3 position;           // World space contact point
    Vec3 local_a;            // Local position on collider A
    Vec3 local_b;            // Local position on collider B
    double penetration = 0;  // Negative = penetrating, positive = separating

    ContactID id;            // For matching contacts between frames

    // Accumulated impulses for warm-starting (filled by solver)
    double normal_impulse = 0;
    double tangent1_impulse = 0;
    double tangent2_impulse = 0;
};

/// Contact manifold between two colliders
struct ContactManifold {
    static constexpr int MAX_POINTS = 4;

    Collider* collider_a = nullptr;
    Collider* collider_b = nullptr;

    Vec3 normal;  // Contact normal (from A to B)

    std::array<ContactPoint, MAX_POINTS> points;
    int point_count = 0;

    // User data for physics bodies
    void* body_a = nullptr;
    void* body_b = nullptr;

    // Add a contact point (returns false if manifold is full)
    bool add_point(const ContactPoint& point) {
        if (point_count >= MAX_POINTS) return false;
        points[point_count++] = point;
        return true;
    }

    // Clear all points
    void clear() {
        point_count = 0;
    }

    // Check if manifolds are for the same collider pair
    bool same_pair(const ContactManifold& other) const {
        return (collider_a == other.collider_a && collider_b == other.collider_b) ||
               (collider_a == other.collider_b && collider_b == other.collider_a);
    }

    // Generate a unique key for this collider pair
    uint64_t pair_key() const {
        auto a = reinterpret_cast<uintptr_t>(collider_a);
        auto b = reinterpret_cast<uintptr_t>(collider_b);
        if (a > b) std::swap(a, b);
        return (uint64_t(a) * 2654435761) ^ uint64_t(b);
    }
};

/// Result of a raycast query
struct RayHit {
    Collider* collider = nullptr;
    Vec3 point;           // Hit point in world space
    Vec3 normal;          // Surface normal at hit point
    double distance = 0;  // Distance from ray origin

    bool hit() const { return collider != nullptr; }
};

/// Pair of potentially colliding colliders (from broad phase)
struct ColliderPair {
    Collider* a = nullptr;
    Collider* b = nullptr;

    bool operator==(const ColliderPair& other) const {
        return (a == other.a && b == other.b) || (a == other.b && b == other.a);
    }
};

} // namespace collision
} // namespace termin
