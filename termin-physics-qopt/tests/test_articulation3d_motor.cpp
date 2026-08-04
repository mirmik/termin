#include <termin/physics_qopt/articulation3d_motor.hpp>
#include <termin/physics_qopt/robotics_control.hpp>

#include "test_check.hpp"

#include <array>
#include <cmath>
#include <memory>
#include <vector>

using namespace termin;
using namespace termin::physics_qopt;
using namespace termin::robotics;

namespace
{
    std::vector<ArticulationLink3D> links()
    {
        const SpatialInertia3 inertia{
            1.0,
            {0.1, 0.1, 0.1},
            Pose3::identity(),
        };
        return {
            {
                .parent_link = articulation_world_link,
                .parent_to_joint_zero = Pose3::identity(),
                .motion_twist_at_joint = {Vec3::unit_y(), Vec3::zero()},
                .joint_to_link = Pose3::identity(),
                .inertia = inertia,
                .diagnostic_name = "first",
            },
            {
                .parent_link = 0,
                .parent_to_joint_zero = Pose3::identity(),
                .motion_twist_at_joint = {Vec3::unit_y(), Vec3::zero()},
                .joint_to_link = Pose3::identity(),
                .inertia = inertia,
                .diagnostic_name = "second",
            },
        };
    }
} // namespace

int main()
{
    Articulation3D model(links(), {{0.0, 0.0}, {0.0, 0.0}}, "plant");
    Articulation3DDynamicsContribution articulation(
        model, Vec3::zero(), "plant-dynamics");
    ArticulationMotorContribution motor(
        articulation,
        {{.dof_index = 1, .effort_limit = 2.0, .diagnostic_name = "motor"}},
        "motor-bank");
    TERMIN_QOPT_CHECK(motor.diagnostic() == ArticulationMotorDiagnostic::None);
    TERMIN_QOPT_CHECK(motor.set_command(0, 5.0) ==
                      ArticulationMotorDiagnostic::None);

    DynamicsTopology topology;
    TERMIN_QOPT_CHECK(motor.register_topology(topology) ==
                      AssemblyDiagnostic::None);
    TERMIN_QOPT_CHECK(articulation.register_topology(topology) ==
                      AssemblyDiagnostic::None);
    TERMIN_QOPT_CHECK(topology.finalize() == AssemblyDiagnostic::None);
    TERMIN_QOPT_CHECK(articulation.bind_topology(topology) ==
                      AssemblyDiagnostic::None);
    TERMIN_QOPT_CHECK(motor.bind_topology(topology) ==
                      AssemblyDiagnostic::None);

    std::vector<double> mass(4, 0.0);
    std::vector<double> load(2, 0.0);
    DynamicsAssembly assembly(topology,
                              {
                                  DenseMatrixView::row_major(mass.data(), 2, 2),
                                  {load.data(), load.size(), 1},
                                  DenseMatrixView::row_major(nullptr, 0, 2),
                                  {nullptr, 0, 1},
                              });
    TERMIN_QOPT_CHECK(assembly.clear() == AssemblyDiagnostic::None);
    TERMIN_QOPT_CHECK(
        articulation.assemble(assembly, DynamicsAssemblyPhase::Acceleration) ==
        AssemblyDiagnostic::None);
    TERMIN_QOPT_CHECK(
        motor.assemble(assembly, DynamicsAssemblyPhase::Acceleration) ==
        AssemblyDiagnostic::None);
    TERMIN_QOPT_CHECK(std::abs(load[0]) < 1.0e-12);
    TERMIN_QOPT_CHECK(std::abs(load[1] - 2.0) < 1.0e-12);
    TERMIN_QOPT_CHECK(std::abs(motor.applied_effort(0) - 2.0) < 1.0e-12);
    TERMIN_QOPT_CHECK(motor.saturated(0));

    const MotorActuatorModel3DResult actuator_model =
        inverse_dynamics_actuators_from_motor(motor);
    TERMIN_QOPT_CHECK(actuator_model.ok());
    TERMIN_QOPT_CHECK(actuator_model.actuators.size() == 1);
    TERMIN_QOPT_CHECK(actuator_model.actuators[0].dof_index == 1);
    TERMIN_QOPT_CHECK(*actuator_model.actuators[0].minimum_effort == -2.0);
    TERMIN_QOPT_CHECK(*actuator_model.actuators[0].maximum_effort == 2.0);

    InverseDynamicsHqpController3D controller(
        model, actuator_model.actuators, Vec3::zero());
    JointVelocityTask3D acceleration_task({1}, {0.5}, 2.0);
    const std::array<const ArticulationTask3D*, 1> control_tasks{
        &acceleration_task};
    const InverseDynamicsControlResult3D control =
        controller.solve(control_tasks);
    TERMIN_QOPT_CHECK(control.ok());
    TERMIN_QOPT_CHECK(apply_inverse_dynamics_motor_commands(motor, control) ==
                      RoboticsControlAdapterDiagnostic3D::None);
    TERMIN_QOPT_CHECK(std::abs(motor.command(0) - control.actuator_effort[0]) <
                      1.0e-12);

    InverseDynamicsControlResult3D reordered = control;
    reordered.actuator_dofs[0] = 0;
    TERMIN_QOPT_CHECK(apply_inverse_dynamics_motor_commands(motor, reordered) ==
                      RoboticsControlAdapterDiagnostic3D::DofMismatch);

    // Dependency binding is a second pass: contribution insertion order does
    // not have to match ownership order.
    Articulation3D owned_model(
        links(), {{0.0, 0.0}, {0.0, 0.0}}, "owned-plant");
    DynamicsSystem system;
    auto owned_articulation =
        std::make_unique<Articulation3DDynamicsContribution>(owned_model,
                                                             Vec3::zero());
    Articulation3DDynamicsContribution* articulation_ptr =
        owned_articulation.get();
    auto owned_motor = std::make_unique<ArticulationMotorContribution>(
        *articulation_ptr,
        std::vector<ArticulationMotorChannel>{
            {.dof_index = 0, .effort_limit = 1.0}});
    TERMIN_QOPT_CHECK(system.add_contribution(std::move(owned_motor)) ==
                      DynamicsSystemDiagnostic::None);
    TERMIN_QOPT_CHECK(system.add_contribution(std::move(owned_articulation)) ==
                      DynamicsSystemDiagnostic::None);
    TERMIN_QOPT_CHECK(system.finalize() == DynamicsSystemDiagnostic::None);

    return 0;
}
