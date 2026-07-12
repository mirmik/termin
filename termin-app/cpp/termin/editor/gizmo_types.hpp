#pragma once

#include "tgfx/types.hpp"
#include <optional>
#include <termin/geom/mat44.hpp>
#include <termin/geom/vec3.hpp>
#include <variant>
#include <vector>

namespace termin {

struct AxisConstraint {
  Vec3f origin;
  Vec3f axis;
};
struct PlaneConstraint {
  Vec3f origin;
  Vec3f normal;
};
struct RadiusConstraint {
  Vec3f center;
};
struct AngleConstraint {
  Vec3f center;
  Vec3f axis;
};
struct NoDrag {};
using DragConstraint = std::variant<AxisConstraint, PlaneConstraint,
                                    RadiusConstraint, AngleConstraint, NoDrag>;

struct SphereGeometry {
  Vec3f center;
  float radius;
  std::optional<float> ray_intersect(const Vec3f &, const Vec3f &) const;
};
struct CylinderGeometry {
  Vec3f start;
  Vec3f end;
  float radius;
  std::optional<float> ray_intersect(const Vec3f &, const Vec3f &) const;
};
struct TorusGeometry {
  Vec3f center;
  Vec3f axis;
  float major_radius;
  float minor_radius;
  std::optional<float> ray_intersect(const Vec3f &, const Vec3f &) const;

private:
  static void _build_basis(const Vec3f &, Vec3f &, Vec3f &);
};
struct QuadGeometry {
  Vec3f p0, p1, p2, p3;
  Vec3f normal;
  std::optional<float> ray_intersect(const Vec3f &, const Vec3f &) const;
};
using ColliderGeometry =
    std::variant<SphereGeometry, CylinderGeometry, TorusGeometry, QuadGeometry>;

struct GizmoCollider {
  int id;
  ColliderGeometry geometry;
  DragConstraint constraint;
  std::optional<float> ray_intersect(const Vec3f &, const Vec3f &) const;
};

void build_basis(const Vec3f &, Vec3f &, Vec3f &);
Vec3f closest_point_on_axis(const Vec3f &, const Vec3f &, const Vec3f &,
                            const Vec3f &);
std::optional<Vec3f> ray_plane_intersect(const Vec3f &, const Vec3f &,
                                         const Vec3f &, const Vec3f &);

} // namespace termin
