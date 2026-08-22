#include "guard_main.h"

GUARD_TEST_MAIN();

#include <cmath>
#include <limits>

#include <components/collider_component.hpp>
#include <inspect/tc_inspect_component_adapter.h>
#include <inspect/tc_inspect_init.h>
#include <tcbase/tc_log.h>
#include <termin/physics_components/components.hpp>
#include <termin/tc_scene.hpp>
#include <termin_collision/termin_collision.h>
#include <termin_scene/internal/tc_scene_extension_registry.h>

namespace {

    int captured_error_count = 0;

    void capture_log(tc_log_level level, const char*) {
        if (level == TC_LOG_ERROR) {
            ++captured_error_count;
        }
    }

    struct LogCapture {
        LogCapture() {
            captured_error_count = 0;
            tc_log_set_callback(capture_log);
        }

        ~LogCapture() {
            tc_log_set_callback(nullptr);
        }
    };

    void initialize_runtime() {
        static const bool initialized = [] {
            tc_inspect_kind_core_init();
            tc_inspect_component_adapter_init();
            tc_scene_ext_registry_init();
            termin_collision_runtime_init();
            termin::register_builtin_scene_component_types();
            termin::ColliderComponent::register_type();
            termin::PhysicsWorldComponent::register_type();
            termin::RigidBodyComponent::register_type();
            return true;
        }();
        (void)initialized;
    }

    struct FallingBoxScene {
        termin::TcSceneRef scene;
        termin::Entity box_entity;
        termin::ColliderComponent* box_collider = nullptr;
        termin::RigidBodyComponent* body = nullptr;
        termin::PhysicsWorldComponent* world = nullptr;
    };

    FallingBoxScene make_falling_box_scene() {
        using namespace termin;

        FallingBoxScene result;
        result.scene = TcSceneRef::create("native game physics");

        Entity floor = result.scene.create_entity("Floor");
        floor.transform().set_local_position({0.0, 0.0, -0.5});
        floor.transform().set_local_scale({10.0, 10.0, 1.0});
        floor.add_component(new ColliderComponent());

        result.box_entity = result.scene.create_entity("Box");
        result.box_entity.transform().set_local_position({0.0, 0.0, 2.0});
        result.box_entity.transform().set_local_scale({1.0, 1.0, 1.0});
        result.box_collider = new ColliderComponent();
        result.box_entity.add_component(result.box_collider);
        result.body = new RigidBodyComponent();
        result.body->mass = 2.0;
        result.box_entity.add_component(result.body);

        Entity world_entity = result.scene.create_entity("Physics World");
        result.world = new PhysicsWorldComponent();
        world_entity.add_component(result.world);
        result.world->start();
        return result;
    }

} // namespace

TEST_CASE("native game physics components register collider mass properties") {
    using namespace termin;

    initialize_runtime();
    FallingBoxScene fixture = make_falling_box_scene();

    REQUIRE(fixture.world->initialized());
    REQUIRE(fixture.body->initialized());
    REQUIRE(fixture.body->rigid_body() != nullptr);
    CHECK(fixture.world->physics_world().body_count() == 1U);
    CHECK(fixture.world->physics_world().collision_world() != nullptr);
    CHECK(fixture.world->physics_world().collision_world()->size() == 2U);
    CHECK(fixture.body->rigid_body()->mass == guard::Approx(2.0));
    CHECK(fixture.body->rigid_body()->inertia.x == guard::Approx(1.0 / 3.0));

    fixture.scene.destroy();
}

TEST_CASE("native game physics falls onto scene-only static collider") {
    using namespace termin;

    initialize_runtime();
    FallingBoxScene fixture = make_falling_box_scene();

    for (int step = 0; step < 360; ++step) {
        fixture.world->fixed_update(1.0F / 120.0F);
    }

    const double z = fixture.box_entity.transform().global_position().z;
    CHECK(std::abs(z - 0.5) <= 0.03);
    CHECK(std::abs(fixture.body->rigid_body()->linear_velocity.z) < 0.2);
    const Vec3 scale = fixture.box_entity.transform().local_scale();
    CHECK(scale.x == guard::Approx(1.0));
    CHECK(scale.y == guard::Approx(1.0));
    CHECK(scale.z == guard::Approx(1.0));

    fixture.scene.destroy();
}

TEST_CASE("external entity transform teleports native rigid body") {
    using namespace termin;

    initialize_runtime();
    FallingBoxScene fixture = make_falling_box_scene();
    for (int step = 0; step < 120; ++step) {
        fixture.world->fixed_update(1.0F / 120.0F);
    }

    fixture.box_entity.transform().set_global_pose(Pose3{Quat::identity(), Vec3{1.5, -0.25, 3.0}});
    fixture.world->fixed_update(1.0F / 120.0F);

    const Pose3 body_pose = fixture.body->rigid_body()->shape_pose();
    CHECK(body_pose.lin.x == guard::Approx(1.5));
    CHECK(body_pose.lin.y == guard::Approx(-0.25));
    CHECK(std::abs(body_pose.lin.z - 3.0) <= 0.002);
    CHECK(fixture.box_entity.transform().global_position().z == guard::Approx(body_pose.lin.z));

    fixture.scene.destroy();
}

TEST_CASE("scaled quaternion cannot hide an external orientation change") {
    using namespace termin;

    initialize_runtime();
    FallingBoxScene fixture = make_falling_box_scene();
    fixture.world->fixed_update(1.0F / 120.0F);

    Pose3 requested = fixture.body->rigid_body()->shape_pose();
    requested.ang = Quat{std::sqrt(3.0), 0.0, 0.0, 1.0};
    fixture.box_entity.transform().set_global_pose(requested);
    fixture.world->fixed_update(1.0F / 120.0F);

    Quat expected_rotation;
    Quat actual_rotation;
    REQUIRE(requested.ang.try_normalized(expected_rotation, 1.0e-12));
    REQUIRE(fixture.body->rigid_body()->shape_pose().ang.try_normalized(actual_rotation, 1.0e-12));
    CHECK(std::abs(actual_rotation.dot(expected_rotation)) >= 1.0 - 1.0e-10);
    CHECK(std::abs(fixture.body->rigid_body()->shape_pose().ang.norm() - 1.0) <= 1.0e-12);

    fixture.scene.destroy();
}

TEST_CASE("physics pose boundary normalizes full-range rotations and rejects invalid ones transactionally") {
    using namespace termin;

    initialize_runtime();
    FallingBoxScene fixture = make_falling_box_scene();
    const double largest = std::numeric_limits<double>::max();

    Pose3 requested{Quat{largest, largest, largest, largest}, Vec3{1.0, -2.0, 3.0}};
    fixture.box_entity.transform().set_global_pose(requested);
    REQUIRE(fixture.body->sync_to_physics());
    const Pose3 normalized_body_pose = fixture.body->rigid_body()->shape_pose();
    CHECK(normalized_body_pose.ang.x == 0.5);
    CHECK(normalized_body_pose.ang.y == 0.5);
    CHECK(normalized_body_pose.ang.z == 0.5);
    CHECK(normalized_body_pose.ang.w == 0.5);

    const Pose3 body_sentinel = normalized_body_pose;
    const Quat invalid_rotations[] = {
        Quat{0.0, 0.0, 0.0, 0.0},
        Quat{std::numeric_limits<double>::quiet_NaN(), 0.0, 0.0, 1.0},
        Quat{0.0, std::numeric_limits<double>::infinity(), 0.0, 1.0},
    };
    for (const Quat& invalid : invalid_rotations) {
        LogCapture logs;
        fixture.box_entity.transform().set_global_pose(Pose3{invalid, Vec3{9.0, 8.0, 7.0}});
        CHECK_FALSE(fixture.body->sync_to_physics());
        CHECK(captured_error_count > 0);

        const Pose3 unchanged = fixture.body->rigid_body()->shape_pose();
        CHECK(unchanged.ang.x == body_sentinel.ang.x);
        CHECK(unchanged.ang.y == body_sentinel.ang.y);
        CHECK(unchanged.ang.z == body_sentinel.ang.z);
        CHECK(unchanged.ang.w == body_sentinel.ang.w);
        CHECK(unchanged.lin == body_sentinel.lin);
    }

    fixture.scene.destroy();
}

TEST_CASE("collider rebuild replaces rigid-body collision mapping") {
    using namespace termin;

    initialize_runtime();
    FallingBoxScene fixture = make_falling_box_scene();
    colliders::Collider* old_collider = fixture.box_collider->attached_collider();
    REQUIRE(old_collider != nullptr);
    const std::uint64_t old_revision = fixture.box_collider->collider_revision();

    fixture.box_collider->set_box_size({0.5, 0.5, 0.5});
    colliders::Collider* new_collider = fixture.box_collider->attached_collider();
    REQUIRE(new_collider != nullptr);
    CHECK(fixture.box_collider->collider_revision() > old_revision);
    fixture.world->fixed_update(1.0F / 120.0F);

    CHECK(fixture.world->physics_world().collision_world()->size() == 2U);
    fixture.body->apply_impulse({0.0, 0.0, 1.0});
    CHECK(fixture.body->rigid_body()->linear_velocity.z > 0.0);

    fixture.scene.destroy();
}
