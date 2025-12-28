#include "guard/guard.h"
#include "termin/collision/collision.hpp"
#include "termin/geom/general_transform3.hpp"
#include "termin/entity/entity.hpp"
#include <vector>
#include <algorithm>

using guard::Approx;
using namespace termin::collision;
using namespace termin::colliders;
using termin::Vec3;
using termin::Pose3;
using termin::Quat;
using termin::Ray3;
using termin::AABB;
using termin::GeneralTransform3;
using termin::GeneralPose3;
using termin::Entity;

// ==================== BVH tests ====================

TEST_CASE("BVH empty")
{
    BVH bvh;
    CHECK(bvh.empty());
    CHECK_EQ(bvh.node_count(), 0u);
}

TEST_CASE("BVH insert single")
{
    BVH bvh;
    SphereCollider sphere(1.0);  // at origin

    bvh.insert(&sphere, sphere.aabb());

    CHECK(!bvh.empty());
    CHECK_EQ(bvh.node_count(), 1u);
    CHECK(bvh.validate());
}

TEST_CASE("BVH insert multiple")
{
    BVH bvh;
    SphereCollider s1(1.0);  // at origin
    SphereCollider s2(1.0, GeneralPose3(Quat::identity(), Vec3(5, 0, 0)));
    SphereCollider s3(1.0, GeneralPose3(Quat::identity(), Vec3(10, 0, 0)));

    bvh.insert(&s1, s1.aabb());
    bvh.insert(&s2, s2.aabb());
    bvh.insert(&s3, s3.aabb());

    CHECK_EQ(bvh.node_count(), 5u);  // 3 leaves + 2 internal nodes
    CHECK(bvh.validate());
}

TEST_CASE("BVH remove")
{
    BVH bvh;
    SphereCollider s1(1.0);
    SphereCollider s2(1.0, GeneralPose3(Quat::identity(), Vec3(5, 0, 0)));

    bvh.insert(&s1, s1.aabb());
    bvh.insert(&s2, s2.aabb());
    CHECK_EQ(bvh.node_count(), 3u);

    bvh.remove(&s1);
    CHECK_EQ(bvh.node_count(), 1u);
    CHECK(bvh.validate());

    bvh.remove(&s2);
    CHECK(bvh.empty());
}

TEST_CASE("BVH update no change")
{
    BVH bvh;
    SphereCollider sphere(1.0);
    bvh.insert(&sphere, sphere.aabb());

    // Small movement within fattened AABB
    bool changed = bvh.update(&sphere, sphere.aabb());
    CHECK(!changed);
}

TEST_CASE("BVH update with movement")
{
    BVH bvh;
    SphereCollider sphere(1.0);
    bvh.insert(&sphere, sphere.aabb());

    // Large movement outside fattened AABB
    sphere = SphereCollider(1.0, GeneralPose3(Quat::identity(), Vec3(10, 0, 0)));
    bool changed = bvh.update(&sphere, sphere.aabb());
    CHECK(changed);
    CHECK(bvh.validate());
}

TEST_CASE("BVH query_aabb")
{
    BVH bvh;
    SphereCollider s1(1.0);
    SphereCollider s2(1.0, GeneralPose3(Quat::identity(), Vec3(5, 0, 0)));
    SphereCollider s3(1.0, GeneralPose3(Quat::identity(), Vec3(10, 0, 0)));

    bvh.insert(&s1, s1.aabb());
    bvh.insert(&s2, s2.aabb());
    bvh.insert(&s3, s3.aabb());

    // Query overlapping s1
    std::vector<Collider*> result;
    AABB query_box(Vec3(-2, -2, -2), Vec3(2, 2, 2));
    bvh.query_aabb(query_box, [&](Collider* c) {
        result.push_back(c);
    });

    CHECK_EQ(result.size(), 1u);
    CHECK_EQ(result[0], &s1);
}

TEST_CASE("BVH query_aabb multiple")
{
    BVH bvh;
    SphereCollider s1(1.0);
    SphereCollider s2(1.0, GeneralPose3(Quat::identity(), Vec3(3, 0, 0)));
    SphereCollider s3(1.0, GeneralPose3(Quat::identity(), Vec3(10, 0, 0)));

    bvh.insert(&s1, s1.aabb());
    bvh.insert(&s2, s2.aabb());
    bvh.insert(&s3, s3.aabb());

    std::vector<Collider*> result;
    AABB query_box(Vec3(-2, -2, -2), Vec3(5, 2, 2));
    bvh.query_aabb(query_box, [&](Collider* c) {
        result.push_back(c);
    });

    CHECK_EQ(result.size(), 2u);
}

TEST_CASE("BVH query_ray")
{
    BVH bvh;
    SphereCollider s1(1.0);
    SphereCollider s2(1.0, GeneralPose3(Quat::identity(), Vec3(5, 0, 0)));
    SphereCollider s3(1.0, GeneralPose3(Quat::identity(), Vec3(0, 5, 0)));

    bvh.insert(&s1, s1.aabb());
    bvh.insert(&s2, s2.aabb());
    bvh.insert(&s3, s3.aabb());

    Ray3 ray(Vec3(-10, 0, 0), Vec3(1, 0, 0));

    std::vector<Collider*> result;
    bvh.query_ray(ray, [&](Collider* c, double, double) {
        result.push_back(c);
    });

    CHECK_EQ(result.size(), 2u);  // s1 and s2 are on the ray path
}

TEST_CASE("BVH query_all_pairs")
{
    CollisionWorld world;
    SphereCollider s1(2.0);
    SphereCollider s2(2.0, GeneralPose3(Quat::identity(), Vec3(3, 0, 0)));  // Overlaps with s1
    SphereCollider s3(1.0, GeneralPose3(Quat::identity(), Vec3(10, 0, 0))); // Far away

    world.add(&s1);
    world.add(&s2);
    world.add(&s3);

    std::vector<std::pair<Collider*, Collider*>> pairs;
    world.bvh().query_all_pairs([&](Collider* a, Collider* b) {
        pairs.push_back({a, b});
    });

    // s1 and s2 should be a pair (overlapping AABBs)
    CHECK(pairs.size() >= 1u);
}

// ==================== CollisionWorld tests ====================

TEST_CASE("CollisionWorld empty")
{
    CollisionWorld world;
    CHECK_EQ(world.size(), 0u);

    auto manifolds = world.detect_contacts();
    CHECK(manifolds.empty());
}

TEST_CASE("CollisionWorld add/remove")
{
    CollisionWorld world;
    SphereCollider sphere(1.0);

    world.add(&sphere);
    CHECK_EQ(world.size(), 1u);
    CHECK(world.contains(&sphere));

    world.remove(&sphere);
    CHECK_EQ(world.size(), 0u);
    CHECK(!world.contains(&sphere));
}

TEST_CASE("CollisionWorld detect_contacts no collision")
{
    CollisionWorld world;
    SphereCollider s1(1.0);
    SphereCollider s2(1.0, GeneralPose3(Quat::identity(), Vec3(5, 0, 0)));

    world.add(&s1);
    world.add(&s2);

    auto manifolds = world.detect_contacts();
    CHECK(manifolds.empty());
}

TEST_CASE("CollisionWorld detect_contacts with collision")
{
    CollisionWorld world;
    SphereCollider s1(1.0);
    SphereCollider s2(1.0, GeneralPose3(Quat::identity(), Vec3(1.5, 0, 0)));  // Overlapping

    world.add(&s1);
    world.add(&s2);

    auto manifolds = world.detect_contacts();
    CHECK_EQ(manifolds.size(), 1u);

    const auto& m = manifolds[0];
    CHECK_EQ(m.point_count, 1);
    CHECK(m.points[0].penetration < 0);  // Negative = penetrating
}

TEST_CASE("CollisionWorld detect_contacts multiple")
{
    CollisionWorld world;
    SphereCollider s1(1.0);
    SphereCollider s2(1.0, GeneralPose3(Quat::identity(), Vec3(1.5, 0, 0)));
    SphereCollider s3(1.0, GeneralPose3(Quat::identity(), Vec3(0, 1.5, 0)));

    world.add(&s1);
    world.add(&s2);
    world.add(&s3);

    auto manifolds = world.detect_contacts();
    CHECK_EQ(manifolds.size(), 2u);  // s1-s2 and s1-s3
}

TEST_CASE("CollisionWorld update_pose")
{
    CollisionWorld world;
    SphereCollider s1(1.0);
    SphereCollider s2(1.0, GeneralPose3(Quat::identity(), Vec3(5, 0, 0)));

    world.add(&s1);
    world.add(&s2);

    auto manifolds = world.detect_contacts();
    CHECK(manifolds.empty());

    // Move s2 to overlap with s1
    s2 = SphereCollider(1.0, GeneralPose3(Quat::identity(), Vec3(1.5, 0, 0)));
    world.update_pose(&s2);

    manifolds = world.detect_contacts();
    CHECK_EQ(manifolds.size(), 1u);
}

TEST_CASE("CollisionWorld query_aabb")
{
    CollisionWorld world;
    SphereCollider s1(1.0);
    SphereCollider s2(1.0, GeneralPose3(Quat::identity(), Vec3(5, 0, 0)));

    world.add(&s1);
    world.add(&s2);

    auto result = world.query_aabb(AABB(Vec3(-2, -2, -2), Vec3(2, 2, 2)));
    CHECK_EQ(result.size(), 1u);
    CHECK_EQ(result[0], &s1);
}

TEST_CASE("CollisionWorld raycast")
{
    CollisionWorld world;
    SphereCollider s1(1.0);
    SphereCollider s2(1.0, GeneralPose3(Quat::identity(), Vec3(5, 0, 0)));
    SphereCollider s3(1.0, GeneralPose3(Quat::identity(), Vec3(0, 5, 0)));

    world.add(&s1);
    world.add(&s2);
    world.add(&s3);

    Ray3 ray(Vec3(-10, 0, 0), Vec3(1, 0, 0));
    auto hits = world.raycast(ray);

    CHECK_EQ(hits.size(), 2u);  // s1 and s2
    // Should be sorted by distance
    CHECK(hits[0].distance < hits[1].distance);
}

TEST_CASE("CollisionWorld raycast_closest")
{
    CollisionWorld world;
    SphereCollider s1(1.0);
    SphereCollider s2(1.0, GeneralPose3(Quat::identity(), Vec3(5, 0, 0)));

    world.add(&s1);
    world.add(&s2);

    Ray3 ray(Vec3(-10, 0, 0), Vec3(1, 0, 0));
    auto hit = world.raycast_closest(ray);

    CHECK(hit.hit());
    CHECK_EQ(hit.collider, &s1);
    CHECK_EQ(hit.distance, Approx(9.0).epsilon(1e-6));  // Ray starts at -10, hits at -1
}

TEST_CASE("CollisionWorld raycast miss")
{
    CollisionWorld world;
    SphereCollider s1(1.0);

    world.add(&s1);

    Ray3 ray(Vec3(-10, 5, 0), Vec3(1, 0, 0));  // Misses the sphere
    auto hit = world.raycast_closest(ray);

    CHECK(!hit.hit());
}

// ==================== Mixed collider tests ====================

TEST_CASE("CollisionWorld mixed colliders")
{
    CollisionWorld world;
    SphereCollider sphere(1.0);
    // Overlapping with sphere: box center at (1.2, 0, 0), half_size (0.5,0.5,0.5) extends to 0.7 in x
    BoxCollider box(Vec3(0.5, 0.5, 0.5), GeneralPose3(Quat::identity(), Vec3(1.2, 0, 0)));
    // Overlapping with sphere: capsule axis at y=1.2, radius 0.5 => surface at y=0.7
    CapsuleCollider capsule(0.5, 0.5, GeneralPose3(Quat::identity(), Vec3(0, 1.2, 0)));

    world.add(&sphere);
    world.add(&box);
    world.add(&capsule);

    auto manifolds = world.detect_contacts();
    CHECK_EQ(manifolds.size(), 2u);  // sphere-box and sphere-capsule
}

// ==================== AttachedCollider tests ====================

TEST_CASE("AttachedCollider basic")
{
    SphereCollider sphere(1.0);  // at origin
    GeneralPose3 pose = GeneralPose3::translation(5, 0, 0);
    tc_transform* tc_t = tc_transform_new_with_pose(
        *reinterpret_cast<const tc_general_pose3*>(&pose));
    GeneralTransform3 transform(tc_t);
    AttachedCollider attached(&sphere, &transform);

    // Center should be translated
    Vec3 center = attached.center();
    CHECK_EQ(center.x, Approx(5.0).epsilon(1e-12));
    CHECK_EQ(center.y, Approx(0.0).epsilon(1e-12));
    CHECK_EQ(center.z, Approx(0.0).epsilon(1e-12));

    tc_transform_free(tc_t);
}

TEST_CASE("AttachedCollider in CollisionWorld")
{
    SphereCollider s1(1.0);
    SphereCollider s2(1.0);
    tc_transform* tc_t1 = tc_transform_new();
    GeneralPose3 pose2 = GeneralPose3::translation(5, 0, 0);
    tc_transform* tc_t2 = tc_transform_new_with_pose(
        *reinterpret_cast<const tc_general_pose3*>(&pose2));
    GeneralTransform3 t1(tc_t1);
    GeneralTransform3 t2(tc_t2);
    AttachedCollider a1(&s1, &t1);
    AttachedCollider a2(&s2, &t2);

    CollisionWorld world;
    world.add(&a1);
    world.add(&a2);

    // No collision - they're far apart
    auto manifolds = world.detect_contacts();
    CHECK(manifolds.empty());

    // Move t2 to overlap
    t2.relocate(GeneralPose3::translation(1.5, 0, 0));
    world.update_pose(&a2);

    manifolds = world.detect_contacts();
    CHECK_EQ(manifolds.size(), 1u);

    tc_transform_free(tc_t1);
    tc_transform_free(tc_t2);
}

// ==================== ContactManifold tests ====================

TEST_CASE("ContactManifold add_point")
{
    ContactManifold manifold;

    for (int i = 0; i < 4; ++i) {
        ContactPoint point;
        point.position = Vec3(i, 0, 0);
        CHECK(manifold.add_point(point));
    }

    CHECK_EQ(manifold.point_count, 4);

    // Fifth point should fail
    ContactPoint extra;
    CHECK(!manifold.add_point(extra));
}

TEST_CASE("ContactManifold clear")
{
    ContactManifold manifold;

    ContactPoint point;
    manifold.add_point(point);
    manifold.add_point(point);
    CHECK_EQ(manifold.point_count, 2);

    manifold.clear();
    CHECK_EQ(manifold.point_count, 0);
}

TEST_CASE("ContactManifold same_pair")
{
    SphereCollider s1(1.0);
    SphereCollider s2(1.0, GeneralPose3(Quat::identity(), Vec3(1, 0, 0)));
    SphereCollider s3(1.0, GeneralPose3(Quat::identity(), Vec3(2, 0, 0)));

    ContactManifold m1;
    m1.collider_a = &s1;
    m1.collider_b = &s2;

    ContactManifold m2;
    m2.collider_a = &s2;
    m2.collider_b = &s1;  // Same pair, reversed

    ContactManifold m3;
    m3.collider_a = &s1;
    m3.collider_b = &s3;  // Different pair

    CHECK(m1.same_pair(m2));
    CHECK(!m1.same_pair(m3));
}

TEST_CASE("ContactManifold pair_key")
{
    SphereCollider s1(1.0);
    SphereCollider s2(1.0, GeneralPose3(Quat::identity(), Vec3(1, 0, 0)));

    ContactManifold m1;
    m1.collider_a = &s1;
    m1.collider_b = &s2;

    ContactManifold m2;
    m2.collider_a = &s2;
    m2.collider_b = &s1;

    // Same pair should have same key
    CHECK_EQ(m1.pair_key(), m2.pair_key());
}

// ==================== AABB on colliders tests ====================

TEST_CASE("SphereCollider aabb")
{
    SphereCollider sphere(0.5, GeneralPose3(Quat::identity(), Vec3(1, 2, 3)));
    AABB box = sphere.aabb();

    CHECK_EQ(box.min_point.x, Approx(0.5).epsilon(1e-12));
    CHECK_EQ(box.min_point.y, Approx(1.5).epsilon(1e-12));
    CHECK_EQ(box.min_point.z, Approx(2.5).epsilon(1e-12));
    CHECK_EQ(box.max_point.x, Approx(1.5).epsilon(1e-12));
    CHECK_EQ(box.max_point.y, Approx(2.5).epsilon(1e-12));
    CHECK_EQ(box.max_point.z, Approx(3.5).epsilon(1e-12));
}

TEST_CASE("BoxCollider aabb identity")
{
    BoxCollider box(Vec3(1, 2, 3));  // half_size, at origin
    AABB aabb = box.aabb();

    CHECK_EQ(aabb.min_point.x, Approx(-1.0).epsilon(1e-12));
    CHECK_EQ(aabb.min_point.y, Approx(-2.0).epsilon(1e-12));
    CHECK_EQ(aabb.min_point.z, Approx(-3.0).epsilon(1e-12));
    CHECK_EQ(aabb.max_point.x, Approx(1.0).epsilon(1e-12));
    CHECK_EQ(aabb.max_point.y, Approx(2.0).epsilon(1e-12));
    CHECK_EQ(aabb.max_point.z, Approx(3.0).epsilon(1e-12));
}

TEST_CASE("CapsuleCollider aabb")
{
    CapsuleCollider capsule(1.0, 0.5);  // half_height=1, radius=0.5, axis along Z
    AABB aabb = capsule.aabb();

    CHECK_EQ(aabb.min_point.x, Approx(-0.5).epsilon(1e-12));
    CHECK_EQ(aabb.min_point.y, Approx(-0.5).epsilon(1e-12));
    CHECK_EQ(aabb.min_point.z, Approx(-1.5).epsilon(1e-12));
    CHECK_EQ(aabb.max_point.x, Approx(0.5).epsilon(1e-12));
    CHECK_EQ(aabb.max_point.y, Approx(0.5).epsilon(1e-12));
    CHECK_EQ(aabb.max_point.z, Approx(1.5).epsilon(1e-12));
}
