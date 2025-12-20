#pragma once

/**
 * @file collider.hpp
 * @brief Простые коллайдеры и детектор столкновений.
 */

#include "../geom/vec3.hpp"
#include "../geom/pose3.hpp"
#include <cmath>
#include <array>
#include <vector>
#include <algorithm>
#include <limits>

namespace termin {
namespace physics {

using geom::Vec3;
using geom::Pose3;

// ==================== Результат коллизии ====================

struct ContactPoint {
    Vec3 point;          // Точка контакта (мировая СК)
    Vec3 normal;         // Нормаль (от A к B)
    double penetration;  // Глубина проникновения (положительная)
};

struct CollisionResult {
    bool colliding = false;
    std::vector<ContactPoint> contacts;
};

// ==================== Детекторы коллизий ====================

/**
 * Box vs Ground (плоскость z = ground_height).
 * Возвращает контакты для всех вершин ниже земли.
 */
inline CollisionResult collide_box_ground(
    const Vec3& half_size,
    const Pose3& pose,
    double ground_height
) {
    CollisionResult result;

    // 8 вершин
    Vec3 local[8] = {
        {-half_size.x, -half_size.y, -half_size.z},
        {+half_size.x, -half_size.y, -half_size.z},
        {-half_size.x, +half_size.y, -half_size.z},
        {+half_size.x, +half_size.y, -half_size.z},
        {-half_size.x, -half_size.y, +half_size.z},
        {+half_size.x, -half_size.y, +half_size.z},
        {-half_size.x, +half_size.y, +half_size.z},
        {+half_size.x, +half_size.y, +half_size.z}
    };

    Vec3 ground_normal(0, 0, 1);

    for (int i = 0; i < 8; ++i) {
        Vec3 world = pose.transform_point(local[i]);
        if (world.z < ground_height) {
            result.colliding = true;
            result.contacts.push_back({
                Vec3(world.x, world.y, ground_height),
                ground_normal,
                ground_height - world.z
            });
        }
    }

    return result;
}

/**
 * Sphere vs Ground.
 */
inline CollisionResult collide_sphere_ground(
    const Vec3& center,
    double radius,
    double ground_height
) {
    CollisionResult result;

    double bottom = center.z - radius;
    if (bottom < ground_height) {
        result.colliding = true;
        result.contacts.push_back({
            Vec3(center.x, center.y, ground_height),
            Vec3(0, 0, 1),
            ground_height - bottom
        });
    }

    return result;
}

/**
 * Sphere vs Sphere.
 */
inline CollisionResult collide_sphere_sphere(
    const Vec3& center_a, double radius_a,
    const Vec3& center_b, double radius_b
) {
    CollisionResult result;

    Vec3 diff = center_b - center_a;
    double dist = diff.norm();
    double sum_r = radius_a + radius_b;

    if (dist < sum_r && dist > 1e-10) {
        result.colliding = true;
        Vec3 normal = diff / dist;
        result.contacts.push_back({
            center_a + normal * radius_a,
            normal,
            sum_r - dist
        });
    }

    return result;
}

/**
 * Box vs Box (SAT — Separating Axis Theorem).
 * Генерирует контакты для всех вершин одного box'а, проникающих в другой.
 */
inline CollisionResult collide_box_box(
    const Vec3& half_a, const Pose3& pose_a,
    const Vec3& half_b, const Pose3& pose_b
) {
    CollisionResult result;

    Vec3 center_a = pose_a.lin;
    Vec3 center_b = pose_b.lin;

    // Оси каждого box'а
    std::array<Vec3, 3> axes_a = {
        pose_a.transform_vector(Vec3(1, 0, 0)),
        pose_a.transform_vector(Vec3(0, 1, 0)),
        pose_a.transform_vector(Vec3(0, 0, 1))
    };
    std::array<Vec3, 3> axes_b = {
        pose_b.transform_vector(Vec3(1, 0, 0)),
        pose_b.transform_vector(Vec3(0, 1, 0)),
        pose_b.transform_vector(Vec3(0, 0, 1))
    };

    Vec3 d = center_b - center_a;
    double min_overlap = std::numeric_limits<double>::max();
    Vec3 best_axis;

    // Проекция box на ось
    auto project_extent = [](const std::array<Vec3, 3>& axes, const Vec3& half, const Vec3& axis) {
        return std::abs(axes[0].dot(axis)) * half.x +
               std::abs(axes[1].dot(axis)) * half.y +
               std::abs(axes[2].dot(axis)) * half.z;
    };

    // Тест оси
    auto test_axis = [&](Vec3 axis) -> bool {
        double len = axis.norm();
        if (len < 1e-8) return true;  // Вырожденная ось
        axis = axis / len;

        double ext_a = project_extent(axes_a, half_a, axis);
        double ext_b = project_extent(axes_b, half_b, axis);
        double dist = std::abs(d.dot(axis));

        double overlap = ext_a + ext_b - dist;
        if (overlap < 0) return false;  // Разделяющая ось

        if (overlap < min_overlap) {
            min_overlap = overlap;
            // Нормаль направлена от A к B
            best_axis = (d.dot(axis) < 0) ? axis * (-1.0) : axis;
        }
        return true;
    };

    // 15 осей SAT
    for (int i = 0; i < 3; ++i) {
        if (!test_axis(axes_a[i])) return result;
        if (!test_axis(axes_b[i])) return result;
    }
    for (int i = 0; i < 3; ++i) {
        for (int j = 0; j < 3; ++j) {
            if (!test_axis(axes_a[i].cross(axes_b[j]))) return result;
        }
    }

    // Коллизия подтверждена — генерируем точки контакта
    result.colliding = true;

    // Собираем все проникающие вершины
    std::vector<ContactPoint> all_contacts;

    // Проверяем вершины box B, проникающие в box A
    Vec3 local_b[8] = {
        {-half_b.x, -half_b.y, -half_b.z}, {+half_b.x, -half_b.y, -half_b.z},
        {-half_b.x, +half_b.y, -half_b.z}, {+half_b.x, +half_b.y, -half_b.z},
        {-half_b.x, -half_b.y, +half_b.z}, {+half_b.x, -half_b.y, +half_b.z},
        {-half_b.x, +half_b.y, +half_b.z}, {+half_b.x, +half_b.y, +half_b.z}
    };

    for (int i = 0; i < 8; ++i) {
        Vec3 world_pt = pose_b.transform_point(local_b[i]);
        Vec3 local_in_a = pose_a.inverse_transform_point(world_pt);

        // Проверяем, внутри ли точка box A
        if (std::abs(local_in_a.x) <= half_a.x + 1e-6 &&
            std::abs(local_in_a.y) <= half_a.y + 1e-6 &&
            std::abs(local_in_a.z) <= half_a.z + 1e-6) {

            // Находим глубину проникновения по нормали
            double pen = best_axis.dot(center_a - world_pt) + 
                         project_extent(axes_a, half_a, best_axis);
            if (pen > 0) {
                all_contacts.push_back({world_pt, best_axis, pen});
            }
        }
    }

    // Проверяем вершины box A, проникающие в box B
    Vec3 local_a[8] = {
        {-half_a.x, -half_a.y, -half_a.z}, {+half_a.x, -half_a.y, -half_a.z},
        {-half_a.x, +half_a.y, -half_a.z}, {+half_a.x, +half_a.y, -half_a.z},
        {-half_a.x, -half_a.y, +half_a.z}, {+half_a.x, -half_a.y, +half_a.z},
        {-half_a.x, +half_a.y, +half_a.z}, {+half_a.x, +half_a.y, +half_a.z}
    };

    for (int i = 0; i < 8; ++i) {
        Vec3 world_pt = pose_a.transform_point(local_a[i]);
        Vec3 local_in_b = pose_b.inverse_transform_point(world_pt);

        // Проверяем, внутри ли точка box B
        if (std::abs(local_in_b.x) <= half_b.x + 1e-6 &&
            std::abs(local_in_b.y) <= half_b.y + 1e-6 &&
            std::abs(local_in_b.z) <= half_b.z + 1e-6) {

            double pen = best_axis.dot(center_b - world_pt) - 
                         project_extent(axes_b, half_b, best_axis);
            pen = -pen;  // Инвертируем для правильного знака
            if (pen > 0) {
                all_contacts.push_back({world_pt, best_axis, pen});
            }
        }
    }

    // Редукция манифолда до 4 точек (для стабильности)
    if (all_contacts.size() <= 4) {
        result.contacts = std::move(all_contacts);
    } else {
        // Выбираем 4 точки, максимально разнесённые друг от друга
        // 1. Находим среднюю точку
        Vec3 centroid;
        for (const auto& cp : all_contacts) {
            centroid += cp.point;
        }
        centroid = centroid * (1.0 / all_contacts.size());

        // 2. Находим точку, наиболее удалённую от центроида
        int idx0 = 0;
        double max_dist = 0;
        for (size_t i = 0; i < all_contacts.size(); ++i) {
            double d = (all_contacts[i].point - centroid).norm();
            if (d > max_dist) { max_dist = d; idx0 = i; }
        }

        // 3. Находим точку, наиболее удалённую от первой
        int idx1 = 0;
        max_dist = 0;
        for (size_t i = 0; i < all_contacts.size(); ++i) {
            if ((int)i == idx0) continue;
            double d = (all_contacts[i].point - all_contacts[idx0].point).norm();
            if (d > max_dist) { max_dist = d; idx1 = i; }
        }

        // 4. Находим точку с максимальным расстоянием от линии (idx0, idx1)
        Vec3 line_dir = (all_contacts[idx1].point - all_contacts[idx0].point);
        double line_len = line_dir.norm();
        if (line_len > 1e-10) line_dir = line_dir * (1.0 / line_len);

        int idx2 = 0;
        max_dist = 0;
        for (size_t i = 0; i < all_contacts.size(); ++i) {
            if ((int)i == idx0 || (int)i == idx1) continue;
            Vec3 v = all_contacts[i].point - all_contacts[idx0].point;
            Vec3 cross = v.cross(line_dir);
            double d = cross.norm();
            if (d > max_dist) { max_dist = d; idx2 = i; }
        }

        // 5. Находим четвёртую точку с противоположной стороны от плоскости
        Vec3 p0 = all_contacts[idx0].point;
        Vec3 p1 = all_contacts[idx1].point;
        Vec3 p2 = all_contacts[idx2].point;
        Vec3 plane_normal = (p1 - p0).cross(p2 - p0);
        double pn_len = plane_normal.norm();
        if (pn_len > 1e-10) plane_normal = plane_normal * (1.0 / pn_len);

        int idx3 = 0;
        double max_signed = -1e10;
        for (size_t i = 0; i < all_contacts.size(); ++i) {
            if ((int)i == idx0 || (int)i == idx1 || (int)i == idx2) continue;
            double d = std::abs((all_contacts[i].point - p0).dot(plane_normal));
            if (d > max_signed) { max_signed = d; idx3 = i; }
        }

        result.contacts.push_back(all_contacts[idx0]);
        result.contacts.push_back(all_contacts[idx1]);
        result.contacts.push_back(all_contacts[idx2]);
        if (idx3 != idx0 && idx3 != idx1 && idx3 != idx2) {
            result.contacts.push_back(all_contacts[idx3]);
        }
    }

    // Если не нашли контактных точек, добавляем одну в центре
    if (result.contacts.empty()) {
        result.contacts.push_back({
            (center_a + center_b) * 0.5,
            best_axis,
            min_overlap
        });
    }

    return result;
}

/**
 * Sphere vs Box.
 */
inline CollisionResult collide_sphere_box(
    const Vec3& sphere_center, double radius,
    const Vec3& half_size, const Pose3& box_pose
) {
    CollisionResult result;

    // Центр сферы в локальных координатах box'а
    Vec3 local = box_pose.inverse_transform_point(sphere_center);

    // Ближайшая точка на box
    Vec3 closest(
        std::clamp(local.x, -half_size.x, half_size.x),
        std::clamp(local.y, -half_size.y, half_size.y),
        std::clamp(local.z, -half_size.z, half_size.z)
    );

    Vec3 diff = local - closest;
    double dist = diff.norm();

    if (dist < radius) {
        result.colliding = true;
        Vec3 closest_world = box_pose.transform_point(closest);

        Vec3 normal;
        if (dist > 1e-10) {
            normal = (sphere_center - closest_world).normalized();
        } else {
            // Сфера внутри box'а — выталкиваем по ближайшей грани
            normal = (sphere_center - box_pose.lin).normalized();
        }

        result.contacts.push_back({
            closest_world,
            normal,
            radius - dist
        });
    }

    return result;
}

} // namespace physics
} // namespace termin
