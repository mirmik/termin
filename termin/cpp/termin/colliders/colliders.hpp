#pragma once

/**
 * @file colliders.hpp
 * @brief Convenience header для всех коллайдеров.
 */

#include "collider.hpp"
#include "collider_primitive.hpp"
#include "box_collider.hpp"
#include "sphere_collider.hpp"
#include "capsule_collider.hpp"
#include "convex_hull_collider.hpp"
#include "gjk.hpp"
#include "attached_collider.hpp"
#include "union_collider.hpp"

// ==================== closest_to_collider implementations ====================
// Определены здесь после того, как все типы полностью объявлены

namespace termin {
namespace colliders {

inline ColliderHit BoxCollider::closest_to_collider(const Collider& other) const {
    switch (other.type()) {
        case ColliderType::Box:
            return closest_to_box_impl(static_cast<const BoxCollider&>(other));
        case ColliderType::Sphere:
            return closest_to_sphere_impl(static_cast<const SphereCollider&>(other));
        case ColliderType::Capsule:
            return closest_to_capsule_impl(static_cast<const CapsuleCollider&>(other));
        case ColliderType::ConvexHull:
            return gjk_collide(*this, static_cast<const ConvexHullCollider&>(other));
    }
    return ColliderHit{};
}

inline ColliderHit SphereCollider::closest_to_collider(const Collider& other) const {
    switch (other.type()) {
        case ColliderType::Box:
            return closest_to_box_impl(static_cast<const BoxCollider&>(other));
        case ColliderType::Sphere:
            return closest_to_sphere_impl(static_cast<const SphereCollider&>(other));
        case ColliderType::Capsule:
            return closest_to_capsule_impl(static_cast<const CapsuleCollider&>(other));
        case ColliderType::ConvexHull:
            return gjk_collide(*this, static_cast<const ConvexHullCollider&>(other));
    }
    return ColliderHit{};
}

inline ColliderHit CapsuleCollider::closest_to_collider(const Collider& other) const {
    switch (other.type()) {
        case ColliderType::Box:
            return closest_to_box_impl(static_cast<const BoxCollider&>(other));
        case ColliderType::Sphere:
            return closest_to_sphere_impl(static_cast<const SphereCollider&>(other));
        case ColliderType::Capsule:
            return closest_to_capsule_impl(static_cast<const CapsuleCollider&>(other));
        case ColliderType::ConvexHull:
            return gjk_collide(*this, static_cast<const ConvexHullCollider&>(other));
    }
    return ColliderHit{};
}

inline ColliderHit ConvexHullCollider::closest_to_box_impl(const BoxCollider& box) const {
    ColliderHit hit = gjk_collide(box, *this);
    std::swap(hit.point_on_a, hit.point_on_b);
    hit.normal = hit.normal * (-1.0);
    return hit;
}

inline ColliderHit ConvexHullCollider::closest_to_sphere_impl(const SphereCollider& sphere) const {
    ColliderHit hit = gjk_collide(sphere, *this);
    std::swap(hit.point_on_a, hit.point_on_b);
    hit.normal = hit.normal * (-1.0);
    return hit;
}

inline ColliderHit ConvexHullCollider::closest_to_capsule_impl(const CapsuleCollider& capsule) const {
    ColliderHit hit = gjk_collide(capsule, *this);
    std::swap(hit.point_on_a, hit.point_on_b);
    hit.normal = hit.normal * (-1.0);
    return hit;
}

inline ColliderHit ConvexHullCollider::closest_to_collider(const Collider& other) const {
    // ConvexHull uses GJK for all pair types
    switch (other.type()) {
        case ColliderType::Box:
            return gjk_collide(*this, static_cast<const BoxCollider&>(other));
        case ColliderType::Sphere:
            return gjk_collide(*this, static_cast<const SphereCollider&>(other));
        case ColliderType::Capsule:
            return gjk_collide(*this, static_cast<const CapsuleCollider&>(other));
        case ColliderType::ConvexHull:
            return gjk_collide(*this, static_cast<const ConvexHullCollider&>(other));
    }
    return ColliderHit{};
}

} // namespace colliders
} // namespace termin
