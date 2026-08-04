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
    std::vector<ArticulationUnit3D> units()
    {
        const SpatialInertia3 inertia{
            1.0,
            {0.1, 0.1, 0.1},
            Pose3::identity(),
        };
        return {
            {
                .parent_unit = articulation_root_frame,
                .parent_to_unit_zero = Pose3::identity(),
                .motion_twist_at_unit = {Vec3::unit_y(), Vec3::zero()},
                .inertia = inertia,
                .diagnostic_name = "first",
            },
            {
                .parent_unit = 0,
                .parent_to_unit_zero = Pose3::identity(),
                .motion_twist_at_unit = {Vec3::unit_y(), Vec3::zero()},
                .inertia = inertia,
                .diagnostic_name = "second",
            },
        };
    }
} // namespace

int main()
{
    Articulation3D model(units(), {{0.0, 0.0}, {0.0, 0.0}}, "plant");
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

    ArticulationFloatingBase3D floating_base{
        .inertia = SpatialInertia3{2.0, {1.0, 1.1, 1.2}, Pose3::identity()},
        .pose_world = Pose3::identity(),
        .velocity_local = Screw3::zero(),
        .diagnostic_name = "contact-base",
    };
    Articulation3D floating_model(floating_base, {}, {{}, {}}, "contact-plant");
    Articulation3DDynamicsContribution floating_articulation(
        floating_model, Vec3::zero(), "contact-dynamics");
    const ContactEndpoint3D contact_endpoint =
        ContactEndpoint3D::articulation_base(floating_articulation,
                                             {1.0, 0.0, 0.0});
    const ContactForceVariableBlock3DResult contact_block =
        inverse_dynamics_contact_force_block(floating_articulation,
                                             contact_endpoint,
                                             {0.0, 0.0, 3.0},
                                             0.5,
                                             20.0,
                                             "ground-contact");
    TERMIN_QOPT_CHECK(contact_block.ok());
    TERMIN_QOPT_CHECK(contact_block.block.variable_count == 3);
    TERMIN_QOPT_CHECK(contact_block.block.inequality_row_count == 6);
    TERMIN_QOPT_CHECK(
        std::abs(contact_block.normal_force_direction_world.z - 1.0) < 1e-12);
    // A +Z force at r=(1,0,0) transfers +Fz and -My to the floating base.
    TERMIN_QOPT_CHECK(
        std::abs(contact_block.block.generalized_force_basis_storage[2 * 3] -
                 1.0) < 1e-12);
    TERMIN_QOPT_CHECK(
        std::abs(contact_block.block.generalized_force_basis_storage[4 * 3] +
                 1.0) < 1e-12);
    TERMIN_QOPT_CHECK(contact_block.block.inequality_matrix_storage[0] == -1.0);
    TERMIN_QOPT_CHECK(contact_block.block.inequality_matrix_storage[3] == -0.5);
    TERMIN_QOPT_CHECK(contact_block.block.inequality_matrix_storage[5 * 3] ==
                      1.0);
    TERMIN_QOPT_CHECK(contact_block.block.inequality_target_storage[5] == 20.0);
    const ContactEndpoint3D static_endpoint =
        ContactEndpoint3D::static_world(Vec3::zero());
    TERMIN_QOPT_CHECK(
        inverse_dynamics_contact_force_block(
            floating_articulation, static_endpoint, Vec3::unit_z(), 0.5)
            .diagnostic ==
        RoboticsControlAdapterDiagnostic3D::InvalidContactEndpoint);

    // Dependency binding is a second pass: contribution insertion order does
    // not have to match ownership order.
    Articulation3D owned_model(
        units(), {{0.0, 0.0}, {0.0, 0.0}}, "owned-plant");
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
