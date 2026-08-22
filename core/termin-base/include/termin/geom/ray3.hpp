#pragma once

#include "vec3.hpp"

#include <cmath>
#include <cstddef>
#include <type_traits>

namespace termin {

    using Ray3 = ::tc_ray3;

    static_assert(std::is_same<Ray3, ::tc_ray3>::value, "termin::Ray3 must alias tc_ray3");
    static_assert(std::is_standard_layout<Ray3>::value, "Ray3 must stay ABI-friendly");
    static_assert(std::is_trivially_copyable<Ray3>::value, "Ray3 must stay trivially copyable");
    static_assert(sizeof(Ray3) == sizeof(Vec3) * 2, "Ray3 must stay a packed origin/direction pair");
    static_assert(alignof(Ray3) == alignof(Vec3), "Ray3 alignment must match Vec3");
    static_assert(offsetof(Ray3, origin) == 0, "Ray3.origin offset changed");
    static_assert(offsetof(Ray3, direction) == sizeof(Vec3), "Ray3.direction offset changed");

    // Intersects a ray with a plane defined by one point and a normal. When
    // forward_only is true, intersections behind the ray origin are rejected.
    // Any failure leaves out_point unchanged.
    [[nodiscard]] inline bool try_intersect_ray_plane(const Ray3& ray,
                                                      const Vec3& plane_origin,
                                                      const Vec3& plane_normal,
                                                      Vec3& out_point,
                                                      bool forward_only,
                                                      double epsilon = 1.0e-10) noexcept {
        if (!ray.origin.is_finite() || !plane_origin.is_finite() || !std::isfinite(epsilon) || epsilon < 0.0) {
            return false;
        }

        Vec3 direction;
        Vec3 normal;
        if (!ray.direction.try_normalized(direction, epsilon) || !plane_normal.try_normalized(normal, epsilon)) {
            return false;
        }

        const Vec3 plane_offset = plane_origin - ray.origin;
        if (!plane_offset.is_finite()) {
            return false;
        }
        const double denominator = direction.dot(normal);
        const double numerator = plane_offset.dot(normal);
        if (!std::isfinite(denominator) || !std::isfinite(numerator) || std::abs(denominator) <= epsilon) {
            return false;
        }

        const double distance = numerator / denominator;
        if (!std::isfinite(distance) || (forward_only && distance < 0.0)) {
            return false;
        }
        const Vec3 point = ray.origin + direction * distance;
        if (!point.is_finite()) {
            return false;
        }
        out_point = point;
        return true;
    }

} // namespace termin
