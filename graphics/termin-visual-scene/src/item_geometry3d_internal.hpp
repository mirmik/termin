#pragma once

#include <cmath>
#include <cstdint>
#include <optional>
#include <span>

#include <termin/geom/aabb.hpp>
#include <termin/geom/color.hpp>

#include "termin_visual_scene/scene3d.hpp"

namespace termin::visual::detail {

    inline bool finite(termin::LinearColor value) {
        return std::isfinite(value.r) && std::isfinite(value.g) && std::isfinite(value.b) && std::isfinite(value.a);
    }

    inline VisualBounds3D to_visual_bounds(const termin::AABB& bounds) {
        return {bounds.min_point, bounds.max_point};
    }

    template <typename Position> std::optional<termin::AABB> bounds_of(std::size_t count, Position&& position) {
        if (count == 0)
            return std::nullopt;
        const termin::Vec3 first = position(0).to_double();
        termin::AABB result{first, first};
        for (std::size_t index = 1; index < count; ++index) {
            result.extend(position(index).to_double());
        }
        return result;
    }

    inline std::optional<double> ray_triangle(tc_ray3 ray, termin::Vec3f af, termin::Vec3f bf, termin::Vec3f cf) {
        termin::RayTriangleHit hit;
        if (!termin::try_intersect_ray_triangle(
                ray, af.to_double(), bf.to_double(), cf.to_double(), hit, true, 1.0e-12) ||
            hit.ray_parameter <= 0.0) {
            return std::nullopt;
        }
        return hit.ray_parameter;
    }

    template <typename Position>
    std::optional<HitCandidate3D> ray_triangles(tc_ray3 ray,
                                                std::size_t vertex_count,
                                                std::span<const std::uint32_t> triangles,
                                                std::span<const std::uint64_t> parts,
                                                Position&& position) {
        std::optional<HitCandidate3D> nearest;
        for (std::size_t triangle = 0; triangle < triangles.size() / 3; ++triangle) {
            const std::uint32_t i0 = triangles[triangle * 3];
            const std::uint32_t i1 = triangles[triangle * 3 + 1];
            const std::uint32_t i2 = triangles[triangle * 3 + 2];
            if (i0 >= vertex_count || i1 >= vertex_count || i2 >= vertex_count)
                continue;
            const auto distance = ray_triangle(ray, position(i0), position(i1), position(i2));
            if (!distance || (nearest && *distance >= nearest->distance))
                continue;
            nearest = HitCandidate3D{*distance, parts.empty() ? triangle + 1 : parts[triangle]};
        }
        return nearest;
    }

    inline std::optional<double> ray_sphere(tc_ray3 ray, termin::Vec3f centerf, double radius) {
        const termin::Vec3 offset = ray.origin - centerf.to_double();
        const double a = ray.direction.dot(ray.direction);
        const double half_b = offset.dot(ray.direction);
        const double c = offset.dot(offset) - radius * radius;
        const double discriminant = half_b * half_b - a * c;
        if (!std::isfinite(discriminant) || discriminant < 0.0 || a <= 1.0e-24)
            return std::nullopt;
        const double root = std::sqrt(discriminant);
        const double near_distance = (-half_b - root) / a;
        if (near_distance > 0.0)
            return near_distance;
        const double far_distance = (-half_b + root) / a;
        return far_distance > 0.0 ? std::optional<double>(far_distance) : std::nullopt;
    }

} // namespace termin::visual::detail
