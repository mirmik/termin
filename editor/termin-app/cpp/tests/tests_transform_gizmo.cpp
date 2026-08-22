#include "guard_main.h"

#include "core/tc_entity_pool_registry.h"
#include "termin/editor/transform_gizmo.hpp"

#include <cmath>

namespace {

    termin::Quat rotation_z(double radians) {
        const double half = radians * 0.5;
        return termin::Quat{0.0, 0.0, std::sin(half), std::cos(half)};
    }

    bool near(double actual, double expected, double epsilon = 1.0e-9) {
        return std::abs(actual - expected) <= epsilon;
    }

    bool vec_near(const termin::Vec3& actual, const termin::Vec3& expected) {
        return near(actual.x, expected.x) && near(actual.y, expected.y) && near(actual.z, expected.z);
    }

    bool quat_near(const termin::Quat& actual, const termin::Quat& expected) {
        const double dot =
            actual.x * expected.x + actual.y * expected.y + actual.z * expected.z + actual.w * expected.w;
        return near(std::abs(dot), 1.0);
    }

} // namespace

TEST_CASE("TransformGizmo edits logical channels below affine ancestry") {
    const tc_entity_pool_handle pool = tc_entity_pool_registry_create(8);
    REQUIRE(tc_entity_pool_handle_valid(pool));

    termin::Entity scaled = termin::Entity::create(pool, "scaled");
    scaled.transform().set_local_scale({2.0, 3.0, 4.0});
    termin::Entity affine_parent = scaled.create_child("affine-parent");
    affine_parent.transform().set_local_rotation(rotation_z(0.4));
    termin::Entity target = affine_parent.create_child("target");
    target.transform().set_local_scale({1.5, 0.75, 2.0});
    REQUIRE(target.transform().kind() == termin::TransformKind::Affine);

    const termin::Vec3 authored_scale = target.transform().local_scale();
    termin::TransformGizmo gizmo;
    gizmo.set_target(target);
    gizmo.set_orientation_mode("world");

    const termin::Vec3 requested_position{9.0, -4.0, 2.0};
    REQUIRE(gizmo.snap_to(requested_position));
    CHECK(vec_near(target.transform().global_position(), requested_position));
    CHECK(vec_near(target.transform().local_scale(), authored_scale));

    const termin::Quat start_orientation = target.transform().global_rotation();
    const termin::Vec3f center{
        static_cast<float>(requested_position.x),
        static_cast<float>(requested_position.y),
        static_cast<float>(requested_position.z),
    };
    const termin::Vec3f start_hit = center + termin::Vec3f{1.0f, 0.0f, 0.0f};
    const termin::Vec3f end_hit = center + termin::Vec3f{0.0f, 1.0f, 0.0f};
    const int rotate_z_id = static_cast<int>(termin::TransformElement::ROTATE_Z);
    gizmo.on_click(rotate_z_id, &start_hit);
    gizmo.on_drag(rotate_z_id, end_hit, termin::Vec3f{0.0f, 0.0f, 0.0f});
    gizmo.on_release(rotate_z_id);

    const termin::Quat expected_orientation = (rotation_z(0.5 * std::acos(-1.0)) * start_orientation).normalized();
    CHECK(quat_near(target.transform().global_rotation(), expected_orientation));
    CHECK(vec_near(target.transform().local_scale(), authored_scale));
    CHECK(target.transform().kind() == termin::TransformKind::Affine);

    tc_entity_pool_registry_destroy(pool);
}

TEST_CASE("TransformGizmo cancel restores the captured target without committing undo") {
    const tc_entity_pool_handle pool = tc_entity_pool_registry_create(4);
    REQUIRE(tc_entity_pool_handle_valid(pool));

    termin::Entity target = termin::Entity::create(pool, "target");
    target.transform().set_global_position({1.0, 2.0, 3.0});
    termin::TransformGizmo gizmo;
    gizmo.set_target(target);
    int transform_updates = 0;
    int undo_commits = 0;
    gizmo.on_transform_changed = [&]() { ++transform_updates; };
    gizmo.on_drag_end = [&](const auto&, const auto&) { ++undo_commits; };

    const int translate_x_id = static_cast<int>(termin::TransformElement::TRANSLATE_X);
    const termin::Vec3f start_hit{1.0f, 2.0f, 3.0f};
    gizmo.on_click(translate_x_id, &start_hit);
    gizmo.on_drag(translate_x_id, {7.0f, 2.0f, 3.0f}, {6.0f, 0.0f, 0.0f});
    REQUIRE_FALSE(vec_near(target.transform().global_position(), {1.0, 2.0, 3.0}));

    gizmo.on_cancel(translate_x_id);
    CHECK(vec_near(target.transform().global_position(), {1.0, 2.0, 3.0}));
    CHECK_EQ(transform_updates, 2);
    CHECK_EQ(undo_commits, 0);

    tc_entity_pool_registry_destroy(pool);
}

TEST_CASE("TransformGizmo rotates around an oriented local axis") {
    const tc_entity_pool_handle pool = tc_entity_pool_registry_create(4);
    REQUIRE(tc_entity_pool_handle_valid(pool));

    termin::Entity target = termin::Entity::create(pool, "target");
    const termin::Quat start_orientation = rotation_z(0.5 * std::acos(-1.0));
    target.transform().relocate(termin::Pose3{start_orientation, termin::Vec3::zero()});

    termin::TransformGizmo gizmo;
    gizmo.set_target(target);
    gizmo.set_orientation_mode("local");

    const int rotate_x_id = static_cast<int>(termin::TransformElement::ROTATE_X);
    const termin::Vec3f start_hit{1.0f, 0.0f, 0.0f};
    const termin::Vec3f end_hit{0.0f, 0.0f, -1.0f};
    gizmo.on_click(rotate_x_id, &start_hit);
    gizmo.on_drag(rotate_x_id, end_hit, termin::Vec3f::zero());
    gizmo.on_release(rotate_x_id);

    const termin::Quat expected_orientation =
        (termin::Quat::from_axis_angle(termin::Vec3::unit_y(), 0.5 * std::acos(-1.0)) * start_orientation).normalized();
    CHECK(quat_near(target.transform().global_rotation(), expected_orientation));

    tc_entity_pool_registry_destroy(pool);
}

TEST_CASE("TransformGizmo preserves quaternion precision through a zero-angle drag") {
    const tc_entity_pool_handle pool = tc_entity_pool_registry_create(4);
    REQUIRE(tc_entity_pool_handle_valid(pool));

    termin::Entity target = termin::Entity::create(pool, "target");
    const termin::Quat authored_orientation =
        termin::Quat{0.1234567890123, -0.2345678901234, 0.3456789012345, 0.9012345678901}.normalized();
    target.transform().relocate(termin::Pose3{authored_orientation, termin::Vec3::zero()});
    const termin::Quat start_orientation = target.transform().global_rotation();

    termin::TransformGizmo gizmo;
    gizmo.set_target(target);
    gizmo.set_orientation_mode("world");

    const int rotate_z_id = static_cast<int>(termin::TransformElement::ROTATE_Z);
    const termin::Vec3f hit{1.0f, 0.0f, 0.0f};
    gizmo.on_click(rotate_z_id, &hit);
    gizmo.on_drag(rotate_z_id, hit, termin::Vec3f::zero());
    gizmo.on_release(rotate_z_id);

    const termin::Quat actual_orientation = target.transform().global_rotation();
    CHECK(near(actual_orientation.x, start_orientation.x, 1.0e-12));
    CHECK(near(actual_orientation.y, start_orientation.y, 1.0e-12));
    CHECK(near(actual_orientation.z, start_orientation.z, 1.0e-12));
    CHECK(near(actual_orientation.w, start_orientation.w, 1.0e-12));

    tc_entity_pool_registry_destroy(pool);
}
