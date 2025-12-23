#pragma once

/**
 * @file collider.hpp
 * @brief Базовый интерфейс коллайдера.
 *
 * Collider — абстрактный интерфейс для всех типов коллайдеров:
 * - ColliderPrimitive (Box, Sphere, Capsule, будущий Mesh)
 * - AttachedCollider (привязка к GeneralTransform3)
 * - UnionCollider (объединение нескольких коллайдеров)
 */

#include "../geom/vec3.hpp"
#include "../geom/ray3.hpp"
#include "../geom/aabb.hpp"
#include <memory>

namespace termin {
namespace colliders {


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

// ==================== Forward declarations ====================

class Collider;
class BoxCollider;
class SphereCollider;
class CapsuleCollider;

using ColliderPtr = std::shared_ptr<Collider>;

// ==================== Базовый интерфейс ====================

/**
 * Абстрактный интерфейс для всех коллайдеров.
 *
 * Наследники:
 * - ColliderPrimitive: базовый класс для геометрических примитивов
 * - AttachedCollider: привязка к GeneralTransform3
 * - UnionCollider: объединение нескольких коллайдеров
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
     * Центр коллайдера в мировых координатах.
     */
    virtual Vec3 center() const = 0;

    /**
     * Axis-aligned bounding box в мировых координатах.
     */
    virtual AABB aabb() const = 0;

    // Double dispatch для коллизий между примитивами
    virtual ColliderHit closest_to_box_impl(const BoxCollider& box) const = 0;
    virtual ColliderHit closest_to_sphere_impl(const SphereCollider& sphere) const = 0;
    virtual ColliderHit closest_to_capsule_impl(const CapsuleCollider& capsule) const = 0;
};

} // namespace colliders
} // namespace termin
