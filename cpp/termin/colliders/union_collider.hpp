#pragma once

/**
 * @file union_collider.hpp
 * @brief Коллайдер, объединяющий несколько коллайдеров.
 */

#include "collider.hpp"
#include <vector>
#include <limits>

namespace termin {
namespace colliders {


/**
 * Коллайдер, представляющий объединение нескольких коллайдеров.
 * Запросы находят ближайший результат среди всех содержащихся коллайдеров.
 */
class UnionCollider : public Collider {
public:
    std::vector<Collider*> colliders_;
    std::vector<ColliderPtr> owned_colliders_;  // Для владения трансформированными коллайдерами

    UnionCollider() = default;

    explicit UnionCollider(std::vector<Collider*> colliders)
        : colliders_(std::move(colliders))
    {}

    const std::vector<Collider*>& colliders() const { return colliders_; }
    void add(Collider* c) { colliders_.push_back(c); }
    void clear() { colliders_.clear(); }

    ColliderType type() const override {
        if (!colliders_.empty()) {
            return colliders_[0]->type();
        }
        return ColliderType::Box;
    }

    Vec3 center() const override {
        if (colliders_.empty()) return Vec3();

        Vec3 sum;
        for (const auto* c : colliders_) {
            Vec3 cc = c->center();
            sum.x += cc.x;
            sum.y += cc.y;
            sum.z += cc.z;
        }
        double n = static_cast<double>(colliders_.size());
        return Vec3{sum.x / n, sum.y / n, sum.z / n};
    }

    AABB aabb() const override {
        if (colliders_.empty()) {
            return AABB(Vec3(), Vec3());
        }

        AABB result = colliders_[0]->aabb();
        for (size_t i = 1; i < colliders_.size(); ++i) {
            result = result.merge(colliders_[i]->aabb());
        }
        return result;
    }

    RayHit closest_to_ray(const Ray3& ray) const override {
        RayHit best;
        best.distance = std::numeric_limits<double>::infinity();

        for (const auto* c : colliders_) {
            RayHit hit = c->closest_to_ray(ray);
            if (hit.distance < best.distance) {
                best = hit;
            }
        }
        return best;
    }

    ColliderHit closest_to_collider(const Collider& other) const override {
        ColliderHit best;
        best.distance = std::numeric_limits<double>::infinity();

        const UnionCollider* other_union = dynamic_cast<const UnionCollider*>(&other);

        for (const auto* c : colliders_) {
            if (other_union != nullptr) {
                for (const auto* oc : other_union->colliders_) {
                    ColliderHit hit = c->closest_to_collider(*oc);
                    if (hit.distance < best.distance) {
                        best = hit;
                    }
                }
            } else {
                ColliderHit hit = c->closest_to_collider(other);
                if (hit.distance < best.distance) {
                    best = hit;
                }
            }
        }
        return best;
    }

    ColliderHit closest_to_box_impl(const BoxCollider& box) const override {
        ColliderHit best;
        best.distance = std::numeric_limits<double>::infinity();
        for (const auto* c : colliders_) {
            ColliderHit hit = c->closest_to_box_impl(box);
            if (hit.distance < best.distance) {
                best = hit;
            }
        }
        return best;
    }

    ColliderHit closest_to_sphere_impl(const SphereCollider& sphere) const override {
        ColliderHit best;
        best.distance = std::numeric_limits<double>::infinity();
        for (const auto* c : colliders_) {
            ColliderHit hit = c->closest_to_sphere_impl(sphere);
            if (hit.distance < best.distance) {
                best = hit;
            }
        }
        return best;
    }

    ColliderHit closest_to_capsule_impl(const CapsuleCollider& capsule) const override {
        ColliderHit best;
        best.distance = std::numeric_limits<double>::infinity();
        for (const auto* c : colliders_) {
            ColliderHit hit = c->closest_to_capsule_impl(capsule);
            if (hit.distance < best.distance) {
                best = hit;
            }
        }
        return best;
    }
};

} // namespace colliders
} // namespace termin
