#include "guard_main.h"
#include "termin/collision/collision.hpp"
#include "termin/geom/general_transform3.hpp"
#include <cmath>

using namespace termin;
using namespace termin::colliders;

static void check_normal(const Vec3& actual, const Vec3& expected) {
    CHECK((actual - expected).norm() < 1e-8);
    CHECK(std::abs(actual.norm() - 1.0) < 1e-8);
}

TEST_CASE("Raycast floor normal is constant across a rotated nonuniformly scaled box") {
    const Quat rotation(0, std::sin(0.6), 0, std::cos(0.6));
    const GeneralPose3 pose(rotation, Vec3(13, -2, 24), Vec3(2, 0.7, 0.3));
    BoxCollider floor(Vec3(4, 3, 0.5), pose);
    collision::CollisionWorld world;
    world.add(&floor);
    const Vec3 normal = rotation.rotate(Vec3(0, 0, 1));
    for (double x : {-3.99, -2.0, 0.0, 2.0, 3.99}) {
        for (double y : {-2.99, 0.0, 2.99}) {
            const Vec3 point = pose.transform_point(Vec3(x, y, 0.5));
            const Ray3 ray(point + normal * 2.0, -normal);
            const auto primitive_hit = floor.closest_to_ray(ray);
            CHECK(primitive_hit.hit());
            CHECK((primitive_hit.point_on_ray - point).norm() < 1e-8);
            check_normal(primitive_hit.normal, normal);
            const auto hit = world.raycast_closest(ray);
            CHECK(hit.hit());
            check_normal(hit.normal, normal);
        }
    }
    const auto inside = floor.closest_to_ray(Ray3(pose.lin, normal));
    CHECK(inside.hit());
    check_normal(inside.normal, normal);
    CHECK((inside.point_on_ray - pose.transform_point(Vec3(0, 0, 0.5))).norm() < 1e-8);
    const auto miss = floor.closest_to_ray(Ray3(pose.transform_point(Vec3(5, 0, 2)), normal));
    CHECK(!miss.hit());
    CHECK(miss.normal.norm() == 0.0);
}

TEST_CASE("Raycast sphere and capsule return surface rather than center direction") {
    SphereCollider sphere(2.0, GeneralPose3(Quat::identity(), Vec3(3, 4, 5), Vec3(2, 3, 4)));
    const Vec3 sphere_normal = Vec3(1, 2, 3).normalized();
    auto hit = sphere.closest_to_ray(Ray3(sphere.center() + sphere_normal * 8, -sphere_normal));
    CHECK(hit.hit());
    check_normal(hit.normal, sphere_normal);
    hit = sphere.closest_to_ray(Ray3(sphere.center(), sphere_normal));
    CHECK(hit.hit());
    check_normal(hit.normal, sphere_normal);

    const Quat rotation(std::sin(0.4), 0, 0, std::cos(0.4));
    const GeneralPose3 pose(rotation, Vec3(10, 20, 30), Vec3(2, 3, 1.5));
    CapsuleCollider capsule(2.0, 0.5, pose);
    const Vec3 side_normal = rotation.rotate(Vec3(1, 0, 0));
    const Vec3 side = pose.lin + rotation.rotate(Vec3(1, 0, 2));
    hit = capsule.closest_to_ray(Ray3(side + side_normal * 2, -side_normal));
    CHECK(hit.hit());
    CHECK((hit.point_on_ray - side).norm() < 1e-8);
    check_normal(hit.normal, side_normal);
    const Vec3 cap_normal = rotation.rotate(Vec3(0.6, 0, 0.8));
    const Vec3 cap_point = capsule.world_b() + cap_normal;
    hit = capsule.closest_to_ray(Ray3(cap_point + cap_normal * 2, -cap_normal));
    CHECK(hit.hit());
    check_normal(hit.normal, cap_normal);
    hit = capsule.closest_to_ray(Ray3(pose.lin, side_normal));
    CHECK(hit.hit());
    CHECK((hit.point_on_ray - pose.lin).norm() < 1e-8);
    CHECK(hit.normal.norm() == 0.0); // Existing interior-overlap contract.
    hit = capsule.closest_to_ray(Ray3(side, side_normal));
    check_normal(hit.normal, side_normal);
}

TEST_CASE("Raycast convex slope normal uses inverse transpose for nonuniform scale") {
    const Quat rotation(0, 0, std::sin(0.35), std::cos(0.35));
    const GeneralPose3 pose(rotation, Vec3(3, 5, 8), Vec3(2, 0.5, 3));
    auto hull = ConvexHullCollider::from_points({Vec3(0, 0, 0), Vec3(2, 0, 0), Vec3(0, 3, 0), Vec3(0, 0, 1)}, pose);
    const Vec3 normal = rotation.rotate(Vec3(0.25, 2.0 / 3.0, 1.0 / 3.0).normalized());
    const Vec3 point = pose.transform_point(Vec3(2.0 / 3.0, 1.0, 1.0 / 3.0));
    const auto hit = hull.closest_to_ray(Ray3(point + normal * 4, -normal));
    CHECK(hit.hit());
    CHECK((hit.point_on_ray - point).norm() < 1e-8);
    check_normal(hit.normal, normal);
    const auto inside = hull.closest_to_ray(Ray3(point - normal * 0.05, normal));
    CHECK(inside.hit());
    check_normal(inside.normal, normal);
}

TEST_CASE("Attached and Union raycasts retain the hit child surface normal") {
    const auto pool_handle = tc_entity_pool_registry_create(4);
    auto* pool = tc_entity_pool_registry_get(pool_handle);
    const auto entity = tc_entity_pool_alloc(pool, "rotated_floor");
    const double position[3] = {3, 7, -24};
    const double scale[3] = {2, 0.5, 3};
    const double rotation[4] = {0, std::sin(0.6), 0, std::cos(0.6)};
    tc_entity_pool_set_local_position(pool, entity, position);
    tc_entity_pool_set_local_scale(pool, entity, scale);
    tc_entity_pool_set_local_rotation(pool, entity, rotation);
    GeneralTransform3 transform(pool_handle, entity);
    BoxCollider floor(Vec3(4, 3, 0.2));
    AttachedCollider attached(&floor, &transform);
    SphereCollider remote(1.0, GeneralPose3(Quat::identity(), Vec3(100, 100, 100)));
    UnionCollider composite({&remote, &attached});
    const auto pose = attached.world_transform();
    const Vec3 normal = pose.ang.rotate(Vec3(0, 0, 1));
    const Vec3 point = pose.transform_point(Vec3(3.9, -2.9, 0.2));
    const Ray3 ray(point + normal * 2, -normal);
    check_normal(attached.closest_to_ray(ray).normal, normal);
    check_normal(composite.closest_to_ray(ray).normal, normal);
    collision::CollisionWorld world;
    world.add(&composite);
    check_normal(world.raycast_closest(ray).normal, normal);
    tc_entity_pool_registry_destroy(pool_handle);
}
