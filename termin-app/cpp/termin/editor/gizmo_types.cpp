#include "termin/editor/gizmo_types.hpp"
#include <cmath>

namespace termin {

std::optional<float> SphereGeometry::ray_intersect(const Vec3f &o, const Vec3f &d) const {
    Vec3f oc = o - center;
    float a = d.dot(d), b = 2 * oc.dot(d), c = oc.dot(oc) - radius * radius;
    float disc = b * b - 4 * a * c;
    if (disc < 0)
        return std::nullopt;
    float s = std::sqrt(disc);
    float t1 = (-b - s) / (2 * a), t2 = (-b + s) / (2 * a);
    if (t1 >= 0)
        return t1;
    if (t2 >= 0)
        return t2;
    return std::nullopt;
}
std::optional<float> CylinderGeometry::ray_intersect(const Vec3f &o, const Vec3f &d) const {
    Vec3f axis = end - start;
    float len = axis.norm();
    if (len < 1e-6f)
        return std::nullopt;
    axis = axis / len;
    Vec3f delta = o - start;
    float rd = d.dot(axis), dd = delta.dot(axis);
    Vec3f dp = d - axis * rd, ep = delta - axis * dd;
    float a = dp.dot(dp), b = 2 * dp.dot(ep), c = ep.dot(ep) - radius * radius;
    if (a < 1e-10f)
        return c <= 0 ? std::optional<float>(0) : std::nullopt;
    float disc = b * b - 4 * a * c;
    if (disc < 0)
        return std::nullopt;
    float s = std::sqrt(disc);
    for (float t : {(-b - s) / (2 * a), (-b + s) / (2 * a)})
        if (t >= 0 && (o + d * t - start).dot(axis) >= 0 && (o + d * t - start).dot(axis) <= len)
            return t;
    return std::nullopt;
}
void TorusGeometry::_build_basis(const Vec3f &ax, Vec3f &t, Vec3f &b) {
    Vec3f up{0, 0, 1};
    if (std::abs(ax.dot(up)) > 0.9f)
        up = {0, 1, 0};
    t = ax.cross(up).normalized();
    b = ax.cross(t);
}
std::optional<float> TorusGeometry::ray_intersect(const Vec3f &o, const Vec3f &d) const {
    Vec3f t, b;
    _build_basis(axis, t, b);
    Vec3f rel = o - center, lo{rel.dot(t), rel.dot(b), rel.dot(axis)},
          ld{d.dot(t), d.dot(b), d.dot(axis)};
    if (std::abs(ld.z) < 1e-6f)
        return std::nullopt;
    float tp = -lo.z / ld.z;
    if (tp < 0)
        return std::nullopt;
    Vec3f h = lo + ld * tp;
    float r = std::sqrt(h.x * h.x + h.y * h.y);
    if (std::abs(r - major_radius) <= minor_radius)
        return tp;
    for (float dz : {-minor_radius * .5f, minor_radius * .5f}) {
        float q = -(lo.z - dz) / ld.z;
        if (q >= 0) {
            Vec3f x = lo + ld * q;
            if (std::abs(std::sqrt(x.x * x.x + x.y * x.y) - major_radius) <= minor_radius)
                return q;
        }
    }
    return std::nullopt;
}
std::optional<float> QuadGeometry::ray_intersect(const Vec3f &o, const Vec3f &d) const {
    float den = d.dot(normal);
    if (std::abs(den) < 1e-6f)
        return std::nullopt;
    float t = (p0 - o).dot(normal) / den;
    if (t < 0)
        return std::nullopt;
    Vec3f h = o + d * t;
    auto side = [&](const Vec3f &a, const Vec3f &b) {
        return (b - a).cross(h - a).dot(normal) >= 0;
    };
    return side(p0, p1) && side(p1, p2) && side(p2, p3) && side(p3, p0) ? std::optional<float>(t)
                                                                        : std::nullopt;
}
std::optional<float> GizmoCollider::ray_intersect(const Vec3f &o, const Vec3f &d) const {
    return std::visit([&](const auto &g) { return g.ray_intersect(o, d); }, geometry);
}
void build_basis(const Vec3f &ax, Vec3f &t, Vec3f &b) {
    Vec3f up{0, 0, 1};
    if (std::abs(ax.dot(up)) > .9f)
        up = {0, 1, 0};
    t = ax.cross(up).normalized();
    b = ax.cross(t);
}
Vec3f closest_point_on_axis(const Vec3f &o, const Vec3f &d, const Vec3f &p, const Vec3f &a) {
    Vec3f w = p - o;
    float aa = a.dot(a), bb = a.dot(d), cc = d.dot(d), dd = a.dot(w), ee = d.dot(w),
          den = aa * cc - bb * bb;
    if (std::abs(den) < 1e-10f)
        return p;
    return p + a * ((bb * ee - cc * dd) / den);
}
std::optional<Vec3f> ray_plane_intersect(const Vec3f &o, const Vec3f &d, const Vec3f &p,
                                         const Vec3f &n) {
    float den = d.dot(n);
    if (std::abs(den) < 1e-6f)
        return std::nullopt;
    float t = (p - o).dot(n) / den;
    return o + d * t;
}
} // namespace termin
