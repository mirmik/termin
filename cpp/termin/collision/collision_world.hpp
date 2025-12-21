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
#include <algorithm>

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
        if (contains(collider)) return;

        colliders_.push_back(collider);
        bvh_.insert(collider, collider->aabb());
    }

    /**
     * Remove a collider from the world.
     */
    void remove(Collider* collider) {
        if (!collider) return;

        auto it = std::find(colliders_.begin(), colliders_.end(), collider);
        if (it == colliders_.end()) return;

        bvh_.remove(collider);
        colliders_.erase(it);
    }

    /**
     * Update a collider's position in the BVH.
     * Call this after the collider's pose changes.
     */
    void update_pose(Collider* collider) {
        if (!collider) return;
        if (!contains(collider)) return;

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
        return std::find(colliders_.begin(), colliders_.end(), collider) != colliders_.end();
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
    // ==================== Box-Box Clipping ====================

    struct ClipVertex {
        Vec3 position;
    };

    struct ClipPlane {
        Vec3 normal;
        double distance;  // plane equation: normal.dot(p) + distance = 0

        double signed_distance(const Vec3& p) const {
            return normal.dot(p) + distance;
        }
    };

    /**
     * Get face vertices in CCW order (looking at face from outside).
     * face_index: 0=+X, 1=-X, 2=+Y, 3=-Y, 4=+Z, 5=-Z
     */
    static std::array<Vec3, 4> get_face_vertices(
        const Vec3& center,
        const std::array<Vec3, 3>& axes,
        const Vec3& half_size,
        int face_index)
    {
        std::array<Vec3, 4> verts;
        double hx = half_size.x, hy = half_size.y, hz = half_size.z;
        Vec3 ax = axes[0], ay = axes[1], az = axes[2];

        switch (face_index) {
            case 0: // +X face
                verts[0] = center + ax * hx - ay * hy - az * hz;
                verts[1] = center + ax * hx + ay * hy - az * hz;
                verts[2] = center + ax * hx + ay * hy + az * hz;
                verts[3] = center + ax * hx - ay * hy + az * hz;
                break;
            case 1: // -X face
                verts[0] = center - ax * hx + ay * hy - az * hz;
                verts[1] = center - ax * hx - ay * hy - az * hz;
                verts[2] = center - ax * hx - ay * hy + az * hz;
                verts[3] = center - ax * hx + ay * hy + az * hz;
                break;
            case 2: // +Y face
                verts[0] = center + ax * hx + ay * hy - az * hz;
                verts[1] = center - ax * hx + ay * hy - az * hz;
                verts[2] = center - ax * hx + ay * hy + az * hz;
                verts[3] = center + ax * hx + ay * hy + az * hz;
                break;
            case 3: // -Y face
                verts[0] = center - ax * hx - ay * hy - az * hz;
                verts[1] = center + ax * hx - ay * hy - az * hz;
                verts[2] = center + ax * hx - ay * hy + az * hz;
                verts[3] = center - ax * hx - ay * hy + az * hz;
                break;
            case 4: // +Z face
                verts[0] = center - ax * hx - ay * hy + az * hz;
                verts[1] = center + ax * hx - ay * hy + az * hz;
                verts[2] = center + ax * hx + ay * hy + az * hz;
                verts[3] = center - ax * hx + ay * hy + az * hz;
                break;
            case 5: // -Z face
                verts[0] = center - ax * hx + ay * hy - az * hz;
                verts[1] = center + ax * hx + ay * hy - az * hz;
                verts[2] = center + ax * hx - ay * hy - az * hz;
                verts[3] = center - ax * hx - ay * hy - az * hz;
                break;
        }
        return verts;
    }

    /**
     * Get face normal.
     */
    static Vec3 get_face_normal(const std::array<Vec3, 3>& axes, int face_index) {
        switch (face_index) {
            case 0: return axes[0];
            case 1: return axes[0] * (-1.0);
            case 2: return axes[1];
            case 3: return axes[1] * (-1.0);
            case 4: return axes[2];
            case 5: return axes[2] * (-1.0);
        }
        return Vec3(0, 0, 1);
    }

    /**
     * Find face most parallel to given direction.
     */
    static int find_reference_face(const std::array<Vec3, 3>& axes, const Vec3& direction) {
        int best_face = 0;
        double best_dot = -std::numeric_limits<double>::infinity();

        for (int i = 0; i < 6; ++i) {
            Vec3 normal = get_face_normal(axes, i);
            double d = normal.dot(direction);
            if (d > best_dot) {
                best_dot = d;
                best_face = i;
            }
        }
        return best_face;
    }

    /**
     * Find face most antiparallel to given direction.
     */
    static int find_incident_face(const std::array<Vec3, 3>& axes, const Vec3& direction) {
        int best_face = 0;
        double best_dot = std::numeric_limits<double>::infinity();

        for (int i = 0; i < 6; ++i) {
            Vec3 normal = get_face_normal(axes, i);
            double d = normal.dot(direction);
            if (d < best_dot) {
                best_dot = d;
                best_face = i;
            }
        }
        return best_face;
    }

    /**
     * Build clip planes from face edges (planes pointing inward).
     */
    static std::array<ClipPlane, 4> build_clip_planes(
        const std::array<Vec3, 4>& face_verts,
        const Vec3& face_normal)
    {
        std::array<ClipPlane, 4> planes;

        for (int i = 0; i < 4; ++i) {
            Vec3 v0 = face_verts[i];
            Vec3 v1 = face_verts[(i + 1) % 4];
            Vec3 edge = v1 - v0;

            // Plane normal points inward (into the face)
            // edge × face_normal gives inward direction with CW vertex winding
            Vec3 plane_normal = edge.cross(face_normal).normalized();

            planes[i].normal = plane_normal;
            planes[i].distance = -plane_normal.dot(v0);
        }
        return planes;
    }

    /**
     * Compute intersection point of edge (a, b) with plane.
     */
    static Vec3 intersect_edge_plane(const Vec3& a, const Vec3& b, const ClipPlane& plane) {
        double da = plane.signed_distance(a);
        double db = plane.signed_distance(b);
        double t = da / (da - db);
        return a + (b - a) * t;
    }

    /**
     * Sutherland-Hodgman polygon clipping.
     * Clips subject polygon against all clip planes.
     */
    static std::vector<Vec3> sutherland_hodgman_clip(
        const std::array<Vec3, 4>& subject,
        const std::array<ClipPlane, 4>& clip_planes)
    {
        std::vector<Vec3> output(subject.begin(), subject.end());

        for (const auto& plane : clip_planes) {
            if (output.empty()) break;

            std::vector<Vec3> input = std::move(output);
            output.clear();

            for (size_t i = 0; i < input.size(); ++i) {
                const Vec3& a = input[i];
                const Vec3& b = input[(i + 1) % input.size()];

                double da = plane.signed_distance(a);
                double db = plane.signed_distance(b);

                bool a_inside = da <= 0;
                bool b_inside = db <= 0;

                if (a_inside && b_inside) {
                    // Both inside - add B
                    output.push_back(b);
                } else if (a_inside && !b_inside) {
                    // A inside, B outside - add intersection
                    output.push_back(intersect_edge_plane(a, b, plane));
                } else if (!a_inside && b_inside) {
                    // A outside, B inside - add intersection and B
                    output.push_back(intersect_edge_plane(a, b, plane));
                    output.push_back(b);
                }
                // Both outside - add nothing
            }
        }

        return output;
    }

    /**
     * Generate multiple contact points for box-box collision using Sutherland-Hodgman clipping.
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
        Vec3 center_b = world_box_b.center();
        auto axes_a = world_box_a.get_axes_world();
        auto axes_b = world_box_b.get_axes_world();
        Vec3 half_a = world_box_a.effective_half_size();
        Vec3 half_b = world_box_b.effective_half_size();

        // Contact normal points from A to B
        Vec3 normal = hit.normal;

        // Find reference face on A (most parallel to normal)
        int ref_face_idx = find_reference_face(axes_a, normal);
        Vec3 ref_normal = get_face_normal(axes_a, ref_face_idx);

        // Find incident face on B (most antiparallel to reference normal)
        int inc_face_idx = find_incident_face(axes_b, ref_normal);

        // Get face vertices
        auto ref_verts = get_face_vertices(center_a, axes_a, half_a, ref_face_idx);
        auto inc_verts = get_face_vertices(center_b, axes_b, half_b, inc_face_idx);

        // Build clip planes from reference face edges
        auto clip_planes = build_clip_planes(ref_verts, ref_normal);

        // Clip incident face against reference face edges
        auto clipped = sutherland_hodgman_clip(inc_verts, clip_planes);

        // Reference plane for depth calculation
        ClipPlane ref_plane;
        ref_plane.normal = ref_normal;
        ref_plane.distance = -ref_normal.dot(ref_verts[0]);

        // Add contact points for vertices below reference plane
        int points_added = 0;
        for (const auto& p : clipped) {
            double depth = ref_plane.signed_distance(p);

            if (depth < 0) {  // Below reference plane = penetrating
                ContactPoint cp;
                cp.position = p;
                cp.local_b = p;
                cp.local_a = p - ref_normal * depth;  // Project onto reference plane
                cp.penetration = depth;  // negative = penetrating

                if (manifold.add_point(cp)) {
                    points_added++;
                }

                if (points_added >= ContactManifold::MAX_POINTS) break;
            }
        }

        // Fallback if no contacts found
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
    std::vector<Collider*> colliders_;
};

} // namespace collision
} // namespace termin
