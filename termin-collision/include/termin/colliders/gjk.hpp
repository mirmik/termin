#pragma once

// GJK (Gilbert-Johnson-Keerthi) + EPA (Expanding Polytope Algorithm)
// Универсальный narrow-phase для любых выпуклых форм с support function.

#include "collider.hpp"
#include "collider_primitive.hpp"
#include <vector>
#include <array>
#include <cmath>
#include <algorithm>
#include <limits>

namespace termin {
namespace colliders {

// Support point в Minkowski difference space.
struct MinkowskiPoint {
    Vec3 point;      // support_a - support_b
    Vec3 support_a;
    Vec3 support_b;
};

inline MinkowskiPoint minkowski_support(const ColliderPrimitive& a, const ColliderPrimitive& b, const Vec3& direction) {
    MinkowskiPoint result;
    result.support_a = a.support(direction);
    result.support_b = b.support(direction * (-1.0));
    result.point = result.support_a - result.support_b;
    return result;
}

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
inline double closest_t_on_segment(const Vec3& A, const Vec3& B) {
    Vec3 AB = B - A;
    double denom = AB.dot(AB);
    if (denom < 1e-20) return 0.0;
    double t = -(A.dot(AB)) / denom;
    return std::clamp(t, 0.0, 1.0);
}

// Closest point on triangle ABC to origin.
struct BaryResult {
    double u, v, w;  // closest = A*u + B*v + C*w
    Vec3 closest;
};

inline BaryResult closest_on_triangle(const Vec3& A, const Vec3& B, const Vec3& C) {
    Vec3 AB = B - A;
    Vec3 AC = C - A;
    Vec3 AO = A * (-1.0);

    double d00 = AB.dot(AB);
    double d01 = AB.dot(AC);
    double d11 = AC.dot(AC);
    double d20 = AO.dot(AB);
    double d21 = AO.dot(AC);
    double denom = d00 * d11 - d01 * d01;

    if (std::abs(denom) > 1e-20) {
        double bv = (d11 * d20 - d01 * d21) / denom;
        double bw = (d00 * d21 - d01 * d20) / denom;
        double bu = 1.0 - bv - bw;

        if (bu >= -1e-10 && bv >= -1e-10 && bw >= -1e-10) {
            Vec3 closest = A * bu + B * bv + C * bw;
            return {bu, bv, bw, closest};
        }
    }

    // Outside triangle or degenerate — closest on edges
    double best_dist_sq = std::numeric_limits<double>::max();
    BaryResult best = {1, 0, 0, A};

    {
        double t = closest_t_on_segment(A, B);
        Vec3 p = A * (1.0 - t) + B * t;
        double d = p.dot(p);
        if (d < best_dist_sq) { best_dist_sq = d; best = {1.0 - t, t, 0, p}; }
    }
    {
        double t = closest_t_on_segment(A, C);
        Vec3 p = A * (1.0 - t) + C * t;
        double d = p.dot(p);
        if (d < best_dist_sq) { best_dist_sq = d; best = {1.0 - t, 0, t, p}; }
    }
    {
        double t = closest_t_on_segment(B, C);
        Vec3 p = B * (1.0 - t) + C * t;
        double d = p.dot(p);
        if (d < best_dist_sq) { best_dist_sq = d; best = {0, 1.0 - t, t, p}; }
    }

    return best;
}

} // namespace detail

// GJK distance algorithm: tracks closest point v on simplex to origin.
// Convergence: when new support point doesn't improve distance.
inline GjkResult gjk(const ColliderPrimitive& a, const ColliderPrimitive& b) {
    GjkResult result;
    constexpr int MAX_ITERATIONS = 64;

    Vec3 direction = a.center() - b.center();
    if (direction.dot(direction) < 1e-20) direction = Vec3(1, 0, 0);

    result.simplex[0] = minkowski_support(a, b, direction);
    result.simplex_size = 1;
    Vec3 v = result.simplex[0].point;

    for (int iter = 0; iter < MAX_ITERATIONS; ++iter) {
        double vv = v.dot(v);

        if (vv < 1e-14) {
            result.intersecting = true;
            return result;
        }

        direction = v * (-1.0);
        MinkowskiPoint w = minkowski_support(a, b, direction);

        // Convergence: v·v - v·w ≤ ε·v·v
        double vw = v.dot(w.point);
        if (vv - vw <= 1e-8 * vv + 1e-14) {
            break;
        }

        result.simplex[result.simplex_size++] = w;

        if (result.simplex_size == 2) {
            double t = detail::closest_t_on_segment(
                result.simplex[0].point, result.simplex[1].point);
            v = result.simplex[0].point * (1.0 - t) + result.simplex[1].point * t;

            if (t < 1e-10) {
                result.simplex_size = 1;
            } else if (t > 1.0 - 1e-10) {
                result.simplex[0] = result.simplex[1];
                result.simplex_size = 1;
            }

        } else if (result.simplex_size == 3) {
            auto bary = detail::closest_on_triangle(
                result.simplex[0].point, result.simplex[1].point, result.simplex[2].point);
            v = bary.closest;

            double weights[3] = {bary.u, bary.v, bary.w};
            std::array<MinkowskiPoint, 4> reduced;
            int count = 0;
            for (int i = 0; i < 3; ++i) {
                if (weights[i] > 1e-10) reduced[count++] = result.simplex[i];
            }
            if (count > 0 && count < 3) {
                for (int i = 0; i < count; ++i) result.simplex[i] = reduced[i];
                result.simplex_size = count;
            }

        } else if (result.simplex_size == 4) {
            const Vec3& A = result.simplex[0].point;
            const Vec3& B = result.simplex[1].point;
            const Vec3& C = result.simplex[2].point;
            const Vec3& D = result.simplex[3].point;

            Vec3 AB = B - A, AC = C - A, AD = D - A;
            Vec3 n_ABC = AB.cross(AC);
            Vec3 n_ACD = AC.cross(AD);
            Vec3 n_ADB = AD.cross(AB);

            // Orient outward (away from opposite vertex)
            if (n_ABC.dot(AD) > 0) n_ABC = n_ABC * (-1.0);
            if (n_ACD.dot(AB) > 0) n_ACD = n_ACD * (-1.0);
            if (n_ADB.dot(AC) > 0) n_ADB = n_ADB * (-1.0);

            Vec3 AO = A * (-1.0);
            bool out_ABC = n_ABC.dot(AO) > 0;
            bool out_ACD = n_ACD.dot(AO) > 0;
            bool out_ADB = n_ADB.dot(AO) > 0;

            Vec3 BC = C - B, BD = D - B;
            Vec3 n_BCD = BC.cross(BD);
            if (n_BCD.dot(A - B) > 0) n_BCD = n_BCD * (-1.0);
            bool out_BCD = n_BCD.dot(B * (-1.0)) > 0;

            if (!out_ABC && !out_ACD && !out_ADB && !out_BCD) {
                result.intersecting = true;
                return result;
            }

            // Find closest visible face
            double best_dist_sq = std::numeric_limits<double>::max();
            detail::BaryResult best_bary = {1, 0, 0, A};
            int best_idx[3] = {0, 0, 0};

            auto try_face = [&](int i0, int i1, int i2, bool outside) {
                if (!outside) return;
                auto bary = detail::closest_on_triangle(
                    result.simplex[i0].point, result.simplex[i1].point, result.simplex[i2].point);
                double d = bary.closest.dot(bary.closest);
                if (d < best_dist_sq) {
                    best_dist_sq = d;
                    best_bary = bary;
                    best_idx[0] = i0; best_idx[1] = i1; best_idx[2] = i2;
                }
            };

            try_face(0, 1, 2, out_ABC);
            try_face(0, 2, 3, out_ACD);
            try_face(0, 3, 1, out_ADB);
            try_face(1, 2, 3, out_BCD);

            v = best_bary.closest;

            MinkowskiPoint face_pts[3] = {
                result.simplex[best_idx[0]],
                result.simplex[best_idx[1]],
                result.simplex[best_idx[2]]
            };
            double weights[3] = {best_bary.u, best_bary.v, best_bary.w};
            int count = 0;
            for (int i = 0; i < 3; ++i) {
                if (weights[i] > 1e-10) result.simplex[count++] = face_pts[i];
            }
            result.simplex_size = count;
        }
    }

    // Not intersecting: compute closest points via barycentric interpolation
    result.intersecting = false;

    if (result.simplex_size == 1) {
        result.closest_on_a = result.simplex[0].support_a;
        result.closest_on_b = result.simplex[0].support_b;
        result.distance = result.simplex[0].point.norm();
    } else if (result.simplex_size == 2) {
        double t = detail::closest_t_on_segment(result.simplex[0].point, result.simplex[1].point);
        result.closest_on_a = result.simplex[0].support_a * (1.0 - t) + result.simplex[1].support_a * t;
        result.closest_on_b = result.simplex[0].support_b * (1.0 - t) + result.simplex[1].support_b * t;
        Vec3 closest = result.simplex[0].point * (1.0 - t) + result.simplex[1].point * t;
        result.distance = closest.norm();
    } else if (result.simplex_size >= 3) {
        auto bary = detail::closest_on_triangle(
            result.simplex[0].point, result.simplex[1].point, result.simplex[2].point);
        result.closest_on_a = result.simplex[0].support_a * bary.u
            + result.simplex[1].support_a * bary.v + result.simplex[2].support_a * bary.w;
        result.closest_on_b = result.simplex[0].support_b * bary.u
            + result.simplex[1].support_b * bary.v + result.simplex[2].support_b * bary.w;
        result.distance = bary.closest.norm();
    }

    return result;
}

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
inline EpaFace make_epa_face_no_flip(const std::vector<MinkowskiPoint>& polytope, int a, int b, int c) {
    EpaFace face;
    face.a = a; face.b = b; face.c = c;
    Vec3 AB = polytope[b].point - polytope[a].point;
    Vec3 AC = polytope[c].point - polytope[a].point;
    Vec3 n = AB.cross(AC);
    double len = n.norm();
    if (len < 1e-14) {
        face.normal = Vec3(0, 0, 1);
        face.distance = 0;
        return face;
    }
    n = n / len;
    face.normal = n;
    face.distance = n.dot(polytope[a].point);
    if (face.distance < 0) face.distance = 0; // numerical guard
    return face;
}

// Build a tetrahedron for EPA from support points.
// Uses tilted directions to avoid degeneracy when origin lies on face planes.
inline bool build_epa_tetrahedron(const ColliderPrimitive& a, const ColliderPrimitive& b,
                                   std::array<MinkowskiPoint, 4>& tet) {
    // Use 14 support directions: 6 axis-aligned + 8 diagonal.
    // Diagonal directions ensure the tetrahedron doesn't have faces coplanar with origin.
    constexpr int N_DIRS = 14;
    MinkowskiPoint pts[N_DIRS];
    Vec3 dirs[N_DIRS] = {
        {1,0,0},{-1,0,0},{0,1,0},{0,-1,0},{0,0,1},{0,0,-1},
        {1,1,1},{1,1,-1},{1,-1,1},{1,-1,-1},
        {-1,1,1},{-1,1,-1},{-1,-1,1},{-1,-1,-1}
    };
    for (int i = 0; i < N_DIRS; ++i) {
        pts[i] = minkowski_support(a, b, dirs[i]);
    }

    // Greedy selection to maximize tetrahedron volume
    // Step 1: farthest from origin
    int idx0 = 0;
    double best = pts[0].point.dot(pts[0].point);
    for (int i = 1; i < N_DIRS; ++i) {
        double d = pts[i].point.dot(pts[i].point);
        if (d > best) { best = d; idx0 = i; }
    }
    tet[0] = pts[idx0];

    // Step 2: farthest from tet[0]
    int idx1 = -1;
    best = -1;
    for (int i = 0; i < N_DIRS; ++i) {
        if (i == idx0) continue;
        Vec3 diff = pts[i].point - tet[0].point;
        double d = diff.dot(diff);
        if (d > best) { best = d; idx1 = i; }
    }
    tet[1] = pts[idx1];

    // Step 3: farthest from line tet[0]-tet[1]
    Vec3 line = tet[1].point - tet[0].point;
    double line_len_sq = line.dot(line);
    int idx2 = -1;
    best = -1;
    for (int i = 0; i < N_DIRS; ++i) {
        if (i == idx0 || i == idx1) continue;
        Vec3 diff = pts[i].point - tet[0].point;
        Vec3 proj = diff - line * (diff.dot(line) / std::max(line_len_sq, 1e-20));
        double d = proj.dot(proj);
        if (d > best) { best = d; idx2 = i; }
    }
    tet[2] = pts[idx2];

    // Step 4: farthest from plane
    Vec3 AB = tet[1].point - tet[0].point;
    Vec3 AC = tet[2].point - tet[0].point;
    Vec3 normal = AB.cross(AC);
    int idx3 = -1;
    best = -1;
    for (int i = 0; i < N_DIRS; ++i) {
        if (i == idx0 || i == idx1 || i == idx2) continue;
        double d = std::abs((pts[i].point - tet[0].point).dot(normal));
        if (d > best) { best = d; idx3 = i; }
    }
    tet[3] = pts[idx3];

    // Verify non-degenerate
    Vec3 AD = tet[3].point - tet[0].point;
    double vol = AB.dot(AC.cross(AD));
    return std::abs(vol) > 1e-14;
}

} // namespace detail

inline EpaResult epa(const ColliderPrimitive& a, const ColliderPrimitive& b) {
    EpaResult result;
    constexpr int MAX_ITERATIONS = 64;
    constexpr double EPA_TOLERANCE = 1e-6;

    std::array<MinkowskiPoint, 4> tet;
    if (!detail::build_epa_tetrahedron(a, b, tet)) {
        result.normal = Vec3(0, 0, 1);
        result.depth = 0.0;
        result.point_on_a = a.center();
        result.point_on_b = b.center();
        return result;
    }

    std::vector<MinkowskiPoint> polytope(tet.begin(), tet.begin() + 4);
    std::vector<detail::EpaFace> faces;

    // Determine winding from signed volume of tetrahedron.
    // vol > 0: standard face_idx gives inward normals → use flipped winding
    // vol < 0: standard face_idx gives outward normals → use as-is
    Vec3 AB = polytope[1].point - polytope[0].point;
    Vec3 AC = polytope[2].point - polytope[0].point;
    Vec3 AD = polytope[3].point - polytope[0].point;
    double vol = AB.cross(AC).dot(AD);

    int face_idx[4][3];
    if (vol > 0) {
        // Flip winding for outward normals
        face_idx[0][0]=0; face_idx[0][1]=2; face_idx[0][2]=1;
        face_idx[1][0]=0; face_idx[1][1]=1; face_idx[1][2]=3;
        face_idx[2][0]=0; face_idx[2][1]=3; face_idx[2][2]=2;
        face_idx[3][0]=1; face_idx[3][1]=2; face_idx[3][2]=3;
    } else {
        face_idx[0][0]=0; face_idx[0][1]=1; face_idx[0][2]=2;
        face_idx[1][0]=0; face_idx[1][1]=3; face_idx[1][2]=1;
        face_idx[2][0]=0; face_idx[2][1]=2; face_idx[2][2]=3;
        face_idx[3][0]=1; face_idx[3][1]=3; face_idx[3][2]=2;
    }
    for (int i = 0; i < 4; ++i) {
        faces.push_back(detail::make_epa_face_no_flip(polytope, face_idx[i][0], face_idx[i][1], face_idx[i][2]));
    }

    for (int iter = 0; iter < MAX_ITERATIONS; ++iter) {
        int closest_face = 0;
        double min_dist = faces[0].distance;
        for (int i = 1; i < (int)faces.size(); ++i) {
            if (faces[i].distance < min_dist) {
                min_dist = faces[i].distance;
                closest_face = i;
            }
        }

        Vec3 search_dir = faces[closest_face].normal;
        MinkowskiPoint new_point = minkowski_support(a, b, search_dir);
        double new_dist = new_point.point.dot(search_dir);

        if (new_dist - min_dist < EPA_TOLERANCE) {
            const auto& f = faces[closest_face];
            result.normal = f.normal;
            result.depth = min_dist;

            // Barycentric interpolation for contact points
            Vec3 proj = f.normal * min_dist;
            Vec3 v0 = polytope[f.b].point - polytope[f.a].point;
            Vec3 v1 = polytope[f.c].point - polytope[f.a].point;
            Vec3 v2 = proj - polytope[f.a].point;
            double d00 = v0.dot(v0);
            double d01 = v0.dot(v1);
            double d11 = v1.dot(v1);
            double d20 = v2.dot(v0);
            double d21 = v2.dot(v1);
            double denom = d00 * d11 - d01 * d01;
            if (std::abs(denom) > 1e-14) {
                double bv = (d11 * d20 - d01 * d21) / denom;
                double bw = (d00 * d21 - d01 * d20) / denom;
                double bu = 1.0 - bv - bw;
                result.point_on_a = polytope[f.a].support_a * bu
                    + polytope[f.b].support_a * bv + polytope[f.c].support_a * bw;
                result.point_on_b = polytope[f.a].support_b * bu
                    + polytope[f.b].support_b * bv + polytope[f.c].support_b * bw;
            } else {
                result.point_on_a = polytope[f.a].support_a;
                result.point_on_b = polytope[f.a].support_b;
            }
            return result;
        }

        // Expand polytope
        int new_idx = (int)polytope.size();
        polytope.push_back(new_point);

        std::vector<bool> visible(faces.size(), false);
        for (int i = 0; i < (int)faces.size(); ++i) {
            if (faces[i].normal.dot(new_point.point - polytope[faces[i].a].point) > 1e-10) {
                visible[i] = true;
            }
        }

        // Collect horizon edges
        using Edge = std::pair<int, int>;
        std::vector<Edge> horizon;

        for (int i = 0; i < (int)faces.size(); ++i) {
            if (!visible[i]) continue;
            int edges[3][2] = {
                {faces[i].a, faces[i].b},
                {faces[i].b, faces[i].c},
                {faces[i].c, faces[i].a}
            };
            for (int e = 0; e < 3; ++e) {
                int ea = edges[e][0], eb = edges[e][1];
                bool is_horizon = false;
                for (int j = 0; j < (int)faces.size(); ++j) {
                    if (j == i || visible[j]) continue;
                    if ((faces[j].a == eb && faces[j].b == ea) ||
                        (faces[j].b == eb && faces[j].c == ea) ||
                        (faces[j].c == eb && faces[j].a == ea)) {
                        is_horizon = true;
                        break;
                    }
                }
                if (is_horizon) {
                    horizon.push_back({ea, eb});
                }
            }
        }

        std::vector<detail::EpaFace> new_faces;
        for (int i = 0; i < (int)faces.size(); ++i) {
            if (!visible[i]) new_faces.push_back(faces[i]);
        }
        for (const auto& edge : horizon) {
            new_faces.push_back(detail::make_epa_face_no_flip(polytope, edge.first, edge.second, new_idx));
        }

        faces = std::move(new_faces);
        if (faces.empty()) break;
    }

    // Max iterations — return best
    if (!faces.empty()) {
        int closest_face = 0;
        double min_dist = faces[0].distance;
        for (int i = 1; i < (int)faces.size(); ++i) {
            if (faces[i].distance < min_dist) {
                min_dist = faces[i].distance;
                closest_face = i;
            }
        }
        const auto& f = faces[closest_face];
        result.normal = f.normal;
        result.depth = min_dist;
        result.point_on_a = polytope[f.a].support_a;
        result.point_on_b = polytope[f.a].support_b;
    }

    return result;
}

// ==================== Wrapper ====================

inline ColliderHit gjk_collide(const ColliderPrimitive& a, const ColliderPrimitive& b) {
    ColliderHit result;
    GjkResult gjk_result = gjk(a, b);

    if (!gjk_result.intersecting) {
        Vec3 diff = gjk_result.closest_on_b - gjk_result.closest_on_a;
        double dist = diff.norm();
        if (dist > 1e-10) {
            result.normal = diff / dist;
        } else {
            result.normal = Vec3(0, 0, 1);
        }
        result.point_on_a = gjk_result.closest_on_a;
        result.point_on_b = gjk_result.closest_on_b;
        result.distance = gjk_result.distance;
    } else {
        EpaResult epa_result = epa(a, b);
        result.normal = epa_result.normal;
        result.point_on_a = epa_result.point_on_a;
        result.point_on_b = epa_result.point_on_b;
        result.distance = -epa_result.depth;
    }

    return result;
}

} // namespace colliders
} // namespace termin
