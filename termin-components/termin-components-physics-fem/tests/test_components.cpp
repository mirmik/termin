#include "guard_main.h"

GUARD_TEST_MAIN();

#include <algorithm>
#include <cmath>
#include <limits>
#include <numbers>

#include <components/collider_component.hpp>
#include <components/rotator_component.hpp>
#include <inspect/tc_inspect_component_adapter.h>
#include <inspect/tc_inspect_init.h>
#include <physics/tc_collision_world.h>
#include <termin/collision/collision_world.hpp>
#include <termin/geom/general_pose3.hpp>
#include <termin/physics_fem/articulation_scene.hpp>
#include <termin/physics_fem/components.hpp>
#include <termin/tc_scene.hpp>
#include <termin_collision/termin_collision.h>
#include <termin_scene/internal/tc_scene_extension_registry.h>

namespace
{
    void register_test_component_types()
    {
        static const bool registered = []()
        {
            tc_inspect_kind_core_init();
            tc_inspect_component_adapter_init();
            tc_scene_ext_registry_init();
            termin_collision_runtime_init();
            termin::register_builtin_scene_component_types();
            termin::ColliderComponent::register_type();
            termin::KinematicUnitComponent::register_type();
            termin::RotatorComponent::register_type();
            termin::FEMRigidBodyComponent::register_type();
            termin::FEMFixedJointComponent::register_type();
            termin::FEMRevoluteJointComponent::register_type();
            termin::FEMArticulationComponent::register_type();
            termin::FEMArticulationMotorComponent::register_type();
            termin::FEMJointLimitComponent::register_type();
            termin::FEMJointServoComponent::register_type();
            termin::FEMPhysicsWorldComponent::register_type();
            return true;
        }();
        (void)registered;
    }

    struct DoublePendulumScene
    {
        termin::TcSceneRef scene;
        termin::FEMPhysicsWorldComponent* world = nullptr;
        termin::FEMArticulationComponent* articulation = nullptr;
        termin::RotatorComponent* joint_a = nullptr;
        termin::RotatorComponent* joint_b = nullptr;
        termin::FEMRigidBodyComponent* body_a = nullptr;
        termin::FEMRigidBodyComponent* body_b = nullptr;
        termin::Entity root;
    };

    DoublePendulumScene make_double_pendulum_scene()
    {
        using namespace termin;

        DoublePendulumScene result;
        result.scene = TcSceneRef::create("reduced double pendulum");

        result.root = result.scene.create_entity("Articulation Root");
        result.root.transform().set_local_position({0.0, 0.0, 4.0});
        result.articulation = new FEMArticulationComponent();
        result.root.add_component(result.articulation);

        Entity joint_a_entity = result.root.create_child("Hip Joint");
        result.joint_a = new RotatorComponent();
        joint_a_entity.add_component(result.joint_a);
        result.joint_a->set_axis(0.0, 1.0, 0.0);
        result.joint_a->set_coordinate_scale(1.0);
        result.joint_a->coordinate = 0.7;
        result.joint_a->origin_position = {0.0, 0.0, 0.0};
        result.joint_a->apply();

        Entity body_a_entity = joint_a_entity.create_child("Link A");
        body_a_entity.transform().set_local_position({0.0, 0.0, -1.0});
        result.body_a = new FEMRigidBodyComponent();
        result.body_a->mass = 1.5;
        result.body_a->inertia_diagonal = {0.5, 0.5, 0.05};
        body_a_entity.add_component(result.body_a);

        Entity joint_b_entity = body_a_entity.create_child("Knee Joint");
        result.joint_b = new RotatorComponent();
        joint_b_entity.add_component(result.joint_b);
        result.joint_b->set_axis(0.0, 1.0, 0.0);
        result.joint_b->set_coordinate_scale(1.0);
        result.joint_b->coordinate = -0.4;
        result.joint_b->origin_position = {0.0, 0.0, -1.0};
        result.joint_b->apply();

        Entity body_b_entity = joint_b_entity.create_child("Link B");
        body_b_entity.transform().set_local_position({0.0, 0.0, -1.0});
        result.body_b = new FEMRigidBodyComponent();
        result.body_b->mass = 1.0;
        result.body_b->inertia_diagonal = {0.4, 0.4, 0.04};
        body_b_entity.add_component(result.body_b);

        // Keep the world after the articulation in pool order. This is the
        // destruction order used by the serialized example and exercises the
        // component-to-world detach contract during scene teardown.
        Entity world_entity = result.scene.create_entity("Physics World");
        result.world = new FEMPhysicsWorldComponent();
        result.world->time_step = 0.001;
        world_entity.add_component(result.world);
        return result;
    }

    struct FloatingTreeScene
    {
        termin::TcSceneRef scene;
        termin::Entity root;
        termin::FEMPhysicsWorldComponent* world = nullptr;
        termin::FEMArticulationComponent* articulation = nullptr;
        termin::FEMRigidBodyComponent* base = nullptr;
        termin::FEMRigidBodyComponent* link_a = nullptr;
        termin::FEMRigidBodyComponent* link_b = nullptr;
        termin::RotatorComponent* joint_a = nullptr;
        termin::RotatorComponent* joint_b = nullptr;
    };

    FloatingTreeScene make_floating_tree_scene()
    {
        using namespace termin;

        FloatingTreeScene result;
        result.scene = TcSceneRef::create("floating articulation tree");
        result.root = result.scene.create_entity("Floating Base");
        result.root.transform().set_local_position({1.0, 0.0, 2.0});
        result.articulation = new FEMArticulationComponent();
        result.articulation->base_mode =
            static_cast<int>(FEMArticulationBaseMode::Floating);
        result.root.add_component(result.articulation);
        result.base = new FEMRigidBodyComponent();
        result.base->mass = 4.0;
        result.base->inertia_diagonal = {1.0, 1.0, 1.0};
        result.root.add_component(result.base);

        const auto add_branch = [&result](const char* joint_name,
                                          const char* body_name,
                                          double x,
                                          RotatorComponent*& joint,
                                          FEMRigidBodyComponent*& body)
        {
            Entity joint_entity = result.root.create_child(joint_name);
            joint = new RotatorComponent();
            joint_entity.add_component(joint);
            joint->set_axis(0.0, 1.0, 0.0);
            joint->origin_position = {x, 0.0, 0.0};
            joint->apply();

            Entity body_entity = joint_entity.create_child(body_name);
            body_entity.transform().set_local_position({0.0, 0.0, -0.5});
            body = new FEMRigidBodyComponent();
            body->mass = 1.0;
            body->inertia_diagonal = {0.1, 0.1, 0.1};
            body_entity.add_component(body);
        };
        add_branch(
            "Left Joint", "Left Link", -0.75, result.joint_a, result.link_a);
        add_branch(
            "Right Joint", "Right Link", 0.75, result.joint_b, result.link_b);

        Entity world_entity = result.scene.create_entity("Physics World");
        result.world = new FEMPhysicsWorldComponent();
        result.world->gravity = {0.0, 0.0, 0.0};
        result.world->time_step = 0.001;
        world_entity.add_component(result.world);
        return result;
    }

    struct ServoLoadScene
    {
        termin::TcSceneRef scene;
        termin::FEMPhysicsWorldComponent* world = nullptr;
        termin::FEMArticulationComponent* articulation = nullptr;
        termin::RotatorComponent* joint = nullptr;
        termin::FEMArticulationMotorComponent* motor = nullptr;
        termin::FEMJointServoComponent* servo = nullptr;
    };

    ServoLoadScene make_servo_load_scene()
    {
        using namespace termin;

        ServoLoadScene result;
        result.scene = TcSceneRef::create("reduced servo load");

        Entity root = result.scene.create_entity("Servo Stand");
        root.transform().set_local_position({0.0, 0.0, 4.0});
        result.articulation = new FEMArticulationComponent();
        root.add_component(result.articulation);

        Entity joint_entity = root.create_child("Servo Joint");
        result.joint = new RotatorComponent();
        joint_entity.add_component(result.joint);
        result.joint->set_axis(0.0, 4.0, 0.0);
        result.joint->set_coordinate(15.0);

        result.motor = new FEMArticulationMotorComponent();
        result.motor->maximum_effort = 50.0;
        joint_entity.add_component(result.motor);

        result.servo = new FEMJointServoComponent();
        result.servo->integral_control_enabled = true;
        result.servo->target_coordinate = 90.0;
        result.servo->position_gain = 100.0;
        result.servo->integral_gain = 100.0;
        result.servo->maximum_integral_effort = 40.0;
        result.servo->velocity_gain = 20.0;
        result.servo->feed_forward_effort = 0.0;
        joint_entity.add_component(result.servo);

        Entity load_entity = joint_entity.create_child("Driven Load");
        load_entity.transform().set_local_position({0.0, 0.0, -1.75});
        auto* body = new FEMRigidBodyComponent();
        body->mass = 2.0;
        body->inertia_diagonal = {0.58, 0.58, 0.041};
        load_entity.add_component(body);

        Entity world_entity = result.scene.create_entity("Physics World");
        result.world = new FEMPhysicsWorldComponent();
        result.world->time_step = 0.005;
        result.world->substeps = 2;
        world_entity.add_component(result.world);
        return result;
    }

    struct MaximalContactScene
    {
        termin::TcSceneRef scene;
        termin::FEMPhysicsWorldComponent* world = nullptr;
        termin::FEMRigidBodyComponent* body = nullptr;
        termin::ColliderComponent* body_collider = nullptr;
        termin::ColliderComponent* terrain_collider = nullptr;
    };

    MaximalContactScene
    make_maximal_contact_scene(double initial_height = 0.45,
                               termin::Vec3 gravity = termin::Vec3::zero(),
                               double time_step = 0.01)
    {
        using namespace termin;

        MaximalContactScene result;
        result.scene = TcSceneRef::create("maximal contact");

        Entity terrain = result.scene.create_entity("Terrain");
        terrain.transform().set_local_position({0.0, 0.0, -0.5});
        result.terrain_collider = new ColliderComponent();
        result.terrain_collider->box_size = {10.0, 10.0, 1.0};
        terrain.add_component(result.terrain_collider);

        Entity body_entity = result.scene.create_entity("Falling Body");
        body_entity.transform().set_local_position({0.0, 0.0, initial_height});
        result.body = new FEMRigidBodyComponent();
        result.body->mass = 1.0;
        result.body->inertia_diagonal = {1.0 / 6.0, 1.0 / 6.0, 1.0 / 6.0};
        body_entity.add_component(result.body);
        result.body_collider = new ColliderComponent();
        result.body_collider->box_size = {1.0, 1.0, 1.0};
        body_entity.add_component(result.body_collider);

        Entity world_entity = result.scene.create_entity("Physics World");
        result.world = new FEMPhysicsWorldComponent();
        result.world->gravity = gravity;
        result.world->time_step = time_step;
        world_entity.add_component(result.world);
        return result;
    }

} // namespace

TEST_CASE("native FEM component doubles round-trip through inspect")
{
    using namespace termin;

    register_test_component_types();

    FEMRigidBodyComponent body;
    body.mass = 1.5;
    body.linear_damping = 0.002;
    body.angular_damping = 0.004;
    tc_value body_data = body.serialize_data();

    FEMRigidBodyComponent restored_body;
    restored_body.deserialize_data(&body_data);
    CHECK(std::abs(restored_body.mass - 1.5) < 1.0e-12);
    CHECK(std::abs(restored_body.linear_damping - 0.002) < 1.0e-12);
    CHECK(std::abs(restored_body.angular_damping - 0.004) < 1.0e-12);
    tc_value_free(&body_data);

    FEMPhysicsWorldComponent world;
    world.time_step = 0.005;
    tc_value world_data = world.serialize_data();

    FEMPhysicsWorldComponent restored_world;
    restored_world.deserialize_data(&world_data);
    CHECK(std::abs(restored_world.time_step - 0.005) < 1.0e-12);
    tc_value_free(&world_data);

    FEMArticulationComponent articulation;
    articulation.base_mode =
        static_cast<int>(FEMArticulationBaseMode::Floating);
    tc_value articulation_data = articulation.serialize_data();
    FEMArticulationComponent restored_articulation;
    restored_articulation.deserialize_data(&articulation_data);
    CHECK(restored_articulation.base_mode ==
          static_cast<int>(FEMArticulationBaseMode::Floating));
    tc_value_free(&articulation_data);

    FEMJointLimitComponent limits;
    limits.minimum_enabled = true;
    limits.maximum_enabled = true;
    limits.minimum_coordinate = -30.0;
    limits.maximum_coordinate = 45.0;
    tc_value limit_data = limits.serialize_data();
    FEMJointLimitComponent restored_limits;
    restored_limits.deserialize_data(&limit_data);
    CHECK(restored_limits.minimum_enabled);
    CHECK(restored_limits.maximum_enabled);
    CHECK(std::abs(restored_limits.minimum_coordinate + 30.0) < 1.0e-12);
    CHECK(std::abs(restored_limits.maximum_coordinate - 45.0) < 1.0e-12);
    tc_value_free(&limit_data);
}

TEST_CASE("rotator attachment distinguishes fresh and deserialized state")
{
    using namespace termin;

    register_test_component_types();
    TcSceneRef scene = TcSceneRef::create("rotator lifecycle");

    Entity fresh_entity = scene.create_entity("Fresh Joint");
    fresh_entity.transform().set_local_position({1.0, 2.0, 3.0});
    fresh_entity.transform().set_local_rotation(
        Quat::from_axis_angle({0.0, 1.0, 0.0}, 0.4));
    fresh_entity.transform().set_local_scale({2.0, 3.0, 4.0});
    auto* fresh = new RotatorComponent();
    fresh_entity.add_component(fresh);
    CHECK((fresh->origin_position - Vec3{1.0, 2.0, 3.0}).norm() < 1.0e-12);
    CHECK(std::abs(fresh->origin_rotation.y - std::sin(0.2)) < 1.0e-12);
    CHECK(
        (fresh_entity.transform().local_scale() - Vec3{2.0, 3.0, 4.0}).norm() <
        1.0e-12);

    RotatorComponent authored;
    authored.set_axis(0.0, 1.0, 0.0);
    authored.set_coordinate_scale(1.0);
    authored.coordinate = 0.8;
    authored.origin_position = {4.0, 5.0, 6.0};
    authored.origin_rotation = {0.0, 0.0, 0.0, 1.0};
    tc_value data = authored.serialize_data();

    Entity restored_entity = scene.create_entity("Restored Joint");
    restored_entity.transform().set_local_scale({2.0, 3.0, 4.0});
    auto* restored = new RotatorComponent();
    restored->deserialize_data(&data, scene.handle());
    restored_entity.add_component(restored);
    tc_value_free(&data);

    CHECK((restored_entity.transform().local_position() - Vec3{4.0, 5.0, 6.0})
              .norm() < 1.0e-12);
    CHECK(std::abs(restored_entity.transform().local_rotation().y -
                   std::sin(0.4)) < 1.0e-12);
    CHECK((restored_entity.transform().local_scale() - Vec3{2.0, 3.0, 4.0})
              .norm() < 1.0e-12);
    tc_value restored_data = restored->serialize_data();
    CHECK(!tc_value_dict_has(&restored_data, "base_scale"));
    CHECK(!tc_value_dict_has(&restored_data, "base_position"));
    CHECK(!tc_value_dict_has(&restored_data, "base_rotation"));
    CHECK(!tc_value_dict_has(&restored_data, "capture_base"));
    CHECK(!tc_value_dict_has(&restored_data, "recalculate_origin"));
    CHECK(tc_value_dict_has(&restored_data, "origin_position"));
    CHECK(tc_value_dict_has(&restored_data, "origin_rotation"));
    CHECK(tc_value_dict_has(&restored_data, "coordinate_scale"));
    tc_value_free(&restored_data);

    scene.destroy();
}

TEST_CASE(
    "kinematic axes are unit directions with an explicit coordinate scale")
{
    using namespace termin;

    RotatorComponent rotator;
    rotator.set_axis(0.0, 4.0, 0.0);
    rotator.set_coordinate_scale(std::numbers::pi_v<double> / 180.0);
    rotator.set_coordinate(90.0);

    CHECK((rotator.get_axis() - Vec3::unit_y()).norm() < 1.0e-12);
    CHECK(std::abs(rotator.get_axis().norm() - 1.0) < 1.0e-12);
    CHECK(std::abs(rotator.physical_coordinate() -
                   std::numbers::pi_v<double> / 2.0) < 1.0e-12);
}

TEST_CASE("scene articulation compiler maps an explicit joint/body hierarchy")
{
    using namespace termin;

    DoublePendulumScene pendulum = make_double_pendulum_scene();
    const FEMArticulationSceneCompilation compiled =
        compile_fem_articulation_scene(pendulum.root);

    REQUIRE(compiled.ok());
    REQUIRE_EQ(compiled.links.size(), 2U);
    REQUIRE_EQ(compiled.bindings.size(), 2U);
    CHECK(compiled.links[0].parent_link == qopt::articulation_world_link);
    CHECK(compiled.links[1].parent_link == 0U);
    CHECK(std::abs(compiled.links[0].parent_to_joint_zero.lin.z - 4.0) <
          1.0e-12);
    CHECK(std::abs(compiled.links[0].motion_twist_at_joint.ang.y - 1.0) <
          1.0e-12);
    CHECK(std::abs(compiled.links[0].motion_twist_at_joint.ang.norm() - 1.0) <
          1.0e-12);
    CHECK(std::abs(compiled.links[1].joint_to_link.lin.z + 1.0) < 1.0e-12);
    CHECK(std::abs(compiled.state.coordinates[0] - 0.7) < 1.0e-12);
    CHECK(std::abs(compiled.state.coordinates[1] + 0.4) < 1.0e-12);

    pendulum.scene.destroy();
}

TEST_CASE("scene articulation compiler maps a floating base and branches")
{
    using namespace termin;

    FloatingTreeScene fixture = make_floating_tree_scene();
    const FEMArticulationSceneCompilation compiled =
        compile_fem_articulation_scene(fixture.root);

    REQUIRE(compiled.ok());
    REQUIRE(compiled.floating_base.has_value());
    CHECK(compiled.base_body == fixture.base);
    CHECK(compiled.base_entity == fixture.root);
    CHECK(
        (compiled.floating_base->pose_world.lin - Vec3{1.0, 0.0, 2.0}).norm() <
        1.0e-12);
    REQUIRE_EQ(compiled.links.size(), 2U);
    CHECK(compiled.links[0].parent_link == qopt::articulation_root_frame);
    CHECK(compiled.links[1].parent_link == qopt::articulation_root_frame);
    CHECK(std::abs(compiled.links[0].parent_to_joint_zero.lin.x + 0.75) <
          1.0e-12);
    CHECK(std::abs(compiled.links[1].parent_to_joint_zero.lin.x - 0.75) <
          1.0e-12);

    fixture.scene.destroy();
}

TEST_CASE("scene articulation compiler rejects contradictory base layouts")
{
    using namespace termin;

    DoublePendulumScene fixed = make_double_pendulum_scene();
    auto* unexpected_body = new FEMRigidBodyComponent();
    fixed.root.add_component(unexpected_body);
    CHECK(compile_fem_articulation_scene(fixed.root).diagnostic ==
          FEMArticulationSceneDiagnostic::UnexpectedRootBody);
    fixed.scene.destroy();

    DoublePendulumScene floating = make_double_pendulum_scene();
    floating.articulation->base_mode =
        static_cast<int>(FEMArticulationBaseMode::Floating);
    CHECK(compile_fem_articulation_scene(floating.root).diagnostic ==
          FEMArticulationSceneDiagnostic::MissingRootBody);
    floating.scene.destroy();

    FloatingTreeScene multiple = make_floating_tree_scene();
    multiple.root.add_component(new FEMRigidBodyComponent());
    CHECK(compile_fem_articulation_scene(multiple.root).diagnostic ==
          FEMArticulationSceneDiagnostic::MultipleBodies);
    multiple.scene.destroy();
}

TEST_CASE("scene articulation compiler converts authored joint limits")
{
    using namespace termin;

    DoublePendulumScene pendulum = make_double_pendulum_scene();
    pendulum.joint_a->set_coordinate_scale(0.1);
    auto* limits = new FEMJointLimitComponent();
    limits->minimum_enabled = true;
    limits->maximum_enabled = true;
    limits->minimum_coordinate = -2.0;
    limits->maximum_coordinate = 3.0;
    pendulum.joint_a->entity().add_component(limits);

    const FEMArticulationSceneCompilation compiled =
        compile_fem_articulation_scene(pendulum.root);
    REQUIRE(compiled.ok());
    REQUIRE(compiled.links[0].limits.minimum.has_value());
    REQUIRE(compiled.links[0].limits.maximum.has_value());
    CHECK(std::abs(*compiled.links[0].limits.minimum + 0.2) < 1.0e-12);
    CHECK(std::abs(*compiled.links[0].limits.maximum - 0.3) < 1.0e-12);
    CHECK(std::abs(compiled.state.coordinates[0] - 0.07) < 1.0e-12);

    pendulum.scene.destroy();
}

TEST_CASE("scene articulation compiler rejects invalid joint limits")
{
    using namespace termin;

    DoublePendulumScene reversed = make_double_pendulum_scene();
    auto* reversed_limits = new FEMJointLimitComponent();
    reversed_limits->minimum_enabled = true;
    reversed_limits->maximum_enabled = true;
    reversed_limits->minimum_coordinate = 2.0;
    reversed_limits->maximum_coordinate = -1.0;
    reversed.joint_a->entity().add_component(reversed_limits);
    const FEMArticulationSceneCompilation reversed_compilation =
        compile_fem_articulation_scene(reversed.root);
    CHECK(reversed_compilation.diagnostic ==
          FEMArticulationSceneDiagnostic::InvalidJointLimits);
    CHECK(reversed_compilation.diagnostic_entity == "Hip Joint");
    reversed.scene.destroy();

    DoublePendulumScene non_finite = make_double_pendulum_scene();
    auto* non_finite_limits = new FEMJointLimitComponent();
    non_finite_limits->minimum_enabled = true;
    non_finite_limits->minimum_coordinate =
        std::numeric_limits<double>::quiet_NaN();
    non_finite.joint_a->entity().add_component(non_finite_limits);
    const FEMArticulationSceneCompilation non_finite_compilation =
        compile_fem_articulation_scene(non_finite.root);
    CHECK(non_finite_compilation.diagnostic ==
          FEMArticulationSceneDiagnostic::InvalidJointLimits);
    non_finite.scene.destroy();
}

TEST_CASE("FEM world advances a compiled reduced double pendulum")
{
    using namespace termin;

    DoublePendulumScene pendulum = make_double_pendulum_scene();
    const double coordinate_before = pendulum.joint_a->coordinate;
    pendulum.world->start();

    REQUIRE(pendulum.articulation->initialized());
    const FEMPhysicsTelemetry initial = pendulum.world->telemetry();
    CHECK(initial.initialized);
    CHECK(initial.body_count == 2U);
    CHECK(initial.articulation_count == 1U);
    CHECK(initial.reduced_dof_count == 2U);
    CHECK(initial.joint_count == 0U);
    CHECK(std::isfinite(initial.total_energy));

    for (int step = 0; step < 20; ++step)
    {
        pendulum.world->update(0.001F);
    }
    const FEMPhysicsTelemetry advanced = pendulum.world->telemetry();
    CHECK(advanced.initialized);
    CHECK(advanced.successful_steps == 20U);
    CHECK(std::abs(pendulum.joint_a->coordinate - coordinate_before) > 1.0e-8);
    CHECK(std::abs(advanced.total_energy - initial.total_energy) < 1.0e-5);

    pendulum.scene.destroy();
}

TEST_CASE("FEM world advances and synchronizes a floating articulation root")
{
    using namespace termin;

    FloatingTreeScene fixture = make_floating_tree_scene();
    auto* motor = new FEMArticulationMotorComponent();
    motor->commanded_effort = 1.0;
    motor->maximum_effort = 2.0;
    fixture.joint_a->entity().add_component(motor);
    fixture.world->start();

    REQUIRE(fixture.articulation->initialized());
    REQUIRE(fixture.base->initialized());
    REQUIRE(fixture.link_a->initialized());
    REQUIRE(motor->initialized());
    const FEMPhysicsTelemetry initial = fixture.world->telemetry();
    CHECK(initial.initialized);
    CHECK(initial.body_count == 3U);
    CHECK(initial.articulation_count == 1U);
    CHECK(initial.reduced_dof_count == 8U);

    REQUIRE(
        fixture.base->set_velocity_local(Screw3{Vec3::zero(), Vec3::unit_x()}));
    const double x_before = fixture.root.transform().global_position().x;
    fixture.world->update(0.001F);
    CHECK(fixture.world->telemetry().successful_steps == 1U);
    CHECK(fixture.root.transform().global_position().x > x_before);
    CHECK(fixture.base->velocity_local().lin.x > 0.9);
    CHECK(std::abs(motor->applied_effort() - 1.0) < 1.0e-12);
    CHECK(std::isfinite(motor->power()));
    CHECK(!fixture.link_a->set_velocity_local(Screw3::zero()));

    fixture.scene.destroy();
}

TEST_CASE("FEM routes contacts to a floating articulation base")
{
    using namespace termin;

    register_test_component_types();
    FloatingTreeScene fixture = make_floating_tree_scene();
    fixture.root.transform().set_global_position({0.0, 0.0, 0.45});
    auto* base_collider = new ColliderComponent();
    base_collider->box_size = {1.0, 1.0, 1.0};
    fixture.root.add_component(base_collider);

    Entity terrain = fixture.scene.create_entity("Terrain");
    terrain.transform().set_local_position({0.0, 0.0, -0.5});
    auto* terrain_collider = new ColliderComponent();
    terrain_collider->box_size = {10.0, 10.0, 1.0};
    terrain.add_component(terrain_collider);

    fixture.world->start();
    REQUIRE(fixture.world->telemetry().initialized);
    fixture.world->update(0.001F);

    const FEMPhysicsTelemetry telemetry = fixture.world->telemetry();
    CHECK(telemetry.initialized);
    CHECK(telemetry.contact_count >= 1U);
    CHECK(telemetry.active_contact_count >= 1U);
    CHECK(fixture.root.transform().global_position().z > 0.45);

    fixture.scene.destroy();
}

TEST_CASE("FEM motor accepts a direct reduced-coordinate effort command")
{
    using namespace termin;

    DoublePendulumScene pendulum = make_double_pendulum_scene();
    auto* motor = new FEMArticulationMotorComponent();
    motor->commanded_effort = 2.0;
    motor->maximum_effort = 1.0;
    pendulum.joint_a->entity().add_component(motor);

    pendulum.world->start();
    REQUIRE(pendulum.articulation->initialized());
    REQUIRE(motor->initialized());
    CHECK(pendulum.world->telemetry().motor_count == 1U);

    pendulum.world->update(0.001f);

    CHECK(std::abs(motor->applied_effort()) <= motor->maximum_effort + 1.0e-12);
    CHECK(motor->saturated());

    pendulum.scene.destroy();
}

TEST_CASE("FEM servo drives a separate articulation motor in physical units")
{
    using namespace termin;

    DoublePendulumScene pendulum = make_double_pendulum_scene();
    auto* motor = new FEMArticulationMotorComponent();
    motor->maximum_effort = 3.0;
    pendulum.joint_a->entity().add_component(motor);
    auto* servo = new FEMJointServoComponent();
    servo->target_coordinate = 0.2;
    servo->position_gain = 40.0;
    servo->velocity_gain = 6.0;
    pendulum.joint_a->entity().add_component(servo);

    pendulum.world->start();
    REQUIRE(pendulum.articulation->initialized());
    REQUIRE(servo->initialized());
    CHECK(pendulum.world->telemetry().motor_count == 1U);

    for (int index = 0; index < 40; ++index)
    {
        pendulum.world->update(0.001f);
    }

    const FEMPhysicsTelemetry telemetry = pendulum.world->telemetry();
    CHECK(telemetry.successful_steps == 40U);
    CHECK(std::isfinite(servo->commanded_effort()));
    CHECK(std::isfinite(motor->applied_effort()));
    CHECK(std::abs(motor->applied_effort()) <= motor->maximum_effort + 1.0e-12);
    CHECK(telemetry.motor_effort_linf <= motor->maximum_effort + 1.0e-12);
    CHECK(motor->saturated());

    pendulum.scene.destroy();
}

TEST_CASE("FEM servo can disable its position control loop")
{
    using namespace termin;

    DoublePendulumScene pendulum = make_double_pendulum_scene();
    auto* motor = new FEMArticulationMotorComponent();
    motor->maximum_effort = 3.0;
    pendulum.joint_a->entity().add_component(motor);
    auto* servo = new FEMJointServoComponent();
    servo->position_control_enabled = false;
    servo->integral_control_enabled = true;
    servo->target_coordinate = 1000.0;
    servo->target_velocity = 0.3;
    servo->position_gain = 1000.0;
    servo->integral_gain = 1000.0;
    servo->velocity_gain = 6.0;
    pendulum.joint_a->entity().add_component(servo);

    pendulum.world->start();
    REQUIRE(servo->initialized());
    pendulum.world->update(0.001f);

    CHECK(std::abs(servo->commanded_effort() - 1.8) < 1.0e-12);
    CHECK(std::abs(servo->position_effort()) < 1.0e-12);
    CHECK(std::abs(servo->velocity_effort() - 1.8) < 1.0e-12);
    CHECK(std::abs(servo->integral_effort()) < 1.0e-12);
    CHECK(std::abs(motor->applied_effort() - 1.8) < 1.0e-12);
    CHECK(!motor->saturated());

    pendulum.scene.destroy();
}

TEST_CASE("FEM servo without a physical motor is rejected")
{
    using namespace termin;

    DoublePendulumScene pendulum = make_double_pendulum_scene();
    auto* servo = new FEMJointServoComponent();
    servo->target_coordinate = 0.2;
    pendulum.joint_a->entity().add_component(servo);

    pendulum.world->start();

    CHECK(!pendulum.world->telemetry().initialized);
    CHECK(!pendulum.articulation->initialized());
    CHECK(!servo->initialized());

    pendulum.scene.destroy();
}

TEST_CASE("FEM servo load reaches and holds its authored target")
{
    using namespace termin;

    ServoLoadScene fixture = make_servo_load_scene();
    fixture.world->start();
    REQUIRE(fixture.articulation->initialized());
    REQUIRE(fixture.motor->initialized());
    REQUIRE(fixture.servo->initialized());

    fixture.world->update(0.005f);
    CHECK(fixture.motor->saturated());
    CHECK(std::abs(fixture.servo->integral_effort()) < 1.0e-12);

    for (int index = 0; index < 1000; ++index)
    {
        fixture.world->update(0.005f);
    }

    const FEMPhysicsTelemetry telemetry = fixture.world->telemetry();
    CHECK(telemetry.initialized);
    CHECK(telemetry.motor_count == 1U);
    CHECK(telemetry.successful_steps >= 2000U);
    CHECK(telemetry.successful_steps <= 2002U);
    CHECK(std::abs(fixture.joint->coordinate - 90.0) < 0.5);
    CHECK(std::abs(fixture.servo->position_error()) < 0.5);
    CHECK(std::isfinite(fixture.servo->integral_effort()));
    CHECK(std::abs(fixture.servo->integral_effort()) > 1.0);
    CHECK(std::abs(fixture.servo->commanded_effort() -
                   (fixture.servo->position_effort() +
                    fixture.servo->integral_effort() +
                    fixture.servo->velocity_effort() +
                    fixture.servo->feed_forward_effort)) < 1.0e-10);
    CHECK(!fixture.motor->saturated());
    CHECK(std::isfinite(telemetry.motor_power));
    CHECK(std::isfinite(telemetry.motor_work));

    fixture.servo->position_control_enabled = false;
    fixture.world->update(0.005f);
    CHECK(std::abs(fixture.servo->integral_effort()) < 1.0e-12);

    fixture.scene.destroy();
}

TEST_CASE(
    "FEM routes a CollisionWorld patch from static terrain to a maximal body")
{
    using namespace termin;

    register_test_component_types();
    MaximalContactScene fixture = make_maximal_contact_scene();
    collision::CollisionWorld* collision_world =
        collision::CollisionWorld::from_scene(fixture.scene.handle());
    REQUIRE(collision_world != nullptr);
    collision_world->update_all();
    REQUIRE(!collision_world->detect_contacts().empty());

    const double height_before =
        fixture.body->entity().transform().global_position().z;
    fixture.world->start();
    fixture.world->update(0.011F);

    const FEMPhysicsTelemetry telemetry = fixture.world->telemetry();
    CHECK(telemetry.initialized);
    CHECK(telemetry.successful_steps >= 1U);
    CHECK(telemetry.contact_count >= 1U);
    CHECK(telemetry.active_contact_count >= 1U);
    CHECK(telemetry.minimum_contact_gap >= -1.0e-8);
    CHECK(fixture.body->entity().transform().global_position().z >
          height_before);

    fixture.scene.destroy();
}

TEST_CASE("FEM frictionless contact arrests a falling maximal body")
{
    using namespace termin;

    register_test_component_types();
    MaximalContactScene fixture =
        make_maximal_contact_scene(2.0, Vec3{0.0, 0.0, -9.81}, 0.002);
    fixture.world->start();
    REQUIRE(fixture.body->initialized());
    REQUIRE(fixture.body->set_velocity_local(
        Screw3{Vec3::zero(), Vec3{0.75, 0.0, 0.0}}));

    const double initial_x =
        fixture.body->entity().transform().global_position().x;
    double minimum_height = 2.0;
    double maximum_height_after_contact = 0.0;
    double reaction_sum = 0.0;
    double minimum_reaction_in_window = std::numeric_limits<double>::infinity();
    std::size_t minimum_contacts_in_window =
        std::numeric_limits<std::size_t>::max();
    std::size_t minimum_cached_contacts_in_window =
        std::numeric_limits<std::size_t>::max();
    std::size_t minimum_warm_contacts_in_window =
        std::numeric_limits<std::size_t>::max();
    bool contact_seen = false;
    constexpr int step_count = 1500;
    constexpr int reaction_window = 500;
    for (int step = 0; step < step_count; ++step)
    {
        fixture.world->update(0.002F);
        const FEMPhysicsTelemetry telemetry = fixture.world->telemetry();
        const double height =
            fixture.body->entity().transform().global_position().z;
        minimum_height = std::min(minimum_height, height);
        if (telemetry.contact_count > 0)
        {
            contact_seen = true;
        }
        if (contact_seen)
        {
            maximum_height_after_contact =
                std::max(maximum_height_after_contact, height);
        }
        if (step >= step_count - reaction_window)
        {
            reaction_sum += telemetry.normal_reaction_sum;
            minimum_reaction_in_window = std::min(
                minimum_reaction_in_window, telemetry.normal_reaction_sum);
            minimum_contacts_in_window =
                std::min(minimum_contacts_in_window, telemetry.contact_count);
            minimum_cached_contacts_in_window =
                std::min(minimum_cached_contacts_in_window,
                         telemetry.cached_contact_count);
            minimum_warm_contacts_in_window =
                std::min(minimum_warm_contacts_in_window,
                         telemetry.warm_started_contact_count);
        }
    }

    const FEMPhysicsTelemetry telemetry = fixture.world->telemetry();
    const Vec3 final_position =
        fixture.body->entity().transform().global_position();
    CHECK(telemetry.initialized);
    CHECK(contact_seen);
    // At dt=2 ms the first impact may advance about 5.5 mm into the plane;
    // split position projection then restores the exact resting pose.
    CHECK(minimum_height >= 0.49);
    CHECK(maximum_height_after_contact <= 0.5 + 1.0e-5);
    CHECK(std::abs(final_position.z - 0.5) < 1.0e-5);
    CHECK(std::abs(final_position.x - initial_x - 0.75 * 3.0) < 2.0e-3);
    CHECK(std::abs(fixture.body->velocity_local().lin.x - 0.75) < 1.0e-6);
    CHECK(std::abs(reaction_sum / reaction_window - 9.81) < 2.0e-3);
    CHECK(minimum_reaction_in_window > 9.80);
    CHECK(minimum_contacts_in_window > 0);
    CHECK(minimum_cached_contacts_in_window > 0);
    CHECK(minimum_warm_contacts_in_window > 0);

    fixture.scene.destroy();
}

TEST_CASE("FEM multi-point box contact dissipates tangential slip")
{
    using namespace termin;

    register_test_component_types();
    MaximalContactScene fixture =
        make_maximal_contact_scene(2.0, Vec3{0.0, 0.0, -9.81}, 0.002);
    fixture.world->contact_friction_coefficient = 0.5;
    fixture.world->start();
    REQUIRE(fixture.body->initialized());
    REQUIRE(fixture.body->set_velocity_local(
        Screw3{Vec3::zero(), Vec3{0.75, 0.0, 0.0}}));

    double maximum_tangent_impulse = 0.0;
    double accumulated_friction_work = 0.0;
    for (int step = 0; step < 1500; ++step)
    {
        fixture.world->update(0.002F);
        const FEMPhysicsTelemetry step_telemetry = fixture.world->telemetry();
        maximum_tangent_impulse = std::max(maximum_tangent_impulse,
                                           step_telemetry.tangent_impulse_sum);
        accumulated_friction_work += step_telemetry.friction_work;
    }

    const FEMPhysicsTelemetry telemetry = fixture.world->telemetry();
    const Vec3 position = fixture.body->entity().transform().global_position();
    CHECK(telemetry.initialized);
    CHECK(telemetry.contact_count >= 1U);
    CHECK(telemetry.active_contact_count >= 1U);
    CHECK(std::abs(position.z - 0.5) < 1.0e-5);
    CHECK(std::abs(fixture.body->velocity_local().lin.x) < 1.0e-6);
    CHECK(maximum_tangent_impulse > 0.0);
    CHECK(accumulated_friction_work < 0.0);
    CHECK(position.x > 0.0);
    CHECK(position.x < 0.75 * 3.0);

    fixture.scene.destroy();
}

TEST_CASE("FEM articulation contact supplies the expected generalized support")
{
    using namespace termin;

    register_test_component_types();
    TcSceneRef scene = TcSceneRef::create("articulation support acceptance");

    Entity terrain = scene.create_entity("Terrain");
    terrain.transform().set_local_position({0.0, 0.0, -0.5});
    auto* terrain_collider = new ColliderComponent();
    terrain_collider->box_size = {10.0, 10.0, 1.0};
    terrain.add_component(terrain_collider);

    Entity root = scene.create_entity("Articulation Root");
    root.transform().set_local_position({0.0, 0.0, 0.5});
    auto* articulation = new FEMArticulationComponent();
    root.add_component(articulation);
    Entity joint_entity = root.create_child("Support Joint");
    auto* joint = new RotatorComponent();
    joint_entity.add_component(joint);
    joint->set_axis(0.0, 1.0, 0.0);
    joint->set_coordinate_scale(1.0);
    joint->set_coordinate(0.0);
    Entity link_entity = joint_entity.create_child("Supported Link");
    link_entity.transform().set_local_position({1.0, 0.0, 0.0});
    auto* link_body = new FEMRigidBodyComponent();
    link_body->mass = 1.0;
    link_body->inertia_diagonal = {1.0 / 6.0, 1.0 / 6.0, 1.0 / 6.0};
    link_entity.add_component(link_body);
    auto* link_collider = new ColliderComponent();
    // A single sphere-plane point keeps this test about the generalized
    // contact equation, without the statically indeterminate box manifold.
    link_collider->collider_type = "Sphere";
    link_entity.add_component(link_collider);

    Entity world_entity = scene.create_entity("Physics World");
    auto* world = new FEMPhysicsWorldComponent();
    world->gravity = {0.0, 0.0, -9.81};
    world->time_step = 0.002;
    world_entity.add_component(world);
    world->start();
    REQUIRE(articulation->initialized());

    double reaction_sum = 0.0;
    std::size_t minimum_contacts_in_window =
        std::numeric_limits<std::size_t>::max();
    std::size_t minimum_warm_contacts_in_window =
        std::numeric_limits<std::size_t>::max();
    constexpr int step_count = 1000;
    constexpr int reaction_window = 500;
    for (int step = 0; step < step_count; ++step)
    {
        world->update(0.002F);
        if (step >= step_count - reaction_window)
        {
            const FEMPhysicsTelemetry step_telemetry = world->telemetry();
            reaction_sum += step_telemetry.normal_reaction_sum;
            minimum_contacts_in_window = std::min(minimum_contacts_in_window,
                                                  step_telemetry.contact_count);
            minimum_warm_contacts_in_window =
                std::min(minimum_warm_contacts_in_window,
                         step_telemetry.warm_started_contact_count);
        }
    }

    const FEMPhysicsTelemetry telemetry = world->telemetry();
    CHECK(telemetry.initialized);
    CHECK(telemetry.contact_count > 0);
    CHECK(std::abs(joint->coordinate) < 1.0e-5);
    // The contact point is one metre from the revolute axis, so its normal
    // reaction supplies the 9.81 N*m generalized gravity effort directly.
    constexpr double support_lever = 1.0;
    CHECK(std::abs(reaction_sum / reaction_window * support_lever - 9.81) <
          2.0e-3);
    CHECK(minimum_contacts_in_window > 0);
    CHECK(minimum_warm_contacts_in_window > 0);
    scene.destroy();
}

TEST_CASE("FEM routes a CollisionWorld patch to an articulation link")
{
    using namespace termin;

    register_test_component_types();
    TcSceneRef scene = TcSceneRef::create("articulation contact");

    Entity terrain = scene.create_entity("Terrain");
    terrain.transform().set_local_position({0.0, 0.0, -0.5});
    auto* terrain_collider = new ColliderComponent();
    terrain_collider->box_size = {10.0, 10.0, 1.0};
    terrain.add_component(terrain_collider);

    Entity root = scene.create_entity("Articulation Root");
    auto* articulation = new FEMArticulationComponent();
    root.add_component(articulation);
    Entity joint_entity = root.create_child("Joint");
    auto* joint = new RotatorComponent();
    joint_entity.add_component(joint);
    joint->set_axis(0.0, 1.0, 0.0);
    joint->set_coordinate_scale(1.0);
    joint->set_coordinate(0.0);
    Entity link_entity = joint_entity.create_child("Contact Link");
    link_entity.transform().set_local_position({1.0, 0.0, 0.45});
    link_entity.add_component(new FEMRigidBodyComponent());
    auto* link_collider = new ColliderComponent();
    link_collider->box_size = {1.0, 1.0, 1.0};
    link_entity.add_component(link_collider);

    Entity world_entity = scene.create_entity("Physics World");
    auto* world = new FEMPhysicsWorldComponent();
    world->gravity = {0.0, 0.0, 0.0};
    world->time_step = 0.01;
    world_entity.add_component(world);

    world->start();
    REQUIRE(articulation->initialized());
    world->update(0.011F);

    const FEMPhysicsTelemetry telemetry = world->telemetry();
    CHECK(telemetry.initialized);
    CHECK(telemetry.contact_count >= 1U);
    CHECK(telemetry.minimum_contact_gap >= -1.0e-8);
    CHECK(std::abs(joint->coordinate) > 1.0e-8);
    scene.destroy();
}

TEST_CASE("FEM contact policy excludes adjacent articulation links")
{
    using namespace termin;

    register_test_component_types();
    DoublePendulumScene fixture = make_double_pendulum_scene();
    auto* collider_a = new ColliderComponent();
    collider_a->box_size = {3.0, 3.0, 3.0};
    fixture.body_a->entity().add_component(collider_a);
    auto* collider_b = new ColliderComponent();
    collider_b->box_size = {3.0, 3.0, 3.0};
    fixture.body_b->entity().add_component(collider_b);

    collision::CollisionWorld* collision_world =
        collision::CollisionWorld::from_scene(fixture.scene.handle());
    REQUIRE(collision_world != nullptr);
    collision_world->update_all();
    REQUIRE(!collision_world->detect_contacts().empty());

    fixture.world->start();
    fixture.world->update(0.002F);
    const FEMPhysicsTelemetry telemetry = fixture.world->telemetry();
    CHECK(telemetry.initialized);
    CHECK(telemetry.contact_count == 0U);
    fixture.scene.destroy();
}

TEST_CASE("FEM contact mapping follows collider disable and removal lifecycle")
{
    using namespace termin;

    register_test_component_types();
    MaximalContactScene fixture = make_maximal_contact_scene();
    fixture.world->start();
    fixture.world->update(0.011F);
    REQUIRE(fixture.world->telemetry().contact_count >= 1U);

    fixture.body_collider->set_enabled(false);
    fixture.world->update(0.011F);
    CHECK(fixture.world->telemetry().initialized);
    CHECK(fixture.world->telemetry().contact_count == 0U);

    Entity body_entity = fixture.body->entity();
    body_entity.remove_component(fixture.body_collider);
    fixture.body_collider = nullptr;
    fixture.world->update(0.011F);
    CHECK(fixture.world->telemetry().initialized);
    CHECK(fixture.world->telemetry().contact_count == 0U);
    fixture.scene.destroy();
}

TEST_CASE("scene articulation compiler rejects an implicit missing body")
{
    using namespace termin;

    TcSceneRef scene = TcSceneRef::create("invalid articulation");
    Entity root = scene.create_entity("Root");
    root.add_component(new FEMArticulationComponent());
    Entity empty_joint = root.create_child("Joint without body");
    empty_joint.add_component(new RotatorComponent());

    const FEMArticulationSceneCompilation compiled =
        compile_fem_articulation_scene(root);
    CHECK(compiled.diagnostic == FEMArticulationSceneDiagnostic::MissingBody);
    CHECK(compiled.diagnostic_entity == "Joint without body");
    scene.destroy();
}
