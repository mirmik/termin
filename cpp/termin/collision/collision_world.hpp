#pragma once

/**
 * @file collision_world.hpp
 * @brief Main collision detection world.
 *
 * Provides unified collision detection for all physics engines.
 * Uses BVH for broad-phase and the existing collider algorithms for narrow-phase.
 */

#include "bvh.hpp"
#include "contact_manifold.hpp"
#include "termin/colliders/colliders.hpp"
#include <vector>
#include <unordered_set>

namespace termin {
namespace collision {

using colliders::Collider;

/**
 * Collision world manages colliders and performs collision detection.
 */
class CollisionWorld {
public:
    CollisionWorld() = default;

    // ==================== Collider management ====================

    /**
     * Add a collider to the world.
     */
    void add(Collider* collider) {
        if (!collider) return;
        if (colliders_.count(collider)) return;

        colliders_.insert(collider);
        bvh_.insert(collider, collider->aabb());
    }

    /**
     * Remove a collider from the world.
     */
    void remove(Collider* collider) {
        if (!collider) return;
        if (!colliders_.count(collider)) return;

        bvh_.remove(collider);
        colliders_.erase(collider);
    }

    /**
     * Update a collider's position in the BVH.
     * Call this after the collider's pose changes.
     */
    void update_pose(Collider* collider) {
        if (!collider) return;
        if (!colliders_.count(collider)) return;

        bvh_.update(collider, collider->aabb());
    }

    /**
     * Update all colliders in the BVH.
     * Call this once per frame before detect_contacts or raycast.
     */
    void update_all() {
        for (auto* collider : colliders_) {
            bvh_.update(collider, collider->aabb());
        }
    }

    /**
     * Check if a collider is in the world.
     */
    bool contains(Collider* collider) const {
        return colliders_.count(collider) > 0;
    }

    /**
     * Get the number of colliders.
     */
    size_t size() const {
        return colliders_.size();
    }

    // ==================== Collision detection ====================

    /**
     * Detect all contacts between colliders.
     * Performs broad-phase (BVH) then narrow-phase (collider algorithms).
     */
    std::vector<ContactManifold> detect_contacts() {
        std::vector<ContactManifold> manifolds;

        // Get potentially overlapping pairs from BVH
        bvh_.query_all_pairs([&](Collider* a, Collider* b) {
            // Narrow-phase: compute actual contact
            ColliderHit hit = a->closest_to_collider(*b);

            if (hit.colliding()) {
                ContactManifold manifold;
                manifold.collider_a = a;
                manifold.collider_b = b;
                manifold.normal = hit.normal;

                ContactPoint point;
                point.position = (hit.point_on_a + hit.point_on_b) * 0.5;
                point.local_a = hit.point_on_a;
                point.local_b = hit.point_on_b;
                point.penetration = hit.distance;  // negative = penetrating

                manifold.add_point(point);
                manifolds.push_back(manifold);
            }
        });

        return manifolds;
    }

    /**
     * Query colliders overlapping with an AABB.
     */
    std::vector<Collider*> query_aabb(const AABB& aabb) const {
        std::vector<Collider*> result;
        bvh_.query_aabb(aabb, [&](Collider* c) {
            result.push_back(c);
        });
        return result;
    }

    /**
     * Raycast against all colliders.
     * Returns all hits sorted by distance.
     */
    std::vector<RayHit> raycast(const Ray3& ray) const {
        std::vector<RayHit> hits;

        // Use BVH to find candidate colliders
        bvh_.query_ray(ray, [&](Collider* collider, double /*t_min*/, double /*t_max*/) {
            colliders::RayHit collider_hit = collider->closest_to_ray(ray);

            if (collider_hit.hit()) {
                RayHit hit;
                hit.collider = collider;
                hit.point = collider_hit.point_on_ray;

                // Compute normal at hit point
                Vec3 center = collider->center();
                hit.normal = (hit.point - center).normalized();

                hit.distance = (hit.point - ray.origin).norm();
                hits.push_back(hit);
            }
        });

        // Sort by distance
        std::sort(hits.begin(), hits.end(), [](const RayHit& a, const RayHit& b) {
            return a.distance < b.distance;
        });

        return hits;
    }

    /**
     * Raycast and return only the closest hit.
     */
    RayHit raycast_closest(const Ray3& ray) const {
        auto hits = raycast(ray);
        if (hits.empty()) {
            return RayHit{};
        }
        return hits[0];
    }

    // ==================== Accessors ====================

    const BVH& bvh() const { return bvh_; }

private:
    BVH bvh_;
    std::unordered_set<Collider*> colliders_;
};

} // namespace collision
} // namespace termin
