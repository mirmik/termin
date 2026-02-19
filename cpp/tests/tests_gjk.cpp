#include "guard/guard.h"
#include "termin/colliders/colliders.hpp"
#include "termin/colliders/gjk.hpp"
#include <cmath>

using guard::Approx;
using namespace termin::colliders;
using termin::Vec3;
using termin::GeneralPose3;
using termin::Quat;

// ==================== Support function tests ====================

TEST_CASE("BoxCollider support along +X")
{
    BoxCollider box(Vec3(1, 1, 1));  // half_size (1,1,1), at origin
    Vec3 s = box.support(Vec3(1, 0, 0));
    CHECK_EQ(s.x, Approx(1.0).epsilon(1e-8));
}

TEST_CASE("BoxCollider support along -X")
{
    BoxCollider box(Vec3(1, 1, 1));
    Vec3 s = box.support(Vec3(-1, 0, 0));
    CHECK_EQ(s.x, Approx(-1.0).epsilon(1e-8));
}

TEST_CASE("BoxCollider support diagonal")
{
    BoxCollider box(Vec3(1, 2, 3));
    Vec3 s = box.support(Vec3(1, 1, 1));
    CHECK_EQ(s.x, Approx(1.0).epsilon(1e-8));
    CHECK_EQ(s.y, Approx(2.0).epsilon(1e-8));
    CHECK_EQ(s.z, Approx(3.0).epsilon(1e-8));
}

TEST_CASE("BoxCollider support with offset")
{
    BoxCollider box(Vec3(1, 1, 1), GeneralPose3(Quat::identity(), Vec3(5, 0, 0)));
    Vec3 s = box.support(Vec3(1, 0, 0));
    CHECK_EQ(s.x, Approx(6.0).epsilon(1e-8));
}

TEST_CASE("SphereCollider support along +X")
{
    SphereCollider sphere(2.0);
    Vec3 s = sphere.support(Vec3(1, 0, 0));
    CHECK_EQ(s.x, Approx(2.0).epsilon(1e-8));
    CHECK_EQ(s.y, Approx(0.0).epsilon(1e-8));
    CHECK_EQ(s.z, Approx(0.0).epsilon(1e-8));
}

TEST_CASE("SphereCollider support with offset")
{
    SphereCollider sphere(1.0, GeneralPose3(Quat::identity(), Vec3(3, 0, 0)));
    Vec3 s = sphere.support(Vec3(1, 0, 0));
    CHECK_EQ(s.x, Approx(4.0).epsilon(1e-8));
}

TEST_CASE("CapsuleCollider support along axis")
{
    CapsuleCollider capsule(1.0, 0.5);  // half_height=1, radius=0.5, axis Z
    Vec3 s = capsule.support(Vec3(0, 0, 1));
    // top endpoint (0,0,1) + radius * (0,0,1) = (0,0,1.5)
    CHECK_EQ(s.z, Approx(1.5).epsilon(1e-8));
}

TEST_CASE("CapsuleCollider support perpendicular to axis")
{
    CapsuleCollider capsule(1.0, 0.5);
    Vec3 s = capsule.support(Vec3(1, 0, 0));
    // One of the endpoints + radius along X
    CHECK_EQ(s.x, Approx(0.5).epsilon(1e-8));
}

// ==================== GJK: non-intersecting pairs ====================

TEST_CASE("GJK Sphere-Sphere separated")
{
    SphereCollider s1(1.0);
    SphereCollider s2(1.0, GeneralPose3(Quat::identity(), Vec3(5, 0, 0)));

    ColliderHit hit = gjk_collide(s1, s2);
    CHECK(!hit.colliding());
    CHECK_EQ(hit.distance, Approx(3.0).epsilon(0.1));
}

TEST_CASE("GJK Box-Box separated")
{
    BoxCollider b1(Vec3(1, 1, 1));
    BoxCollider b2(Vec3(1, 1, 1), GeneralPose3(Quat::identity(), Vec3(5, 0, 0)));

    ColliderHit hit = gjk_collide(b1, b2);
    CHECK(!hit.colliding());
    CHECK_EQ(hit.distance, Approx(3.0).epsilon(0.1));
}

TEST_CASE("GJK Box-Sphere separated")
{
    BoxCollider box(Vec3(1, 1, 1));
    SphereCollider sphere(0.5, GeneralPose3(Quat::identity(), Vec3(3, 0, 0)));

    ColliderHit hit = gjk_collide(box, sphere);
    CHECK(!hit.colliding());
    CHECK_EQ(hit.distance, Approx(1.5).epsilon(0.1));
}

TEST_CASE("GJK Capsule-Sphere separated")
{
    CapsuleCollider capsule(1.0, 0.5);
    SphereCollider sphere(0.5, GeneralPose3(Quat::identity(), Vec3(3, 0, 0)));

    ColliderHit hit = gjk_collide(capsule, sphere);
    CHECK(!hit.colliding());
    CHECK_EQ(hit.distance, Approx(2.0).epsilon(0.1));
}

// ==================== GJK: intersecting pairs ====================

TEST_CASE("GJK Sphere-Sphere overlapping")
{
    SphereCollider s1(1.0);
    SphereCollider s2(1.0, GeneralPose3(Quat::identity(), Vec3(1, 0, 0)));

    ColliderHit hit = gjk_collide(s1, s2);
    CHECK(hit.colliding());
    CHECK_EQ(hit.distance, Approx(-1.0).epsilon(0.1));
}

TEST_CASE("GJK Box-Box overlapping")
{
    BoxCollider b1(Vec3(1, 1, 1));
    BoxCollider b2(Vec3(1, 1, 1), GeneralPose3(Quat::identity(), Vec3(1, 0, 0)));

    ColliderHit hit = gjk_collide(b1, b2);
    CHECK(hit.colliding());
    CHECK_EQ(hit.distance, Approx(-1.0).epsilon(0.1));
}

TEST_CASE("GJK Sphere-Box overlapping")
{
    SphereCollider sphere(1.0);
    BoxCollider box(Vec3(1, 1, 1), GeneralPose3(Quat::identity(), Vec3(1.5, 0, 0)));

    ColliderHit hit = gjk_collide(sphere, box);
    CHECK(hit.colliding());
    // analytic: 1.5 - 1 - 1 = -0.5
    CHECK_EQ(hit.distance, Approx(-0.5).epsilon(0.15));
}

TEST_CASE("GJK Capsule-Capsule overlapping")
{
    CapsuleCollider c1(1.0, 0.5);
    CapsuleCollider c2(1.0, 0.5, GeneralPose3(Quat::identity(), Vec3(0.5, 0, 0)));

    ColliderHit hit = gjk_collide(c1, c2);
    CHECK(hit.colliding());
    CHECK_EQ(hit.distance, Approx(-0.5).epsilon(0.1));
}

// ==================== GJK: touching (distance ~0) ====================

TEST_CASE("GJK Sphere-Sphere touching")
{
    SphereCollider s1(1.0);
    SphereCollider s2(1.0, GeneralPose3(Quat::identity(), Vec3(2, 0, 0)));

    ColliderHit hit = gjk_collide(s1, s2);
    CHECK_EQ(std::abs(hit.distance), Approx(0.0).epsilon(0.1));
}

TEST_CASE("GJK Box-Box touching")
{
    BoxCollider b1(Vec3(1, 1, 1));
    BoxCollider b2(Vec3(1, 1, 1), GeneralPose3(Quat::identity(), Vec3(2, 0, 0)));

    ColliderHit hit = gjk_collide(b1, b2);
    CHECK_EQ(std::abs(hit.distance), Approx(0.0).epsilon(0.1));
}

// ==================== GJK vs analytic comparison ====================

TEST_CASE("GJK vs analytic: Sphere-Sphere distance")
{
    SphereCollider s1(1.5);
    SphereCollider s2(0.7, GeneralPose3(Quat::identity(), Vec3(4, 0, 0)));

    ColliderHit analytic = s1.closest_to_collider(s2);
    ColliderHit gjk_hit = gjk_collide(s1, s2);

    CHECK_EQ(gjk_hit.distance, Approx(analytic.distance).epsilon(0.1));
}

TEST_CASE("GJK vs analytic: Box-Box distance")
{
    BoxCollider b1(Vec3(1, 2, 1));
    BoxCollider b2(Vec3(1, 1, 1), GeneralPose3(Quat::identity(), Vec3(4, 0, 0)));

    ColliderHit analytic = b1.closest_to_collider(b2);
    ColliderHit gjk_hit = gjk_collide(b1, b2);

    CHECK_EQ(gjk_hit.distance, Approx(analytic.distance).epsilon(0.1));
}

TEST_CASE("GJK vs analytic: Box-Sphere distance")
{
    BoxCollider box(Vec3(1, 1, 1));
    SphereCollider sphere(0.5, GeneralPose3(Quat::identity(), Vec3(3, 0, 0)));

    ColliderHit analytic = box.closest_to_collider(sphere);
    ColliderHit gjk_hit = gjk_collide(box, sphere);

    CHECK_EQ(gjk_hit.distance, Approx(analytic.distance).epsilon(0.1));
}

TEST_CASE("GJK vs analytic: Capsule-Sphere distance")
{
    CapsuleCollider capsule(1.0, 0.5);
    SphereCollider sphere(0.5, GeneralPose3(Quat::identity(), Vec3(3, 0, 0)));

    ColliderHit analytic = capsule.closest_to_collider(sphere);
    ColliderHit gjk_hit = gjk_collide(capsule, sphere);

    CHECK_EQ(gjk_hit.distance, Approx(analytic.distance).epsilon(0.1));
}

TEST_CASE("GJK vs analytic: Capsule-Capsule distance")
{
    CapsuleCollider c1(1.0, 0.5);
    CapsuleCollider c2(1.0, 0.5, GeneralPose3(Quat::identity(), Vec3(3, 0, 0)));

    ColliderHit analytic = c1.closest_to_collider(c2);
    ColliderHit gjk_hit = gjk_collide(c1, c2);

    CHECK_EQ(gjk_hit.distance, Approx(analytic.distance).epsilon(0.1));
}

// ==================== GJK vs analytic: penetration ====================

TEST_CASE("GJK vs analytic: Sphere-Sphere penetration")
{
    SphereCollider s1(1.0);
    SphereCollider s2(1.0, GeneralPose3(Quat::identity(), Vec3(1.5, 0, 0)));

    ColliderHit analytic = s1.closest_to_collider(s2);
    ColliderHit gjk_hit = gjk_collide(s1, s2);

    CHECK(gjk_hit.colliding());
    CHECK_EQ(gjk_hit.distance, Approx(analytic.distance).epsilon(0.15));
}

TEST_CASE("GJK vs analytic: Box-Box penetration")
{
    BoxCollider b1(Vec3(1, 1, 1));
    BoxCollider b2(Vec3(1, 1, 1), GeneralPose3(Quat::identity(), Vec3(1.5, 0, 0)));

    ColliderHit analytic = b1.closest_to_collider(b2);
    ColliderHit gjk_hit = gjk_collide(b1, b2);

    CHECK(gjk_hit.colliding());
    CHECK_EQ(gjk_hit.distance, Approx(analytic.distance).epsilon(0.15));
}
