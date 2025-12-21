#pragma once

/**
 * @file attached_collider.hpp
 * @brief Коллайдер, привязанный к GeneralTransform3.
 *
 * AttachedCollider комбинирует:
 * - Базовый ColliderPrimitive (геометрия в локальных координатах)
 * - GeneralTransform3* (указатель на трансформ entity)
 *
 * Итоговый трансформ = entity_transform * collider.transform
 */

#include "collider.hpp"
#include "collider_primitive.hpp"
#include "box_collider.hpp"
#include "sphere_collider.hpp"
#include "capsule_collider.hpp"
#include "../geom/general_transform3.hpp"
#include <cassert>
#include <memory>

namespace termin {
namespace colliders {

using geom::GeneralPose3;
using geom::GeneralTransform3;

/**
 * Коллайдер, привязанный к GeneralTransform3.
 *
 * Наследуется от Collider для полиморфного использования в CollisionWorld.
 * Мировой трансформ = transform_->global_pose() * collider_->transform
 */
class AttachedCollider : public Collider {
public:
    ColliderPrimitive* collider_;
    GeneralTransform3* transform_;

    /**
     * Создать привязанный коллайдер.
     * @param collider Базовый примитив (в локальных координатах), не должен быть null
     * @param transform Указатель на GeneralTransform3, не должен быть null
     */
    AttachedCollider(ColliderPrimitive* collider, GeneralTransform3* transform)
        : collider_(collider)
        , transform_(transform)
    {
        assert(collider_ != nullptr && "collider must not be null");
        assert(transform_ != nullptr && "transform must not be null");
    }

    ColliderPrimitive* collider() const { return collider_; }
    GeneralTransform3* transform() const { return transform_; }

    /**
     * Получить комбинированный мировой трансформ.
     * entity_transform * collider.transform
     */
    GeneralPose3 world_transform() const {
        return transform_->global_pose() * collider_->transform;
    }

    ColliderType type() const override {
        return collider_->type();
    }

    Vec3 center() const override {
        GeneralPose3 wt = world_transform();
        return wt.lin;
    }

    AABB aabb() const override {
        // Для корректного AABB нужно применить мировой трансформ
        // Создаём временный коллайдер с мировым трансформом
        GeneralPose3 wt = world_transform();

        if (auto* box = dynamic_cast<BoxCollider*>(collider_)) {
            BoxCollider world_box(box->half_size, wt);
            return world_box.aabb();
        } else if (auto* sphere = dynamic_cast<SphereCollider*>(collider_)) {
            SphereCollider world_sphere(sphere->radius, wt);
            return world_sphere.aabb();
        } else if (auto* capsule = dynamic_cast<CapsuleCollider*>(collider_)) {
            CapsuleCollider world_capsule(capsule->half_height, capsule->radius, wt);
            return world_capsule.aabb();
        }

        // Fallback
        return collider_->aabb();
    }

    RayHit closest_to_ray(const Ray3& ray) const override {
        GeneralPose3 wt = world_transform();

        if (auto* box = dynamic_cast<BoxCollider*>(collider_)) {
            BoxCollider world_box(box->half_size, wt);
            return world_box.closest_to_ray(ray);
        } else if (auto* sphere = dynamic_cast<SphereCollider*>(collider_)) {
            SphereCollider world_sphere(sphere->radius, wt);
            return world_sphere.closest_to_ray(ray);
        } else if (auto* capsule = dynamic_cast<CapsuleCollider*>(collider_)) {
            CapsuleCollider world_capsule(capsule->half_height, capsule->radius, wt);
            return world_capsule.closest_to_ray(ray);
        }

        return RayHit{};
    }

    ColliderHit closest_to_collider(const Collider& other) const override {
        GeneralPose3 wt = world_transform();

        // Создаём world-space версию нашего коллайдера
        std::unique_ptr<ColliderPrimitive> world_collider;

        if (auto* box = dynamic_cast<BoxCollider*>(collider_)) {
            world_collider = std::make_unique<BoxCollider>(box->half_size, wt);
        } else if (auto* sphere = dynamic_cast<SphereCollider*>(collider_)) {
            world_collider = std::make_unique<SphereCollider>(sphere->radius, wt);
        } else if (auto* capsule = dynamic_cast<CapsuleCollider*>(collider_)) {
            world_collider = std::make_unique<CapsuleCollider>(capsule->half_height, capsule->radius, wt);
        } else {
            return ColliderHit{};
        }

        // Если other тоже AttachedCollider, разворачиваем его
        const AttachedCollider* other_attached = dynamic_cast<const AttachedCollider*>(&other);
        if (other_attached != nullptr) {
            GeneralPose3 other_wt = other_attached->world_transform();

            std::unique_ptr<ColliderPrimitive> other_world;
            if (auto* box = dynamic_cast<BoxCollider*>(other_attached->collider_)) {
                other_world = std::make_unique<BoxCollider>(box->half_size, other_wt);
            } else if (auto* sphere = dynamic_cast<SphereCollider*>(other_attached->collider_)) {
                other_world = std::make_unique<SphereCollider>(sphere->radius, other_wt);
            } else if (auto* capsule = dynamic_cast<CapsuleCollider*>(other_attached->collider_)) {
                other_world = std::make_unique<CapsuleCollider>(capsule->half_height, capsule->radius, other_wt);
            }

            if (other_world) {
                return world_collider->closest_to_collider(*other_world);
            }
        }

        return world_collider->closest_to_collider(other);
    }

    ColliderHit closest_to_box_impl(const BoxCollider& box) const override {
        GeneralPose3 wt = world_transform();

        if (auto* b = dynamic_cast<BoxCollider*>(collider_)) {
            BoxCollider world_box(b->half_size, wt);
            return world_box.closest_to_box_impl(box);
        } else if (auto* s = dynamic_cast<SphereCollider*>(collider_)) {
            SphereCollider world_sphere(s->radius, wt);
            return world_sphere.closest_to_box_impl(box);
        } else if (auto* c = dynamic_cast<CapsuleCollider*>(collider_)) {
            CapsuleCollider world_capsule(c->half_height, c->radius, wt);
            return world_capsule.closest_to_box_impl(box);
        }
        return ColliderHit{};
    }

    ColliderHit closest_to_sphere_impl(const SphereCollider& sphere) const override {
        GeneralPose3 wt = world_transform();

        if (auto* b = dynamic_cast<BoxCollider*>(collider_)) {
            BoxCollider world_box(b->half_size, wt);
            return world_box.closest_to_sphere_impl(sphere);
        } else if (auto* s = dynamic_cast<SphereCollider*>(collider_)) {
            SphereCollider world_sphere(s->radius, wt);
            return world_sphere.closest_to_sphere_impl(sphere);
        } else if (auto* c = dynamic_cast<CapsuleCollider*>(collider_)) {
            CapsuleCollider world_capsule(c->half_height, c->radius, wt);
            return world_capsule.closest_to_sphere_impl(sphere);
        }
        return ColliderHit{};
    }

    ColliderHit closest_to_capsule_impl(const CapsuleCollider& capsule) const override {
        GeneralPose3 wt = world_transform();

        if (auto* b = dynamic_cast<BoxCollider*>(collider_)) {
            BoxCollider world_box(b->half_size, wt);
            return world_box.closest_to_capsule_impl(capsule);
        } else if (auto* s = dynamic_cast<SphereCollider*>(collider_)) {
            SphereCollider world_sphere(s->radius, wt);
            return world_sphere.closest_to_capsule_impl(capsule);
        } else if (auto* c = dynamic_cast<CapsuleCollider*>(collider_)) {
            CapsuleCollider world_capsule(c->half_height, c->radius, wt);
            return world_capsule.closest_to_capsule_impl(capsule);
        }
        return ColliderHit{};
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
