#pragma once

/**
 * @file collider_primitive.hpp
 * @brief Базовый класс для геометрических примитивов-коллайдеров.
 *
 * ColliderPrimitive содержит GeneralPose3 transform, который включает:
 * - lin: позиция центра
 * - ang: ориентация
 * - scale: масштаб (интерпретация зависит от типа примитива)
 *
 * Каждый примитив сам решает, как интерпретировать scale:
 * - BoxCollider: полный non-uniform scale
 * - SphereCollider: uniform scale (min компонент)
 * - CapsuleCollider: scale.z для высоты, min(scale.x, scale.y) для радиуса
 */

#include "collider.hpp"
#include "../geom/general_pose3.hpp"

namespace termin {
namespace colliders {

using geom::GeneralPose3;
using geom::Pose3;

/**
 * Базовый класс для геометрических примитивов.
 *
 * Хранит GeneralPose3 transform, который задаёт позицию, ориентацию и масштаб.
 */
class ColliderPrimitive : public Collider {
public:
    GeneralPose3 transform;

    ColliderPrimitive() : transform() {}
    explicit ColliderPrimitive(const GeneralPose3& t) : transform(t) {}

    /**
     * Центр коллайдера = transform.lin
     */
    Vec3 center() const override {
        return transform.lin;
    }

    /**
     * Uniform scale — минимальный компонент scale.
     * Используется для Sphere и радиуса Capsule.
     */
    double uniform_scale() const {
        return std::min({transform.scale.x, transform.scale.y, transform.scale.z});
    }

    /**
     * Создать Pose3 из transform (без scale).
     * Используется для внутренних вычислений.
     */
    Pose3 pose() const {
        return transform.to_pose3();
    }
};

} // namespace colliders
} // namespace termin
