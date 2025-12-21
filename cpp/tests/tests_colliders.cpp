#include "guard/guard.h"
#include "termin/colliders/colliders.hpp"
#include <cmath>

using guard::Approx;
using namespace termin::colliders;
using termin::geom::Vec3;
using termin::geom::Pose3;
using termin::geom::Quat;
using termin::geom::Ray3;

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
    BoxCollider box(Vec3(0, 0, 0), Vec3(1, 1, 1));
    Vec3 c = box.center();
    CHECK_EQ(c.x, Approx(0.0).epsilon(1e-12));
    CHECK_EQ(c.y, Approx(0.0).epsilon(1e-12));
    CHECK_EQ(c.z, Approx(0.0).epsilon(1e-12));
}

TEST_CASE("BoxCollider center with pose")
{
    BoxCollider box(Vec3(0, 0, 0), Vec3(1, 1, 1), Pose3(Quat::identity(), Vec3(5, 0, 0)));
    Vec3 c = box.center();
    CHECK_EQ(c.x, Approx(5.0).epsilon(1e-12));
    CHECK_EQ(c.y, Approx(0.0).epsilon(1e-12));
    CHECK_EQ(c.z, Approx(0.0).epsilon(1e-12));
}

TEST_CASE("BoxCollider closest_to_ray hit")
{
    BoxCollider box(Vec3(0, 0, 0), Vec3(1, 1, 1));  // half_size = (1,1,1) -> box from -1 to 1
    Ray3 ray(Vec3(5, 0, 0), Vec3(-1, 0, 0));

    RayHit hit = box.closest_to_ray(ray);
    CHECK(hit.hit());
    CHECK_EQ(hit.distance, Approx(0.0).epsilon(1e-8));
    CHECK_EQ(hit.point_on_collider.x, Approx(1.0).epsilon(1e-8));
}

TEST_CASE("BoxCollider closest_to_ray miss")
{
    BoxCollider box(Vec3(0, 0, 0), Vec3(1, 1, 1));
    Ray3 ray(Vec3(5, 5, 0), Vec3(-1, 0, 0));  // Ray misses box

    RayHit hit = box.closest_to_ray(ray);
    CHECK(!hit.hit());
    CHECK(hit.distance > 0);
}

TEST_CASE("BoxCollider closest_to_box")
{
    BoxCollider box1(Vec3(0, 0, 0), Vec3(1, 1, 1));
    BoxCollider box2(Vec3(5, 0, 0), Vec3(1, 1, 1));

    ColliderHit hit = box1.closest_to_collider(box2);
    CHECK(!hit.colliding());
    // Distance between two boxes: 5 - 2 = 3 (each box extends 1 unit)
    CHECK_EQ(hit.distance, Approx(3.0).epsilon(1e-8));
}

TEST_CASE("BoxCollider closest_to_box touching")
{
    BoxCollider box1(Vec3(0, 0, 0), Vec3(1, 1, 1));  // from -1 to 1
    BoxCollider box2(Vec3(2, 0, 0), Vec3(1, 1, 1));  // from 1 to 3, exactly touching at x=1

    ColliderHit hit = box1.closest_to_collider(box2);
    // Distance should be 0 (touching)
    CHECK_EQ(hit.distance, Approx(0.0).epsilon(1e-6));
}

TEST_CASE("BoxCollider closest_to_box overlapping")
{
    BoxCollider box1(Vec3(0, 0, 0), Vec3(1, 1, 1));  // from -1 to 1
    BoxCollider box2(Vec3(1, 0, 0), Vec3(1, 1, 1));  // from 0 to 2, overlapping

    ColliderHit hit = box1.closest_to_collider(box2);
    CHECK(hit.colliding());
    // Penetration = 1 (overlap from 0 to 1)
    CHECK_EQ(hit.distance, Approx(-1.0).epsilon(1e-6));
}

// ==================== SphereCollider tests ====================

TEST_CASE("SphereCollider center")
{
    SphereCollider sphere(Vec3(1, 2, 3), 0.5);
    Vec3 c = sphere.center();
    CHECK_EQ(c.x, Approx(1.0).epsilon(1e-12));
    CHECK_EQ(c.y, Approx(2.0).epsilon(1e-12));
    CHECK_EQ(c.z, Approx(3.0).epsilon(1e-12));
}

TEST_CASE("SphereCollider closest_to_ray hit")
{
    SphereCollider sphere(Vec3(0, 0, 0), 1.0);
    Ray3 ray(Vec3(5, 0, 0), Vec3(-1, 0, 0));

    RayHit hit = sphere.closest_to_ray(ray);
    CHECK(hit.hit());
    CHECK_EQ(hit.distance, Approx(0.0).epsilon(1e-8));
    CHECK_EQ(hit.point_on_collider.x, Approx(1.0).epsilon(1e-8));
}

TEST_CASE("SphereCollider closest_to_ray miss")
{
    SphereCollider sphere(Vec3(0, 0, 0), 1.0);
    Ray3 ray(Vec3(5, 5, 0), Vec3(-1, 0, 0));  // Ray misses sphere

    RayHit hit = sphere.closest_to_ray(ray);
    CHECK(!hit.hit());
    CHECK(hit.distance > 0);
}

TEST_CASE("SphereCollider closest_to_sphere")
{
    SphereCollider s1(Vec3(0, 0, 0), 1.0);
    SphereCollider s2(Vec3(5, 0, 0), 1.0);

    ColliderHit hit = s1.closest_to_collider(s2);
    CHECK(!hit.colliding());
    // Distance: 5 - 2 = 3
    CHECK_EQ(hit.distance, Approx(3.0).epsilon(1e-8));
}

TEST_CASE("SphereCollider closest_to_sphere touching")
{
    SphereCollider s1(Vec3(0, 0, 0), 1.0);
    SphereCollider s2(Vec3(2, 0, 0), 1.0);  // Exactly touching

    ColliderHit hit = s1.closest_to_collider(s2);
    CHECK_EQ(hit.distance, Approx(0.0).epsilon(1e-8));
}

TEST_CASE("SphereCollider closest_to_sphere overlapping")
{
    SphereCollider s1(Vec3(0, 0, 0), 1.0);
    SphereCollider s2(Vec3(1, 0, 0), 1.0);  // Overlapping

    ColliderHit hit = s1.closest_to_collider(s2);
    CHECK(hit.colliding());
    CHECK_EQ(hit.distance, Approx(-1.0).epsilon(1e-8));  // Penetration = 1
}

TEST_CASE("SphereCollider closest_to_box")
{
    SphereCollider sphere(Vec3(0, 0, 0), 1.0);
    BoxCollider box(Vec3(5, 0, 0), Vec3(1, 1, 1));

    ColliderHit hit = sphere.closest_to_collider(box);
    CHECK(!hit.colliding());
    // Distance: 4 - 1 = 3
    CHECK_EQ(hit.distance, Approx(3.0).epsilon(1e-8));
}

// ==================== CapsuleCollider tests ====================

TEST_CASE("CapsuleCollider center")
{
    CapsuleCollider capsule(Vec3(0, 0, -1), Vec3(0, 0, 1), 0.5);
    Vec3 c = capsule.center();
    CHECK_EQ(c.x, Approx(0.0).epsilon(1e-12));
    CHECK_EQ(c.y, Approx(0.0).epsilon(1e-12));
    CHECK_EQ(c.z, Approx(0.0).epsilon(1e-12));
}

TEST_CASE("CapsuleCollider closest_to_ray hit cylinder")
{
    CapsuleCollider capsule(Vec3(0, 0, -1), Vec3(0, 0, 1), 0.5);
    Ray3 ray(Vec3(5, 0, 0), Vec3(-1, 0, 0));

    RayHit hit = capsule.closest_to_ray(ray);
    CHECK(hit.hit());
    CHECK_EQ(hit.distance, Approx(0.0).epsilon(1e-8));
    CHECK_EQ(hit.point_on_collider.x, Approx(0.5).epsilon(1e-8));
}

TEST_CASE("CapsuleCollider closest_to_ray hit cap")
{
    CapsuleCollider capsule(Vec3(0, 0, -1), Vec3(0, 0, 1), 0.5);
    Ray3 ray(Vec3(0, 0, 5), Vec3(0, 0, -1));

    RayHit hit = capsule.closest_to_ray(ray);
    CHECK(hit.hit());
    CHECK_EQ(hit.distance, Approx(0.0).epsilon(1e-8));
    CHECK_EQ(hit.point_on_collider.z, Approx(1.5).epsilon(1e-8));  // top cap
}

TEST_CASE("CapsuleCollider closest_to_ray miss")
{
    CapsuleCollider capsule(Vec3(0, 0, -1), Vec3(0, 0, 1), 0.5);
    Ray3 ray(Vec3(5, 5, 0), Vec3(-1, 0, 0));

    RayHit hit = capsule.closest_to_ray(ray);
    CHECK(!hit.hit());
    CHECK(hit.distance > 0);
}

TEST_CASE("CapsuleCollider closest_to_capsule parallel")
{
    CapsuleCollider c1(Vec3(0, 0, -1), Vec3(0, 0, 1), 0.5);
    CapsuleCollider c2(Vec3(3, 0, -1), Vec3(3, 0, 1), 0.5);

    ColliderHit hit = c1.closest_to_collider(c2);
    CHECK(!hit.colliding());
    CHECK_EQ(hit.distance, Approx(2.0).epsilon(1e-8));  // 3 - 0.5 - 0.5 = 2
}

TEST_CASE("CapsuleCollider closest_to_capsule overlapping")
{
    CapsuleCollider c1(Vec3(0, 0, -1), Vec3(0, 0, 1), 0.5);
    CapsuleCollider c2(Vec3(0.5, 0, -1), Vec3(0.5, 0, 1), 0.5);

    ColliderHit hit = c1.closest_to_collider(c2);
    CHECK(hit.colliding());
    CHECK_EQ(hit.distance, Approx(-0.5).epsilon(1e-8));  // 0.5 - 1.0 = -0.5
}

TEST_CASE("CapsuleCollider closest_to_sphere")
{
    CapsuleCollider capsule(Vec3(0, 0, -1), Vec3(0, 0, 1), 0.5);
    SphereCollider sphere(Vec3(3, 0, 0), 0.5);

    ColliderHit hit = capsule.closest_to_collider(sphere);
    CHECK(!hit.colliding());
    CHECK_EQ(hit.distance, Approx(2.0).epsilon(1e-8));  // 3 - 0.5 - 0.5 = 2
}

TEST_CASE("CapsuleCollider closest_to_box")
{
    CapsuleCollider capsule(Vec3(0, 0, -1), Vec3(0, 0, 1), 0.5);
    BoxCollider box(Vec3(3, 0, 0), Vec3(0.5, 0.5, 0.5));

    ColliderHit hit = capsule.closest_to_collider(box);
    CHECK(!hit.colliding());
    // Distance: 3 - 0.5 - 0.5 = 2
    CHECK_EQ(hit.distance, Approx(2.0).epsilon(1e-8));
}

// ==================== Transform tests ====================

TEST_CASE("BoxCollider transform_by")
{
    BoxCollider box(Vec3(0, 0, 0), Vec3(1, 1, 1));
    Pose3 transform(Quat::identity(), Vec3(5, 0, 0));

    auto transformed = box.transform_by(transform);
    Vec3 c = transformed->center();
    CHECK_EQ(c.x, Approx(5.0).epsilon(1e-12));
}

TEST_CASE("SphereCollider transform_by")
{
    SphereCollider sphere(Vec3(0, 0, 0), 1.0);
    Pose3 transform(Quat::identity(), Vec3(5, 0, 0));

    auto transformed = sphere.transform_by(transform);
    Vec3 c = transformed->center();
    CHECK_EQ(c.x, Approx(5.0).epsilon(1e-12));
}

TEST_CASE("CapsuleCollider transform_by")
{
    CapsuleCollider capsule(Vec3(0, 0, -1), Vec3(0, 0, 1), 0.5);
    Pose3 transform(Quat::identity(), Vec3(5, 0, 0));

    auto transformed = capsule.transform_by(transform);
    Vec3 c = transformed->center();
    CHECK_EQ(c.x, Approx(5.0).epsilon(1e-12));
}

// ==================== Cross-type collision tests ====================

TEST_CASE("Box to Sphere collision")
{
    BoxCollider box(Vec3(0, 0, 0), Vec3(1, 1, 1));  // half_size (1,1,1)
    SphereCollider sphere(Vec3(3, 0, 0), 0.5);

    ColliderHit hit = box.closest_to_collider(sphere);
    CHECK(!hit.colliding());
    // Distance: 3 - 1 - 0.5 = 1.5
    CHECK_EQ(hit.distance, Approx(1.5).epsilon(1e-8));
}

TEST_CASE("Box to Capsule collision")
{
    BoxCollider box(Vec3(0, 0, 0), Vec3(1, 1, 1));
    CapsuleCollider capsule(Vec3(4, 0, -1), Vec3(4, 0, 1), 0.5);

    ColliderHit hit = box.closest_to_collider(capsule);
    CHECK(!hit.colliding());
    // Distance: 4 - 1 - 0.5 = 2.5
    CHECK_EQ(hit.distance, Approx(2.5).epsilon(1e-8));
}

TEST_CASE("Sphere to Capsule collision")
{
    SphereCollider sphere(Vec3(0, 0, 0), 1.0);
    CapsuleCollider capsule(Vec3(3, 0, -1), Vec3(3, 0, 1), 0.5);

    ColliderHit hit = sphere.closest_to_collider(capsule);
    CHECK(!hit.colliding());
    // Distance: 3 - 1 - 0.5 = 1.5
    CHECK_EQ(hit.distance, Approx(1.5).epsilon(1e-8));
}
