#pragma once

// ConvexHullCollider — выпуклая оболочка из набора вершин.
// Использует quickhull для построения из облака точек.
// Коллизии через GJK+EPA (support function на вершинах).

#include "collider_primitive.hpp"
#include "gjk.hpp"
#include <vector>
#include <cmath>
#include <algorithm>
#include <limits>

namespace termin {
namespace colliders {

struct ConvexFace {
    int a, b, c;  // indices into vertices (CCW when viewed from outside)
    Vec3 normal;   // outward normal (local space)
};

class ConvexHullCollider : public ColliderPrimitive {
public:
    std::vector<Vec3> vertices;    // local space
    std::vector<ConvexFace> faces;
    std::vector<std::pair<int, int>> edges;  // unique edges (precomputed from faces)

    ConvexHullCollider() : ColliderPrimitive() {}

    ConvexHullCollider(std::vector<Vec3> verts, std::vector<ConvexFace> faces_,
                       const GeneralPose3& t = GeneralPose3())
        : ColliderPrimitive(t), vertices(std::move(verts)), faces(std::move(faces_))
    {
        _build_edges();
    }

    // Build from point cloud using quickhull
    static ConvexHullCollider from_points(const std::vector<Vec3>& points,
                                          const GeneralPose3& t = GeneralPose3());

    ColliderType type() const override { return ColliderType::ConvexHull; }

    AABB aabb() const override {
        if (vertices.empty()) return AABB(center(), center());
        Pose3 p = pose();
        Vec3 s = transform.scale;
        Vec3 v0 = p.transform_point(Vec3(vertices[0].x * s.x, vertices[0].y * s.y, vertices[0].z * s.z));
        AABB result(v0, v0);
        for (int i = 1; i < (int)vertices.size(); ++i) {
            Vec3 scaled(vertices[i].x * s.x, vertices[i].y * s.y, vertices[i].z * s.z);
            result.extend(p.transform_point(scaled));
        }
        return result;
    }

    Vec3 center() const override {
        return transform.lin;
    }

    Vec3 support(const Vec3& direction) const override {
        if (vertices.empty()) return center();
        // Transform direction to local space (inverse rotation, no scale needed for argmax)
        Vec3 local_dir = transform.ang.inverse().rotate(direction);
        Vec3 s = transform.scale;

        double best_dot = -std::numeric_limits<double>::max();
        int best_idx = 0;
        for (int i = 0; i < (int)vertices.size(); ++i) {
            // Scaled vertex dot with local_dir
            double d = (vertices[i].x * s.x) * local_dir.x
                     + (vertices[i].y * s.y) * local_dir.y
                     + (vertices[i].z * s.z) * local_dir.z;
            if (d > best_dot) {
                best_dot = d;
                best_idx = i;
            }
        }

        Vec3 scaled(vertices[best_idx].x * s.x, vertices[best_idx].y * s.y, vertices[best_idx].z * s.z);
        return transform.ang.rotate(scaled) + transform.lin;
    }

    std::unique_ptr<ColliderPrimitive> clone_at(const GeneralPose3& pose) const override {
        auto clone = std::make_unique<ConvexHullCollider>(vertices, faces, pose);
        clone->edges = edges;
        return clone;
    }

    RayHit closest_to_ray(const Ray3& ray) const override;
    ColliderHit closest_to_collider(const Collider& other) const override;

    // All _impl through GJK
    ColliderHit closest_to_box_impl(const BoxCollider& box) const override;
    ColliderHit closest_to_sphere_impl(const SphereCollider& sphere) const override;
    ColliderHit closest_to_capsule_impl(const CapsuleCollider& capsule) const override;

private:
    void _build_edges() {
        edges.clear();
        for (const auto& face : faces) {
            int pairs[3][2] = {{face.a, face.b}, {face.b, face.c}, {face.c, face.a}};
            for (auto& p : pairs) {
                int lo = std::min(p[0], p[1]);
                int hi = std::max(p[0], p[1]);
                bool dup = false;
                for (const auto& e : edges) {
                    if (e.first == lo && e.second == hi) { dup = true; break; }
                }
                if (!dup) edges.push_back({lo, hi});
            }
        }
    }

    // Transform vertex to world space
    Vec3 vertex_world(int idx) const {
        Vec3 s = transform.scale;
        Vec3 scaled(vertices[idx].x * s.x, vertices[idx].y * s.y, vertices[idx].z * s.z);
        return transform.ang.rotate(scaled) + transform.lin;
    }
};

// ==================== Quickhull ====================

namespace quickhull {

struct QhFace {
    int a, b, c;
    Vec3 normal;
    double dist;  // n.dot(vertices[a])
    std::vector<int> outside_set;
    bool alive = true;
};

inline void compute_face_normal(QhFace& face, const std::vector<Vec3>& verts) {
    Vec3 AB = verts[face.b] - verts[face.a];
    Vec3 AC = verts[face.c] - verts[face.a];
    Vec3 n = AB.cross(AC);
    double len = n.norm();
    if (len > 1e-14) {
        face.normal = n / len;
    } else {
        face.normal = Vec3(0, 0, 1);
    }
    face.dist = face.normal.dot(verts[face.a]);
}

inline std::vector<ConvexFace> build(const std::vector<Vec3>& points) {
    std::vector<ConvexFace> result;
    if (points.size() < 4) return result;

    std::vector<Vec3> verts = points;

    // Find initial tetrahedron: 4 maximally spread points
    // Step 1: most extreme points along axes
    int extremes[6] = {0,0,0,0,0,0};
    for (int i = 1; i < (int)verts.size(); ++i) {
        if (verts[i].x < verts[extremes[0]].x) extremes[0] = i;
        if (verts[i].x > verts[extremes[1]].x) extremes[1] = i;
        if (verts[i].y < verts[extremes[2]].y) extremes[2] = i;
        if (verts[i].y > verts[extremes[3]].y) extremes[3] = i;
        if (verts[i].z < verts[extremes[4]].z) extremes[4] = i;
        if (verts[i].z > verts[extremes[5]].z) extremes[5] = i;
    }

    // Most distant pair
    int p0 = 0, p1 = 1;
    double best_dist = -1;
    for (int i = 0; i < 6; ++i) {
        for (int j = i + 1; j < 6; ++j) {
            Vec3 diff = verts[extremes[i]] - verts[extremes[j]];
            double d = diff.dot(diff);
            if (d > best_dist) {
                best_dist = d;
                p0 = extremes[i];
                p1 = extremes[j];
            }
        }
    }

    // Farthest from line p0-p1
    Vec3 line_dir = verts[p1] - verts[p0];
    double line_len_sq = line_dir.dot(line_dir);
    int p2 = -1;
    best_dist = -1;
    for (int i = 0; i < (int)verts.size(); ++i) {
        if (i == p0 || i == p1) continue;
        Vec3 diff = verts[i] - verts[p0];
        Vec3 proj = diff - line_dir * (diff.dot(line_dir) / std::max(line_len_sq, 1e-20));
        double d = proj.dot(proj);
        if (d > best_dist) { best_dist = d; p2 = i; }
    }
    if (p2 < 0) return result;

    // Farthest from plane p0-p1-p2
    Vec3 tri_normal = (verts[p1] - verts[p0]).cross(verts[p2] - verts[p0]);
    double tri_norm_len = tri_normal.norm();
    if (tri_norm_len < 1e-14) return result;
    tri_normal = tri_normal / tri_norm_len;

    int p3 = -1;
    best_dist = -1;
    for (int i = 0; i < (int)verts.size(); ++i) {
        if (i == p0 || i == p1 || i == p2) continue;
        double d = std::abs((verts[i] - verts[p0]).dot(tri_normal));
        if (d > best_dist) { best_dist = d; p3 = i; }
    }
    if (p3 < 0) return result;

    // Orient tetrahedron: ensure outward normals
    double vol = (verts[p1] - verts[p0]).cross(verts[p2] - verts[p0]).dot(verts[p3] - verts[p0]);
    if (vol > 0) std::swap(p1, p2);  // flip to get outward normals from standard winding

    // Build initial 4 faces
    std::vector<QhFace> faces(4);
    int face_tris[4][3] = {{p0,p1,p2}, {p0,p3,p1}, {p0,p2,p3}, {p1,p3,p2}};
    for (int i = 0; i < 4; ++i) {
        faces[i].a = face_tris[i][0];
        faces[i].b = face_tris[i][1];
        faces[i].c = face_tris[i][2];
        compute_face_normal(faces[i], verts);
    }

    // Assign points to outside sets
    bool used[4] = {};
    for (int k = 0; k < 4; ++k) {
        int idx = face_tris[k][0]; // p0 appears in all, but let's mark all 4
        (void)idx;
    }

    for (int i = 0; i < (int)verts.size(); ++i) {
        if (i == p0 || i == p1 || i == p2 || i == p3) continue;
        double best_above = 0;
        int best_face = -1;
        for (int f = 0; f < (int)faces.size(); ++f) {
            if (!faces[f].alive) continue;
            double above = faces[f].normal.dot(verts[i]) - faces[f].dist;
            if (above > best_above) {
                best_above = above;
                best_face = f;
            }
        }
        if (best_face >= 0) {
            faces[best_face].outside_set.push_back(i);
        }
    }

    // Iterative expansion
    constexpr int MAX_QH_ITERATIONS = 1000;
    for (int iter = 0; iter < MAX_QH_ITERATIONS; ++iter) {
        // Find face with farthest outside point
        int work_face = -1;
        double max_above = 0;
        int eye_point = -1;

        for (int f = 0; f < (int)faces.size(); ++f) {
            if (!faces[f].alive || faces[f].outside_set.empty()) continue;
            for (int pi : faces[f].outside_set) {
                double above = faces[f].normal.dot(verts[pi]) - faces[f].dist;
                if (above > max_above) {
                    max_above = above;
                    work_face = f;
                    eye_point = pi;
                }
            }
        }
        if (work_face < 0) break;  // all points inside hull

        // Find all visible faces from eye_point
        std::vector<bool> visible(faces.size(), false);
        for (int f = 0; f < (int)faces.size(); ++f) {
            if (!faces[f].alive) continue;
            double above = faces[f].normal.dot(verts[eye_point]) - faces[f].dist;
            if (above > -1e-10) {
                visible[f] = true;
            }
        }

        // Collect horizon edges
        using Edge = std::pair<int, int>;
        std::vector<Edge> horizon;
        for (int f = 0; f < (int)faces.size(); ++f) {
            if (!visible[f] || !faces[f].alive) continue;
            int edges[3][2] = {
                {faces[f].a, faces[f].b},
                {faces[f].b, faces[f].c},
                {faces[f].c, faces[f].a}
            };
            for (int e = 0; e < 3; ++e) {
                int ea = edges[e][0], eb = edges[e][1];
                bool is_horizon = false;
                for (int j = 0; j < (int)faces.size(); ++j) {
                    if (j == f || !faces[j].alive || visible[j]) continue;
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

        // Collect orphaned outside points from visible faces
        std::vector<int> orphans;
        for (int f = 0; f < (int)faces.size(); ++f) {
            if (!visible[f] || !faces[f].alive) continue;
            for (int pi : faces[f].outside_set) {
                if (pi != eye_point) orphans.push_back(pi);
            }
            faces[f].alive = false;
        }

        // Create new faces from horizon edges to eye_point
        int first_new = (int)faces.size();
        for (const auto& edge : horizon) {
            QhFace nf;
            nf.a = edge.first;
            nf.b = edge.second;
            nf.c = eye_point;
            compute_face_normal(nf, verts);
            faces.push_back(nf);
        }

        // Redistribute orphans
        for (int pi : orphans) {
            double best_above = 0;
            int best_face = -1;
            for (int f = first_new; f < (int)faces.size(); ++f) {
                if (!faces[f].alive) continue;
                double above = faces[f].normal.dot(verts[pi]) - faces[f].dist;
                if (above > best_above) {
                    best_above = above;
                    best_face = f;
                }
            }
            if (best_face >= 0) {
                faces[best_face].outside_set.push_back(pi);
            }
        }
    }

    // Collect alive faces
    for (const auto& f : faces) {
        if (!f.alive) continue;
        result.push_back({f.a, f.b, f.c, f.normal});
    }
    return result;
}

} // namespace quickhull

// ==================== from_points ====================

inline ConvexHullCollider ConvexHullCollider::from_points(
    const std::vector<Vec3>& points, const GeneralPose3& t)
{
    auto faces = quickhull::build(points);
    return ConvexHullCollider(points, std::move(faces), t);
}

// ==================== Ray intersection ====================

inline RayHit ConvexHullCollider::closest_to_ray(const Ray3& ray) const {
    RayHit best;
    best.distance = std::numeric_limits<double>::max();

    if (faces.empty()) {
        best.point_on_collider = center();
        best.point_on_ray = ray.origin;
        best.distance = (center() - ray.origin).norm();
        return best;
    }

    // Möller-Trumbore for each face
    bool any_hit = false;
    for (const auto& face : faces) {
        Vec3 A = vertex_world(face.a);
        Vec3 B = vertex_world(face.b);
        Vec3 C = vertex_world(face.c);

        Vec3 AB = B - A;
        Vec3 AC = C - A;
        Vec3 h = ray.direction.cross(AC);
        double det = AB.dot(h);
        if (std::abs(det) < 1e-14) continue;

        double inv_det = 1.0 / det;
        Vec3 s = ray.origin - A;
        double u = inv_det * s.dot(h);
        if (u < -1e-8 || u > 1.0 + 1e-8) continue;

        Vec3 q = s.cross(AB);
        double v = inv_det * ray.direction.dot(q);
        if (v < -1e-8 || u + v > 1.0 + 1e-8) continue;

        double t = inv_det * AC.dot(q);
        if (t >= 0 && t < best.distance) {
            best.point_on_ray = ray.point_at(t);
            best.point_on_collider = best.point_on_ray;
            best.distance = 0.0;
            any_hit = true;
        }
    }

    if (any_hit) return best;

    // No intersection — find closest point to ray
    // Use support function approach: closest on each face edge/vertex
    best.distance = std::numeric_limits<double>::max();
    for (const auto& face : faces) {
        int idx[3] = {face.a, face.b, face.c};
        for (int e = 0; e < 3; ++e) {
            Vec3 P = vertex_world(idx[e]);
            Vec3 Q = vertex_world(idx[(e + 1) % 3]);
            Vec3 PQ = Q - P;
            Vec3 PO = ray.origin - P;

            // Closest between line segment PQ and ray
            double pq_sq = PQ.dot(PQ);
            double d_pq = ray.direction.dot(PQ);
            double d_sq = ray.direction.dot(ray.direction);

            double denom = d_sq * pq_sq - d_pq * d_pq;
            double t_ray = 0, t_seg = 0;
            if (std::abs(denom) > 1e-14) {
                Vec3 w = ray.origin - P;
                t_ray = (pq_sq * ray.direction.dot(w) - d_pq * PQ.dot(w)) / (-denom);
                t_seg = (-d_sq * PQ.dot(w) + d_pq * ray.direction.dot(w)) / (-denom);
            }
            t_ray = std::max(0.0, t_ray);
            t_seg = std::clamp(t_seg, 0.0, 1.0);

            Vec3 pr = ray.point_at(t_ray);
            Vec3 ps = P + PQ * t_seg;
            double d = (pr - ps).norm();
            if (d < best.distance) {
                best.point_on_ray = pr;
                best.point_on_collider = ps;
                best.distance = d;
            }
        }
    }
    return best;
}

// closest_to_*_impl defined in colliders.hpp after all types are complete

} // namespace colliders
} // namespace termin
