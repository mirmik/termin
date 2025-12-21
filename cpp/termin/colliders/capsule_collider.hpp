#pragma once

#include "collider.hpp"
#include "box_collider.hpp"
#include "sphere_collider.hpp"
#include <cmath>
#include <algorithm>
#include <optional>

namespace termin {
namespace colliders {

/**
 * Capsule collider — капсула (цилиндр с полусферами на концах).
 */
class CapsuleCollider : public Collider {
public:
    Vec3 local_a;   // Первая точка оси в локальных координатах
    Vec3 local_b;   // Вторая точка оси в локальных координатах
    double radius;
    Pose3 pose;     // Поза в мировых координатах

    CapsuleCollider()
        : local_a(0, 0, -0.5), local_b(0, 0, 0.5), radius(0.25), pose() {}

    CapsuleCollider(const Vec3& a, const Vec3& b, double radius, const Pose3& pose = Pose3())
        : local_a(a), local_b(b), radius(radius), pose(pose) {}

    // ==================== Интерфейс Collider ====================

    ColliderType type() const override { return ColliderType::Capsule; }

    Vec3 center() const override {
        Vec3 local_center = (local_a + local_b) * 0.5;
        return pose.transform_point(local_center);
    }

    AABB aabb() const override {
        Vec3 a = world_a();
        Vec3 b = world_b();
        Vec3 r(radius, radius, radius);
        Vec3 min_pt(std::min(a.x, b.x), std::min(a.y, b.y), std::min(a.z, b.z));
        Vec3 max_pt(std::max(a.x, b.x), std::max(a.y, b.y), std::max(a.z, b.z));
        return AABB(min_pt - r, max_pt + r);
    }

    /**
     * Концы капсулы в мировых координатах.
     */
    Vec3 world_a() const { return pose.transform_point(local_a); }
    Vec3 world_b() const { return pose.transform_point(local_b); }

    RayHit closest_to_ray(const Ray3& ray) const override;
    ColliderHit closest_to_collider(const Collider& other) const override;
    ColliderPtr transform_by(const Pose3& t) const override;

    // Double dispatch implementations
    ColliderHit closest_to_box_impl(const BoxCollider& box) const override;
    ColliderHit closest_to_sphere_impl(const SphereCollider& sphere) const override;
    ColliderHit closest_to_capsule_impl(const CapsuleCollider& capsule) const override;

private:
    /**
     * Ближайшие точки между двумя отрезками.
     */
    static void closest_points_segments(
        const Vec3& a1, const Vec3& b1,
        const Vec3& a2, const Vec3& b2,
        Vec3& p1, Vec3& p2
    );

    /**
     * Проекция точки на отрезок [A, B], возвращает параметр t ∈ [0, 1].
     */
    static double project_to_segment(const Vec3& p, const Vec3& a, const Vec3& b);

    /**
     * Пересечение луча со сферой, возвращает t или nullopt.
     */
    static std::optional<double> sphere_ray_hit(
        const Vec3& center, double r,
        const Vec3& origin, const Vec3& dir
    );
};

// ==================== Реализация методов ====================

inline ColliderPtr CapsuleCollider::transform_by(const Pose3& t) const {
    return std::make_shared<CapsuleCollider>(local_a, local_b, radius, t * pose);
}

inline double CapsuleCollider::project_to_segment(const Vec3& p, const Vec3& a, const Vec3& b) {
    Vec3 ab = b - a;
    double len_sq = ab.dot(ab);
    if (len_sq < 1e-16) return 0.0;
    double t = (p - a).dot(ab) / len_sq;
    return std::clamp(t, 0.0, 1.0);
}

inline void CapsuleCollider::closest_points_segments(
    const Vec3& a1, const Vec3& b1,
    const Vec3& a2, const Vec3& b2,
    Vec3& p1, Vec3& p2
) {
    Vec3 d1 = b1 - a1;
    Vec3 d2 = b2 - a2;
    Vec3 r = a1 - a2;

    double a = d1.dot(d1);
    double e = d2.dot(d2);
    double f = d2.dot(r);

    double s = 0, t = 0;

    if (a < 1e-10 && e < 1e-10) {
        // Оба отрезка вырождены в точки
        p1 = a1;
        p2 = a2;
        return;
    }

    if (a < 1e-10) {
        // Первый отрезок вырожден
        s = 0;
        t = std::clamp(f / e, 0.0, 1.0);
    } else {
        double c = d1.dot(r);
        if (e < 1e-10) {
            // Второй отрезок вырожден
            t = 0;
            s = std::clamp(-c / a, 0.0, 1.0);
        } else {
            double b = d1.dot(d2);
            double denom = a * e - b * b;

            if (std::abs(denom) > 1e-10) {
                s = std::clamp((b * f - c * e) / denom, 0.0, 1.0);
            } else {
                s = 0;
            }

            t = (b * s + f) / e;

            if (t < 0) {
                t = 0;
                s = std::clamp(-c / a, 0.0, 1.0);
            } else if (t > 1) {
                t = 1;
                s = std::clamp((b - c) / a, 0.0, 1.0);
            }
        }
    }

    p1 = a1 + d1 * s;
    p2 = a2 + d2 * t;
}

inline std::optional<double> CapsuleCollider::sphere_ray_hit(
    const Vec3& center, double r,
    const Vec3& origin, const Vec3& dir
) {
    Vec3 m = origin - center;
    double b = m.dot(dir);
    double c = m.dot(m) - r * r;
    double disc = b * b - c;

    if (disc < 0) return std::nullopt;

    double sqrt_disc = std::sqrt(disc);
    double t0 = -b - sqrt_disc;
    if (t0 >= 0) return t0;

    double t1 = -b + sqrt_disc;
    if (t1 >= 0) return t1;

    return std::nullopt;
}

inline RayHit CapsuleCollider::closest_to_ray(const Ray3& ray) const {
    RayHit result;

    Vec3 A = world_a();
    Vec3 B = world_b();
    Vec3 O = ray.origin;
    Vec3 D = ray.direction;

    Vec3 axis = B - A;
    double length = axis.norm();

    // Вырожденная капсула → сфера
    if (length < 1e-10) {
        SphereCollider sphere(A, radius);
        return sphere.closest_to_ray(ray);
    }

    Vec3 U = axis / length;

    // Проверка: луч внутри капсулы?
    double proj0 = (O - A).dot(U);
    Vec3 closest_axis_pt = A + U * std::clamp(proj0, 0.0, length);
    double dist_axis0 = (O - closest_axis_pt).norm();
    if (dist_axis0 <= radius + 1e-8) {
        result.point_on_collider = O;
        result.point_on_ray = O;
        result.distance = 0.0;
        return result;
    }

    std::vector<double> t_candidates;

    // 1. Пересечение с цилиндрической частью
    Vec3 w = O - A;
    double w_par = w.dot(U);
    Vec3 w_perp = w - U * w_par;
    double D_par = D.dot(U);
    Vec3 D_perp = D - U * D_par;

    double a = D_perp.dot(D_perp);
    double b = 2.0 * D_perp.dot(w_perp);
    double c = w_perp.dot(w_perp) - radius * radius;

    if (a > 1e-12) {
        double disc = b * b - 4.0 * a * c;
        if (disc >= 0) {
            double sqrt_disc = std::sqrt(disc);
            double t0 = (-b - sqrt_disc) / (2.0 * a);
            double t1 = (-b + sqrt_disc) / (2.0 * a);

            for (double t : {t0, t1}) {
                if (t < 0) continue;
                double s = w_par + t * D_par;  // параметр вдоль оси
                if (s >= 0 && s <= length) {
                    t_candidates.push_back(t);
                }
            }
        }
    }

    // 2. Пересечение со сферическими концами
    auto t_sphere_a = sphere_ray_hit(A, radius, O, D);
    if (t_sphere_a) t_candidates.push_back(*t_sphere_a);

    auto t_sphere_b = sphere_ray_hit(B, radius, O, D);
    if (t_sphere_b) t_candidates.push_back(*t_sphere_b);

    // Есть пересечение?
    if (!t_candidates.empty()) {
        double t_hit = *std::min_element(t_candidates.begin(), t_candidates.end());
        Vec3 p_hit = ray.point_at(t_hit);
        result.point_on_ray = p_hit;
        result.point_on_collider = p_hit;
        result.distance = 0.0;
        return result;
    }

    // Нет пересечения — ближайшие точки между лучом и осью капсулы
    const double FAR = 1e6;
    Vec3 ray_end = O + D * FAR;

    Vec3 p_seg, p_ray_seg;
    closest_points_segments(A, B, O, ray_end, p_seg, p_ray_seg);

    Vec3 dir_vec = p_ray_seg - p_seg;
    double n = dir_vec.norm();

    if (n > 1e-10) {
        result.point_on_collider = p_seg + dir_vec * (radius / n);
    } else {
        // Луч параллелен оси
        Vec3 normal = U.cross(Vec3(1, 0, 0));
        if (normal.norm() < 1e-8) {
            normal = U.cross(Vec3(0, 1, 0));
        }
        normal = normal.normalized();
        result.point_on_collider = p_seg + normal * radius;
    }

    result.point_on_ray = p_ray_seg;
    result.distance = (result.point_on_collider - p_ray_seg).norm();

    return result;
}

// closest_to_collider определён в colliders.hpp после всех типов

inline ColliderHit CapsuleCollider::closest_to_sphere_impl(const SphereCollider& sphere) const {
    ColliderHit result;

    Vec3 A = world_a();
    Vec3 B = world_b();
    Vec3 C = sphere.center();

    // Проекция центра сферы на ось капсулы
    double t = project_to_segment(C, A, B);
    Vec3 closest_on_axis = A + (B - A) * t;

    Vec3 diff = C - closest_on_axis;
    double dist = diff.norm();

    if (dist > 1e-10) {
        result.normal = diff / dist;
    } else {
        result.normal = Vec3(0, 0, 1);
    }

    result.point_on_a = closest_on_axis + result.normal * radius;
    result.point_on_b = C - result.normal * sphere.radius;
    result.distance = dist - radius - sphere.radius;

    return result;
}

inline ColliderHit CapsuleCollider::closest_to_capsule_impl(const CapsuleCollider& other) const {
    ColliderHit result;

    Vec3 a1 = world_a(), b1 = world_b();
    Vec3 a2 = other.world_a(), b2 = other.world_b();

    Vec3 p1, p2;
    closest_points_segments(a1, b1, a2, b2, p1, p2);

    Vec3 diff = p2 - p1;
    double dist = diff.norm();

    if (dist > 1e-10) {
        result.normal = diff / dist;
    } else {
        result.normal = Vec3(0, 0, 1);
    }

    result.point_on_a = p1 + result.normal * radius;
    result.point_on_b = p2 - result.normal * other.radius;
    result.distance = dist - radius - other.radius;

    return result;
}

inline ColliderHit CapsuleCollider::closest_to_box_impl(const BoxCollider& box) const {
    ColliderHit result;

    // Переносим капсулу в локальные координаты box'а
    Vec3 A = box.pose.inverse_transform_point(world_a());
    Vec3 B = box.pose.inverse_transform_point(world_b());

    Vec3 box_min = box.local_center - box.half_size;
    Vec3 box_max = box.local_center + box.half_size;

    // Ближайшая точка на оси капсулы
    // Для каждой точки на оси ищем ближайшую точку на box
    // Это сложная задача, используем приближение

    // Тестируем несколько точек на оси капсулы
    double best_dist = std::numeric_limits<double>::max();
    Vec3 best_axis_pt, best_box_pt;

    for (int i = 0; i <= 10; ++i) {
        double t = i / 10.0;
        Vec3 axis_pt = A + (B - A) * t;

        // Clamp to box
        Vec3 box_pt(
            std::clamp(axis_pt.x, box_min.x, box_max.x),
            std::clamp(axis_pt.y, box_min.y, box_max.y),
            std::clamp(axis_pt.z, box_min.z, box_max.z)
        );

        double dist = (axis_pt - box_pt).norm();
        if (dist < best_dist) {
            best_dist = dist;
            best_axis_pt = axis_pt;
            best_box_pt = box_pt;
        }
    }

    // Также проверяем проекцию ближайшей точки box на ось
    Vec3 closest_box_world = box.pose.transform_point(best_box_pt);
    double t = project_to_segment(box.pose.inverse_transform_point(closest_box_world), A, B);
    Vec3 axis_pt = A + (B - A) * t;

    Vec3 box_pt(
        std::clamp(axis_pt.x, box_min.x, box_max.x),
        std::clamp(axis_pt.y, box_min.y, box_max.y),
        std::clamp(axis_pt.z, box_min.z, box_max.z)
    );

    double dist = (axis_pt - box_pt).norm();
    if (dist < best_dist) {
        best_dist = dist;
        best_axis_pt = axis_pt;
        best_box_pt = box_pt;
    }

    // Переводим обратно в мировые координаты
    Vec3 world_axis_pt = box.pose.transform_point(best_axis_pt);
    Vec3 world_box_pt = box.pose.transform_point(best_box_pt);

    Vec3 diff = world_box_pt - world_axis_pt;
    double d = diff.norm();

    if (d > 1e-10) {
        result.normal = diff / d;
    } else {
        result.normal = (world_box_pt - box.center()).normalized();
    }

    result.point_on_a = world_axis_pt + result.normal * radius;
    result.point_on_b = world_box_pt;
    result.distance = d - radius;

    return result;
}

// BoxCollider::closest_to_capsule_impl определён здесь
inline ColliderHit BoxCollider::closest_to_capsule_impl(const CapsuleCollider& capsule) const {
    ColliderHit hit = capsule.closest_to_box_impl(*this);
    std::swap(hit.point_on_a, hit.point_on_b);
    hit.normal = hit.normal * (-1.0);
    return hit;
}

// SphereCollider::closest_to_capsule_impl определён здесь
inline ColliderHit SphereCollider::closest_to_capsule_impl(const CapsuleCollider& capsule) const {
    ColliderHit hit = capsule.closest_to_sphere_impl(*this);
    std::swap(hit.point_on_a, hit.point_on_b);
    hit.normal = hit.normal * (-1.0);
    return hit;
}

} // namespace colliders
} // namespace termin
