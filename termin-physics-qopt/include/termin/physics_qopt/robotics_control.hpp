#pragma once

#include <cstdint>
#include <string_view>
#include <vector>

#include <termin/physics_qopt/articulation3d_motor.hpp>
#include <termin/physics_qopt/termin_physics_qopt_api.hpp>
#include <termin/robotics/inverse_dynamics_control.hpp>

namespace termin::physics_qopt
{
    enum class RoboticsControlAdapterDiagnostic3D : std::uint8_t
    {
        None,
        InvalidMotor,
        InvalidControlResult,
        DimensionMismatch,
        DofMismatch,
        CommandFailure,
        InternalFailure,
    };

    [[nodiscard]] TERMIN_PHYSICS_QOPT_API std::string_view
    robotics_control_adapter_diagnostic_name(
        RoboticsControlAdapterDiagnostic3D diagnostic) noexcept;

    struct TERMIN_PHYSICS_QOPT_API MotorActuatorModel3DResult
    {
        std::vector<robotics::InverseDynamicsActuator3D> actuators;
        RoboticsControlAdapterDiagnostic3D diagnostic =
            RoboticsControlAdapterDiagnostic3D::None;

        [[nodiscard]] bool ok() const noexcept;
    };

    // Converts physical motor channels into the symmetric effort bounds used
    // by the solver-neutral inverse-dynamics controller. Channel order and DOF
    // identity are preserved.
    [[nodiscard]] TERMIN_PHYSICS_QOPT_API MotorActuatorModel3DResult
    inverse_dynamics_actuators_from_motor(
        const ArticulationMotorContribution& motor) noexcept;

    // Writes controller efforts into matching motor channels. The adapter
    // rejects stale or reordered results instead of silently commanding the
    // wrong reduced DOF.
    [[nodiscard]] TERMIN_PHYSICS_QOPT_API RoboticsControlAdapterDiagnostic3D
    apply_inverse_dynamics_motor_commands(
        ArticulationMotorContribution& motor,
        const robotics::InverseDynamicsControlResult3D& control) noexcept;

} // namespace termin::physics_qopt
