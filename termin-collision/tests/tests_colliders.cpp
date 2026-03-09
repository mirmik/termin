#include "guard/guard.h"
#include "termin/colliders/colliders.hpp"
#include <cmath>

using guard::Approx;
using namespace termin::colliders;
using termin::Vec3;
using termin::Pose3;
using termin::GeneralPose3;
using termin::Quat;
using termin::Ray3;

// ==================== Ray3 tests ====================

TEST_CASE("Ray3 point_at")
{
    Ray3 ray(Vec3(0, 0, 0), Vec3(1, 0, 0));
    Vec3 p = ray.point_at(5.0);
    CHECK_EQ(p.x, Approx(5.0).epsilon(1e-12));
    CHECK_EQ(p.y, Approx(0.0).epsilon(1e-12));
    CHECK_EQ(p.z, Approx(0.0).epsilon(1e-12));
}

// ==================== BoxCollider tests ====================

TEST_CASE("BoxCollider center")
{
    BoxCollider box(Vec3(1, 1, 1));  // half_size = (1,1,1), default transform at origin
    Vec3 c = box.center();
    CHECK_EQ(c.x, Approx(0.0).epsilon(1e-12));
    CHECK_EQ(c.y, Approx(0.0).epsilon(1e-12));
    CHECK_EQ(c.z, Approx(0.0).epsilon(1e-12));
}

TEST_CASE("BoxCollider center with pose")
{
    BoxCollider box(Vec3(1, 1, 1), GeneralPose3(Quat::identity(), Vec3(5, 0, 0)));
    Vec3 c = box.center();
    CHECK_EQ(c.x, Approx(5.0).epsilon(1e-12));
    CHECK_EQ(c.y, Approx(0.0).epsilon(1e-12));
    CHECK_EQ(c.z, Approx(0.0).epsilon(1e-12));
}

TEST_CASE("BoxCollider closest_to_ray hit")
{
    BoxCollider box(Vec3(1, 1, 1));  // half_size = (1,1,1) -> box from -1 to 1
    Ray3 ray(Vec3(5, 0, 0), Vec3(-1, 0, 0));

    RayHit hit = box.closest_to_ray(ray);
    CHECK(hit.hit());
    CHECK_EQ(hit.distance, Approx(0.0).epsilon(1e-8));
    CHECK_EQ(hit.point_on_collider.x, Approx(1.0).epsilon(1e-8));
}

TEST_CASE("BoxCollider closest_to_ray miss")
{
    BoxCollider box(Vec3(1, 1, 1));
    Ray3 ray(Vec3(5, 5, 0), Vec3(-1, 0, 0));  // Ray misses box

    RayHit hit = box.closest_to_ray(ray);
    CHECK(!hit.hit());
    CHECK(hit.distance > 0);
}

TEST_CASE("BoxCollider closest_to_box")
{
    BoxCollider box1(Vec3(1, 1, 1));  // at origin
    BoxCollider box2(Vec3(1, 1, 1), GeneralPose3(Quat::identity(), Vec3(5, 0, 0)));

    ColliderHit hit = box1.closest_to_collider(box2);
    CHECK(!hit.colliding());
    // Distance between two boxes: 5 - 2 = 3 (each box extends 1 unit)
    CHECK_EQ(hit.distance, Approx(3.0).epsilon(1e-8));
}

TEST_CASE("BoxCollider closest_to_box touching")
{
    BoxCollider box1(Vec3(1, 1, 1));  // from -1 to 1
    BoxCollider box2(Vec3(1, 1, 1), GeneralPose3(Quat::identity(), Vec3(2, 0, 0)));  // from 1 to 3, exactly touching at x=1

    ColliderHit hit = box1.closest_to_collider(box2);
    // Distance should be 0 (touching)
    CHECK_EQ(hit.distance, Approx(0.0).epsilon(1e-6));
}

TEST_CASE("BoxCollider closest_to_box overlapping")
{
    BoxCollider box1(Vec3(1, 1, 1));  // from -1 to 1
    BoxCollider box2(Vec3(1, 1, 1), GeneralPose3(Quat::identity(), Vec3(1, 0, 0)));  // from 0 to 2, overlapping

    ColliderHit hit = box1.closest_to_collider(box2);
    CHECK(hit.colliding());
    // Penetration = 1 (overlap from 0 to 1)
    CHECK_EQ(hit.distance, Approx(-1.0).epsilon(1e-6));
}

// ==================== SphereCollider tests ====================

TEST_CASE("SphereCollider center")
{
    SphereCollider sphere(0.5, GeneralPose3(Quat::identity(), Vec3(1, 2, 3)));
    Vec3 c = sphere.center();
    CHECK_EQ(c.x, Approx(1.0).epsilon(1e-12));
    CHECK_EQ(c.y, Approx(2.0).epsilon(1e-12));
    CHECK_EQ(c.z, Approx(3.0).epsilon(1e-12));
}

TEST_CASE("SphereCollider closest_to_ray hit")
{
    SphereCollider sphere(1.0);  // radius=1.0, at origin
    Ray3 ray(Vec3(5, 0, 0), Vec3(-1, 0, 0));

    RayHit hit = sphere.closest_to_ray(ray);
    CHECK(hit.hit());
    CHECK_EQ(hit.distance, Approx(0.0).epsilon(1e-8));
    CHECK_EQ(hit.point_on_collider.x, Approx(1.0).epsilon(1e-8));
}

TEST_CASE("SphereCollider closest_to_ray miss")
{
    SphereCollider sphere(1.0);
    Ray3 ray(Vec3(5, 5, 0), Vec3(-1, 0, 0));  // Ray misses sphere

    RayHit hit = sphere.closest_to_ray(ray);
    CHECK(!hit.hit());
    CHECK(hit.distance > 0);
}

TEST_CASE("SphereCollider closest_to_sphere")
{
    SphereCollider s1(1.0);  // at origin
    SphereCollider s2(1.0, GeneralPose3(Quat::identity(), Vec3(5, 0, 0)));

    ColliderHit hit = s1.closest_to_collider(s2);
    CHECK(!hit.colliding());
    // Distance: 5 - 2 = 3
    CHECK_EQ(hit.distance, Approx(3.0).epsilon(1e-8));
}

TEST_CASE("SphereCollider closest_to_sphere touching")
{
    SphereCollider s1(1.0);  // at origin
    SphereCollider s2(1.0, GeneralPose3(Quat::identity(), Vec3(2, 0, 0)));  // Exactly touching

    ColliderHit hit = s1.closest_to_collider(s2);
    CHECK_EQ(hit.distance, Approx(0.0).epsilon(1e-8));
}

TEST_CASE("SphereCollider closest_to_sphere overlapping")
{
    SphereCollider s1(1.0);  // at origin
    SphereCollider s2(1.0, GeneralPose3(Quat::identity(), Vec3(1, 0, 0)));  // Overlapping

    ColliderHit hit = s1.closest_to_collider(s2);
    CHECK(hit.colliding());
    CHECK_EQ(hit.distance, Approx(-1.0).epsilon(1e-8));  // Penetration = 1
}

TEST_CASE("SphereCollider closest_to_box")
{
    SphereCollider sphere(1.0);  // at origin
    BoxCollider box(Vec3(1, 1, 1), GeneralPose3(Quat::identity(), Vec3(5, 0, 0)));

    ColliderHit hit = sphere.closest_to_collider(box);
    CHECK(!hit.colliding());
    // Distance: 4 - 1 = 3
    CHECK_EQ(hit.distance, Approx(3.0).epsilon(1e-8));
}

// ==================== CapsuleCollider tests ====================
// New API: CapsuleCollider(half_height, radius, transform)
// Axis is along local Z-axis

TEST_CASE("CapsuleCollider center")
{
    CapsuleCollider capsule(1.0, 0.5);  // half_height=1.0, radius=0.5, at origin
    Vec3 c = capsule.center();
    CHECK_EQ(c.x, Approx(0.0).epsilon(1e-12));
    CHECK_EQ(c.y, Approx(0.0).epsilon(1e-12));
    CHECK_EQ(c.z, Approx(0.0).epsilon(1e-12));
}

TEST_CASE("CapsuleCollider closest_to_ray hit cylinder")
{
    CapsuleCollider capsule(1.0, 0.5);  // half_height=1.0, radius=0.5 (axis from -1 to 1 on Z)
    Ray3 ray(Vec3(5, 0, 0), Vec3(-1, 0, 0));

    RayHit hit = capsule.closest_to_ray(ray);
    CHECK(hit.hit());
    CHECK_EQ(hit.distance, Approx(0.0).epsilon(1e-8));
    CHECK_EQ(hit.point_on_collider.x, Approx(0.5).epsilon(1e-8));
}

TEST_CASE("CapsuleCollider closest_to_ray hit cap")
{
    CapsuleCollider capsule(1.0, 0.5);  // half_height=1.0, radius=0.5
    Ray3 ray(Vec3(0, 0, 5), Vec3(0, 0, -1));

    RayHit hit = capsule.closest_to_ray(ray);
    CHECK(hit.hit());
    CHECK_EQ(hit.distance, Approx(0.0).epsilon(1e-8));
    CHECK_EQ(hit.point_on_collider.z, Approx(1.5).epsilon(1e-8));  // top cap
}

TEST_CASE("CapsuleCollider closest_to_ray miss")
{
    CapsuleCollider capsule(1.0, 0.5);
    Ray3 ray(Vec3(5, 5, 0), Vec3(-1, 0, 0));

    RayHit hit = capsule.closest_to_ray(ray);
    CHECK(!hit.hit());
    CHECK(hit.distance > 0);
}

TEST_CASE("CapsuleCollider closest_to_capsule parallel")
{
    CapsuleCollider c1(1.0, 0.5);  // at origin
    CapsuleCollider c2(1.0, 0.5, GeneralPose3(Quat::identity(), Vec3(3, 0, 0)));

    ColliderHit hit = c1.closest_to_collider(c2);
    CHECK(!hit.colliding());
    CHECK_EQ(hit.distance, Approx(2.0).epsilon(1e-8));  // 3 - 0.5 - 0.5 = 2
}

TEST_CASE("CapsuleCollider closest_to_capsule overlapping")
{
    CapsuleCollider c1(1.0, 0.5);  // at origin
    CapsuleCollider c2(1.0, 0.5, GeneralPose3(Quat::identity(), Vec3(0.5, 0, 0)));

    ColliderHit hit = c1.closest_to_collider(c2);
    CHECK(hit.colliding());
    CHECK_EQ(hit.distance, Approx(-0.5).epsilon(1e-8));  // 0.5 - 1.0 = -0.5
}

TEST_CASE("CapsuleCollider closest_to_sphere")
{
    CapsuleCollider capsule(1.0, 0.5);  // at origin
    SphereCollider sphere(0.5, GeneralPose3(Quat::identity(), Vec3(3, 0, 0)));

    ColliderHit hit = capsule.closest_to_collider(sphere);
    CHECK(!hit.colliding());
    CHECK_EQ(hit.distance, Approx(2.0).epsilon(1e-8));  // 3 - 0.5 - 0.5 = 2
}

TEST_CASE("CapsuleCollider closest_to_box")
{
    CapsuleCollider capsule(1.0, 0.5);  // at origin
    BoxCollider box(Vec3(0.5, 0.5, 0.5), GeneralPose3(Quat::identity(), Vec3(3, 0, 0)));

    ColliderHit hit = capsule.closest_to_collider(box);
    CHECK(!hit.colliding());
    // Distance: 3 - 0.5 - 0.5 = 2
    CHECK_EQ(hit.distance, Approx(2.0).epsilon(1e-8));
}

// ==================== Cross-type collision tests ====================

TEST_CASE("Box to Sphere collision")
{
    BoxCollider box(Vec3(1, 1, 1));  // half_size (1,1,1), at origin
    SphereCollider sphere(0.5, GeneralPose3(Quat::identity(), Vec3(3, 0, 0)));

    ColliderHit hit = box.closest_to_collider(sphere);
    CHECK(!hit.colliding());
    // Distance: 3 - 1 - 0.5 = 1.5
    CHECK_EQ(hit.distance, Approx(1.5).epsilon(1e-8));
}

TEST_CASE("Box to Capsule collision")
{
    BoxCollider box(Vec3(1, 1, 1));  // at origin
    CapsuleCollider capsule(1.0, 0.5, GeneralPose3(Quat::identity(), Vec3(4, 0, 0)));

    ColliderHit hit = box.closest_to_collider(capsule);
    CHECK(!hit.colliding());
    // Distance: 4 - 1 - 0.5 = 2.5
    CHECK_EQ(hit.distance, Approx(2.5).epsilon(1e-8));
}

TEST_CASE("Sphere to Capsule collision")
{
    SphereCollider sphere(1.0);  // at origin
    CapsuleCollider capsule(1.0, 0.5, GeneralPose3(Quat::identity(), Vec3(3, 0, 0)));

    ColliderHit hit = sphere.closest_to_collider(capsule);
    CHECK(!hit.colliding());
    // Distance: 3 - 1 - 0.5 = 1.5
    CHECK_EQ(hit.distance, Approx(1.5).epsilon(1e-8));
}

// ==================== Scale tests ====================

TEST_CASE("BoxCollider with scale")
{
    // Box with half_size (1,1,1) but scaled by (2,2,2) -> effective half_size (2,2,2)
    BoxCollider box(Vec3(1, 1, 1), GeneralPose3(Quat::identity(), Vec3(0, 0, 0), Vec3(2, 2, 2)));
    Vec3 eff = box.effective_half_size();
    CHECK_EQ(eff.x, Approx(2.0).epsilon(1e-12));
    CHECK_EQ(eff.y, Approx(2.0).epsilon(1e-12));
    CHECK_EQ(eff.z, Approx(2.0).epsilon(1e-12));
}

TEST_CASE("BoxCollider with non-uniform scale")
{
    // Box with half_size (1,1,1) but scaled by (2,3,4)
    BoxCollider box(Vec3(1, 1, 1), GeneralPose3(Quat::identity(), Vec3(0, 0, 0), Vec3(2, 3, 4)));
    Vec3 eff = box.effective_half_size();
    CHECK_EQ(eff.x, Approx(2.0).epsilon(1e-12));
    CHECK_EQ(eff.y, Approx(3.0).epsilon(1e-12));
    CHECK_EQ(eff.z, Approx(4.0).epsilon(1e-12));
}

TEST_CASE("SphereCollider with scale")
{
    // Sphere with radius 1.0 but scaled by (2,3,4) -> effective radius = min(2,3,4) * 1 = 2
    SphereCollider sphere(1.0, GeneralPose3(Quat::identity(), Vec3(0, 0, 0), Vec3(2, 3, 4)));
    CHECK_EQ(sphere.effective_radius(), Approx(2.0).epsilon(1e-12));
}

TEST_CASE("CapsuleCollider with scale")
{
    // Capsule with half_height=1, radius=0.5
    // scale (2, 3, 4) -> effective_half_height = 1*4 = 4, effective_radius = 0.5*min(2,3) = 1
    CapsuleCollider capsule(1.0, 0.5, GeneralPose3(Quat::identity(), Vec3(0, 0, 0), Vec3(2, 3, 4)));
    CHECK_EQ(capsule.effective_half_height(), Approx(4.0).epsilon(1e-12));
    CHECK_EQ(capsule.effective_radius(), Approx(1.0).epsilon(1e-12));
}
