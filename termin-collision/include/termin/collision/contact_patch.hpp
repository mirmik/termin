#pragma once

#include "termin/colliders/collider.hpp"
#include "termin_collision/termin_collision.h"

#include <cstddef>
#include <cstdint>
#include <limits>
#include <span>
#include <vector>

namespace termin::collision
{

    using colliders::Collider;

    struct ContactFeaturePair
    {
        static constexpr uint32_t INVALID_FEATURE =
            std::numeric_limits<uint32_t>::max();

        uint32_t feature_a = INVALID_FEATURE;
        uint32_t feature_b = INVALID_FEATURE;

        bool operator==(const ContactFeaturePair&) const = default;
    };

    /**
     * Solver-neutral geometric contact candidate.
     *
     * All points are expressed in world coordinates. normal_world belongs to
     * the containing ContactPatch and points from collider A towards collider
     * B. signed_gap is negative for penetration and satisfies
     * dot(point_on_b_world - point_on_a_world, normal_world) == signed_gap.
     */
    struct ContactCandidate
    {
        Vec3 point_on_a_world = Vec3::zero();
        Vec3 point_on_b_world = Vec3::zero();
        double signed_gap = 0.0;
        ContactFeaturePair features;

        Vec3 representative_point_world() const
        {
            return (point_on_a_world + point_on_b_world) * 0.5;
        }
    };

    struct ContactPatch
    {
        Collider* collider_a = nullptr;
        Collider* collider_b = nullptr;
        Vec3 normal_world = Vec3::zero();
        std::vector<ContactCandidate> points;

        bool same_pair(const ContactPatch& other) const;
        uint64_t pair_key() const;
    };

    struct ContactPatchReductionConfig
    {
        std::size_t max_points = 4;
        double duplicate_tolerance = 1e-9;
        double metric_tolerance = 1e-12;
    };

    struct RayHit
    {
        Collider* collider = nullptr;
        Vec3 point = Vec3::zero();
        Vec3 normal = Vec3::zero();
        double distance = 0.0;

        bool hit() const
        {
            return collider != nullptr;
        }
    };

    struct ColliderPair
    {
        Collider* a = nullptr;
        Collider* b = nullptr;

        bool operator==(const ColliderPair& other) const
        {
            return (a == other.a && b == other.b) ||
                   (a == other.b && b == other.a);
        }
    };

    /**
     * Selects a deterministic, spatially representative subset of candidates.
     *
     * Selection starts with the deepest point, then maximizes distance,
     * triangle area and finally distance from the already selected set in the
     * contact plane. The result is independent of candidate input order.
     */
    TERMIN_COLLISION_API std::vector<ContactCandidate>
    reduce_contact_candidates(std::span<const ContactCandidate> candidates,
                              const Vec3& normal_world,
                              const ContactPatchReductionConfig& config = {});

    TERMIN_COLLISION_API ContactPatch
    reduce_contact_patch(const ContactPatch& patch,
                         const ContactPatchReductionConfig& config = {});

} // namespace termin::collision
