#include <termin/physics_qopt/robotics_control.hpp>

#include <cmath>
#include <cstdio>
#include <exception>

namespace termin::physics_qopt
{
    namespace
    {
        RoboticsControlAdapterDiagnostic3D
        failure(RoboticsControlAdapterDiagnostic3D diagnostic,
                std::string_view message) noexcept
        {
            std::fprintf(
                stderr,
                "[termin-physics-qopt] robotics control adapter failed: "
                "%.*s (%.*s)\n",
                static_cast<int>(message.size()),
                message.data(),
                static_cast<int>(
                    robotics_control_adapter_diagnostic_name(diagnostic)
                        .size()),
                robotics_control_adapter_diagnostic_name(diagnostic).data());
            return diagnostic;
        }
    } // namespace

    std::string_view robotics_control_adapter_diagnostic_name(
        RoboticsControlAdapterDiagnostic3D diagnostic) noexcept
    {
        switch (diagnostic)
        {
        case RoboticsControlAdapterDiagnostic3D::None:
            return "none";
        case RoboticsControlAdapterDiagnostic3D::InvalidMotor:
            return "invalid-motor";
        case RoboticsControlAdapterDiagnostic3D::InvalidControlResult:
            return "invalid-control-result";
        case RoboticsControlAdapterDiagnostic3D::DimensionMismatch:
            return "dimension-mismatch";
        case RoboticsControlAdapterDiagnostic3D::DofMismatch:
            return "dof-mismatch";
        case RoboticsControlAdapterDiagnostic3D::CommandFailure:
            return "command-failure";
        case RoboticsControlAdapterDiagnostic3D::InternalFailure:
            return "internal-failure";
        }
        return "unknown";
    }

    bool MotorActuatorModel3DResult::ok() const noexcept
    {
        return diagnostic == RoboticsControlAdapterDiagnostic3D::None;
    }

    MotorActuatorModel3DResult inverse_dynamics_actuators_from_motor(
        const ArticulationMotorContribution& motor) noexcept
    {
        if (motor.diagnostic() != ArticulationMotorDiagnostic::None)
        {
            failure(RoboticsControlAdapterDiagnostic3D::InvalidMotor,
                    "motor contribution is invalid");
            return {{}, RoboticsControlAdapterDiagnostic3D::InvalidMotor};
        }
        try
        {
            MotorActuatorModel3DResult result;
            result.actuators.reserve(motor.channel_count());
            for (const ArticulationMotorChannel& channel : motor.channels())
            {
                result.actuators.push_back(
                    {.dof_index = channel.dof_index,
                     .minimum_effort = -channel.effort_limit,
                     .maximum_effort = channel.effort_limit,
                     .diagnostic_name = channel.diagnostic_name});
            }
            return result;
        }
        catch (const std::exception& error)
        {
            std::fprintf(stderr,
                         "[termin-physics-qopt] motor actuator conversion "
                         "failed: %s\n",
                         error.what());
        }
        catch (...)
        {
            std::fprintf(stderr,
                         "[termin-physics-qopt] motor actuator conversion "
                         "failed with an unknown exception\n");
        }
        return {{}, RoboticsControlAdapterDiagnostic3D::InternalFailure};
    }

    RoboticsControlAdapterDiagnostic3D apply_inverse_dynamics_motor_commands(
        ArticulationMotorContribution& motor,
        const robotics::InverseDynamicsControlResult3D& control) noexcept
    {
        if (motor.diagnostic() != ArticulationMotorDiagnostic::None)
        {
            return failure(RoboticsControlAdapterDiagnostic3D::InvalidMotor,
                           "motor contribution is invalid");
        }
        if (!control.ok())
        {
            return failure(
                RoboticsControlAdapterDiagnostic3D::InvalidControlResult,
                "controller result is not optimal");
        }
        if (control.actuator_dofs.size() != motor.channel_count() ||
            control.actuator_effort.size() != motor.channel_count())
        {
            return failure(
                RoboticsControlAdapterDiagnostic3D::DimensionMismatch,
                "controller and motor channel counts differ");
        }
        for (std::size_t index = 0; index < motor.channel_count(); ++index)
        {
            if (control.actuator_dofs[index] !=
                motor.channels()[index].dof_index)
            {
                return failure(RoboticsControlAdapterDiagnostic3D::DofMismatch,
                               "controller and motor DOF order differs");
            }
            if (!std::isfinite(control.actuator_effort[index]))
            {
                return failure(
                    RoboticsControlAdapterDiagnostic3D::InvalidControlResult,
                    "controller effort is not finite");
            }
        }
        for (std::size_t index = 0; index < motor.channel_count(); ++index)
        {
            if (motor.set_command(index, control.actuator_effort[index]) !=
                ArticulationMotorDiagnostic::None)
            {
                return failure(
                    RoboticsControlAdapterDiagnostic3D::CommandFailure,
                    "motor rejected controller effort");
            }
        }
        return RoboticsControlAdapterDiagnostic3D::None;
    }

} // namespace termin::physics_qopt
