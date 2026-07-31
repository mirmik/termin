#pragma once

#include <string>

#include <termin/colliders/collider_primitive.hpp>
#include <termin/geom/pose3.hpp>
#include <termin/physics/termin_physics_api.hpp>

namespace termin::physics {

// Uniform-density mass properties expressed in an authored shape's local
// frame. inertia_frame_local maps principal-inertia coordinates into that
// shape frame: its translation is the center of mass and its rotation contains
// the principal axes.
struct TERMIN_PHYSICS_API MassProperties {
  double mass = 1.0;
  Vec3 principal_moments{1.0, 1.0, 1.0};
  Pose3 inertia_frame_local{};
};

// Compute mass properties for a collider after applying the owning entity's
// positive decomposed scale. The collider's own local offset, rotation and
// scale are included exactly as AttachedCollider includes them.
//
// Returns false and fills diagnostic for unsupported or degenerate geometry.
TERMIN_PHYSICS_API bool try_compute_mass_properties(
    const colliders::ColliderPrimitive &collider,
    const Vec3 &entity_scale,
    double mass,
    MassProperties &result,
    std::string &diagnostic);

} // namespace termin::physics
