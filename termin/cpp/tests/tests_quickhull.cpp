#include "guard/guard.h"
#include "termin/colliders/convex_hull_collider.hpp"
#include <cmath>
#include <algorithm>
#include <set>

using guard::Approx;
using namespace termin::colliders;
using termin::Vec3;
using termin::GeneralPose3;

// ==================== Quickhull: basic shapes ====================

TEST_CASE("Quickhull: cube 8 points")
{
    std::vector<Vec3> pts = {
        {-1,-1,-1}, {1,-1,-1}, {-1,1,-1}, {1,1,-1},
        {-1,-1,1},  {1,-1,1},  {-1,1,1},  {1,1,1}
    };

    auto hull = ConvexHullCollider::from_points(pts);
    CHECK_EQ((int)hull.vertices.size(), 8);
    CHECK_EQ((int)hull.faces.size(), 12);  // 6 faces * 2 triangles each... actually quickhull gives triangulated
    // Actually a cube has 6 quad faces = 12 triangles
    // But quickhull might give fewer if some faces are coplanar.
    // At minimum 6 faces (if merging coplanar), at most 12 (all triangulated)
    CHECK((int)hull.faces.size() >= 6);
    CHECK((int)hull.faces.size() <= 12);
}

TEST_CASE("Quickhull: tetrahedron 4 points")
{
    std::vector<Vec3> pts = {
        {1, 1, 1}, {-1, -1, 1}, {-1, 1, -1}, {1, -1, -1}
    };

    auto hull = ConvexHullCollider::from_points(pts);
    CHECK_EQ((int)hull.vertices.size(), 4);
    CHECK_EQ((int)hull.faces.size(), 4);
}

TEST_CASE("Quickhull: interior points filtered")
{
    std::vector<Vec3> pts = {
        {-1,-1,-1}, {1,-1,-1}, {-1,1,-1}, {1,1,-1},
        {-1,-1,1},  {1,-1,1},  {-1,1,1},  {1,1,1},
        // Interior points
        {0,0,0}, {0.5,0.5,0.5}, {-0.3,0.2,-0.1}
    };

    auto hull = ConvexHullCollider::from_points(pts);
    CHECK_EQ((int)hull.faces.size(), 12);  // Cube still has 12 tri faces
}

TEST_CASE("Quickhull: duplicate points handled")
{
    std::vector<Vec3> pts = {
        {1,1,1}, {-1,-1,1}, {-1,1,-1}, {1,-1,-1},
        {1,1,1}, {1,1,1}, {-1,-1,1}  // duplicates
    };

    auto hull = ConvexHullCollider::from_points(pts);
    CHECK_EQ((int)hull.faces.size(), 4);  // Still a tetrahedron
}

// ==================== Quickhull: normal orientation ====================

TEST_CASE("Quickhull: all normals point outward")
{
    std::vector<Vec3> pts = {
        {-1,-1,-1}, {1,-1,-1}, {-1,1,-1}, {1,1,-1},
        {-1,-1,1},  {1,-1,1},  {-1,1,1},  {1,1,1}
    };

    auto hull = ConvexHullCollider::from_points(pts);

    // Centroid
    Vec3 centroid(0, 0, 0);
    for (const auto& v : hull.vertices) {
        centroid = centroid + v;
    }
    centroid = centroid * (1.0 / hull.vertices.size());

    for (const auto& face : hull.faces) {
        Vec3 face_center = (hull.vertices[face.a] + hull.vertices[face.b] + hull.vertices[face.c]) * (1.0/3.0);
        Vec3 outward = face_center - centroid;
        CHECK(face.normal.dot(outward) > 0);
    }
}

TEST_CASE("Quickhull: all original points inside or on hull")
{
    std::vector<Vec3> pts = {
        {-1,-1,-1}, {1,-1,-1}, {-1,1,-1}, {1,1,-1},
        {-1,-1,1},  {1,-1,1},  {-1,1,1},  {1,1,1},
        {0,0,0}, {0.9,0.9,0.9}
    };

    auto hull = ConvexHullCollider::from_points(pts);

    for (const auto& p : pts) {
        bool inside = true;
        for (const auto& face : hull.faces) {
            double d = (p - hull.vertices[face.a]).dot(face.normal);
            if (d > 1e-6) {
                inside = false;
                break;
            }
        }
        CHECK(inside);
    }
}

// ==================== Quickhull: degenerate cases ====================

TEST_CASE("Quickhull: fewer than 4 points")
{
    std::vector<Vec3> pts = {{1,0,0}, {0,1,0}};
    auto hull = ConvexHullCollider::from_points(pts);
    CHECK_EQ((int)hull.vertices.size(), 2);
    CHECK_EQ((int)hull.faces.size(), 0);  // Can't form faces
}

TEST_CASE("Quickhull: random sphere points")
{
    // Generate points on a sphere + some inside
    std::vector<Vec3> pts;
    for (int i = 0; i < 50; ++i) {
        double phi = 3.14159265 * i / 25.0;
        double theta = 2.0 * 3.14159265 * i * 0.618;
        double r = (i % 3 == 0) ? 0.5 : 1.0;  // Some interior points
        pts.push_back(Vec3(
            r * std::sin(phi) * std::cos(theta),
            r * std::sin(phi) * std::sin(theta),
            r * std::cos(phi)
        ));
    }

    auto hull = ConvexHullCollider::from_points(pts);
    CHECK((int)hull.faces.size() >= 4);

    // All points should be inside or on hull
    for (const auto& p : pts) {
        bool inside = true;
        for (const auto& face : hull.faces) {
            double d = (p - hull.vertices[face.a]).dot(face.normal);
            if (d > 1e-4) {
                inside = false;
                break;
            }
        }
        CHECK(inside);
    }
}
