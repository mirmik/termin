#pragma once

#include "termin/geom/vec3.hpp"
#include "termin/geom/mat44.hpp"
#include "termin/render/types.hpp"

#include <variant>
#include <vector>
#include <cmath>
#include <optional>

namespace termin {

// ============================================================
// Drag Constraints
// ============================================================

struct AxisConstraint {
    Vec3f origin;
    Vec3f axis;  // normalized direction
};

struct PlaneConstraint {
    Vec3f origin;
    Vec3f normal;  // normalized
};

struct RadiusConstraint {
    Vec3f center;
};

struct AngleConstraint {
    Vec3f center;
    Vec3f axis;  // normalized rotation axis
};

struct NoDrag {};

using DragConstraint = std::variant<
    AxisConstraint,
    PlaneConstraint,
    RadiusConstraint,
    AngleConstraint,
    NoDrag
>;

// ============================================================
// Collider Geometry
// ============================================================

struct SphereGeometry {
    Vec3f center;
    float radius;

    std::optional<float> ray_intersect(const Vec3f& ray_origin, const Vec3f& ray_dir) const {
        Vec3f oc = ray_origin - center;
        float a = ray_dir.dot(ray_dir);
        float b = 2.0f * oc.dot(ray_dir);
        float c = oc.dot(oc) - radius * radius;

        float discriminant = b * b - 4.0f * a * c;
        if (discriminant < 0) {
            return std::nullopt;
        }

        float sqrt_disc = std::sqrt(discriminant);
        float t1 = (-b - sqrt_disc) / (2.0f * a);
        float t2 = (-b + sqrt_disc) / (2.0f * a);

        if (t1 >= 0) return t1;
        if (t2 >= 0) return t2;
        return std::nullopt;
    }
};

struct CylinderGeometry {
    Vec3f start;
    Vec3f end;
    float radius;

    std::optional<float> ray_intersect(const Vec3f& ray_origin, const Vec3f& ray_dir) const {
        Vec3f cyl_axis = end - start;
        float cyl_length = cyl_axis.norm();
        if (cyl_length < 1e-6f) {
            return std::nullopt;
        }
        cyl_axis = cyl_axis / cyl_length;

        Vec3f delta = ray_origin - start;

        float ray_dot_axis = ray_dir.dot(cyl_axis);
        float delta_dot_axis = delta.dot(cyl_axis);

        Vec3f d_perp = ray_dir - cyl_axis * ray_dot_axis;
        Vec3f delta_perp = delta - cyl_axis * delta_dot_axis;

        float a = d_perp.dot(d_perp);
        float b = 2.0f * d_perp.dot(delta_perp);
        float c = delta_perp.dot(delta_perp) - radius * radius;

        float discriminant = b * b - 4.0f * a * c;
        if (discriminant < 0) {
            return std::nullopt;
        }

        if (a < 1e-10f) {
            if (c <= 0) return 0.0f;
            return std::nullopt;
        }

        float sqrt_disc = std::sqrt(discriminant);
        float t1 = (-b - sqrt_disc) / (2.0f * a);
        float t2 = (-b + sqrt_disc) / (2.0f * a);

        for (float t : {t1, t2}) {
            if (t < 0) continue;
            Vec3f hit_point = ray_origin + ray_dir * t;
            float proj = (hit_point - start).dot(cyl_axis);
            if (proj >= 0 && proj <= cyl_length) {
                return t;
            }
        }

        return std::nullopt;
    }
};

struct TorusGeometry {
    Vec3f center;
    Vec3f axis;  // normalized
    float major_radius;
    float minor_radius;

    std::optional<float> ray_intersect(const Vec3f& ray_origin, const Vec3f& ray_dir) const {
        // Build local coordinate system
        Vec3f tangent, bitangent;
        _build_basis(axis, tangent, bitangent);

        // Transform ray to local space (tangent=X, bitangent=Y, axis=Z)
        Vec3f local_origin;
        Vec3f rel = ray_origin - center;
        local_origin.x = rel.dot(tangent);
        local_origin.y = rel.dot(bitangent);
        local_origin.z = rel.dot(axis);

        Vec3f local_dir;
        local_dir.x = ray_dir.dot(tangent);
        local_dir.y = ray_dir.dot(bitangent);
        local_dir.z = ray_dir.dot(axis);

        // Simplified: intersect with plane Z=0, check annulus
        if (std::abs(local_dir.z) < 1e-6f) {
            if (std::abs(local_origin.z) > minor_radius) {
                return std::nullopt;
            }
            return std::nullopt;
        }

        float t_plane = -local_origin.z / local_dir.z;
        if (t_plane < 0) {
            return std::nullopt;
        }

        Vec3f hit_local = local_origin + local_dir * t_plane;
        float dist_from_center = std::sqrt(hit_local.x * hit_local.x + hit_local.y * hit_local.y);

        if (std::abs(dist_from_center - major_radius) <= minor_radius) {
            return t_plane;
        }

        // Check above/below for minor radius
        for (float dz : {-minor_radius * 0.5f, minor_radius * 0.5f}) {
            if (std::abs(local_dir.z) < 1e-6f) continue;
            float t_off = -(local_origin.z - dz) / local_dir.z;
            if (t_off < 0) continue;
            Vec3f hit = local_origin + local_dir * t_off;
            float dist = std::sqrt(hit.x * hit.x + hit.y * hit.y);
            if (std::abs(dist - major_radius) <= minor_radius) {
                return t_off;
            }
        }

        return std::nullopt;
    }

private:
    static void _build_basis(const Vec3f& ax, Vec3f& tangent, Vec3f& bitangent) {
        Vec3f up{0.0f, 0.0f, 1.0f};
        if (std::abs(ax.dot(up)) > 0.9f) {
            up = Vec3f{0.0f, 1.0f, 0.0f};
        }
        tangent = ax.cross(up).normalized();
        bitangent = ax.cross(tangent);
    }
};

struct QuadGeometry {
    Vec3f p0, p1, p2, p3;
    Vec3f normal;

    std::optional<float> ray_intersect(const Vec3f& ray_origin, const Vec3f& ray_dir) const {
        float denom = ray_dir.dot(normal);
        if (std::abs(denom) < 1e-6f) {
            return std::nullopt;
        }

        float t = (p0 - ray_origin).dot(normal) / denom;
        if (t < 0) {
            return std::nullopt;
        }

        Vec3f hit = ray_origin + ray_dir * t;

        // Check if hit is inside quad (all edges same winding)
        auto same_side = [&](const Vec3f& edge_start, const Vec3f& edge_end, const Vec3f& point) {
            Vec3f edge = edge_end - edge_start;
            Vec3f to_point = point - edge_start;
            Vec3f cross_prod = edge.cross(to_point);
            return cross_prod.dot(normal) >= 0;
        };

        if (same_side(p0, p1, hit) &&
            same_side(p1, p2, hit) &&
            same_side(p2, p3, hit) &&
            same_side(p3, p0, hit)) {
            return t;
        }

        return std::nullopt;
    }
};

using ColliderGeometry = std::variant<
    SphereGeometry,
    CylinderGeometry,
    TorusGeometry,
    QuadGeometry
>;

// ============================================================
// GizmoCollider
// ============================================================

struct GizmoCollider {
    int id;
    ColliderGeometry geometry;
    DragConstraint constraint;

    std::optional<float> ray_intersect(const Vec3f& ray_origin, const Vec3f& ray_dir) const {
        return std::visit([&](const auto& geom) {
            return geom.ray_intersect(ray_origin, ray_dir);
        }, geometry);
    }
};

// ============================================================
// Utility functions
// ============================================================

inline void build_basis(const Vec3f& axis, Vec3f& tangent, Vec3f& bitangent) {
    Vec3f up{0.0f, 0.0f, 1.0f};
    if (std::abs(axis.dot(up)) > 0.9f) {
        up = Vec3f{0.0f, 1.0f, 0.0f};
    }
    tangent = axis.cross(up).normalized();
    bitangent = axis.cross(tangent);
}

// Closest point on axis to ray
inline Vec3f closest_point_on_axis(
    const Vec3f& ray_origin,
    const Vec3f& ray_dir,
    const Vec3f& axis_point,
    const Vec3f& axis_dir
) {
    Vec3f w0 = axis_point - ray_origin;
    float a = axis_dir.dot(axis_dir);
    float b = axis_dir.dot(ray_dir);
    float c = ray_dir.dot(ray_dir);
    float d = axis_dir.dot(w0);
    float e = ray_dir.dot(w0);

    float denom = a * c - b * b;
    if (std::abs(denom) < 1e-10f) {
        return axis_point;
    }

    float s = (b * e - c * d) / denom;
    return axis_point + axis_dir * s;
}

// Ray-plane intersection
inline std::optional<Vec3f> ray_plane_intersect(
    const Vec3f& ray_origin,
    const Vec3f& ray_dir,
    const Vec3f& plane_origin,
    const Vec3f& plane_normal
) {
    float denom = ray_dir.dot(plane_normal);
    if (std::abs(denom) < 1e-6f) {
        return std::nullopt;
    }

    float t = (plane_origin - ray_origin).dot(plane_normal) / denom;
    return ray_origin + ray_dir * t;
}

} // namespace termin
