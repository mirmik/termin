#pragma once

/**
 * @file collider.hpp
 * @brief Унифицированная система коллайдеров с поддержкой raycast и collision detection.
 */

#include "../geom/vec3.hpp"
#include "../geom/pose3.hpp"
#include "../geom/ray3.hpp"
#include <memory>
#include <cmath>
#include <algorithm>

namespace termin {
namespace colliders {

using geom::Vec3;
using geom::Pose3;
using geom::Ray3;

// ==================== Результаты запросов ====================

/**
 * Результат raycast запроса.
 */
struct RayHit {
    Vec3 point_on_collider;  // Ближайшая точка на коллайдере
    Vec3 point_on_ray;       // Ближайшая точка на луче
    double distance;         // Расстояние между точками (0 = пересечение)

    bool hit() const { return distance < 1e-8; }
};

/**
 * Результат запроса ближайших точек между коллайдерами.
 */
struct ColliderHit {
    Vec3 point_on_a;   // Ближайшая точка на первом коллайдере
    Vec3 point_on_b;   // Ближайшая точка на втором коллайдере
    Vec3 normal;       // Нормаль контакта (от A к B)
    double distance;   // Расстояние (отрицательное = пенетрация)

    bool colliding() const { return distance < 0; }
};

// ==================== Типы коллайдеров ====================

enum class ColliderType {
    Box,
    Sphere,
    Capsule
};

// ==================== Базовый класс коллайдера ====================

class Collider;
using ColliderPtr = std::shared_ptr<Collider>;

/**
 * Абстрактный базовый класс для всех коллайдеров.
 */
class Collider {
public:
    virtual ~Collider() = default;

    /**
     * Тип коллайдера.
     */
    virtual ColliderType type() const = 0;

    /**
     * Найти ближайшие точки между коллайдером и лучом.
     * Возвращает RayHit с distance=0 при пересечении.
     */
    virtual RayHit closest_to_ray(const Ray3& ray) const = 0;

    /**
     * Найти ближайшие точки между двумя коллайдерами.
     * Возвращает ColliderHit с отрицательным distance при пенетрации.
     */
    virtual ColliderHit closest_to_collider(const Collider& other) const = 0;

    /**
     * Создать копию коллайдера, трансформированную заданной позой.
     */
    virtual ColliderPtr transform_by(const Pose3& pose) const = 0;

    /**
     * Центр коллайдера в мировых координатах.
     */
    virtual Vec3 center() const = 0;

    // Методы для double dispatch (public для взаимного доступа между типами)
    virtual ColliderHit closest_to_box_impl(const class BoxCollider& box) const = 0;
    virtual ColliderHit closest_to_sphere_impl(const class SphereCollider& sphere) const = 0;
    virtual ColliderHit closest_to_capsule_impl(const class CapsuleCollider& capsule) const = 0;
};

} // namespace colliders
} // namespace termin
