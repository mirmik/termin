#pragma once

/**
 * @file colliders.hpp
 * @brief Convenience header для всех коллайдеров.
 */

#include "collider.hpp"
#include "box_collider.hpp"
#include "sphere_collider.hpp"
#include "capsule_collider.hpp"

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
    }
    return ColliderHit{};
}

} // namespace colliders
} // namespace termin
