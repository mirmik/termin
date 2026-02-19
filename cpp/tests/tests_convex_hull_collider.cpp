#include "guard/guard.h"
#include "termin/colliders/colliders.hpp"
#include "termin/colliders/gjk.hpp"
#include <cmath>

using guard::Approx;
using namespace termin::colliders;
using termin::Vec3;
using termin::GeneralPose3;
using termin::Quat;
using termin::AABB;
using termin::AABB;

// Helper: create a cube ConvexHullCollider from 8 points
static ConvexHullCollider make_cube_hull(const Vec3& half_size, const GeneralPose3& t = GeneralPose3()) {
    double hx = half_size.x, hy = half_size.y, hz = half_size.z;
    std::vector<Vec3> pts = {
        {-hx,-hy,-hz}, {hx,-hy,-hz}, {-hx,hy,-hz}, {hx,hy,-hz},
        {-hx,-hy,hz},  {hx,-hy,hz},  {-hx,hy,hz},  {hx,hy,hz}
    };
    return ConvexHullCollider::from_points(pts, t);
}

// ==================== Support function tests ====================

TEST_CASE("ConvexHull support: cube along +X")
{
    auto hull = make_cube_hull(Vec3(1, 1, 1));
    Vec3 s = hull.support(Vec3(1, 0, 0));
    CHECK_EQ(s.x, Approx(1.0).epsilon(1e-6));
}

TEST_CASE("ConvexHull support: cube along -Y")
{
    auto hull = make_cube_hull(Vec3(1, 2, 3));
    Vec3 s = hull.support(Vec3(0, -1, 0));
    CHECK_EQ(s.y, Approx(-2.0).epsilon(1e-6));
}

TEST_CASE("ConvexHull support: cube diagonal")
{
    auto hull = make_cube_hull(Vec3(1, 2, 3));
    Vec3 s = hull.support(Vec3(1, 1, 1));
    CHECK_EQ(s.x, Approx(1.0).epsilon(1e-6));
    CHECK_EQ(s.y, Approx(2.0).epsilon(1e-6));
    CHECK_EQ(s.z, Approx(3.0).epsilon(1e-6));
}

TEST_CASE("ConvexHull support: cube with offset")
{
    auto hull = make_cube_hull(Vec3(1, 1, 1), GeneralPose3(Quat::identity(), Vec3(5, 0, 0)));
    Vec3 s = hull.support(Vec3(1, 0, 0));
    CHECK_EQ(s.x, Approx(6.0).epsilon(1e-6));
}

// ==================== AABB tests ====================

TEST_CASE("ConvexHull AABB matches BoxCollider AABB")
{
    auto hull = make_cube_hull(Vec3(1, 2, 3));
    BoxCollider box(Vec3(1, 2, 3));

    AABB hull_aabb = hull.aabb();
    AABB box_aabb = box.aabb();

    CHECK_EQ(hull_aabb.min_point.x, Approx(box_aabb.min_point.x).epsilon(1e-6));
    CHECK_EQ(hull_aabb.min_point.y, Approx(box_aabb.min_point.y).epsilon(1e-6));
    CHECK_EQ(hull_aabb.min_point.z, Approx(box_aabb.min_point.z).epsilon(1e-6));
    CHECK_EQ(hull_aabb.max_point.x, Approx(box_aabb.max_point.x).epsilon(1e-6));
    CHECK_EQ(hull_aabb.max_point.y, Approx(box_aabb.max_point.y).epsilon(1e-6));
    CHECK_EQ(hull_aabb.max_point.z, Approx(box_aabb.max_point.z).epsilon(1e-6));
}

// ==================== GJK: ConvexHull vs Box ====================

TEST_CASE("ConvexHull-Box separated")
{
    auto hull = make_cube_hull(Vec3(1, 1, 1));
    BoxCollider box(Vec3(1, 1, 1), GeneralPose3(Quat::identity(), Vec3(5, 0, 0)));

    ColliderHit hit = hull.closest_to_collider(box);
    CHECK(!hit.colliding());
    CHECK_EQ(hit.distance, Approx(3.0).epsilon(0.1));
}

TEST_CASE("ConvexHull-Box overlapping")
{
    auto hull = make_cube_hull(Vec3(1, 1, 1));
    BoxCollider box(Vec3(1, 1, 1), GeneralPose3(Quat::identity(), Vec3(1, 0, 0)));

    ColliderHit hit = hull.closest_to_collider(box);
    CHECK(hit.colliding());
    CHECK_EQ(hit.distance, Approx(-1.0).epsilon(0.15));
}

// ==================== GJK: ConvexHull vs Sphere ====================

TEST_CASE("ConvexHull-Sphere separated")
{
    auto hull = make_cube_hull(Vec3(1, 1, 1));
    SphereCollider sphere(0.5, GeneralPose3(Quat::identity(), Vec3(3, 0, 0)));

    ColliderHit hit = hull.closest_to_collider(sphere);
    CHECK(!hit.colliding());
    CHECK_EQ(hit.distance, Approx(1.5).epsilon(0.1));
}

TEST_CASE("ConvexHull-Sphere overlapping")
{
    auto hull = make_cube_hull(Vec3(1, 1, 1));
    SphereCollider sphere(1.0, GeneralPose3(Quat::identity(), Vec3(1.5, 0, 0)));

    ColliderHit hit = hull.closest_to_collider(sphere);
    CHECK(hit.colliding());
}

// ==================== GJK: ConvexHull vs ConvexHull ====================

TEST_CASE("ConvexHull-ConvexHull separated")
{
    auto h1 = make_cube_hull(Vec3(1, 1, 1));
    auto h2 = make_cube_hull(Vec3(1, 1, 1), GeneralPose3(Quat::identity(), Vec3(5, 0, 0)));

    ColliderHit hit = h1.closest_to_collider(h2);
    CHECK(!hit.colliding());
    CHECK_EQ(hit.distance, Approx(3.0).epsilon(0.1));
}

TEST_CASE("ConvexHull-ConvexHull overlapping")
{
    auto h1 = make_cube_hull(Vec3(1, 1, 1));
    auto h2 = make_cube_hull(Vec3(1, 1, 1), GeneralPose3(Quat::identity(), Vec3(1, 0, 0)));

    ColliderHit hit = h1.closest_to_collider(h2);
    CHECK(hit.colliding());
    CHECK_EQ(hit.distance, Approx(-1.0).epsilon(0.15));
}

// ==================== ConvexHull cube vs BoxCollider comparison ====================

TEST_CASE("ConvexHull cube matches Box: distance to sphere")
{
    auto hull = make_cube_hull(Vec3(1, 1, 1));
    BoxCollider box(Vec3(1, 1, 1));
    SphereCollider sphere(0.5, GeneralPose3(Quat::identity(), Vec3(3, 0, 0)));

    ColliderHit hull_hit = hull.closest_to_collider(sphere);
    ColliderHit box_hit = box.closest_to_collider(sphere);

    CHECK_EQ(hull_hit.distance, Approx(box_hit.distance).epsilon(0.1));
}

TEST_CASE("ConvexHull cube matches Box: distance to box")
{
    auto hull = make_cube_hull(Vec3(1, 2, 1));
    BoxCollider b1(Vec3(1, 2, 1));
    BoxCollider b2(Vec3(1, 1, 1), GeneralPose3(Quat::identity(), Vec3(4, 0, 0)));

    ColliderHit hull_hit = hull.closest_to_collider(b2);
    ColliderHit box_hit = b1.closest_to_collider(b2);

    CHECK_EQ(hull_hit.distance, Approx(box_hit.distance).epsilon(0.1));
}

// ==================== Reverse dispatch: Box/Sphere → ConvexHull ====================

TEST_CASE("Box.closest_to_collider(ConvexHull) works")
{
    BoxCollider box(Vec3(1, 1, 1));
    auto hull = make_cube_hull(Vec3(1, 1, 1), GeneralPose3(Quat::identity(), Vec3(5, 0, 0)));

    ColliderHit hit = box.closest_to_collider(hull);
    CHECK(!hit.colliding());
    CHECK_EQ(hit.distance, Approx(3.0).epsilon(0.1));
}

TEST_CASE("Sphere.closest_to_collider(ConvexHull) works")
{
    SphereCollider sphere(1.0);
    auto hull = make_cube_hull(Vec3(1, 1, 1), GeneralPose3(Quat::identity(), Vec3(5, 0, 0)));

    ColliderHit hit = sphere.closest_to_collider(hull);
    CHECK(!hit.colliding());
    CHECK_EQ(hit.distance, Approx(3.0).epsilon(0.1));
}

// ==================== clone_at ====================

TEST_CASE("ConvexHull clone_at preserves geometry")
{
    auto hull = make_cube_hull(Vec3(1, 1, 1));
    GeneralPose3 new_pose(Quat::identity(), Vec3(10, 0, 0));
    auto cloned = hull.clone_at(new_pose);

    CHECK_EQ(cloned->center().x, Approx(10.0).epsilon(1e-6));
    Vec3 s = cloned->support(Vec3(1, 0, 0));
    CHECK_EQ(s.x, Approx(11.0).epsilon(1e-6));
}
