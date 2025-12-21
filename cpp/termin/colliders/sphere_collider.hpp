#pragma once

#include "collider.hpp"
#include "box_collider.hpp"
#include <cmath>
#include <algorithm>

namespace termin {
namespace colliders {

// Forward declaration
class CapsuleCollider;

/**
 * Sphere collider — сфера.
 */
class SphereCollider : public Collider {
public:
    Vec3 local_center;  // Центр в локальных координатах
    double radius;
    Pose3 pose;         // Поза в мировых координатах

    SphereCollider()
        : local_center(0, 0, 0), radius(0.5), pose() {}

    SphereCollider(const Vec3& center, double radius, const Pose3& pose = Pose3())
        : local_center(center), radius(radius), pose(pose) {}

    // ==================== Интерфейс Collider ====================

    ColliderType type() const override { return ColliderType::Sphere; }

    Vec3 center() const override {
        return pose.transform_point(local_center);
    }

    AABB aabb() const override {
        Vec3 c = center();
        Vec3 r(radius, radius, radius);
        return AABB(c - r, c + r);
    }

    RayHit closest_to_ray(const Ray3& ray) const override;
    ColliderHit closest_to_collider(const Collider& other) const override;
    ColliderPtr transform_by(const Pose3& t) const override;

    // ==================== Специфичные методы ====================

    /**
     * Коллизия с плоскостью земли (z = ground_height).
     */
    struct GroundContact {
        Vec3 point;
        Vec3 normal;
        double penetration;
    };

    GroundContact collide_ground(double ground_height) const {
        GroundContact result;
        Vec3 c = center();
        double bottom = c.z - radius;

        result.normal = Vec3(0, 0, 1);
        result.point = Vec3(c.x, c.y, ground_height);
        result.penetration = (bottom < ground_height) ? (ground_height - bottom) : 0.0;

        return result;
    }

    // Double dispatch implementations
    ColliderHit closest_to_box_impl(const BoxCollider& box) const override;
    ColliderHit closest_to_sphere_impl(const SphereCollider& sphere) const override;
    ColliderHit closest_to_capsule_impl(const CapsuleCollider& capsule) const override;
};

// ==================== Реализация методов ====================

inline ColliderPtr SphereCollider::transform_by(const Pose3& t) const {
    return std::make_shared<SphereCollider>(local_center, radius, t * pose);
}

inline RayHit SphereCollider::closest_to_ray(const Ray3& ray) const {
    RayHit result;

    Vec3 C = center();
    Vec3 O = ray.origin;
    Vec3 D = ray.direction;

    Vec3 OC = O - C;
    double b = 2.0 * D.dot(OC);
    double c = OC.dot(OC) - radius * radius;
    double disc = b * b - 4.0 * c;

    // Нет пересечения — вернуть ближайшие точки
    if (disc < 0) {
        double t = (C - O).dot(D);
        if (t < 0) t = 0;

        Vec3 p_ray = ray.point_at(t);
        Vec3 dir_vec = p_ray - C;
        double dist = dir_vec.norm();

        if (dist > 1e-10) {
            result.point_on_collider = C + dir_vec * (radius / dist);
        } else {
            result.point_on_collider = C + Vec3(radius, 0, 0);
        }
        result.point_on_ray = p_ray;
        result.distance = (result.point_on_collider - p_ray).norm();
        return result;
    }

    // Есть пересечения: берём ближайшее t >= 0
    double sqrt_disc = std::sqrt(disc);
    double t1 = (-b - sqrt_disc) * 0.5;
    double t2 = (-b + sqrt_disc) * 0.5;

    double t_hit = -1;
    if (t1 >= 0) {
        t_hit = t1;
    } else if (t2 >= 0) {
        t_hit = t2;
    }

    // Пересечение позади луча
    if (t_hit < 0) {
        double t = (C - O).dot(D);
        if (t < 0) t = 0;

        Vec3 p_ray = ray.point_at(t);
        Vec3 dir_vec = p_ray - C;
        double dist = dir_vec.norm();

        result.point_on_collider = C + dir_vec * (radius / dist);
        result.point_on_ray = p_ray;
        result.distance = (result.point_on_collider - p_ray).norm();
        return result;
    }

    // Корректное пересечение
    Vec3 p_ray = ray.point_at(t_hit);
    Vec3 dir_vec = p_ray - C;
    double dist = dir_vec.norm();

    if (dist > 1e-10) {
        result.point_on_collider = C + dir_vec * (radius / dist);
    } else {
        result.point_on_collider = p_ray;
    }
    result.point_on_ray = p_ray;
    result.distance = 0.0;

    return result;
}

// closest_to_collider определён в colliders.hpp после всех типов

inline ColliderHit SphereCollider::closest_to_sphere_impl(const SphereCollider& other) const {
    ColliderHit result;

    Vec3 c_a = center();
    Vec3 c_b = other.center();
    Vec3 diff = c_b - c_a;
    double dist = diff.norm();
    double sum_r = radius + other.radius;

    if (dist > 1e-10) {
        result.normal = diff / dist;
    } else {
        result.normal = Vec3(0, 0, 1);
    }

    result.point_on_a = c_a + result.normal * radius;
    result.point_on_b = c_b - result.normal * other.radius;
    result.distance = dist - sum_r;

    return result;
}

inline ColliderHit SphereCollider::closest_to_box_impl(const BoxCollider& box) const {
    ColliderHit result;

    Vec3 sphere_center = center();

    // Центр сферы в локальных координатах box'а
    Vec3 local = box.pose.inverse_transform_point(sphere_center);

    Vec3 box_min = box.local_center - box.half_size;
    Vec3 box_max = box.local_center + box.half_size;

    // Ближайшая точка на box
    Vec3 closest(
        std::clamp(local.x, box_min.x, box_max.x),
        std::clamp(local.y, box_min.y, box_max.y),
        std::clamp(local.z, box_min.z, box_max.z)
    );

    Vec3 diff = local - closest;
    double dist = diff.norm();

    Vec3 closest_world = box.pose.transform_point(closest);

    if (dist > 1e-10) {
        result.normal = (sphere_center - closest_world).normalized();
    } else {
        // Сфера внутри box'а
        result.normal = (sphere_center - box.center()).normalized();
    }

    result.point_on_a = sphere_center - result.normal * radius;
    result.point_on_b = closest_world;
    result.distance = dist - radius;

    return result;
}

// BoxCollider::closest_to_sphere_impl определён здесь, после SphereCollider
inline ColliderHit BoxCollider::closest_to_sphere_impl(const SphereCollider& sphere) const {
    // Используем симметрию: sphere-box = -(box-sphere)
    ColliderHit hit = sphere.closest_to_box_impl(*this);
    // Меняем местами точки и инвертируем нормаль
    std::swap(hit.point_on_a, hit.point_on_b);
    hit.normal = hit.normal * (-1.0);
    return hit;
}

} // namespace colliders
} // namespace termin
