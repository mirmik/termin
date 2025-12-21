#pragma once

#include "collider_primitive.hpp"
#include "box_collider.hpp"
#include <cmath>
#include <algorithm>

namespace termin {
namespace colliders {

// Forward declaration
class CapsuleCollider;

/**
 * Sphere collider — сфера.
 *
 * Геометрия определяется:
 * - radius: радиус в локальных координатах
 * - transform: позиция и масштаб (rotation игнорируется - сфера симметрична)
 *
 * Эффективный радиус = radius * min(scale.x, scale.y, scale.z)
 */
class SphereCollider : public ColliderPrimitive {
public:
    double radius;  // Радиус (до применения scale)

    SphereCollider()
        : ColliderPrimitive(), radius(0.5) {}

    SphereCollider(double radius, const GeneralPose3& t = GeneralPose3())
        : ColliderPrimitive(t), radius(radius) {}

    // ==================== Эффективные размеры ====================

    /**
     * Радиус с учётом uniform scale.
     */
    double effective_radius() const {
        return radius * uniform_scale();
    }

    // ==================== Интерфейс Collider ====================

    ColliderType type() const override { return ColliderType::Sphere; }

    AABB aabb() const override {
        Vec3 c = center();
        double r = effective_radius();
        Vec3 rv(r, r, r);
        return AABB(c - rv, c + rv);
    }

    RayHit closest_to_ray(const Ray3& ray) const override;
    ColliderHit closest_to_collider(const Collider& other) const override;

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
        double r = effective_radius();
        double bottom = c.z - r;

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

inline RayHit SphereCollider::closest_to_ray(const Ray3& ray) const {
    RayHit result;

    Vec3 C = center();
    double R = effective_radius();
    Vec3 O = ray.origin;
    Vec3 D = ray.direction;

    Vec3 OC = O - C;
    double b = 2.0 * D.dot(OC);
    double c = OC.dot(OC) - R * R;
    double disc = b * b - 4.0 * c;

    // Нет пересечения — вернуть ближайшие точки
    if (disc < 0) {
        double t = (C - O).dot(D);
        if (t < 0) t = 0;

        Vec3 p_ray = ray.point_at(t);
        Vec3 dir_vec = p_ray - C;
        double dist = dir_vec.norm();

        if (dist > 1e-10) {
            result.point_on_collider = C + dir_vec * (R / dist);
        } else {
            result.point_on_collider = C + Vec3(R, 0, 0);
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

        result.point_on_collider = C + dir_vec * (R / dist);
        result.point_on_ray = p_ray;
        result.distance = (result.point_on_collider - p_ray).norm();
        return result;
    }

    // Корректное пересечение
    Vec3 p_ray = ray.point_at(t_hit);
    Vec3 dir_vec = p_ray - C;
    double dist = dir_vec.norm();

    if (dist > 1e-10) {
        result.point_on_collider = C + dir_vec * (R / dist);
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
    double r_a = effective_radius();
    double r_b = other.effective_radius();

    Vec3 diff = c_b - c_a;
    double dist = diff.norm();
    double sum_r = r_a + r_b;

    if (dist > 1e-10) {
        result.normal = diff / dist;
    } else {
        result.normal = Vec3(0, 0, 1);
    }

    result.point_on_a = c_a + result.normal * r_a;
    result.point_on_b = c_b - result.normal * r_b;
    result.distance = dist - sum_r;

    return result;
}

inline ColliderHit SphereCollider::closest_to_box_impl(const BoxCollider& box) const {
    ColliderHit result;

    Vec3 sphere_center = center();
    double sphere_radius = effective_radius();

    // Центр сферы в локальных координатах box'а (unscaled space)
    Vec3 local = box.transform.inverse_transform_point(sphere_center);

    // Bounds в unscaled пространстве (inverse_transform_point уже применил inverse scale)
    Vec3 half = box.half_size;
    Vec3 box_min = Vec3(-half.x, -half.y, -half.z);
    Vec3 box_max = Vec3(+half.x, +half.y, +half.z);

    // Ближайшая точка на box
    Vec3 closest(
        std::clamp(local.x, box_min.x, box_max.x),
        std::clamp(local.y, box_min.y, box_max.y),
        std::clamp(local.z, box_min.z, box_max.z)
    );

    Vec3 closest_world = box.transform.transform_point(closest);

    // Расстояние в мировом пространстве
    Vec3 diff_world = closest_world - sphere_center;
    double dist_world = diff_world.norm();

    if (dist_world > 1e-10) {
        // Normal points from A (sphere) toward B (box)
        result.normal = diff_world / dist_world;
    } else {
        // Сфера внутри box'а — направление к центру box'а
        result.normal = (box.center() - sphere_center).normalized();
    }

    // Point on sphere surface in direction of box
    result.point_on_a = sphere_center + result.normal * sphere_radius;
    result.point_on_b = closest_world;
    result.distance = dist_world - sphere_radius;

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
