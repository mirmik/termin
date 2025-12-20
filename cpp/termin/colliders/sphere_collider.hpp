#pragma once

#include "../geom/vec3.hpp"
#include "../geom/pose3.hpp"
#include "box_collider.hpp"
#include <cmath>

namespace termin {
namespace colliders {

using geom::Vec3;
using geom::Pose3;

/**
 * Sphere collider.
 */
class SphereCollider {
public:
    Vec3 center;    // Центр в мировых координатах
    double radius;

    SphereCollider() : center(0, 0, 0), radius(0.5) {}
    SphereCollider(const Vec3& center, double radius)
        : center(center), radius(radius) {}

    // Трансформировать коллайдер
    SphereCollider transform_by(const Pose3& t) const {
        return SphereCollider(t.transform_point(center), radius);
    }

    /**
     * Коллизия сфера-сфера.
     */
    CollisionResult collide_sphere(const SphereCollider& other) const {
        CollisionResult result;

        Vec3 diff = other.center - center;
        double dist = diff.norm();
        double sum_r = radius + other.radius;

        if (dist < sum_r) {
            result.colliding = true;
            result.distance = dist - sum_r;  // Отрицательное = пенетрация

            if (dist > 1e-8) {
                result.normal = diff / dist;
            } else {
                result.normal = Vec3(0, 0, 1);  // Arbitrary
            }
            result.point = center + result.normal * radius;
        } else {
            result.colliding = false;
            result.distance = dist - sum_r;
            if (dist > 1e-8) {
                result.normal = diff / dist;
            } else {
                result.normal = Vec3(0, 0, 1);
            }
            result.point = center + result.normal * radius;
        }
        return result;
    }

    /**
     * Коллизия сфера-box (используем closest point on box).
     */
    CollisionResult collide_box(const BoxCollider& box) const {
        CollisionResult result;

        // Переводим центр сферы в локальные координаты box'а
        Vec3 local_center = box.pose.inverse_transform_point(center);

        // Clamp to box bounds
        Vec3 box_min = box.center - box.half_size;
        Vec3 box_max = box.center + box.half_size;

        Vec3 closest_local = {
            std::clamp(local_center.x, box_min.x, box_max.x),
            std::clamp(local_center.y, box_min.y, box_max.y),
            std::clamp(local_center.z, box_min.z, box_max.z)
        };

        // Расстояние в локальных координатах
        Vec3 diff_local = local_center - closest_local;
        double dist = diff_local.norm();

        // Переводим обратно в мировые координаты
        Vec3 closest_world = box.pose.transform_point(closest_local);

        if (dist < radius) {
            result.colliding = true;
            result.distance = dist - radius;

            if (dist > 1e-8) {
                result.normal = (center - closest_world).normalized();
            } else {
                // Сфера внутри box'а - нужно найти ближайшую грань
                // Упрощённо: берём направление к центру box'а
                result.normal = (center - box.world_center()).normalized();
            }
            result.point = closest_world;
        } else {
            result.colliding = false;
            result.distance = dist - radius;
            result.normal = (center - closest_world).normalized();
            result.point = closest_world;
        }
        return result;
    }

    /**
     * Коллизия с плоскостью земли (z = ground_height).
     */
    CollisionResult collide_ground(double ground_height) const {
        CollisionResult result;
        double bottom = center.z - radius;

        if (bottom < ground_height) {
            result.colliding = true;
            result.distance = bottom - ground_height;  // Отрицательное
            result.normal = Vec3(0, 0, 1);
            result.point = Vec3(center.x, center.y, ground_height);
        } else {
            result.colliding = false;
            result.distance = bottom - ground_height;
            result.normal = Vec3(0, 0, 1);
            result.point = Vec3(center.x, center.y, ground_height);
        }
        return result;
    }
};

} // namespace colliders
} // namespace termin
