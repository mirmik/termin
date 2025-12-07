#pragma once

#include "../geom/vec3.hpp"
#include "../geom/pose3.hpp"
#include <cmath>
#include <algorithm>
#include <array>

namespace termin {
namespace colliders {

using geom::Vec3;
using geom::Pose3;
using geom::Quat;

/**
 * Результат проверки коллизии.
 */
struct CollisionResult {
    Vec3 point;       // Точка контакта
    Vec3 normal;      // Нормаль (от A к B)
    double distance;  // Расстояние (отрицательное = пенетрация)
    bool colliding;   // Есть ли коллизия
};

/**
 * Box collider с поддержкой SAT collision detection.
 */
class BoxCollider {
public:
    Vec3 center;      // Центр в локальных координатах
    Vec3 half_size;   // Половинные размеры
    Pose3 pose;       // Поза в мировых координатах

    BoxCollider()
        : center(0, 0, 0), half_size(0.5, 0.5, 0.5), pose() {}

    BoxCollider(const Vec3& center, const Vec3& half_size, const Pose3& pose = Pose3())
        : center(center), half_size(half_size), pose(pose) {}

    // Создать из полного размера
    static BoxCollider from_size(const Vec3& center, const Vec3& size, const Pose3& pose = Pose3()) {
        return BoxCollider(center, Vec3(size.x/2, size.y/2, size.z/2), pose);
    }

    // Трансформировать коллайдер
    BoxCollider transform_by(const Pose3& t) const {
        return BoxCollider(center, half_size, t * pose);
    }

    // Центр в мировых координатах
    Vec3 world_center() const {
        return pose.transform_point(center);
    }

    // Получить 8 вершин в мировых координатах
    std::array<Vec3, 8> get_corners_world() const {
        std::array<Vec3, 8> corners;
        Vec3 c = center;
        Vec3 h = half_size;

        // 8 вершин куба
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

    // Получить 3 оси (нормали граней) в мировых координатах
    std::array<Vec3, 3> get_axes_world() const {
        return {
            pose.transform_vector(Vec3(1, 0, 0)),
            pose.transform_vector(Vec3(0, 1, 0)),
            pose.transform_vector(Vec3(0, 0, 1))
        };
    }

    /**
     * SAT collision detection между двумя box collider'ами.
     */
    CollisionResult collide_box(const BoxCollider& other) const {
        CollisionResult result;
        result.colliding = false;
        result.distance = std::numeric_limits<double>::max();

        Vec3 center_a = world_center();
        Vec3 center_b = other.world_center();

        auto axes_a = get_axes_world();
        auto axes_b = other.get_axes_world();

        Vec3 d = center_b - center_a;

        double min_overlap = std::numeric_limits<double>::max();
        Vec3 best_axis;

        // Lambda для проекции box на ось
        auto project_box = [](const Vec3& center, const std::array<Vec3, 3>& axes,
                             const Vec3& half, const Vec3& axis) -> std::pair<double, double> {
            double c_proj = center.dot(axis);
            double r = std::abs(axes[0].dot(axis)) * half.x +
                      std::abs(axes[1].dot(axis)) * half.y +
                      std::abs(axes[2].dot(axis)) * half.z;
            return {c_proj - r, c_proj + r};
        };

        // Lambda для тестирования оси
        auto test_axis = [&](Vec3 axis) -> bool {
            double length = axis.norm();
            if (length < 1e-8) return true;  // Degenerate axis

            axis = axis / length;

            auto [min_a, max_a] = project_box(center_a, axes_a, half_size, axis);
            auto [min_b, max_b] = project_box(center_b, axes_b, other.half_size, axis);

            // Проверка на разделяющую ось
            if (max_a < min_b || max_b < min_a) {
                return false;  // Separating axis found
            }

            // Вычисление overlap
            double overlap = std::min(max_a, max_b) - std::max(min_a, min_b);
            if (overlap < min_overlap) {
                min_overlap = overlap;
                // Направление от A к B
                if (d.dot(axis) < 0) {
                    axis = axis * (-1.0);
                }
                best_axis = axis;
            }
            return true;
        };

        // Тест 3 осей box A
        for (int i = 0; i < 3; ++i) {
            if (!test_axis(axes_a[i])) {
                // Separating axis - no collision
                result.distance = 0.01;  // Approximate
                return result;
            }
        }

        // Тест 3 осей box B
        for (int i = 0; i < 3; ++i) {
            if (!test_axis(axes_b[i])) {
                result.distance = 0.01;
                return result;
            }
        }

        // Тест 9 cross product осей
        for (int i = 0; i < 3; ++i) {
            for (int j = 0; j < 3; ++j) {
                Vec3 cross = axes_a[i].cross(axes_b[j]);
                if (!test_axis(cross)) {
                    result.distance = 0.01;
                    return result;
                }
            }
        }

        // Коллизия обнаружена
        result.colliding = true;
        result.distance = -min_overlap;  // Отрицательное = пенетрация
        result.normal = best_axis;
        result.point = (center_a + center_b) * 0.5;  // Approximate contact point

        return result;
    }

    /**
     * Проверка коллизии с плоскостью земли (z = ground_height).
     * Возвращает вектор контактов (до 8 вершин могут касаться).
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
};

} // namespace colliders
} // namespace termin
