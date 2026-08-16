#include "guard_main.h"

GUARD_TEST_MAIN();

#include <algorithm>
#include <array>
#include <cmath>
#include <limits>
#include <numbers>

#include <components/articulation_component.hpp>
#include <components/collider_component.hpp>
#include <components/rotator_component.hpp>
#include <inspect/tc_inspect_component_adapter.h>
#include <inspect/tc_inspect_init.h>
#include <physics/tc_collision_world.h>
#include <termin/collision/collision_world.hpp>
#include <termin/geom/general_pose3.hpp>
#include <termin/physics_fem/articulation_scene.hpp>
#include <termin/physics_fem/components.hpp>
#include <termin/render/render_lifecycle.hpp>
#include <termin/robotics/inverse_dynamics_control.hpp>
#include <termin/tc_scene.hpp>
#include <termin_collision/termin_collision.h>
#include <termin_scene/internal/tc_scene_extension_registry.h>

extern "C" {
#include <core/tc_debug_geometry.h>
#include <core/tc_scene_render_mount.h>
}

namespace {
    void register_test_component_types() {
        static const bool registered = []() {
            tc_inspect_kind_core_init();
            tc_inspect_component_adapter_init();
            tc_scene_ext_registry_init();
            tc_scene_render_mount_extension_init();
            termin_collision_runtime_init();
            termin::register_builtin_scene_component_types();
            termin::ColliderComponent::register_type();
            termin::KinematicUnitComponent::register_type();
            termin::RotatorComponent::register_type();
            termin::ArticulationComponent::register_type();
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

    void prepare_render_lifecycle(const termin::TcSceneRef& scene) {
        const termin::RenderPrepareContext context(scene.handle());
        tc_scene_render_mount_prepare(scene.handle(), reinterpret_cast<const tc_render_prepare_context*>(&context));
    }

    struct DoublePendulumScene {
        termin::TcSceneRef scene;
        termin::FEMPhysicsWorldComponent* world = nullptr;
        termin::FEMArticulationComponent* articulation = nullptr;
        termin::RotatorComponent* joint_a = nullptr;
        termin::RotatorComponent* joint_b = nullptr;
        termin::FEMRigidBodyComponent* body_a = nullptr;
        termin::FEMRigidBodyComponent* body_b = nullptr;
        termin::Entity root;
    };

    DoublePendulumScene make_double_pendulum_scene() {
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
        result.scene.set_fixed_timestep(0.001);
        world_entity.add_component(result.world);
        return result;
    }

    struct FloatingTreeScene {
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

    FloatingTreeScene make_floating_tree_scene() {
        using namespace termin;

        FloatingTreeScene result;
        result.scene = TcSceneRef::create("floating articulation tree");
        result.root = result.scene.create_entity("Floating Base");
        result.root.transform().set_local_position({1.0, 0.0, 2.0});
        result.articulation = new FEMArticulationComponent();
        result.articulation->base_mode = static_cast<int>(FEMArticulationBaseMode::Floating);
        result.root.add_component(result.articulation);
        result.base = new FEMRigidBodyComponent();
        result.base->mass = 4.0;
        result.base->inertia_diagonal = {1.0, 1.0, 1.0};
        result.root.add_component(result.base);

        const auto add_branch = [&result](const char* joint_name,
                                          const char* body_name,
                                          double x,
                                          RotatorComponent*& joint,
                                          FEMRigidBodyComponent*& body) {
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
        add_branch("Left Joint", "Left Link", -0.75, result.joint_a, result.link_a);
        add_branch("Right Joint", "Right Link", 0.75, result.joint_b, result.link_b);

        Entity world_entity = result.scene.create_entity("Physics World");
        result.world = new FEMPhysicsWorldComponent();
        result.world->gravity = {0.0, 0.0, 0.0};
        result.scene.set_fixed_timestep(0.001);
        world_entity.add_component(result.world);
        return result;
    }

    struct StandingRobotScene {
        termin::TcSceneRef scene;
        termin::Entity root;
        termin::FEMPhysicsWorldComponent* world = nullptr;
        termin::FEMArticulationComponent* articulation = nullptr;
        termin::FEMRigidBodyComponent* base = nullptr;
        std::array<termin::RotatorComponent*, 8> joints{};
        std::array<termin::FEMRigidBodyComponent*, 8> legs{};
        std::array<termin::FEMArticulationMotorComponent*, 8> motors{};
        std::array<termin::FEMJointServoComponent*, 8> servos{};
    };

    StandingRobotScene make_standing_robot_scene(termin::Vec3 root_position = {0.0, 0.0, 1.67},
                                                 termin::Quat root_rotation = termin::Quat::identity()) {
        using namespace termin;

        StandingRobotScene result;
        result.scene = TcSceneRef::create("standing articulated robot");

        Entity terrain = result.scene.create_entity("Terrain");
        terrain.transform().set_local_position({0.0, 0.0, -0.25});
        auto* terrain_collider = new ColliderComponent();
        terrain_collider->box_size = {8.0, 8.0, 0.5};
        terrain.add_component(terrain_collider);

        result.root = result.scene.create_entity("Robot Base");
        result.root.transform().set_local_position(root_position);
        result.root.transform().set_local_rotation(root_rotation);
        result.articulation = new FEMArticulationComponent();
        result.articulation->base_mode = static_cast<int>(FEMArticulationBaseMode::Floating);
        result.root.add_component(result.articulation);
        result.base = new FEMRigidBodyComponent();
        result.base->mass = 8.0;
        result.base->inertia_diagonal = {1.1, 1.6, 1.9};
        result.root.add_component(result.base);
        auto* base_collider = new ColliderComponent();
        base_collider->box_size = {1.4, 1.0, 0.4};
        result.root.add_component(base_collider);

        constexpr std::array<double, 4> hip_x{-0.58, 0.58, -0.58, 0.58};
        constexpr std::array<double, 4> hip_y{-0.4, -0.4, 0.4, 0.4};
        constexpr std::array<double, 4> side_sign{1.0, -1.0, 1.0, -1.0};
        constexpr std::array<const char*, 4> hip_names{
            "Front Left Hip",
            "Front Right Hip",
            "Rear Left Hip",
            "Rear Right Hip",
        };
        constexpr std::array<const char*, 4> upper_leg_names{
            "Front Left Upper Leg",
            "Front Right Upper Leg",
            "Rear Left Upper Leg",
            "Rear Right Upper Leg",
        };
        constexpr std::array<const char*, 4> knee_names{
            "Front Left Knee",
            "Front Right Knee",
            "Rear Left Knee",
            "Rear Right Knee",
        };
        constexpr std::array<const char*, 4> lower_leg_names{
            "Front Left Lower Leg",
            "Front Right Lower Leg",
            "Rear Left Lower Leg",
            "Rear Right Lower Leg",
        };
        constexpr std::array<const char*, 4> foot_names{
            "Front Left Foot Effector",
            "Front Right Foot Effector",
            "Rear Left Foot Effector",
            "Rear Right Foot Effector",
        };
        const auto add_servo = [&result](Entity joint_entity, std::size_t index, double target) {
            result.joints[index] = new RotatorComponent();
            joint_entity.add_component(result.joints[index]);
            result.joints[index]->set_axis(0.0, 1.0, 0.0);
            result.joints[index]->set_coordinate_scale(std::numbers::pi_v<double> / 180.0);
            result.joints[index]->coordinate = target;

            result.motors[index] = new FEMArticulationMotorComponent();
            result.motors[index]->maximum_effort = 40.0;
            joint_entity.add_component(result.motors[index]);

            result.servos[index] = new FEMJointServoComponent();
            result.servos[index]->target_coordinate = target;
            result.servos[index]->position_gain = 100.0;
            result.servos[index]->velocity_gain = 15.0;
            result.servos[index]->feed_forward_effort = 0.0;
            joint_entity.add_component(result.servos[index]);
        };

        for (std::size_t branch = 0; branch < hip_x.size(); ++branch) {
            const std::size_t hip_index = branch * 2U;
            const std::size_t knee_index = hip_index + 1U;
            const double hip_target = -15.0 * side_sign[branch];
            const double knee_target = 30.0 * side_sign[branch];

            Entity hip_entity = result.root.create_child(hip_names[branch]);
            add_servo(hip_entity, hip_index, hip_target);
            result.joints[hip_index]->origin_position = {hip_x[branch], hip_y[branch], -0.1};
            result.joints[hip_index]->apply();

            Entity upper_leg = hip_entity.create_child(upper_leg_names[branch]);
            upper_leg.transform().set_local_position({0.0, 0.0, -0.35});
            result.legs[hip_index] = new FEMRigidBodyComponent();
            result.legs[hip_index]->mass = 0.4;
            result.legs[hip_index]->inertia_diagonal = {0.018, 0.018, 0.003};
            upper_leg.add_component(result.legs[hip_index]);

            Entity knee_entity = upper_leg.create_child(knee_names[branch]);
            add_servo(knee_entity, knee_index, knee_target);
            result.joints[knee_index]->origin_position = {0.0, 0.0, -0.35};
            result.joints[knee_index]->apply();

            Entity lower_leg = knee_entity.create_child(lower_leg_names[branch]);
            lower_leg.transform().set_local_position({0.0, 0.0, -0.35});
            result.legs[knee_index] = new FEMRigidBodyComponent();
            result.legs[knee_index]->mass = 0.4;
            result.legs[knee_index]->inertia_diagonal = {0.018, 0.018, 0.003};
            lower_leg.add_component(result.legs[knee_index]);

            Entity foot_effector = lower_leg.create_child(foot_names[branch]);
            foot_effector.transform().set_local_position({0.0, 0.0, -0.35});
            auto* foot_collider = new ColliderComponent();
            foot_collider->collider_type = "Sphere";
            foot_collider->box_size = {0.24, 0.24, 0.24};
            foot_effector.add_component(foot_collider);
        }

        Entity world_entity = result.scene.create_entity("Physics World");
        result.world = new FEMPhysicsWorldComponent();
        result.world->gravity = {0.0, 0.0, -9.81};
        result.scene.set_fixed_timestep(0.002);
        result.world->contact_friction_coefficient = 0.8;
        world_entity.add_component(result.world);
        return result;
    }

    struct ServoLoadScene {
        termin::TcSceneRef scene;
        termin::FEMPhysicsWorldComponent* world = nullptr;
        termin::FEMArticulationComponent* articulation = nullptr;
        termin::RotatorComponent* joint = nullptr;
        termin::FEMArticulationMotorComponent* motor = nullptr;
        termin::FEMJointServoComponent* servo = nullptr;
    };

    ServoLoadScene make_servo_load_scene() {
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
        result.scene.set_fixed_timestep(0.005);
        world_entity.add_component(result.world);
        return result;
    }

    struct MaximalContactScene {
        termin::TcSceneRef scene;
        termin::FEMPhysicsWorldComponent* world = nullptr;
        termin::FEMRigidBodyComponent* body = nullptr;
        termin::ColliderComponent* body_collider = nullptr;
        termin::ColliderComponent* terrain_collider = nullptr;
    };

    MaximalContactScene make_maximal_contact_scene(double initial_height = 0.45,
                                                   termin::Vec3 gravity = termin::Vec3::zero(),
                                                   double time_step = 0.01) {
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
        result.scene.set_fixed_timestep(time_step);
        world_entity.add_component(result.world);
        return result;
    }

    struct SharedUnitScene {
        termin::Entity root;
        termin::Entity unit_entity;
        termin::ArticulationComponent* owner = nullptr;
        termin::FEMArticulationComponent* fem = nullptr;
        termin::RotatorComponent* unit = nullptr;
    };

    SharedUnitScene add_shared_unit_scene(termin::TcSceneRef scene, const char* root_name, termin::Vec3 root_position) {
        using namespace termin;

        SharedUnitScene result;
        result.root = scene.create_entity(root_name);
        result.root.transform().set_local_position(root_position);
        result.owner = new ArticulationComponent();
        result.fem = new FEMArticulationComponent();
        result.root.add_component(result.owner);
        result.root.add_component(result.fem);

        result.unit_entity = result.root.create_child("Unit");
        result.unit = new RotatorComponent();
        result.unit->mass = 1.0;
        result.unit->inertia_diagonal = {0.2, 0.2, 0.2};
        result.unit_entity.add_component(result.unit);
        result.unit->set_axis(0.0, 1.0, 0.0);
        return result;
    }

    termin::ColliderComponent*
    add_sphere_collider(termin::Entity parent, const char* name, termin::Vec3 local_position) {
        using namespace termin;

        Entity collider_entity = parent.create_child(name);
        collider_entity.transform().set_local_position(local_position);
        auto* collider = new ColliderComponent();
        collider->collider_type = "Sphere";
        collider->box_size = {1.0, 1.0, 1.0};
        collider_entity.add_component(collider);
        return collider;
    }

} // namespace

TEST_CASE("native FEM component doubles round-trip through inspect") {
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
    world.contact_friction_coefficient = 0.7;
    world.contact_friction_cone_facets = 8;
    tc_value world_data = world.serialize_data();

    FEMPhysicsWorldComponent restored_world;
    restored_world.deserialize_data(&world_data);
    CHECK(std::abs(restored_world.contact_friction_coefficient - 0.7) < 1.0e-12);
    CHECK(restored_world.contact_friction_cone_facets == 8);
    tc_value_free(&world_data);

    FEMArticulationComponent articulation;
    articulation.base_mode = static_cast<int>(FEMArticulationBaseMode::Floating);
    tc_value articulation_data = articulation.serialize_data();
    FEMArticulationComponent restored_articulation;
    restored_articulation.deserialize_data(&articulation_data);
    CHECK(restored_articulation.base_mode == static_cast<int>(FEMArticulationBaseMode::Floating));
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

TEST_CASE("FEM borrows ArticulationComponent model and accepts HQP efforts") {
    using namespace termin;
    using namespace termin::robotics;

    register_test_component_types();
    TcSceneRef scene = TcSceneRef::create("shared articulation control");
    Entity root = scene.create_entity("Arm Root");
    auto* owner = new ArticulationComponent();
    auto* fem = new FEMArticulationComponent();
    root.add_component(owner);
    root.add_component(fem);

    Entity shoulder_entity = root.create_child("Shoulder");
    auto* shoulder = new RotatorComponent();
    shoulder->set_axis(0.0, 1.0, 0.0);
    shoulder->mass = 1.0;
    shoulder->inertia_diagonal = {0.2, 0.2, 0.1};
    shoulder_entity.add_component(shoulder);
    auto* shoulder_motor = new FEMArticulationMotorComponent();
    shoulder_motor->maximum_effort = 8.0;
    shoulder_entity.add_component(shoulder_motor);

    Entity elbow_entity = shoulder_entity.create_child("Elbow");
    auto* elbow = new RotatorComponent();
    elbow->set_axis(0.0, 1.0, 0.0);
    elbow->origin_position = {0.8, 0.0, 0.0};
    elbow->mass = 0.7;
    elbow->inertia_diagonal = {0.1, 0.1, 0.05};
    elbow_entity.add_component(elbow);
    auto* elbow_motor = new FEMArticulationMotorComponent();
    elbow_motor->maximum_effort = 5.0;
    elbow_entity.add_component(elbow_motor);

    Entity world_entity = scene.create_entity("Physics World");
    auto* world = new FEMPhysicsWorldComponent();
    world->gravity = {0.0, 0.0, 0.0};
    world_entity.add_component(world);
    world->start();

    REQUIRE(owner->initialized());
    REQUIRE(fem->initialized());
    CHECK(fem->articulation() == owner->articulation());
    const std::vector<std::size_t> dofs = fem->actuator_dof_indices();
    const std::vector<double> limits = fem->actuator_effort_limits();
    REQUIRE(dofs.size() == 2U);
    REQUIRE(dofs[0] == 0U);
    REQUIRE(dofs[1] == 1U);
    REQUIRE(limits.size() == 2U);
    REQUIRE(limits[0] == 8.0);
    REQUIRE(limits[1] == 5.0);

    std::vector<InverseDynamicsActuator3D> actuators;
    for (std::size_t index = 0; index < dofs.size(); ++index) {
        actuators.push_back({
            .dof_index = dofs[index],
            .minimum_effort = -limits[index],
            .maximum_effort = limits[index],
        });
    }
    InverseDynamicsHqpController3D controller(*owner->articulation(), std::move(actuators), Vec3::zero());
    JointPostureTask3D posture({}, {0.3, -0.2}, {0.0, 0.0}, 20.0, 8.0);
    const std::array<const ArticulationTask3D*, 1> tasks{&posture};
    const InverseDynamicsControlResult3D control = controller.solve(tasks, {.time_step = 0.002});
    REQUIRE(control.ok());
    REQUIRE(fem->apply_inverse_dynamics_control(control));

    world->fixed_update(0.002F);
    CHECK(world->telemetry().successful_steps == 1U);
    CHECK(std::abs(owner->articulation()->state().velocities[0]) > 1.0e-9);
    CHECK(std::abs(shoulder_motor->commanded_effort) > 1.0e-9);

    Articulation3D* active_model = fem->articulation();
    REQUIRE(owner->rebuild());
    CHECK(owner->articulation() != active_model);
    CHECK(fem->articulation() == active_model);
    world->fixed_update(0.002F);
    CHECK(world->telemetry().successful_steps == 1U);

    scene.destroy();
}

TEST_CASE("rotator attachment distinguishes fresh and deserialized state") {
    using namespace termin;

    register_test_component_types();
    TcSceneRef scene = TcSceneRef::create("rotator lifecycle");

    Entity fresh_entity = scene.create_entity("Fresh Joint");
    fresh_entity.transform().set_local_position({1.0, 2.0, 3.0});
    fresh_entity.transform().set_local_rotation(Quat::from_axis_angle({0.0, 1.0, 0.0}, 0.4));
    fresh_entity.transform().set_local_scale({2.0, 3.0, 4.0});
    auto* fresh = new RotatorComponent();
    fresh_entity.add_component(fresh);
    CHECK((fresh->origin_position - Vec3{1.0, 2.0, 3.0}).norm() < 1.0e-12);
    CHECK(std::abs(fresh->origin_rotation.y - std::sin(0.2)) < 1.0e-12);
    CHECK((fresh_entity.transform().local_scale() - Vec3{2.0, 3.0, 4.0}).norm() < 1.0e-12);

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

    CHECK((restored_entity.transform().local_position() - Vec3{4.0, 5.0, 6.0}).norm() < 1.0e-12);
    CHECK(std::abs(restored_entity.transform().local_rotation().y - std::sin(0.4)) < 1.0e-12);
    CHECK((restored_entity.transform().local_scale() - Vec3{2.0, 3.0, 4.0}).norm() < 1.0e-12);
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

TEST_CASE("kinematic axes are unit directions with an explicit coordinate scale") {
    using namespace termin;

    RotatorComponent rotator;
    rotator.set_axis(0.0, 4.0, 0.0);
    rotator.set_coordinate_scale(std::numbers::pi_v<double> / 180.0);
    rotator.set_coordinate(90.0);

    CHECK((rotator.get_axis() - Vec3::unit_y()).norm() < 1.0e-12);
    CHECK(std::abs(rotator.get_axis().norm() - 1.0) < 1.0e-12);
    CHECK(std::abs(rotator.physical_coordinate() - std::numbers::pi_v<double> / 2.0) < 1.0e-12);
}

TEST_CASE("scene articulation compiler collapses authored frames into units") {
    using namespace termin;

    DoublePendulumScene pendulum = make_double_pendulum_scene();
    const FEMArticulationSceneCompilation compiled = compile_fem_articulation_scene(pendulum.root);

    REQUIRE(compiled.ok());
    REQUIRE_EQ(compiled.units.size(), 2U);
    REQUIRE_EQ(compiled.bindings.size(), 2U);
    CHECK(compiled.units[0].parent_unit == robotics::articulation_root_frame);
    CHECK(compiled.units[1].parent_unit == 0U);
    CHECK(std::abs(compiled.units[0].parent_to_unit_zero.lin.z - 3.0) < 1.0e-12);
    CHECK(std::abs(compiled.units[0].motion_twist_at_unit.ang.y - 1.0) < 1.0e-12);
    CHECK(std::abs(compiled.units[0].motion_twist_at_unit.ang.norm() - 1.0) < 1.0e-12);
    CHECK(std::abs(compiled.units[1].parent_to_unit_zero.lin.z + 2.0) < 1.0e-12);
    CHECK(std::abs(compiled.state.coordinates[0] - 0.7) < 1.0e-12);
    CHECK(std::abs(compiled.state.coordinates[1] + 0.4) < 1.0e-12);

    pendulum.scene.destroy();
}

TEST_CASE("scene articulation compiler maps a floating base and branches") {
    using namespace termin;

    FloatingTreeScene fixture = make_floating_tree_scene();
    const FEMArticulationSceneCompilation compiled = compile_fem_articulation_scene(fixture.root);

    REQUIRE(compiled.ok());
    REQUIRE(compiled.floating_base.has_value());
    CHECK(compiled.base_body == fixture.base);
    CHECK(compiled.base_entity == fixture.root);
    CHECK((compiled.floating_base->pose_world.lin - Vec3{1.0, 0.0, 2.0}).norm() < 1.0e-12);
    REQUIRE_EQ(compiled.units.size(), 2U);
    CHECK(compiled.units[0].parent_unit == robotics::articulation_root_frame);
    CHECK(compiled.units[1].parent_unit == robotics::articulation_root_frame);
    CHECK(std::abs(compiled.units[0].parent_to_unit_zero.lin.x + 0.75) < 1.0e-12);
    CHECK(std::abs(compiled.units[1].parent_to_unit_zero.lin.x - 0.75) < 1.0e-12);

    fixture.scene.destroy();
}

TEST_CASE("scene articulation compiler rejects contradictory base layouts") {
    using namespace termin;

    DoublePendulumScene fixed = make_double_pendulum_scene();
    auto* unexpected_body = new FEMRigidBodyComponent();
    fixed.root.add_component(unexpected_body);
    CHECK(compile_fem_articulation_scene(fixed.root).diagnostic == FEMArticulationSceneDiagnostic::UnexpectedRootBody);
    fixed.scene.destroy();

    DoublePendulumScene floating = make_double_pendulum_scene();
    floating.articulation->base_mode = static_cast<int>(FEMArticulationBaseMode::Floating);
    CHECK(compile_fem_articulation_scene(floating.root).diagnostic == FEMArticulationSceneDiagnostic::MissingRootBody);
    floating.scene.destroy();

    FloatingTreeScene multiple = make_floating_tree_scene();
    multiple.root.add_component(new FEMRigidBodyComponent());
    CHECK(compile_fem_articulation_scene(multiple.root).diagnostic == FEMArticulationSceneDiagnostic::MultipleBodies);
    multiple.scene.destroy();
}

TEST_CASE("scene articulation compiler converts authored joint limits") {
    using namespace termin;

    DoublePendulumScene pendulum = make_double_pendulum_scene();
    pendulum.joint_a->set_coordinate_scale(0.1);
    auto* limits = new FEMJointLimitComponent();
    limits->minimum_enabled = true;
    limits->maximum_enabled = true;
    limits->minimum_coordinate = -2.0;
    limits->maximum_coordinate = 3.0;
    pendulum.joint_a->entity().add_component(limits);

    const FEMArticulationSceneCompilation compiled = compile_fem_articulation_scene(pendulum.root);
    REQUIRE(compiled.ok());
    REQUIRE(compiled.units[0].limits.minimum.has_value());
    REQUIRE(compiled.units[0].limits.maximum.has_value());
    CHECK(std::abs(*compiled.units[0].limits.minimum + 0.2) < 1.0e-12);
    CHECK(std::abs(*compiled.units[0].limits.maximum - 0.3) < 1.0e-12);
    CHECK(std::abs(compiled.state.coordinates[0] - 0.07) < 1.0e-12);

    pendulum.scene.destroy();
}

TEST_CASE("scene articulation compiler rejects invalid joint limits") {
    using namespace termin;

    DoublePendulumScene reversed = make_double_pendulum_scene();
    auto* reversed_limits = new FEMJointLimitComponent();
    reversed_limits->minimum_enabled = true;
    reversed_limits->maximum_enabled = true;
    reversed_limits->minimum_coordinate = 2.0;
    reversed_limits->maximum_coordinate = -1.0;
    reversed.joint_a->entity().add_component(reversed_limits);
    const FEMArticulationSceneCompilation reversed_compilation = compile_fem_articulation_scene(reversed.root);
    CHECK(reversed_compilation.diagnostic == FEMArticulationSceneDiagnostic::InvalidJointLimits);
    CHECK(reversed_compilation.diagnostic_entity == "Hip Joint");
    reversed.scene.destroy();

    DoublePendulumScene non_finite = make_double_pendulum_scene();
    auto* non_finite_limits = new FEMJointLimitComponent();
    non_finite_limits->minimum_enabled = true;
    non_finite_limits->minimum_coordinate = std::numeric_limits<double>::quiet_NaN();
    non_finite.joint_a->entity().add_component(non_finite_limits);
    const FEMArticulationSceneCompilation non_finite_compilation = compile_fem_articulation_scene(non_finite.root);
    CHECK(non_finite_compilation.diagnostic == FEMArticulationSceneDiagnostic::InvalidJointLimits);
    non_finite.scene.destroy();
}

TEST_CASE("FEM world advances a compiled reduced double pendulum") {
    using namespace termin;

    DoublePendulumScene pendulum = make_double_pendulum_scene();
    const double coordinate_before = pendulum.joint_a->coordinate;
    pendulum.world->start();

    REQUIRE(pendulum.articulation->initialized());
    REQUIRE(pendulum.articulation->articulation() != nullptr);
    const FEMPhysicsTelemetry initial = pendulum.world->telemetry();
    CHECK(initial.initialized);
    CHECK(initial.body_count == 2U);
    CHECK(initial.articulation_count == 1U);
    CHECK(initial.reduced_dof_count == 2U);
    CHECK(initial.joint_count == 0U);
    CHECK(std::isfinite(initial.total_energy));

    for (int step = 0; step < 20; ++step) {
        pendulum.world->fixed_update(0.001F);
    }
    const FEMPhysicsTelemetry advanced = pendulum.world->telemetry();
    CHECK(advanced.initialized);
    CHECK(advanced.successful_steps == 20U);
    CHECK(std::abs(pendulum.joint_a->coordinate - coordinate_before) > 1.0e-8);
    CHECK(std::abs(advanced.total_energy - initial.total_energy) < 1.0e-5);

    pendulum.scene.destroy();
}

TEST_CASE("FEM world advances and synchronizes a floating articulation root") {
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

    REQUIRE(fixture.base->set_velocity_local(Screw3{Vec3::zero(), Vec3::unit_x()}));
    const double x_before = fixture.root.transform().global_position().x;
    fixture.world->fixed_update(0.001F);
    CHECK(fixture.world->telemetry().successful_steps == 1U);
    CHECK(fixture.root.transform().global_position().x > x_before);
    CHECK(fixture.base->velocity_local().lin.x > 0.9);
    CHECK(std::abs(motor->applied_effort() - 1.0) < 1.0e-12);
    CHECK(std::isfinite(motor->power()));
    CHECK(!fixture.link_a->set_velocity_local(Screw3::zero()));

    fixture.scene.destroy();
}

TEST_CASE("FEM routes contacts to a floating articulation base") {
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
    fixture.world->fixed_update(0.001F);

    const FEMPhysicsTelemetry telemetry = fixture.world->telemetry();
    CHECK(telemetry.initialized);
    CHECK(telemetry.contact_count >= 1U);
    CHECK(telemetry.active_contact_count >= 1U);
    CHECK(fixture.root.transform().global_position().z > 0.45);

    fixture.scene.destroy();
}

TEST_CASE("FEM floating robot stands on servo-controlled frictional legs") {
    using namespace termin;

    register_test_component_types();
    StandingRobotScene fixture = make_standing_robot_scene();
    fixture.world->start();

    REQUIRE(fixture.articulation->initialized());
    REQUIRE(fixture.base->initialized());
    const FEMPhysicsTelemetry initial = fixture.world->telemetry();
    CHECK(initial.initialized);
    CHECK(initial.body_count == 9U);
    CHECK(initial.articulation_count == 1U);
    CHECK(initial.reduced_dof_count == 14U);
    CHECK(initial.motor_count == 8U);

    bool contact_seen = false;
    double accumulated_friction_work = 0.0;
    double reaction_sum = 0.0;
    constexpr int standing_steps = 2500;
    constexpr int reaction_window = 500;
    for (int step = 0; step < standing_steps; ++step) {
        fixture.world->fixed_update(0.002F);
        const FEMPhysicsTelemetry telemetry = fixture.world->telemetry();
        contact_seen = contact_seen || telemetry.active_contact_count > 0U;
        accumulated_friction_work += telemetry.friction_work;
        if (step >= standing_steps - reaction_window) {
            reaction_sum += telemetry.normal_reaction_sum;
        }
    }

    const Vec3 standing_position = fixture.root.transform().global_position();
    const FEMPhysicsTelemetry standing = fixture.world->telemetry();
    CHECK(standing.successful_steps == standing_steps);
    CHECK(contact_seen);
    CHECK(standing.active_contact_count >= 4U);
    CHECK(standing.sliding_contact_count == 0U);
    CHECK(accumulated_friction_work <= 1.0e-10);
    CHECK(standing_position.z > 1.37);
    CHECK(standing_position.z < 1.67);
    CHECK(std::abs(standing_position.x) < 0.1);
    CHECK(std::abs(standing_position.y) < 0.1);

    CHECK(std::abs(reaction_sum / reaction_window - 11.2 * 9.81) < 0.5);
    CHECK(standing.motor_effort_linf > 0.0);

    for (FEMJointServoComponent* servo : fixture.servos) {
        servo->set_enabled(false);
    }
    constexpr int maximum_collapse_steps = 1500;
    const double collapse_height = standing_position.z - 0.25;
    int collapse_steps = 0;
    while (collapse_steps < maximum_collapse_steps && fixture.root.transform().global_position().z >= collapse_height) {
        fixture.world->fixed_update(0.002F);
        ++collapse_steps;
    }
    const Vec3 fallen_position = fixture.root.transform().global_position();
    CHECK(fixture.world->telemetry().successful_steps == standing_steps + collapse_steps);
    CHECK(fallen_position.z < collapse_height);

    fixture.scene.destroy();
}

TEST_CASE("FEM floating robot survives an asymmetric high tilted landing") {
    using namespace termin;

    register_test_component_types();
    StandingRobotScene fixture = make_standing_robot_scene({0.0, 0.0, 3.3596982955932617},
                                                           Quat{
                                                               -0.03302609427971528,
                                                               -0.0715192083359704,
                                                               -0.002369370458237609,
                                                               0.9968894953901635,
                                                           });
    fixture.world->start();

    bool contact_seen = false;
    constexpr int landing_steps = 25000;
    for (int step = 0; step < landing_steps; ++step) {
        fixture.world->fixed_update(0.002F);
        contact_seen = contact_seen || fixture.world->telemetry().active_contact_count > 0U;
    }

    const FEMPhysicsTelemetry telemetry = fixture.world->telemetry();
    const Vec3 position = fixture.root.transform().global_position();
    CHECK(telemetry.initialized);
    CHECK(telemetry.successful_steps == landing_steps);
    CHECK(contact_seen);
    CHECK(std::isfinite(position.x));
    CHECK(std::isfinite(position.y));
    CHECK(std::isfinite(position.z));
    CHECK(position.z > 1.0);

    fixture.scene.destroy();
}

TEST_CASE("FEM motor accepts a direct reduced-coordinate effort command") {
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

    pendulum.world->fixed_update(0.001f);

    CHECK(std::abs(motor->applied_effort()) <= motor->maximum_effort + 1.0e-12);
    CHECK(motor->saturated());

    pendulum.scene.destroy();
}

TEST_CASE("FEM servo drives a separate articulation motor in physical units") {
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

    for (int index = 0; index < 40; ++index) {
        pendulum.world->fixed_update(0.001f);
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

TEST_CASE("FEM servo can disable its position control loop") {
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
    pendulum.world->fixed_update(0.001f);

    CHECK(std::abs(servo->commanded_effort() - 1.8) < 1.0e-12);
    CHECK(std::abs(servo->position_effort()) < 1.0e-12);
    CHECK(std::abs(servo->velocity_effort() - 1.8) < 1.0e-12);
    CHECK(std::abs(servo->integral_effort()) < 1.0e-12);
    CHECK(std::abs(motor->applied_effort() - 1.8) < 1.0e-12);
    CHECK(!motor->saturated());

    pendulum.scene.destroy();
}

TEST_CASE("FEM servo without a physical motor is rejected") {
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

TEST_CASE("FEM servo load reaches and holds its authored target") {
    using namespace termin;

    ServoLoadScene fixture = make_servo_load_scene();
    fixture.world->start();
    REQUIRE(fixture.articulation->initialized());
    REQUIRE(fixture.motor->initialized());
    REQUIRE(fixture.servo->initialized());

    fixture.world->fixed_update(0.005f);
    CHECK(fixture.motor->saturated());
    CHECK(std::abs(fixture.servo->integral_effort()) < 1.0e-12);

    for (int index = 0; index < 1000; ++index) {
        fixture.world->fixed_update(0.005f);
    }

    const FEMPhysicsTelemetry telemetry = fixture.world->telemetry();
    CHECK(telemetry.initialized);
    CHECK(telemetry.motor_count == 1U);
    CHECK(telemetry.successful_steps == 1001U);
    CHECK(std::abs(fixture.joint->coordinate - 90.0) < 0.5);
    CHECK(std::abs(fixture.servo->position_error()) < 0.5);
    CHECK(std::isfinite(fixture.servo->integral_effort()));
    CHECK(std::abs(fixture.servo->integral_effort()) > 1.0);
    CHECK(std::abs(fixture.servo->commanded_effort() -
                   (fixture.servo->position_effort() + fixture.servo->integral_effort() +
                    fixture.servo->velocity_effort() + fixture.servo->feed_forward_effort)) < 1.0e-10);
    CHECK(!fixture.motor->saturated());
    CHECK(std::isfinite(telemetry.motor_power));
    CHECK(std::isfinite(telemetry.motor_work));

    fixture.servo->position_control_enabled = false;
    fixture.world->fixed_update(0.005f);
    CHECK(std::abs(fixture.servo->integral_effort()) < 1.0e-12);

    fixture.scene.destroy();
}

TEST_CASE("FEM routes a CollisionWorld patch from static terrain to a maximal body") {
    using namespace termin;

    register_test_component_types();
    MaximalContactScene fixture = make_maximal_contact_scene();
    collision::CollisionWorld* collision_world = collision::CollisionWorld::from_scene(fixture.scene.handle());
    REQUIRE(collision_world != nullptr);
    collision_world->update_all();
    REQUIRE(!collision_world->detect_contacts().empty());

    const double height_before = fixture.body->entity().transform().global_position().z;
    fixture.world->start();
    fixture.world->fixed_update(0.011F);

    const FEMPhysicsTelemetry telemetry = fixture.world->telemetry();
    CHECK(telemetry.initialized);
    CHECK(telemetry.successful_steps >= 1U);
    CHECK(telemetry.contact_count >= 1U);
    CHECK(telemetry.active_contact_count >= 1U);
    CHECK(telemetry.minimum_contact_gap >= -1.0e-8);
    CHECK(fixture.body->entity().transform().global_position().z > height_before);

    fixture.scene.destroy();
}

TEST_CASE("FEM frictionless contact arrests a falling maximal body") {
    using namespace termin;

    register_test_component_types();
    MaximalContactScene fixture = make_maximal_contact_scene(2.0, Vec3{0.0, 0.0, -9.81}, 0.002);
    fixture.world->start();
    REQUIRE(fixture.body->initialized());
    REQUIRE(fixture.body->set_velocity_local(Screw3{Vec3::zero(), Vec3{0.75, 0.0, 0.0}}));

    const double initial_x = fixture.body->entity().transform().global_position().x;
    double minimum_height = 2.0;
    double maximum_height_after_contact = 0.0;
    double reaction_sum = 0.0;
    double minimum_reaction_in_window = std::numeric_limits<double>::infinity();
    std::size_t minimum_contacts_in_window = std::numeric_limits<std::size_t>::max();
    std::size_t minimum_cached_contacts_in_window = std::numeric_limits<std::size_t>::max();
    std::size_t minimum_warm_contacts_in_window = std::numeric_limits<std::size_t>::max();
    bool contact_seen = false;
    constexpr int step_count = 1500;
    constexpr int reaction_window = 500;
    for (int step = 0; step < step_count; ++step) {
        fixture.world->fixed_update(0.002F);
        const FEMPhysicsTelemetry telemetry = fixture.world->telemetry();
        const double height = fixture.body->entity().transform().global_position().z;
        minimum_height = std::min(minimum_height, height);
        if (telemetry.contact_count > 0) {
            contact_seen = true;
        }
        if (contact_seen) {
            maximum_height_after_contact = std::max(maximum_height_after_contact, height);
        }
        if (step >= step_count - reaction_window) {
            reaction_sum += telemetry.normal_reaction_sum;
            minimum_reaction_in_window = std::min(minimum_reaction_in_window, telemetry.normal_reaction_sum);
            minimum_contacts_in_window = std::min(minimum_contacts_in_window, telemetry.contact_count);
            minimum_cached_contacts_in_window =
                std::min(minimum_cached_contacts_in_window, telemetry.cached_contact_count);
            minimum_warm_contacts_in_window =
                std::min(minimum_warm_contacts_in_window, telemetry.warm_started_contact_count);
        }
    }

    const FEMPhysicsTelemetry telemetry = fixture.world->telemetry();
    const Vec3 final_position = fixture.body->entity().transform().global_position();
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

TEST_CASE("FEM multi-point box contact dissipates tangential slip") {
    using namespace termin;

    register_test_component_types();
    MaximalContactScene fixture = make_maximal_contact_scene(2.0, Vec3{0.0, 0.0, -9.81}, 0.002);
    fixture.world->contact_friction_coefficient = 0.5;
    fixture.world->start();
    REQUIRE(fixture.body->initialized());
    constexpr double initial_tangent_speed = 0.75;
    REQUIRE(fixture.body->set_velocity_local(Screw3{Vec3::zero(), Vec3{initial_tangent_speed, 0.0, 0.0}}));

    double maximum_tangent_impulse = 0.0;
    double accumulated_friction_work = 0.0;
    for (int step = 0; step < 1500; ++step) {
        fixture.world->fixed_update(0.002F);
        const FEMPhysicsTelemetry step_telemetry = fixture.world->telemetry();
        maximum_tangent_impulse = std::max(maximum_tangent_impulse, step_telemetry.tangent_impulse_sum);
        accumulated_friction_work += step_telemetry.friction_work;
    }

    const FEMPhysicsTelemetry telemetry = fixture.world->telemetry();
    const Vec3 position = fixture.body->entity().transform().global_position();
    CHECK(telemetry.initialized);
    CHECK(telemetry.contact_count >= 1U);
    CHECK(telemetry.active_contact_count >= 1U);
    // The realtime six-facet cone leaves a small contact-switching chatter;
    // require it to dissipate more than 99% of the initial slip without
    // demanding the exact axial cancellation of an eight-facet cone.
    CHECK(std::abs(position.z - 0.5) < 2.0e-5);
    CHECK_LT(std::abs(fixture.body->velocity_local().lin.x), initial_tangent_speed * 0.01);
    CHECK(maximum_tangent_impulse > 0.0);
    CHECK(accumulated_friction_work < 0.0);
    CHECK(position.x > 0.0);
    CHECK(position.x < initial_tangent_speed * 3.0);

    fixture.scene.destroy();
}

TEST_CASE("FEM articulation contact supplies the expected generalized support") {
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
    scene.set_fixed_timestep(0.002);
    world_entity.add_component(world);
    world->start();
    REQUIRE(articulation->initialized());

    double reaction_sum = 0.0;
    std::size_t minimum_contacts_in_window = std::numeric_limits<std::size_t>::max();
    std::size_t minimum_warm_contacts_in_window = std::numeric_limits<std::size_t>::max();
    constexpr int step_count = 1000;
    constexpr int reaction_window = 500;
    for (int step = 0; step < step_count; ++step) {
        world->fixed_update(0.002F);
        if (step >= step_count - reaction_window) {
            const FEMPhysicsTelemetry step_telemetry = world->telemetry();
            reaction_sum += step_telemetry.normal_reaction_sum;
            minimum_contacts_in_window = std::min(minimum_contacts_in_window, step_telemetry.contact_count);
            minimum_warm_contacts_in_window =
                std::min(minimum_warm_contacts_in_window, step_telemetry.warm_started_contact_count);
        }
    }

    const FEMPhysicsTelemetry telemetry = world->telemetry();
    CHECK(telemetry.initialized);
    CHECK(telemetry.contact_count > 0);
    CHECK(std::abs(joint->coordinate) < 1.0e-5);
    // The contact point is one metre from the revolute axis, so its normal
    // reaction supplies the 9.81 N*m generalized gravity effort directly.
    constexpr double support_lever = 1.0;
    CHECK(std::abs(reaction_sum / reaction_window * support_lever - 9.81) < 2.0e-3);
    CHECK(minimum_contacts_in_window > 0);
    CHECK(minimum_warm_contacts_in_window > 0);
    scene.destroy();
}

TEST_CASE("FEM routes a CollisionWorld patch to an articulation unit") {
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
    scene.set_fixed_timestep(0.01);
    world_entity.add_component(world);

    world->start();
    REQUIRE(articulation->initialized());
    world->fixed_update(0.011F);

    const FEMPhysicsTelemetry telemetry = world->telemetry();
    CHECK(telemetry.initialized);
    CHECK(telemetry.contact_count >= 1U);
    CHECK(telemetry.minimum_contact_gap >= -1.0e-8);
    CHECK(std::abs(joint->coordinate) > 1.0e-8);
    scene.destroy();
}

TEST_CASE("FEM maps direct shared articulation unit contact against static") {
    using namespace termin;

    register_test_component_types();
    TcSceneRef scene = TcSceneRef::create("shared unit static contact");

    Entity terrain = scene.create_entity("Terrain");
    terrain.transform().set_local_position({0.0, 0.0, -0.5});
    auto* terrain_collider = new ColliderComponent();
    terrain_collider->box_size = {10.0, 10.0, 1.0};
    terrain.add_component(terrain_collider);

    SharedUnitScene articulation = add_shared_unit_scene(scene, "Shared Root", {0.0, 0.0, 0.45});
    Entity collider_entity = articulation.unit_entity.create_child("Unit Collider");
    collider_entity.transform().set_local_position({1.0, 0.0, 0.0});
    auto* unit_collider = new ColliderComponent();
    unit_collider->box_size = {1.0, 1.0, 1.0};
    collider_entity.add_component(unit_collider);

    Entity world_entity = scene.create_entity("Physics World");
    auto* world = new FEMPhysicsWorldComponent();
    world->gravity = Vec3::zero();
    world_entity.add_component(world);
    world->start();
    REQUIRE(articulation.fem->initialized());

    world->fixed_update(0.002F);
    CHECK(world->telemetry().initialized);
    CHECK(world->telemetry().contact_count >= 1U);
    scene.destroy();
}

TEST_CASE("FEM keeps a shared articulation body entity as one unit anchor") {
    using namespace termin;

    register_test_component_types();
    TcSceneRef scene = TcSceneRef::create("shared body anchor contact");

    Entity terrain = scene.create_entity("Terrain");
    terrain.transform().set_local_position({0.0, 0.0, -0.5});
    auto* terrain_collider = new ColliderComponent();
    terrain_collider->box_size = {10.0, 10.0, 1.0};
    terrain.add_component(terrain_collider);

    SharedUnitScene articulation = add_shared_unit_scene(scene, "Shared Root", {0.0, 0.0, 0.45});
    Entity body_entity = articulation.unit_entity.create_child("Body Anchor");
    body_entity.transform().set_local_position({1.0, 0.0, 0.0});
    auto* body = new FEMRigidBodyComponent();
    body_entity.add_component(body);
    auto* body_collider = new ColliderComponent();
    body_collider->box_size = {1.0, 1.0, 1.0};
    body_entity.add_component(body_collider);

    Entity world_entity = scene.create_entity("Physics World");
    auto* world = new FEMPhysicsWorldComponent();
    world->gravity = Vec3::zero();
    world_entity.add_component(world);
    world->start();
    REQUIRE(articulation.fem->initialized());
    REQUIRE(body->initialized());

    world->fixed_update(0.002F);
    const FEMPhysicsTelemetry telemetry = world->telemetry();
    CHECK(telemetry.initialized);
    CHECK(telemetry.body_count == 1U);
    CHECK(telemetry.contact_count >= 1U);
    scene.destroy();
}

TEST_CASE("FEM maps contact between two direct shared articulations") {
    using namespace termin;

    register_test_component_types();
    TcSceneRef scene = TcSceneRef::create("shared articulation pair contact");
    SharedUnitScene left = add_shared_unit_scene(scene, "Left Root", {-0.45, 0.0, 0.0});
    SharedUnitScene right = add_shared_unit_scene(scene, "Right Root", {0.45, 0.0, 0.0});
    add_sphere_collider(left.unit_entity, "Left Collider", {0.0, 0.0, 0.5});
    add_sphere_collider(right.unit_entity, "Right Collider", {0.0, 0.0, 0.5});

    collision::CollisionWorld* collision_world = collision::CollisionWorld::from_scene(scene.handle());
    REQUIRE(collision_world != nullptr);
    collision_world->update_all();
    REQUIRE(!collision_world->detect_contacts().empty());

    Entity world_entity = scene.create_entity("Physics World");
    auto* world = new FEMPhysicsWorldComponent();
    world->gravity = Vec3::zero();
    world_entity.add_component(world);
    world->start();
    REQUIRE(left.fem->initialized());
    REQUIRE(right.fem->initialized());

    world->fixed_update(0.002F);
    CHECK(world->telemetry().initialized);
    CHECK(world->telemetry().contact_count >= 1U);
    scene.destroy();
}

TEST_CASE("FEM filters contact between colliders on one shared unit") {
    using namespace termin;

    register_test_component_types();
    TcSceneRef scene = TcSceneRef::create("shared same unit contact");
    SharedUnitScene articulation = add_shared_unit_scene(scene, "Shared Root", Vec3::zero());
    add_sphere_collider(articulation.unit_entity, "Left Collider", {-0.45, 0.0, 0.5});
    add_sphere_collider(articulation.unit_entity, "Right Collider", {0.45, 0.0, 0.5});

    collision::CollisionWorld* collision_world = collision::CollisionWorld::from_scene(scene.handle());
    REQUIRE(collision_world != nullptr);
    collision_world->update_all();
    REQUIRE(!collision_world->detect_contacts().empty());

    Entity world_entity = scene.create_entity("Physics World");
    auto* world = new FEMPhysicsWorldComponent();
    world->gravity = Vec3::zero();
    world_entity.add_component(world);
    world->start();
    REQUIRE(articulation.fem->initialized());

    world->fixed_update(0.002F);
    CHECK(world->telemetry().initialized);
    CHECK(world->telemetry().contact_count == 0U);
    scene.destroy();
}

TEST_CASE("FEM filters adjacent direct shared units unless enabled") {
    using namespace termin;

    register_test_component_types();
    TcSceneRef scene = TcSceneRef::create("shared adjacent unit contact");
    SharedUnitScene articulation = add_shared_unit_scene(scene, "Shared Root", Vec3::zero());
    add_sphere_collider(articulation.unit_entity, "Parent Collider", {-0.45, 0.0, 0.5});

    Entity child_entity = articulation.unit_entity.create_child("Child Unit");
    auto* child = new RotatorComponent();
    child->mass = 1.0;
    child->inertia_diagonal = {0.2, 0.2, 0.2};
    child_entity.add_component(child);
    child->set_axis(0.0, 1.0, 0.0);
    add_sphere_collider(child_entity, "Child Collider", {0.45, 0.0, 0.5});

    collision::CollisionWorld* collision_world = collision::CollisionWorld::from_scene(scene.handle());
    REQUIRE(collision_world != nullptr);
    collision_world->update_all();
    REQUIRE(!collision_world->detect_contacts().empty());

    Entity world_entity = scene.create_entity("Physics World");
    auto* world = new FEMPhysicsWorldComponent();
    world->gravity = Vec3::zero();
    world_entity.add_component(world);
    world->start();
    REQUIRE(articulation.fem->initialized());

    world->fixed_update(0.002F);
    CHECK(world->telemetry().initialized);
    CHECK(world->telemetry().contact_count == 0U);

    world->adjacent_unit_collision_enabled = true;
    world->fixed_update(0.002F);
    CHECK(world->telemetry().initialized);
    CHECK(world->telemetry().contact_count >= 1U);
    scene.destroy();
}

TEST_CASE("FEM contact policy excludes adjacent articulation units") {
    using namespace termin;

    register_test_component_types();
    DoublePendulumScene fixture = make_double_pendulum_scene();
    auto* collider_a = new ColliderComponent();
    collider_a->box_size = {3.0, 3.0, 3.0};
    fixture.body_a->entity().add_component(collider_a);
    auto* collider_b = new ColliderComponent();
    collider_b->box_size = {3.0, 3.0, 3.0};
    fixture.body_b->entity().add_component(collider_b);

    collision::CollisionWorld* collision_world = collision::CollisionWorld::from_scene(fixture.scene.handle());
    REQUIRE(collision_world != nullptr);
    collision_world->update_all();
    REQUIRE(!collision_world->detect_contacts().empty());

    fixture.world->start();
    fixture.world->fixed_update(0.002F);
    const FEMPhysicsTelemetry telemetry = fixture.world->telemetry();
    CHECK(telemetry.initialized);
    CHECK(telemetry.contact_count == 0U);
    fixture.scene.destroy();
}

TEST_CASE("FEM contact mapping follows collider disable and removal lifecycle") {
    using namespace termin;

    register_test_component_types();
    MaximalContactScene fixture = make_maximal_contact_scene();
    fixture.world->start();
    fixture.world->fixed_update(0.011F);
    REQUIRE(fixture.world->telemetry().contact_count >= 1U);

    fixture.body_collider->set_enabled(false);
    fixture.world->fixed_update(0.011F);
    CHECK(fixture.world->telemetry().initialized);
    CHECK(fixture.world->telemetry().contact_count == 0U);

    Entity body_entity = fixture.body->entity();
    body_entity.remove_component(fixture.body_collider);
    fixture.body_collider = nullptr;
    fixture.world->fixed_update(0.011F);
    CHECK(fixture.world->telemetry().initialized);
    CHECK(fixture.world->telemetry().contact_count == 0U);
    fixture.scene.destroy();
}

TEST_CASE("scene articulation compiler rejects an implicit missing body") {
    using namespace termin;

    TcSceneRef scene = TcSceneRef::create("invalid articulation");
    Entity root = scene.create_entity("Root");
    root.add_component(new FEMArticulationComponent());
    Entity empty_joint = root.create_child("Joint without body");
    empty_joint.add_component(new RotatorComponent());

    const FEMArticulationSceneCompilation compiled = compile_fem_articulation_scene(root);
    CHECK(compiled.diagnostic == FEMArticulationSceneDiagnostic::MissingBody);
    CHECK(compiled.diagnostic_entity == "Joint without body");
    scene.destroy();
}

TEST_CASE("FEM joints publish registry-controlled debug geometry") {
    using namespace termin;

    register_test_component_types();
    const tc_debug_geometry_type_id debug_type = tc_debug_geometry_type_find("physics.fem.joints");
    REQUIRE(debug_type != TC_DEBUG_GEOMETRY_TYPE_INVALID);

    TcSceneRef scene = TcSceneRef::create("FEM joint debug geometry");
    Entity body_a_entity = scene.create_entity("Body A");
    body_a_entity.transform().set_local_position({0.0, 0.0, 0.0});
    body_a_entity.add_component(new FEMRigidBodyComponent());
    Entity body_b_entity = scene.create_entity("Body B");
    body_b_entity.transform().set_local_position({2.0, 0.0, 0.0});
    body_b_entity.add_component(new FEMRigidBodyComponent());

    Entity fixed_entity = scene.create_entity("Fixed Joint");
    fixed_entity.transform().set_local_position({0.0, 0.0, 1.0});
    auto* fixed = new FEMFixedJointComponent();
    fixed->body_entity_name = "Body A";
    fixed_entity.add_component(fixed);

    Entity revolute_entity = scene.create_entity("Revolute Joint");
    auto* revolute = new FEMRevoluteJointComponent();
    revolute->body_a_entity_name = "Body A";
    revolute->body_b_entity_name = "Body B";
    revolute->joint_offset_in_body_a = {1.0, 0.0, 0.0};
    revolute_entity.add_component(revolute);

    Entity world_entity = scene.create_entity("Physics World");
    auto* world = new FEMPhysicsWorldComponent();
    world->gravity = {0.0, 0.0, 0.0};
    world_entity.add_component(world);

    REQUIRE(tc_scene_render_mount_ensure(scene.handle()));
    int attachment_storage = 0;
    const auto* attachment = reinterpret_cast<const tc_render_attachment_context*>(&attachment_storage);
    tc_scene_render_mount_notify_attach(scene.handle(), attachment);

    // STOP/editor state uses authored body transforms before the solver starts.
    prepare_render_lifecycle(scene);
    CHECK(tc_scene_debug_geometry_primitive_count(scene.handle()) == 5U);

    world->start();
    REQUIRE(world->telemetry().initialized);
    world->fixed_update(0.001F);
    prepare_render_lifecycle(scene);
    CHECK(tc_scene_debug_geometry_primitive_count(scene.handle()) == 5U);
    std::size_t line_count = 0;
    std::size_t sphere_count = 0;
    for (std::size_t index = 0; index < tc_scene_debug_geometry_primitive_count(scene.handle()); ++index) {
        const tc_debug_geometry_primitive* primitive = tc_scene_debug_geometry_primitive_at(scene.handle(), index);
        REQUIRE(primitive != nullptr);
        CHECK(primitive->type_id == debug_type);
        line_count += primitive->kind == TC_DEBUG_GEOMETRY_LINE ? 1U : 0U;
        sphere_count += primitive->kind == TC_DEBUG_GEOMETRY_WIRE_SPHERE ? 1U : 0U;
    }
    CHECK(line_count == 3U);
    CHECK(sphere_count == 2U);

    REQUIRE(tc_scene_debug_geometry_set_enabled(scene.handle(), debug_type, false));
    prepare_render_lifecycle(scene);
    CHECK(tc_scene_debug_geometry_primitive_count(scene.handle()) == 0U);

    REQUIRE(tc_scene_debug_geometry_set_enabled(scene.handle(), debug_type, true));
    revolute->set_enabled(false);
    prepare_render_lifecycle(scene);
    CHECK(tc_scene_debug_geometry_primitive_count(scene.handle()) == 2U);

    fixed_entity.remove_component(fixed);
    fixed = nullptr;
    prepare_render_lifecycle(scene);
    CHECK(tc_scene_debug_geometry_primitive_count(scene.handle()) == 0U);

    revolute->set_enabled(true);
    prepare_render_lifecycle(scene);
    CHECK(tc_scene_debug_geometry_primitive_count(scene.handle()) == 3U);

    tc_scene_render_mount_notify_detach(scene.handle(), attachment);
    scene.destroy();
}
