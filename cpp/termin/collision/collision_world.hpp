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

                // For box-box collisions, generate multiple contact points
                if (a->type() == colliders::ColliderType::Box &&
                    b->type() == colliders::ColliderType::Box) {
                    generate_box_box_contacts(a, b, hit, manifold);
                } else {
                    // Single contact point for other types
                    ContactPoint point;
                    point.position = (hit.point_on_a + hit.point_on_b) * 0.5;
                    point.local_a = hit.point_on_a;
                    point.local_b = hit.point_on_b;
                    point.penetration = hit.distance;  // negative = penetrating
                    manifold.add_point(point);
                }

                manifolds.push_back(manifold);
            }
        });

        return manifolds;
    }

private:
    /**
     * Generate multiple contact points for box-box collision.
     * Finds all vertices of box B that penetrate box A.
     */
    void generate_box_box_contacts(Collider* a, Collider* b,
                                   const ColliderHit& hit,
                                   ContactManifold& manifold) {
        // Get box pointers - may be AttachedCollider
        const colliders::BoxCollider* box_a = nullptr;
        const colliders::BoxCollider* box_b = nullptr;
        GeneralPose3 transform_a, transform_b;

        // Unwrap AttachedCollider if needed
        if (auto* attached_a = dynamic_cast<colliders::AttachedCollider*>(a)) {
            box_a = dynamic_cast<const colliders::BoxCollider*>(attached_a->collider());
            transform_a = attached_a->world_transform();
        } else {
            box_a = dynamic_cast<const colliders::BoxCollider*>(a);
            if (box_a) transform_a = box_a->transform;
        }

        if (auto* attached_b = dynamic_cast<colliders::AttachedCollider*>(b)) {
            box_b = dynamic_cast<const colliders::BoxCollider*>(attached_b->collider());
            transform_b = attached_b->world_transform();
        } else {
            box_b = dynamic_cast<const colliders::BoxCollider*>(b);
            if (box_b) transform_b = box_b->transform;
        }

        if (!box_a || !box_b) {
            // Fallback to single point
            ContactPoint point;
            point.position = (hit.point_on_a + hit.point_on_b) * 0.5;
            point.local_a = hit.point_on_a;
            point.local_b = hit.point_on_b;
            point.penetration = hit.distance;
            manifold.add_point(point);
            return;
        }

        // Create world-space boxes
        colliders::BoxCollider world_box_a(box_a->half_size, transform_a);
        colliders::BoxCollider world_box_b(box_b->half_size, transform_b);

        Vec3 center_a = world_box_a.center();
        auto axes_a = world_box_a.get_axes_world();
        Vec3 half_a = world_box_a.effective_half_size();

        // Check corners of B against A
        auto corners_b = world_box_b.get_corners_world();
        int points_added = 0;

        for (const auto& corner : corners_b) {
            // Check if corner is inside box A
            Vec3 rel = corner - center_a;
            double proj[3] = {
                std::abs(rel.dot(axes_a[0])),
                std::abs(rel.dot(axes_a[1])),
                std::abs(rel.dot(axes_a[2]))
            };

            double half_ext[3] = {half_a.x, half_a.y, half_a.z};
            bool inside = proj[0] <= half_ext[0] &&
                          proj[1] <= half_ext[1] &&
                          proj[2] <= half_ext[2];

            if (inside) {
                // Corner is penetrating - add contact
                ContactPoint point;
                point.position = corner;
                point.local_b = corner;
                // Project corner onto A's surface along the normal
                point.local_a = corner + manifold.normal * (-hit.distance);

                // Compute penetration depth for this corner
                double min_pen = std::numeric_limits<double>::infinity();
                for (int i = 0; i < 3; ++i) {
                    double pen = half_ext[i] - proj[i];
                    if (pen < min_pen) min_pen = pen;
                }
                point.penetration = -min_pen;  // negative = penetrating

                if (manifold.add_point(point)) {
                    points_added++;
                }

                if (points_added >= ContactManifold::MAX_POINTS) break;
            }
        }

        // If no corners of B are in A, try corners of A in B
        if (points_added == 0) {
            Vec3 center_b = world_box_b.center();
            auto axes_b = world_box_b.get_axes_world();
            Vec3 half_b = world_box_b.effective_half_size();

            auto corners_a = world_box_a.get_corners_world();

            for (const auto& corner : corners_a) {
                Vec3 rel = corner - center_b;
                double proj[3] = {
                    std::abs(rel.dot(axes_b[0])),
                    std::abs(rel.dot(axes_b[1])),
                    std::abs(rel.dot(axes_b[2]))
                };

                double half_ext[3] = {half_b.x, half_b.y, half_b.z};
                bool inside = proj[0] <= half_ext[0] &&
                              proj[1] <= half_ext[1] &&
                              proj[2] <= half_ext[2];

                if (inside) {
                    ContactPoint point;
                    point.position = corner;
                    point.local_a = corner;
                    point.local_b = corner - manifold.normal * (-hit.distance);

                    double min_pen = std::numeric_limits<double>::infinity();
                    for (int i = 0; i < 3; ++i) {
                        double pen = half_ext[i] - proj[i];
                        if (pen < min_pen) min_pen = pen;
                    }
                    point.penetration = -min_pen;

                    if (manifold.add_point(point)) {
                        points_added++;
                    }

                    if (points_added >= ContactManifold::MAX_POINTS) break;
                }
            }
        }

        // Fallback if still no contacts (edge-edge case)
        if (points_added == 0) {
            ContactPoint point;
            point.position = (hit.point_on_a + hit.point_on_b) * 0.5;
            point.local_a = hit.point_on_a;
            point.local_b = hit.point_on_b;
            point.penetration = hit.distance;
            manifold.add_point(point);
        }
    }

public:

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
