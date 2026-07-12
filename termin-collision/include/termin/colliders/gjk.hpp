#pragma once

// GJK (Gilbert-Johnson-Keerthi) + EPA (Expanding Polytope Algorithm)
// Универсальный narrow-phase для любых выпуклых форм с support function.

#include "collider.hpp"
#include "collider_primitive.hpp"
#include <termin_collision/termin_collision.h>
#include <vector>
#include <array>

namespace termin {
namespace colliders {

// Support point в Minkowski difference space.
struct MinkowskiPoint {
    Vec3 point;      // support_a - support_b
    Vec3 support_a;
    Vec3 support_b;
};

TERMIN_COLLISION_API MinkowskiPoint minkowski_support(
    const ColliderPrimitive& a,
    const ColliderPrimitive& b,
    const Vec3& direction
);

// ==================== GJK ====================

struct GjkResult {
    bool intersecting = false;
    std::array<MinkowskiPoint, 4> simplex;
    int simplex_size = 0;
    Vec3 closest_on_a;
    Vec3 closest_on_b;
    double distance = 0.0;
};

namespace detail {

// Closest point on segment [A, B] to origin.
// Returns t in [0,1] where closest = A*(1-t) + B*t
double closest_t_on_segment(const Vec3& A, const Vec3& B);

// Closest point on triangle ABC to origin.
struct BaryResult {
    double u, v, w;  // closest = A*u + B*v + C*w
    Vec3 closest;
};

BaryResult closest_on_triangle(const Vec3& A, const Vec3& B, const Vec3& C);

} // namespace detail

// GJK distance algorithm: tracks closest point v on simplex to origin.
// Convergence: when new support point doesn't improve distance.
TERMIN_COLLISION_API GjkResult gjk(const ColliderPrimitive& a, const ColliderPrimitive& b);

// ==================== EPA ====================

struct EpaResult {
    Vec3 normal;
    double depth = 0.0;
    Vec3 point_on_a;
    Vec3 point_on_b;
};

namespace detail {

struct EpaFace {
    int a, b, c;
    Vec3 normal;
    double distance;
};

// Compute face normal and distance from winding (a,b,c).
// Does NOT flip — caller must ensure correct winding.
EpaFace make_epa_face_no_flip(const std::vector<MinkowskiPoint>& polytope, int a, int b, int c);

// Build a tetrahedron for EPA from support points.
// Uses tilted directions to avoid degeneracy when origin lies on face planes.
bool build_epa_tetrahedron(const ColliderPrimitive& a, const ColliderPrimitive& b,
                                   std::array<MinkowskiPoint, 4>& tet);

} // namespace detail

TERMIN_COLLISION_API EpaResult epa(const ColliderPrimitive& a, const ColliderPrimitive& b);

// ==================== Wrapper ====================

TERMIN_COLLISION_API ColliderHit gjk_collide(const ColliderPrimitive& a, const ColliderPrimitive& b);

} // namespace colliders
} // namespace termin
