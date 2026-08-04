#include "guard_main.h"

GUARD_TEST_MAIN();

#include <cmath>
#include <numbers>

#include <components/articulation_component.hpp>
#include <components/kinematic_unit_component.hpp>
#include <components/rotator_component.hpp>
#include <inspect/tc_inspect_component_adapter.h>
#include <inspect/tc_inspect_init.h>
#include <termin/tc_scene.hpp>
#include <termin_scene/internal/tc_scene_extension_registry.h>

namespace
{
    void register_types()
    {
        static const bool registered = []()
        {
            tc_inspect_kind_core_init();
            tc_inspect_component_adapter_init();
            tc_scene_ext_registry_init();
            termin::register_builtin_scene_component_types();
            termin::KinematicUnitComponent::register_type();
            termin::ArticulationComponent::register_type();
            termin::RotatorComponent::register_type();
            return true;
        }();
        (void)registered;
    }
}

TEST_CASE("ArticulationComponent compiles and explicitly integrates a direct "
          "unit tree")
{
    using namespace termin;

    register_types();
    TcSceneRef scene = TcSceneRef::create("kinematic articulation");
    Entity root = scene.create_entity("Arm Root");
    root.transform().set_local_position({1.0, 2.0, 0.0});
    auto* component = new ArticulationComponent();
    root.add_component(component);

    Entity shoulder_entity = root.create_child("Shoulder");
    auto* shoulder = new RotatorComponent();
    shoulder_entity.add_component(shoulder);
    shoulder->set_coordinate_scale(1.0);
    shoulder->min_coordinate = -3.0;
    shoulder->max_coordinate = 3.0;
    shoulder->center_of_mass = {0.5, 0.0, 0.0};
    shoulder->apply();

    Entity elbow_entity = shoulder_entity.create_child("Elbow");
    auto* elbow = new RotatorComponent();
    elbow_entity.add_component(elbow);
    elbow->set_coordinate_scale(1.0);
    elbow->min_coordinate = -3.0;
    elbow->max_coordinate = 3.0;
    elbow->origin_position = {1.0, 0.0, 0.0};
    elbow->center_of_mass = {0.5, 0.0, 0.0};
    elbow->apply();

    REQUIRE(component->rebuild());
    REQUIRE(component->initialized());
    REQUIRE(component->unit_count() == 2);
    robotics::Articulation3D* articulation = component->articulation();
    REQUIRE(articulation != nullptr);

    auto initial = articulation->point_kinematics(1, {1.0, 0.0, 0.0});
    REQUIRE(initial.ok());
    CHECK(std::abs(initial.value.position_world.x - 3.0) < 1e-10);
    CHECK(std::abs(initial.value.position_world.y - 2.0) < 1e-10);

    const double velocity[] = {std::numbers::pi_v<double> / 2.0, 0.0};
    REQUIRE(component->integrate_velocity(velocity, 1.0));
    CHECK(std::abs(shoulder->coordinate -
                   std::numbers::pi_v<double> / 2.0) < 1e-10);

    auto advanced = articulation->point_kinematics(1, {1.0, 0.0, 0.0});
    REQUIRE(advanced.ok());
    CHECK(std::abs(advanced.value.position_world.x - 1.0) < 1e-10);
    CHECK(std::abs(advanced.value.position_world.y - 4.0) < 1e-10);
    const Pose3 elbow_world = elbow_entity.transform().global_pose();
    CHECK(std::abs(elbow_world.lin.x -
                   articulation->unit_poses_world()[1].lin.x) < 1e-10);
    CHECK(std::abs(elbow_world.lin.y -
                   articulation->unit_poses_world()[1].lin.y) < 1e-10);
}

TEST_CASE("ArticulationComponent rejects units hidden behind fixed scene "
          "entities")
{
    using namespace termin;

    register_types();
    TcSceneRef scene = TcSceneRef::create("indirect articulation");
    Entity root = scene.create_entity("Root");
    auto* component = new ArticulationComponent();
    root.add_component(component);
    Entity spacer = root.create_child("Forbidden Spacer");
    Entity unit_entity = spacer.create_child("Unit");
    unit_entity.add_component(new RotatorComponent());

    CHECK_FALSE(component->rebuild());
    CHECK(component->diagnostic() ==
          ArticulationComponentDiagnostic::IndirectUnit);
    CHECK(component->diagnostic_entity() == "Forbidden Spacer");
}
