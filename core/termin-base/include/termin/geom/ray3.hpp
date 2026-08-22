#pragma once

#include "vec3.hpp"

#include <algorithm>
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

    /**
     * Semantic result of a two-sided ray/triangle intersection.
     *
     * ray_parameter is t in origin + direction * t, so the intersection point
     * is exactly ray.point_at(ray_parameter). It is a metric distance when
     * ray.direction is a unit vector. barycentric stores the weights for
     * vertices (a, b, c), and normal is the finite unit normal defined by
     * their winding.
     */
    struct RayTriangleHit {
        double ray_parameter = 0.0;
        Vec3 barycentric{};
        Vec3 normal{};
    };

    static_assert(std::is_standard_layout<RayTriangleHit>::value, "RayTriangleHit must stay ABI-friendly");
    static_assert(std::is_trivially_copyable<RayTriangleHit>::value, "RayTriangleHit must stay trivially copyable");

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

    /**
     * Intersect a ray with the closed triangle (a, b, c), without back-face culling.
     *
     * epsilon is dimensionless. It controls scale-relative triangle
     * degeneracy, angular parallelism, closed-edge barycentric tolerance, and
     * representability of the original ray parameter; it is deliberately not
     * a minimum hit distance. Uniformly scaling the triangle therefore does
     * not change the validity decision.
     * Accepted boundary slack is snapped back onto the closed barycentric
     * simplex. When forward_only is true, intersections with t < 0 are
     * rejected while t == 0 remains a hit. Any failure leaves out_hit
     * unchanged.
     */
    [[nodiscard]] inline bool try_intersect_ray_triangle(const Ray3& ray,
                                                         const Vec3& a,
                                                         const Vec3& b,
                                                         const Vec3& c,
                                                         RayTriangleHit& out_hit,
                                                         bool forward_only = true,
                                                         double epsilon = 1.0e-10) noexcept {
        if (!ray.origin.is_finite() || !ray.direction.is_finite() || !a.is_finite() || !b.is_finite() ||
            !c.is_finite() || !std::isfinite(epsilon) || epsilon < 0.0) {
            return false;
        }

        const double direction_length = std::hypot(ray.direction.x, ray.direction.y, ray.direction.z);
        if (!std::isfinite(direction_length) || direction_length <= 0.0) {
            return false;
        }
        const Vec3 direction = ray.direction / direction_length;

        const Vec3 edge1 = b - a;
        const Vec3 edge2 = c - a;
        const Vec3 edge3 = c - b;
        if (!edge1.is_finite() || !edge2.is_finite() || !edge3.is_finite()) {
            return false;
        }
        const double edge1_length = std::hypot(edge1.x, edge1.y, edge1.z);
        const double edge2_length = std::hypot(edge2.x, edge2.y, edge2.z);
        const double edge3_length = std::hypot(edge3.x, edge3.y, edge3.z);
        const double edge_scale = std::max({edge1_length, edge2_length, edge3_length});
        if (!std::isfinite(edge_scale) || edge_scale <= 0.0) {
            return false;
        }

        const Vec3 scaled_edge1 = edge1 / edge_scale;
        const Vec3 scaled_edge2 = edge2 / edge_scale;
        const Vec3 scaled_area_vector = scaled_edge1.cross(scaled_edge2);
        const double scaled_double_area = std::hypot(scaled_area_vector.x, scaled_area_vector.y, scaled_area_vector.z);
        if (!std::isfinite(scaled_double_area) || scaled_double_area <= epsilon) {
            return false;
        }
        const Vec3 normal = scaled_area_vector / scaled_double_area;

        const Vec3 p = direction.cross(scaled_edge2);
        const double determinant = scaled_edge1.dot(p);
        if (!std::isfinite(determinant) || std::abs(determinant) <= epsilon * scaled_double_area) {
            return false;
        }
        const double inverse_determinant = 1.0 / determinant;

        const Vec3 offset = ray.origin - a;
        if (!offset.is_finite()) {
            return false;
        }
        const Vec3 scaled_offset = offset / edge_scale;
        if (!scaled_offset.is_finite()) {
            return false;
        }
        const double u = scaled_offset.dot(p) * inverse_determinant;
        const Vec3 q = scaled_offset.cross(scaled_edge1);
        const double v = direction.dot(q) * inverse_determinant;
        const double w = 1.0 - u - v;
        const double metric_distance = edge_scale * scaled_edge2.dot(q) * inverse_determinant;
        const double ray_parameter = metric_distance / direction_length;
        if (!std::isfinite(u) || !std::isfinite(v) || !std::isfinite(w) || !std::isfinite(ray_parameter) ||
            (metric_distance != 0.0 && ray_parameter == 0.0) || u < -epsilon || u > 1.0 + epsilon || v < -epsilon ||
            v > 1.0 + epsilon || w < -epsilon || w > 1.0 + epsilon || (forward_only && ray_parameter < 0.0)) {
            return false;
        }

        Vec3 barycentric{
            std::clamp(w, 0.0, 1.0),
            std::clamp(u, 0.0, 1.0),
            std::clamp(v, 0.0, 1.0),
        };
        const double barycentric_sum = barycentric.x + barycentric.y + barycentric.z;
        if (!std::isfinite(barycentric_sum) || barycentric_sum <= 0.0) {
            return false;
        }
        barycentric /= barycentric_sum;

        const double canonical_parameter = ray_parameter == 0.0 ? 0.0 : ray_parameter;
        const Vec3 parameterized_displacement = ray.direction * canonical_parameter;
        const Vec3 metric_displacement = direction * metric_distance;
        const Vec3 displacement_error = parameterized_displacement - metric_displacement;
        if (!parameterized_displacement.is_finite() || !metric_displacement.is_finite() ||
            !displacement_error.is_finite()) {
            return false;
        }
        const double relative_displacement_error =
            std::hypot(displacement_error.x, displacement_error.y, displacement_error.z) / edge_scale;
        if (!std::isfinite(relative_displacement_error) || relative_displacement_error > epsilon) {
            return false;
        }
        const Vec3 point = ray.point_at(canonical_parameter);
        if (!point.is_finite()) {
            return false;
        }

        out_hit = RayTriangleHit{canonical_parameter, barycentric, normal};
        return true;
    }

} // namespace termin
