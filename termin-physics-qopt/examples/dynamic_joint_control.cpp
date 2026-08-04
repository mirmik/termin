#include <termin/physics_qopt/physics_qopt.hpp>
#include <termin/robotics/robotics.hpp>

#include <array>
#include <cmath>
#include <cstdio>
#include <memory>

using namespace termin;
using namespace termin::physics_qopt;
using namespace termin::robotics;

int main()
{
    ArticulationLink3D link{
        .parent_link = articulation_root_frame,
        .parent_to_joint_zero = Pose3::identity(),
        .motion_twist_at_joint = {Vec3::unit_y(), Vec3::zero()},
        .joint_to_link = Pose3::identity(),
        .inertia = SpatialInertia3{1.0,
                                   {0.2, 0.25, 0.3},
                                   Pose3::translation(0.4, 0.0, 0.0)},
        .limits = {.minimum = -1.5, .maximum = 1.5},
        .diagnostic_name = "shoulder",
    };
    Articulation3D arm({link}, {{-0.7}, {0.0}}, "dynamic-example");
    DynamicsSystem system;
    auto dynamics = std::make_unique<Articulation3DDynamicsContribution>(
        arm, Vec3{0.0, 0.0, -9.81}, "arm-dynamics");
    Articulation3DDynamicsContribution* dynamics_ptr = dynamics.get();
    auto motor = std::make_unique<ArticulationMotorContribution>(
        *dynamics_ptr,
        std::vector<ArticulationMotorChannel>{
            {.dof_index = 0,
             .effort_limit = 12.0,
             .diagnostic_name = "shoulder-motor"}},
        "arm-motor");
    ArticulationMotorContribution* motor_ptr = motor.get();
    const MotorActuatorModel3DResult actuator_model =
        inverse_dynamics_actuators_from_motor(*motor_ptr);
    if (!actuator_model.ok() ||
        system.add_contribution(std::move(motor)) !=
            DynamicsSystemDiagnostic::None ||
        system.add_contribution(std::move(dynamics)) !=
            DynamicsSystemDiagnostic::None ||
        system.finalize() != DynamicsSystemDiagnostic::None)
    {
        return 1;
    }

    InverseDynamicsHqpController3D controller(
        arm, actuator_model.actuators, {0.0, 0.0, -9.81});
    constexpr double time_step = 0.002;
    for (std::size_t step = 0; step < 1200; ++step)
    {
        JointPostureTask3D posture({0}, {0.6}, {0.0}, 28.0, 10.0);
        JointLimitConstraint3D position_limit({.priority = 0});
        JointVelocityLimitConstraint3D velocity_limit(
            {0}, {-2.5}, {2.5}, {.priority = 0});
        const std::array<const ArticulationTask3D*, 3> tasks{
            &position_limit, &velocity_limit, &posture};
        const InverseDynamicsControlResult3D control =
            controller.solve(tasks, {.time_step = time_step});
        if (!control.ok() ||
            apply_inverse_dynamics_motor_commands(*motor_ptr, control) !=
                RoboticsControlAdapterDiagnostic3D::None)
        {
            return 2;
        }
        if (!system.step({.time_step = time_step}).ok())
        {
            return 3;
        }
    }
    const double position_error = std::abs(arm.state().coordinates[0] - 0.6);
    const double speed = std::abs(arm.state().velocities[0]);
    std::printf("dynamic position error=%g speed=%g\n", position_error, speed);
    return position_error < 2.0e-3 && speed < 2.0e-3 ? 0 : 4;
}
