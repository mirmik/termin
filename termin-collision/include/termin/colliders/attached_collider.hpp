#pragma once

// AttachedCollider — коллайдер, привязанный к GeneralTransform3.
//
// Комбинирует:
// - Базовый ColliderPrimitive (геометрия в локальных координатах)
// - GeneralTransform3* (указатель на трансформ entity)
//
// Итоговый трансформ = entity_transform * collider.transform

#include "collider.hpp"
#include "collider_primitive.hpp"
#include <termin/geom/general_transform3.hpp>
#include "tc_types.h"  // For tc_entity_id
#include <cassert>
#include <cmath>
#include <memory>
#include <stdexcept>
#include <tcbase/tc_log.h>

namespace termin {
namespace colliders {


// Коллайдер, привязанный к GeneralTransform3.
//
// Наследуется от Collider для полиморфного использования в CollisionWorld.
// Мировой трансформ должен оставаться точно представимым как TRS.
class AttachedCollider : public Collider {
public:
    ColliderPrimitive* collider_;
    GeneralTransform3* transform_;
    tc_entity_id owner_entity_id_ = TC_ENTITY_ID_INVALID;

    AttachedCollider(ColliderPrimitive* collider, GeneralTransform3* transform, tc_entity_id entity_id = TC_ENTITY_ID_INVALID)
        : collider_(collider)
        , transform_(transform)
        , owner_entity_id_(entity_id)
    {
        assert(collider_ != nullptr && "collider must not be null");
        assert(transform_ != nullptr && "transform must not be null");
    }

    ColliderPrimitive* collider() const { return collider_; }
    GeneralTransform3* transform() const { return transform_; }
    tc_entity_id owner_entity_id() const { return owner_entity_id_; }

    // entity_transform * collider.transform
    GeneralPose3 world_transform() const {
        const std::optional<Vec3> entity_scale =
            transform_->decomposed_global_scale();
        if (!entity_scale) {
            tc_log_error(
                "[AttachedCollider] entity '%s' has an affine world transform; "
                "TRS collider projection is forbidden",
                transform_->name());
            throw std::runtime_error(
                "Attached collider does not support affine entity ancestry");
        }

        const Quat collider_rotation = collider_->transform.ang.normalized();
        const bool collider_rotation_is_identity =
            std::abs(collider_rotation.x) <= 1.0e-12
            && std::abs(collider_rotation.y) <= 1.0e-12
            && std::abs(collider_rotation.z) <= 1.0e-12
            && std::abs(std::abs(collider_rotation.w) - 1.0) <= 1.0e-12;
        if (transform_->kind() == TransformKind::AxisScaled
            && !collider_rotation_is_identity) {
            tc_log_error(
                "[AttachedCollider] entity '%s' has axis scale and its collider "
                "has a local rotation; their composition requires shear",
                transform_->name());
            throw std::runtime_error(
                "Attached collider transform would require affine shear");
        }

        const GeneralPose3 entity_pose{
            transform_->global_rotation(),
            transform_->global_position(),
            *entity_scale,
        };
        return entity_pose * collider_->transform;
    }

    ColliderType type() const override {
        return collider_->type();
    }

    Vec3 center() const override {
        return world_transform().lin;
    }

    AABB aabb() const override {
        auto world = collider_->clone_at(world_transform());
        return world->aabb();
    }

    RayHit closest_to_ray(const Ray3& ray) const override {
        auto world = collider_->clone_at(world_transform());
        return world->closest_to_ray(ray);
    }

    ColliderHit closest_to_collider(const Collider& other) const override {
        auto world = collider_->clone_at(world_transform());

        // Если other тоже AttachedCollider, разворачиваем его
        const AttachedCollider* other_attached = dynamic_cast<const AttachedCollider*>(&other);
        if (other_attached != nullptr) {
            auto other_world = other_attached->collider_->clone_at(other_attached->world_transform());
            return world->closest_to_collider(*other_world);
        }

        return world->closest_to_collider(other);
    }

    ColliderHit closest_to_box_impl(const BoxCollider& box) const override {
        auto world = collider_->clone_at(world_transform());
        return world->closest_to_box_impl(box);
    }

    ColliderHit closest_to_sphere_impl(const SphereCollider& sphere) const override {
        auto world = collider_->clone_at(world_transform());
        return world->closest_to_sphere_impl(sphere);
    }

    ColliderHit closest_to_capsule_impl(const CapsuleCollider& capsule) const override {
        auto world = collider_->clone_at(world_transform());
        return world->closest_to_capsule_impl(capsule);
    }

    bool colliding(const Collider& other) const {
        return closest_to_collider(other).colliding();
    }

    double distance(const Collider& other) const {
        return closest_to_collider(other).distance;
    }
};

} // namespace colliders
} // namespace termin
