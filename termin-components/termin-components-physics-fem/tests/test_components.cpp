#include "guard_main.h"

GUARD_TEST_MAIN();

#include <cmath>
#include <numbers>

#include <components/rotator_component.hpp>
#include <inspect/tc_inspect_component_adapter.h>
#include <inspect/tc_inspect_init.h>
#include <termin/geom/general_pose3.hpp>
#include <termin/physics_fem/articulation_scene.hpp>
#include <termin/physics_fem/components.hpp>
#include <termin/tc_scene.hpp>

namespace
{
    void register_test_component_types()
    {
        static const bool registered = []()
        {
            tc_inspect_kind_core_init();
            tc_inspect_component_adapter_init();
            termin::register_builtin_scene_component_types();
            termin::KinematicUnitComponent::register_type();
            termin::RotatorComponent::register_type();
            termin::FEMRigidBodyComponent::register_type();
            termin::FEMFixedJointComponent::register_type();
            termin::FEMRevoluteJointComponent::register_type();
            termin::FEMArticulationComponent::register_type();
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
        result.joint_a->axis_x = 0.0;
        result.joint_a->axis_y = 1.0;
        result.joint_a->axis_z = 0.0;
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
        result.joint_b->axis_x = 0.0;
        result.joint_b->axis_y = 1.0;
        result.joint_b->axis_z = 0.0;
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
    authored.axis_x = 0.0;
    authored.axis_y = 1.0;
    authored.axis_z = 0.0;
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
    tc_value_free(&restored_data);

    scene.destroy();
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
    CHECK(std::abs(compiled.links[1].joint_to_link.lin.z + 1.0) < 1.0e-12);
    CHECK(std::abs(compiled.state.coordinates[0] - 0.7) < 1.0e-12);
    CHECK(std::abs(compiled.state.coordinates[1] + 0.4) < 1.0e-12);

    pendulum.scene.destroy();
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
