#pragma once

#include "collider_primitive.hpp"
#include <array>
#include <vector>
#include <limits>
#include <cmath>
#include <algorithm>

namespace termin {
namespace colliders {

// Forward declarations
class SphereCollider;
class CapsuleCollider;

/**
 * Box collider — ориентированный параллелепипед.
 *
 * Геометрия определяется:
 * - half_size: половинные размеры в локальных координатах
 * - transform: позиция, ориентация и масштаб
 *
 * Эффективные размеры = half_size * transform.scale
 */
class BoxCollider : public ColliderPrimitive {
public:
    Vec3 half_size;  // Половинные размеры (до применения scale)

    BoxCollider()
        : ColliderPrimitive(), half_size(0.5, 0.5, 0.5) {}

    BoxCollider(const Vec3& half_size, const GeneralPose3& t = GeneralPose3())
        : ColliderPrimitive(t), half_size(half_size) {}

    // Создать из полного размера
    static BoxCollider from_size(const Vec3& size, const GeneralPose3& t = GeneralPose3()) {
        return BoxCollider(Vec3(size.x/2, size.y/2, size.z/2), t);
    }

    // ==================== Эффективные размеры ====================

    /**
     * Половинные размеры с учётом scale.
     */
    Vec3 effective_half_size() const {
        return Vec3(
            half_size.x * transform.scale.x,
            half_size.y * transform.scale.y,
            half_size.z * transform.scale.z
        );
    }

    // ==================== Интерфейс Collider ====================

    ColliderType type() const override { return ColliderType::Box; }

    AABB aabb() const override {
        auto corners = get_corners_world();
        AABB result(corners[0], corners[0]);
        for (int i = 1; i < 8; ++i) {
            result.extend(corners[i]);
        }
        return result;
    }

    RayHit closest_to_ray(const Ray3& ray) const override;
    ColliderHit closest_to_collider(const Collider& other) const override;

    std::unique_ptr<ColliderPrimitive> clone_at(const GeneralPose3& pose) const override {
        return std::make_unique<BoxCollider>(half_size, pose);
    }

    Vec3 support(const Vec3& direction) const override {
        // Трансформируем direction в локальное пространство (без scale)
        Vec3 local_dir = transform.ang.inverse().rotate(direction);
        Vec3 hs = effective_half_size();
        // Выбираем знак каждой оси по проекции direction
        Vec3 local_point(
            local_dir.x >= 0 ? hs.x : -hs.x,
            local_dir.y >= 0 ? hs.y : -hs.y,
            local_dir.z >= 0 ? hs.z : -hs.z
        );
        // Трансформируем обратно в world (rotation + translation, без scale — она уже в hs)
        return transform.ang.rotate(local_point) + transform.lin;
    }

    // ==================== Геометрия ====================

    /**
     * Получить 8 вершин в мировых координатах.
     */
    std::array<Vec3, 8> get_corners_world() const {
        std::array<Vec3, 8> corners;
        Vec3 h = effective_half_size();

        Vec3 local[8] = {
            {-h.x, -h.y, -h.z},
            {+h.x, -h.y, -h.z},
            {-h.x, +h.y, -h.z},
            {+h.x, +h.y, -h.z},
            {-h.x, -h.y, +h.z},
            {+h.x, -h.y, +h.z},
            {-h.x, +h.y, +h.z},
            {+h.x, +h.y, +h.z}
        };

        Pose3 p = pose();
        for (int i = 0; i < 8; ++i) {
            corners[i] = p.transform_point(local[i]);
        }
        return corners;
    }

    /**
     * Получить 3 оси (нормали граней) в мировых координатах.
     */
    std::array<Vec3, 3> get_axes_world() const {
        Pose3 p = pose();
        return {
            p.transform_vector(Vec3(1, 0, 0)),
            p.transform_vector(Vec3(0, 1, 0)),
            p.transform_vector(Vec3(0, 0, 1))
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
     * Точка в локальных координатах box'а (с учётом scale).
     */
    Vec3 to_local(const Vec3& world_point) const {
        return transform.inverse_transform_point(world_point);
    }

    /**
     * AABB bounds в локальных координатах (БЕЗ scale, т.к. to_local уже применяет inverse scale).
     */
    void local_bounds(Vec3& min_pt, Vec3& max_pt) const {
        min_pt = Vec3(-half_size.x, -half_size.y, -half_size.z);
        max_pt = Vec3(+half_size.x, +half_size.y, +half_size.z);
    }
};

// ==================== Реализация методов ====================

inline RayHit BoxCollider::closest_to_ray(const Ray3& ray) const {
    RayHit result;

    // Переносим луч в локальные координаты (с учётом scale)
    Vec3 O_local = to_local(ray.origin);
    Vec3 D_local = transform.inverse_transform_vector(ray.direction);

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
            // t_hit — параметр для локального луча, преобразуем точку обратно в мировые координаты
            Vec3 p_local = O_local + D_local * t_hit;
            Vec3 p_world = transform.transform_point(p_local);
            result.point_on_ray = p_world;
            result.point_on_collider = p_world;
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

    Vec3 p_ray_local = O_local + D_local * best_t;
    Vec3 p_box_local(
        std::clamp(p_ray_local.x, box_min.x, box_max.x),
        std::clamp(p_ray_local.y, box_min.y, box_max.y),
        std::clamp(p_ray_local.z, box_min.z, box_max.z)
    );
    // Преобразуем обе точки из локальных в мировые координаты
    result.point_on_ray = transform.transform_point(p_ray_local);
    result.point_on_collider = transform.transform_point(p_box_local);
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

    Vec3 half_a = effective_half_size();
    Vec3 half_b = other.effective_half_size();

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

        double ext_a = project_extent(axes_a, half_a, axis);
        double ext_b = project_extent(axes_b, half_b, axis);
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

    // Есть коллизия - нужно найти точки контакта на поверхностях
    result.normal = best_axis;
    result.distance = -min_overlap;

    // Найдём глубже всего проникающие вершины box B в box A
    auto corners_b = other.get_corners_world();
    double deepest_pen = -std::numeric_limits<double>::infinity();
    Vec3 best_corner;
    bool found_corner = false;

    for (const auto& corner : corners_b) {
        // Проверяем, насколько глубоко эта вершина проникла в A
        // Проекция на ось пенетрации
        Vec3 rel = corner - center_a;
        double pen_depth = -rel.dot(best_axis);  // Насколько глубоко в направлении -normal

        // Проверяем, внутри ли вершина box A (приблизительно)
        double proj_x = std::abs(rel.dot(axes_a[0]));
        double proj_y = std::abs(rel.dot(axes_a[1]));
        double proj_z = std::abs(rel.dot(axes_a[2]));

        bool inside = proj_x <= half_a.x + 1e-6 &&
                      proj_y <= half_a.y + 1e-6 &&
                      proj_z <= half_a.z + 1e-6;

        if (inside || pen_depth > 0) {
            if (pen_depth > deepest_pen) {
                deepest_pen = pen_depth;
                best_corner = corner;
                found_corner = true;
            }
        }
    }

    if (found_corner) {
        // Точка на B - это вершина
        result.point_on_b = best_corner;
        // Точка на A - проекция вершины на поверхность A вдоль нормали
        result.point_on_a = best_corner + best_axis * min_overlap;
    } else {
        // Fallback: попробуем вершины A в B
        auto corners_a = get_corners_world();
        deepest_pen = -std::numeric_limits<double>::infinity();

        for (const auto& corner : corners_a) {
            Vec3 rel = corner - center_b;
            double pen_depth = rel.dot(best_axis);

            double proj_x = std::abs(rel.dot(axes_b[0]));
            double proj_y = std::abs(rel.dot(axes_b[1]));
            double proj_z = std::abs(rel.dot(axes_b[2]));

            bool inside = proj_x <= half_b.x + 1e-6 &&
                          proj_y <= half_b.y + 1e-6 &&
                          proj_z <= half_b.z + 1e-6;

            if (inside || pen_depth > 0) {
                if (pen_depth > deepest_pen) {
                    deepest_pen = pen_depth;
                    best_corner = corner;
                    found_corner = true;
                }
            }
        }

        if (found_corner) {
            result.point_on_a = best_corner;
            result.point_on_b = best_corner - best_axis * min_overlap;
        } else {
            // Последний fallback: midpoint на поверхностях вдоль нормали
            result.point_on_a = center_a + best_axis * (d.dot(best_axis) * 0.5 - min_overlap * 0.5);
            result.point_on_b = center_b - best_axis * (d.dot(best_axis) * 0.5 - min_overlap * 0.5);
        }
    }

    return result;
}

} // namespace colliders
} // namespace termin
