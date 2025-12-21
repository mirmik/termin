#pragma once

#include "collider.hpp"
#include <array>
#include <vector>
#include <limits>

namespace termin {
namespace colliders {

// Forward declarations
class SphereCollider;
class CapsuleCollider;

/**
 * Box collider — ориентированный параллелепипед.
 */
class BoxCollider : public Collider {
public:
    Vec3 local_center;  // Центр в локальных координатах
    Vec3 half_size;     // Половинные размеры
    Pose3 pose;         // Поза в мировых координатах

    BoxCollider()
        : local_center(0, 0, 0), half_size(0.5, 0.5, 0.5), pose() {}

    BoxCollider(const Vec3& center, const Vec3& half_size, const Pose3& pose = Pose3())
        : local_center(center), half_size(half_size), pose(pose) {}

    // Создать из полного размера
    static BoxCollider from_size(const Vec3& center, const Vec3& size, const Pose3& pose = Pose3()) {
        return BoxCollider(center, Vec3(size.x/2, size.y/2, size.z/2), pose);
    }

    // ==================== Интерфейс Collider ====================

    ColliderType type() const override { return ColliderType::Box; }

    Vec3 center() const override {
        return pose.transform_point(local_center);
    }

    RayHit closest_to_ray(const Ray3& ray) const override;
    ColliderHit closest_to_collider(const Collider& other) const override;
    ColliderPtr transform_by(const Pose3& t) const override;

    // ==================== Геометрия ====================

    /**
     * Получить 8 вершин в мировых координатах.
     */
    std::array<Vec3, 8> get_corners_world() const {
        std::array<Vec3, 8> corners;
        Vec3 c = local_center;
        Vec3 h = half_size;

        Vec3 local[8] = {
            {c.x - h.x, c.y - h.y, c.z - h.z},
            {c.x + h.x, c.y - h.y, c.z - h.z},
            {c.x - h.x, c.y + h.y, c.z - h.z},
            {c.x + h.x, c.y + h.y, c.z - h.z},
            {c.x - h.x, c.y - h.y, c.z + h.z},
            {c.x + h.x, c.y - h.y, c.z + h.z},
            {c.x - h.x, c.y + h.y, c.z + h.z},
            {c.x + h.x, c.y + h.y, c.z + h.z}
        };

        for (int i = 0; i < 8; ++i) {
            corners[i] = pose.transform_point(local[i]);
        }
        return corners;
    }

    /**
     * Получить 3 оси (нормали граней) в мировых координатах.
     */
    std::array<Vec3, 3> get_axes_world() const {
        return {
            pose.transform_vector(Vec3(1, 0, 0)),
            pose.transform_vector(Vec3(0, 1, 0)),
            pose.transform_vector(Vec3(0, 0, 1))
        };
    }

    // ==================== Специфичные методы ====================

    /**
     * Коллизия с плоскостью земли (z = ground_height).
     */
    struct GroundContact {
        Vec3 point;
        double penetration;
    };

    std::vector<GroundContact> collide_ground(double ground_height) const {
        std::vector<GroundContact> contacts;
        auto corners = get_corners_world();

        for (const auto& corner : corners) {
            if (corner.z < ground_height) {
                contacts.push_back({
                    Vec3(corner.x, corner.y, ground_height),
                    ground_height - corner.z
                });
            }
        }
        return contacts;
    }

    // Double dispatch implementations
    ColliderHit closest_to_box_impl(const BoxCollider& box) const override;
    ColliderHit closest_to_sphere_impl(const SphereCollider& sphere) const override;
    ColliderHit closest_to_capsule_impl(const CapsuleCollider& capsule) const override;

private:
    /**
     * Точка в локальных координатах box'а.
     */
    Vec3 to_local(const Vec3& world_point) const {
        return pose.inverse_transform_point(world_point);
    }

    /**
     * AABB bounds в локальных координатах.
     */
    void local_bounds(Vec3& min_pt, Vec3& max_pt) const {
        min_pt = local_center - half_size;
        max_pt = local_center + half_size;
    }
};

// ==================== Реализация методов ====================

inline ColliderPtr BoxCollider::transform_by(const Pose3& t) const {
    return std::make_shared<BoxCollider>(local_center, half_size, t * pose);
}

inline RayHit BoxCollider::closest_to_ray(const Ray3& ray) const {
    RayHit result;

    // Переносим луч в локальные координаты
    Vec3 O_local = to_local(ray.origin);
    Vec3 D_local = pose.inverse_transform_vector(ray.direction);

    double n = D_local.norm();
    if (n < 1e-10) {
        D_local = Vec3(0, 0, 1);
    } else {
        D_local = D_local / n;
    }

    Vec3 box_min, box_max;
    local_bounds(box_min, box_max);

    double tmin = -std::numeric_limits<double>::infinity();
    double tmax = std::numeric_limits<double>::infinity();
    bool hit_possible = true;

    // Slab method для AABB-Ray intersection
    for (int i = 0; i < 3; ++i) {
        if (std::abs(D_local[i]) < 1e-10) {
            // Луч параллелен плоскости
            if (O_local[i] < box_min[i] || O_local[i] > box_max[i]) {
                hit_possible = false;
            }
        } else {
            double t1 = (box_min[i] - O_local[i]) / D_local[i];
            double t2 = (box_max[i] - O_local[i]) / D_local[i];
            if (t1 > t2) std::swap(t1, t2);
            tmin = std::max(tmin, t1);
            tmax = std::min(tmax, t2);
        }
    }

    // Есть пересечение?
    if (hit_possible && tmax >= std::max(tmin, 0.0)) {
        double t_hit = (tmin >= 0) ? tmin : tmax;
        if (t_hit >= 0) {
            Vec3 p_ray = ray.point_at(t_hit);
            result.point_on_ray = p_ray;
            result.point_on_collider = p_ray;
            result.distance = 0.0;
            return result;
        }
    }

    // Нет пересечения — ищем ближайшие точки
    double best_t = 0.0;
    double best_dist = std::numeric_limits<double>::infinity();

    // Проверяем несколько кандидатов t
    std::vector<double> candidates = {0.0};
    for (int i = 0; i < 3; ++i) {
        if (std::abs(D_local[i]) > 1e-10) {
            candidates.push_back((box_min[i] - O_local[i]) / D_local[i]);
            candidates.push_back((box_max[i] - O_local[i]) / D_local[i]);
        }
    }

    for (double t : candidates) {
        if (t < 0) continue;

        Vec3 p_ray_local = O_local + D_local * t;

        // Clamp to box
        Vec3 p_box_local(
            std::clamp(p_ray_local.x, box_min.x, box_max.x),
            std::clamp(p_ray_local.y, box_min.y, box_max.y),
            std::clamp(p_ray_local.z, box_min.z, box_max.z)
        );

        double dist = (p_box_local - p_ray_local).norm();
        if (dist < best_dist) {
            best_dist = dist;
            best_t = t;
        }
    }

    result.point_on_ray = ray.point_at(best_t);
    Vec3 p_ray_local = O_local + D_local * best_t;
    Vec3 p_box_local(
        std::clamp(p_ray_local.x, box_min.x, box_max.x),
        std::clamp(p_ray_local.y, box_min.y, box_max.y),
        std::clamp(p_ray_local.z, box_min.z, box_max.z)
    );
    result.point_on_collider = pose.transform_point(p_box_local);
    result.distance = best_dist;

    return result;
}

// closest_to_collider определён в colliders.hpp после всех типов

inline ColliderHit BoxCollider::closest_to_box_impl(const BoxCollider& other) const {
    ColliderHit result;

    Vec3 center_a = center();
    Vec3 center_b = other.center();

    auto axes_a = get_axes_world();
    auto axes_b = other.get_axes_world();

    Vec3 d = center_b - center_a;
    double min_overlap = std::numeric_limits<double>::max();
    Vec3 best_axis;

    // Проекция box на ось
    auto project_extent = [](const std::array<Vec3, 3>& axes, const Vec3& half, const Vec3& axis) {
        return std::abs(axes[0].dot(axis)) * half.x +
               std::abs(axes[1].dot(axis)) * half.y +
               std::abs(axes[2].dot(axis)) * half.z;
    };

    bool separated = false;
    auto test_axis = [&](Vec3 axis) {
        double len = axis.norm();
        if (len < 1e-8) return;  // Вырожденная ось
        axis = axis / len;

        double ext_a = project_extent(axes_a, half_size, axis);
        double ext_b = project_extent(axes_b, other.half_size, axis);
        double dist = std::abs(d.dot(axis));
        double overlap = ext_a + ext_b - dist;

        if (overlap < 0) {
            separated = true;
        }

        if (overlap < min_overlap) {
            min_overlap = overlap;
            best_axis = (d.dot(axis) < 0) ? axis * (-1.0) : axis;
        }
    };

    // 15 осей SAT
    for (int i = 0; i < 3; ++i) {
        test_axis(axes_a[i]);
        test_axis(axes_b[i]);
    }
    for (int i = 0; i < 3; ++i) {
        for (int j = 0; j < 3; ++j) {
            test_axis(axes_a[i].cross(axes_b[j]));
        }
    }

    if (separated) {
        // Нет коллизии — приблизительные ближайшие точки
        result.point_on_a = center_a;
        result.point_on_b = center_b;
        result.normal = (center_b - center_a).normalized();
        result.distance = min_overlap < 0 ? -min_overlap : 0.01;
        return result;
    }

    // Есть коллизия
    result.normal = best_axis;
    result.distance = -min_overlap;
    result.point_on_a = (center_a + center_b) * 0.5;
    result.point_on_b = result.point_on_a;

    return result;
}

} // namespace colliders
} // namespace termin
