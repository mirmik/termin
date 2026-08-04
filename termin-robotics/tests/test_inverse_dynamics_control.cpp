#include <termin/robotics/inverse_dynamics_control.hpp>

#include "test_check.hpp"

#include <algorithm>
#include <array>
#include <cmath>
#include <vector>

using namespace termin;
using namespace termin::robotics;

namespace
{
    constexpr double tolerance = 1e-8;

    SpatialInertia3 link_inertia()
    {
        return {1.2, {0.35, 0.45, 0.55}, Pose3::translation(0.35, 0.0, 0.0)};
    }

    ArticulationLink3D revolute_link(std::size_t parent, std::string name)
    {
        return {
            .parent_link = parent,
            .parent_to_joint_zero = Pose3::identity(),
            .motion_twist_at_joint = {Vec3::unit_y(), Vec3::zero()},
            .joint_to_link = Pose3::identity(),
            .inertia = link_inertia(),
            .limits = {.minimum = -2.0, .maximum = 2.0},
            .diagnostic_name = std::move(name),
        };
    }

    Articulation3D fixed_model(double coordinate = 0.0, double velocity = 0.0)
    {
        return Articulation3D({revolute_link(articulation_root_frame, "joint")},
                              {{coordinate}, {velocity}},
                              "inverse-dynamics-test");
    }

    std::span<const ArticulationTask3D* const>
    task_span(const std::vector<const ArticulationTask3D*>& tasks)
    {
        return {tasks.data(), tasks.size()};
    }

    void test_joint_posture_linearization()
    {
        Articulation3D articulation = fixed_model(0.5, 0.2);
        JointPostureTask3D posture({0}, {1.0}, {0.0}, 4.0, 2.0, {0.1});
        const TaskLinearization3DResult result = posture.linearize(
            {&articulation, TaskDerivativeOrder3D::Acceleration, 0.01});
        TERMIN_ROBOTICS_CHECK(result.ok());
        TERMIN_ROBOTICS_CHECK(result.value.derivative_order ==
                              TaskDerivativeOrder3D::Acceleration);
        TERMIN_ROBOTICS_CHECK(result.value.row_count() == 1);
        TERMIN_ROBOTICS_CHECK(std::abs(result.value.matrix()(0, 0) - 1.0) <
                              tolerance);
        TERMIN_ROBOTICS_CHECK(std::abs(result.value.target()[0] - 1.7) <
                              tolerance);

        const TaskLinearization3DResult wrong_order = posture.linearize(
            {&articulation, TaskDerivativeOrder3D::Velocity, 0.01});
        TERMIN_ROBOTICS_CHECK(wrong_order.diagnostic ==
                              TaskDiagnostic3D::UnsupportedDerivativeOrder);
    }

    void test_effort_bound_and_gravity_compensation()
    {
        Articulation3D articulation = fixed_model();
        InverseDynamicsHqpController3D bounded(articulation,
                                               {{.dof_index = 0,
                                                 .minimum_effort = -0.25,
                                                 .maximum_effort = 0.25,
                                                 .diagnostic_name = "joint"}},
                                               Vec3::zero());
        JointPostureTask3D posture({0}, {1.0}, {0.0}, 20.0, 4.0);
        const std::vector<const ArticulationTask3D*> tasks{&posture};
        const InverseDynamicsControlResult3D result =
            bounded.solve(task_span(tasks), {.time_step = 0.01});
        TERMIN_ROBOTICS_CHECK(result.ok());
        TERMIN_ROBOTICS_CHECK(result.generalized_acceleration[0] > 0.0);
        TERMIN_ROBOTICS_CHECK(result.actuator_effort.size() == 1);
        TERMIN_ROBOTICS_CHECK(result.actuator_effort[0] <= 0.25 + tolerance);
        TERMIN_ROBOTICS_CHECK(result.actuator_effort[0] >= 0.25 - tolerance);
        TERMIN_ROBOTICS_CHECK(std::abs(result.required_generalized_effort[0] -
                                       result.actuator_effort[0]) < tolerance);

        Articulation3D gravity_model = fixed_model(0.4, 0.0);
        const Vec3 gravity{0.0, 0.0, -9.81};
        InverseDynamicsHqpController3D gravity_controller(gravity_model,
                                                          gravity);
        JointVelocityTask3D zero_acceleration({0}, {0.0}, 1.0);
        const std::array<const ArticulationTask3D*, 1> gravity_tasks{
            &zero_acceleration};
        const InverseDynamicsControlResult3D held =
            gravity_controller.solve(gravity_tasks);
        TERMIN_ROBOTICS_CHECK(held.ok());
        TERMIN_ROBOTICS_CHECK(std::abs(held.generalized_acceleration[0]) <
                              tolerance);
        std::vector<double> expected;
        TERMIN_ROBOTICS_CHECK(
            gravity_model.inverse_dynamics({0.0}, {0.0}, gravity, expected));
        TERMIN_ROBOTICS_CHECK(std::abs(held.actuator_effort[0] - expected[0]) <
                              tolerance);

        const InverseDynamicsControlResult3D passive_hold =
            gravity_controller.solve(
                std::span<const ArticulationTask3D* const>{});
        TERMIN_ROBOTICS_CHECK(passive_hold.ok());
        TERMIN_ROBOTICS_CHECK(
            std::abs(passive_hold.generalized_acceleration[0]) < tolerance);
        TERMIN_ROBOTICS_CHECK(std::abs(passive_hold.actuator_effort[0] -
                                       expected[0]) < tolerance);
    }

    void test_closed_loop_joint_tracking()
    {
        Articulation3D articulation = fixed_model(-0.8, 0.0);
        InverseDynamicsHqpController3D controller(
            articulation,
            {{.dof_index = 0, .minimum_effort = -2.0, .maximum_effort = 2.0}},
            Vec3::zero());
        constexpr double time_step = 0.01;
        for (std::size_t step = 0; step < 400; ++step)
        {
            JointPostureTask3D posture({0}, {0.7}, {0.0}, 24.0, 9.0);
            JointVelocityLimitConstraint3D velocity_limit(
                {0}, {-2.0}, {2.0}, {.priority = 0});
            JointLimitConstraint3D position_limit({.priority = 0});
            const std::vector<const ArticulationTask3D*> tasks{
                &velocity_limit, &position_limit, &posture};
            const InverseDynamicsControlResult3D solved =
                controller.solve(task_span(tasks), {.time_step = time_step});
            TERMIN_ROBOTICS_CHECK(solved.ok());
            TERMIN_ROBOTICS_CHECK(std::abs(solved.actuator_effort[0]) <=
                                  2.0 + tolerance);

            Articulation3DState state = articulation.state();
            state.velocities[0] +=
                time_step * solved.generalized_acceleration[0];
            state.coordinates[0] += time_step * state.velocities[0];
            TERMIN_ROBOTICS_CHECK(articulation.set_state(std::move(state)) ==
                                  Articulation3DDiagnostic::None);
        }
        TERMIN_ROBOTICS_CHECK(
            std::abs(articulation.state().coordinates[0] - 0.7) < 2e-3);
        TERMIN_ROBOTICS_CHECK(std::abs(articulation.state().velocities[0]) <
                              2e-3);
    }

    void test_floating_base_unactuated_dynamics()
    {
        ArticulationFloatingBase3D base{
            .inertia = SpatialInertia3{3.0, {1.0, 1.1, 1.2}, Pose3::identity()},
            .pose_world = Pose3::translation(0.0, 0.0, 1.0),
            .velocity_local = Screw3::zero(),
            .diagnostic_name = "base",
        };
        Articulation3D articulation(
            base,
            {revolute_link(articulation_root_frame, "joint")},
            {{0.2}, {0.0}},
            "floating-test");
        InverseDynamicsHqpController3D controller(articulation,
                                                  {0.0, 0.0, -9.81});
        TERMIN_ROBOTICS_CHECK(controller.actuators().size() == 1);
        TERMIN_ROBOTICS_CHECK(controller.actuators()[0].dof_index == 6);
        JointPostureTask3D posture({0}, {0.6}, {0.0}, 8.0, 3.0);
        const std::array<const ArticulationTask3D*, 1> tasks{&posture};
        const InverseDynamicsControlResult3D result = controller.solve(tasks);
        TERMIN_ROBOTICS_CHECK(result.ok());
        TERMIN_ROBOTICS_CHECK(result.generalized_acceleration.size() == 7);
        TERMIN_ROBOTICS_CHECK(result.required_generalized_effort.size() == 7);
        TERMIN_ROBOTICS_CHECK(result.actuator_effort.size() == 1);
        TERMIN_ROBOTICS_CHECK(result.unactuated_residual_linf < 1e-7);
        for (std::size_t dof = 0; dof < 6; ++dof)
        {
            TERMIN_ROBOTICS_CHECK(
                std::abs(result.required_generalized_effort[dof]) < 1e-7);
        }
    }

    void test_invalid_actuator_diagnostics()
    {
        Articulation3D articulation = fixed_model();
        InverseDynamicsHqpController3D controller(
            articulation, {{.dof_index = 0}, {.dof_index = 0}}, Vec3::zero());
        JointVelocityTask3D task({0}, {0.0});
        const std::array<const ArticulationTask3D*, 1> tasks{&task};
        const InverseDynamicsControlResult3D result = controller.solve(tasks);
        TERMIN_ROBOTICS_CHECK(
            result.diagnostic ==
            InverseDynamicsControlDiagnostic3D::DuplicateActuator);
    }

    void test_environmental_force_decision_variable()
    {
        Articulation3D articulation = fixed_model();
        InverseDynamicsHqpController3D controller(
            articulation,
            std::vector<InverseDynamicsActuator3D>{},
            Vec3::zero());
        JointVelocityTask3D hold({0}, {0.0}, 1.0);
        const std::array<const ArticulationTask3D*, 1> tasks{&hold};
        InverseDynamicsForceVariableBlock3D force{
            .variable_count = 1,
            .generalized_force_basis_storage = {1.0},
            .inequality_row_count = 2,
            .inequality_matrix_storage = {-1.0, 1.0},
            .inequality_target_storage = {0.0, 2.0},
            .diagnostic_name = "support",
        };
        InverseDynamicsControlOptions3D options;
        options.external_generalized_effort = {-1.0};
        options.force_variable_blocks = {force};
        const InverseDynamicsControlResult3D result =
            controller.solve(tasks, options);
        TERMIN_ROBOTICS_CHECK(result.ok());
        TERMIN_ROBOTICS_CHECK(result.force_variable_values.size() == 1);
        TERMIN_ROBOTICS_CHECK(std::abs(result.force_variable_values[0] - 1.0) <
                              tolerance);
        TERMIN_ROBOTICS_CHECK(
            std::abs(result.force_variable_generalized_effort[0] - 1.0) <
            tolerance);
        TERMIN_ROBOTICS_CHECK(std::abs(result.generalized_acceleration[0]) <
                              tolerance);
        TERMIN_ROBOTICS_CHECK(result.unactuated_residual_linf < tolerance);
    }
} // namespace

int main()
{
    test_joint_posture_linearization();
    test_effort_bound_and_gravity_compensation();
    test_closed_loop_joint_tracking();
    test_floating_base_unactuated_dynamics();
    test_invalid_actuator_diagnostics();
    test_environmental_force_decision_variable();
    return 0;
}
