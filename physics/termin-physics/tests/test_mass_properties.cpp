#include "guard_main.h"

#include <algorithm>
#include <array>
#include <cmath>
#include <string>
#include <vector>

#include <termin/colliders/colliders.hpp>
#include <termin/physics/mass_properties.hpp>
#include <termin/physics/rigid_body.hpp>

using guard::Approx;
using termin::GeneralPose3;
using termin::Pose3;
using termin::Quat;
using termin::SpatialInertia3;
using termin::Vec3;
using termin::colliders::BoxCollider;
using termin::colliders::CapsuleCollider;
using termin::colliders::ConvexHullCollider;
using termin::physics::RigidBody;
using termin::physics::try_compute_mass_properties;

namespace {

    SpatialInertia3
    checked_properties(const termin::colliders::ColliderPrimitive& collider, const Vec3& scale, double mass) {
        SpatialInertia3 result;
        std::string diagnostic;
        REQUIRE(try_compute_mass_properties(collider, scale, mass, result, diagnostic));
        CHECK(diagnostic.empty());
        return result;
    }

    std::array<double, 3> sorted_moments(const Vec3& moments) {
        std::array<double, 3> result{moments.x, moments.y, moments.z};
        std::sort(result.begin(), result.end());
        return result;
    }

} // namespace

TEST_CASE("Capsule mass properties use collision-effective dimensions") {
    CapsuleCollider capsule(0.75, 0.5);
    const Vec3 entity_scale(3.0, 2.0, 4.0);
    const double mass = 5.0;
    const SpatialInertia3 properties = checked_properties(capsule, entity_scale, mass);

    const double radius = 1.0;
    const double half_height = 3.0;
    constexpr double pi = 3.14159265358979323846;
    const double cylinder_volume = 2.0 * pi * radius * radius * half_height;
    const double sphere_volume = 4.0 * pi * radius * radius * radius / 3.0;
    const double cylinder_mass = mass * cylinder_volume / (cylinder_volume + sphere_volume);
    const double sphere_mass = mass - cylinder_mass;
    const double expected_axial = radius * radius * (0.5 * cylinder_mass + 0.4 * sphere_mass);
    const double expected_transverse =
        cylinder_mass * (3.0 * radius * radius + 4.0 * half_height * half_height) / 12.0 +
        sphere_mass * (0.4 * radius * radius + 0.75 * half_height * radius + half_height * half_height);

    CHECK(properties.principal_moments.x == Approx(expected_transverse));
    CHECK(properties.principal_moments.y == Approx(expected_transverse));
    CHECK(properties.principal_moments.z == Approx(expected_axial));
}

TEST_CASE("Cube hull agrees with equivalent box mass properties") {
    const std::vector<Vec3> vertices = {
        {-1.0, -2.0, -3.0},
        {1.0, -2.0, -3.0},
        {-1.0, 2.0, -3.0},
        {1.0, 2.0, -3.0},
        {-1.0, -2.0, 3.0},
        {1.0, -2.0, 3.0},
        {-1.0, 2.0, 3.0},
        {1.0, 2.0, 3.0},
    };
    const ConvexHullCollider hull = ConvexHullCollider::from_points(vertices);
    const BoxCollider box(Vec3(1.0, 2.0, 3.0));
    const SpatialInertia3 hull_properties = checked_properties(hull, Vec3(1.5, 0.5, 2.0), 7.0);
    const SpatialInertia3 box_properties = checked_properties(box, Vec3(1.5, 0.5, 2.0), 7.0);

    const auto hull_moments = sorted_moments(hull_properties.principal_moments);
    const auto box_moments = sorted_moments(box_properties.principal_moments);
    for (int index = 0; index < 3; ++index) {
        CHECK(hull_moments[index] == Approx(box_moments[index]).epsilon(1.0e-9));
    }
    CHECK(std::abs(hull_properties.inertia_frame.lin.x) < 1.0e-12);
    CHECK(std::abs(hull_properties.inertia_frame.lin.y) < 1.0e-12);
    CHECK(std::abs(hull_properties.inertia_frame.lin.z) < 1.0e-12);
}

TEST_CASE("Asymmetric hull keeps a stable local center and principal frame") {
    const std::vector<Vec3> vertices = {
        {0.0, 0.0, 0.0},
        {2.0, 0.0, 0.0},
        {0.0, 1.0, 0.0},
        {0.0, 0.0, 3.0},
    };
    const ConvexHullCollider hull =
        ConvexHullCollider::from_points(vertices, GeneralPose3(Quat::identity(), Vec3(1.0, -2.0, 0.5)));
    const SpatialInertia3 properties = checked_properties(hull, Vec3(2.0, 3.0, 0.5), 4.0);

    CHECK(properties.inertia_frame.lin.x == Approx(3.0));
    CHECK(properties.inertia_frame.lin.y == Approx(-5.25));
    CHECK(properties.inertia_frame.lin.z == Approx(0.625));
    CHECK(properties.principal_moments.x > 0.0);
    CHECK(properties.principal_moments.y > properties.principal_moments.x);
    CHECK(properties.principal_moments.z > properties.principal_moments.y);

    const Pose3 authored_pose(Quat::from_axis_angle(Vec3::unit_y(), 0.7), Vec3(10.0, 20.0, 30.0));
    const RigidBody body = RigidBody::create_with_mass_properties(properties, authored_pose);
    const Pose3 recovered = body.shape_pose();
    CHECK(recovered.lin.x == Approx(authored_pose.lin.x));
    CHECK(recovered.lin.y == Approx(authored_pose.lin.y));
    CHECK(recovered.lin.z == Approx(authored_pose.lin.z));
    const double quaternion_dot = recovered.ang.x * authored_pose.ang.x + recovered.ang.y * authored_pose.ang.y +
                                  recovered.ang.z * authored_pose.ang.z + recovered.ang.w * authored_pose.ang.w;
    CHECK(std::abs(quaternion_dot) == Approx(1.0));
}

TEST_CASE("Rigid body exposes world inverse inertia as a semantic matrix") {
    RigidBody body;
    body.inertia = {2.0, 4.0, 8.0};
    body.pose.ang = Quat::from_axis_angle(Vec3::unit_z(), 3.14159265358979323846 / 2.0);

    const auto inverse_inertia = body.world_inertia_inv();
    CHECK((inverse_inertia.transform(Vec3::unit_x()) - Vec3{0.25, 0.0, 0.0}).norm() < 1.0e-12);
    CHECK((inverse_inertia.transform(Vec3::unit_y()) - Vec3{0.0, 0.5, 0.0}).norm() < 1.0e-12);
    CHECK((body.apply_inv_inertia_world(Vec3::unit_z()) - Vec3{0.0, 0.0, 0.125}).norm() < 1.0e-12);

    body.is_static = true;
    CHECK(body.world_inertia_inv().transform(Vec3{1.0, 2.0, 3.0}).norm() == Approx(0.0));
}

TEST_CASE("Degenerate convex hull mass properties fail explicitly") {
    const ConvexHullCollider hull = ConvexHullCollider::from_points({
        {0.0, 0.0, 0.0},
        {1.0, 0.0, 0.0},
        {0.0, 1.0, 0.0},
        {1.0, 1.0, 0.0},
    });
    SpatialInertia3 properties;
    std::string diagnostic;
    CHECK_FALSE(try_compute_mass_properties(hull, Vec3(1.0, 1.0, 1.0), 1.0, properties, diagnostic));
    CHECK_FALSE(diagnostic.empty());
}
