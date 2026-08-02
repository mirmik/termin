#include "guard_main.h"

GUARD_TEST_MAIN();

#include <cmath>

#include <inspect/tc_inspect_component_adapter.h>
#include <inspect/tc_inspect_init.h>
#include <termin/physics_fem/components.hpp>
#include <termin/tc_scene.hpp>

TEST_CASE("native FEM component doubles round-trip through inspect")
{
    using namespace termin;

    tc_inspect_kind_core_init();
    tc_inspect_component_adapter_init();
    register_builtin_scene_component_types();
    FEMRigidBodyComponent::register_type();
    FEMFixedJointComponent::register_type();
    FEMRevoluteJointComponent::register_type();
    FEMPhysicsWorldComponent::register_type();

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
