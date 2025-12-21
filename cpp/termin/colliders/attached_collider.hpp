#pragma once

/**
 * @file attached_collider.hpp
 * @brief Коллайдер, привязанный к GeneralTransform3.
 */

#include "collider.hpp"
#include "../geom/pose3.hpp"
#include "../geom/aabb.hpp"
#include "../geom/general_transform3.hpp"
#include <cassert>

namespace termin {
namespace colliders {

using geom::Pose3;
using geom::Vec3;
using geom::AABB;
using geom::GeneralTransform3;

/**
 * Коллайдер, привязанный к GeneralTransform3.
 *
 * Наследуется от Collider для полиморфного использования в CollisionWorld.
 * Мировая поза получается из transform_->global_pose().
 * Внутренний коллайдер трансформируется этой позой.
 */
class AttachedCollider : public Collider {
public:
    Collider* collider_;
    GeneralTransform3* transform_;

    /**
     * Создать привязанный коллайдер.
     * @param collider Базовый коллайдер (в локальных координатах), не должен быть null
     * @param transform Указатель на GeneralTransform3, не должен быть null
     */
    AttachedCollider(Collider* collider, GeneralTransform3* transform)
        : collider_(collider)
        , transform_(transform)
    {
        assert(collider_ != nullptr && "collider must not be null");
        assert(transform_ != nullptr && "transform must not be null");
    }

    Collider* collider() const { return collider_; }
    GeneralTransform3* transform() const { return transform_; }

    /// Получить мировую позу из трансформа
    Pose3 world_pose() const {
        return transform_->global_pose().to_pose3();
    }

    ColliderType type() const override {
        return collider_->type();
    }

    Vec3 center() const override {
        Pose3 pose = world_pose();
        return pose.transform_point(collider_->center());
    }

    AABB aabb() const override {
        AABB local = collider_->aabb();
        Pose3 pose = world_pose();

        Vec3 corners[8] = {
            {local.min_point.x, local.min_point.y, local.min_point.z},
            {local.max_point.x, local.min_point.y, local.min_point.z},
            {local.min_point.x, local.max_point.y, local.min_point.z},
            {local.max_point.x, local.max_point.y, local.min_point.z},
            {local.min_point.x, local.min_point.y, local.max_point.z},
            {local.max_point.x, local.min_point.y, local.max_point.z},
            {local.min_point.x, local.max_point.y, local.max_point.z},
            {local.max_point.x, local.max_point.y, local.max_point.z},
        };

        Vec3 first = pose.transform_point(corners[0]);
        AABB result(first, first);
        for (int i = 1; i < 8; ++i) {
            result.extend(pose.transform_point(corners[i]));
        }
        return result;
    }

    RayHit closest_to_ray(const Ray3& ray) const override {
        Pose3 pose = world_pose();
        ColliderPtr world_collider = collider_->transform_by(pose);
        return world_collider->closest_to_ray(ray);
    }

    ColliderHit closest_to_collider(const Collider& other) const override {
        Pose3 pose = world_pose();
        ColliderPtr world_collider = collider_->transform_by(pose);

        const AttachedCollider* other_attached = dynamic_cast<const AttachedCollider*>(&other);
        if (other_attached != nullptr) {
            Pose3 other_pose = other_attached->world_pose();
            ColliderPtr other_world = other_attached->collider_->transform_by(other_pose);
            return world_collider->closest_to_collider(*other_world);
        }

        return world_collider->closest_to_collider(other);
    }

    ColliderPtr transform_by(const Pose3& pose) const override {
        Pose3 combined = pose * world_pose();
        return collider_->transform_by(combined);
    }

    ColliderHit closest_to_box_impl(const BoxCollider& box) const override {
        Pose3 pose = world_pose();
        ColliderPtr world_collider = collider_->transform_by(pose);
        return world_collider->closest_to_box_impl(box);
    }

    ColliderHit closest_to_sphere_impl(const SphereCollider& sphere) const override {
        Pose3 pose = world_pose();
        ColliderPtr world_collider = collider_->transform_by(pose);
        return world_collider->closest_to_sphere_impl(sphere);
    }

    ColliderHit closest_to_capsule_impl(const CapsuleCollider& capsule) const override {
        Pose3 pose = world_pose();
        ColliderPtr world_collider = collider_->transform_by(pose);
        return world_collider->closest_to_capsule_impl(capsule);
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
