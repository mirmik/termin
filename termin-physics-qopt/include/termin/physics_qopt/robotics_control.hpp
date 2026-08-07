#pragma once

#include <cstdint>
#include <optional>
#include <string_view>
#include <vector>

#include <termin/physics_qopt/articulation3d_motor.hpp>
#include <termin/physics_qopt/contact3d.hpp>
#include <termin/physics_qopt/termin_physics_qopt_api.hpp>
#include <termin/robotics/inverse_dynamics_control.hpp>

namespace termin::physics_qopt {
    enum class RoboticsControlAdapterDiagnostic3D : std::uint8_t {
        None,
        InvalidMotor,
        InvalidControlResult,
        DimensionMismatch,
        DofMismatch,
        InvalidContactEndpoint,
        InvalidContactNormal,
        InvalidFrictionCoefficient,
        InvalidNormalForceLimit,
        PointKinematicsFailure,
        CommandFailure,
        InternalFailure,
    };

    [[nodiscard]] TERMIN_PHYSICS_QOPT_API std::string_view
    robotics_control_adapter_diagnostic_name(RoboticsControlAdapterDiagnostic3D diagnostic) noexcept;

    struct TERMIN_PHYSICS_QOPT_API MotorActuatorModel3DResult {
        std::vector<robotics::InverseDynamicsActuator3D> actuators;
        RoboticsControlAdapterDiagnostic3D diagnostic = RoboticsControlAdapterDiagnostic3D::None;

        [[nodiscard]] bool ok() const noexcept;
    };

    struct TERMIN_PHYSICS_QOPT_API ContactForceVariableBlock3DResult {
        robotics::InverseDynamicsForceVariableBlock3D block;
        termin::Vec3 normal_force_direction_world = termin::Vec3::zero();
        termin::Vec3 tangent_1_world = termin::Vec3::zero();
        termin::Vec3 tangent_2_world = termin::Vec3::zero();
        RoboticsControlAdapterDiagnostic3D diagnostic = RoboticsControlAdapterDiagnostic3D::None;

        [[nodiscard]] bool ok() const noexcept;
    };

    // Converts physical motor channels into the symmetric effort bounds used
    // by the solver-neutral inverse-dynamics controller. Channel order and DOF
    // identity are preserved.
    [[nodiscard]] TERMIN_PHYSICS_QOPT_API MotorActuatorModel3DResult
    inverse_dynamics_actuators_from_motor(const ArticulationMotorContribution& motor) noexcept;

    // Writes controller efforts into matching motor channels. The adapter
    // rejects stale or reordered results instead of silently commanding the
    // wrong reduced DOF.
    [[nodiscard]] TERMIN_PHYSICS_QOPT_API RoboticsControlAdapterDiagnostic3D apply_inverse_dynamics_motor_commands(
        ArticulationMotorContribution& motor, const robotics::InverseDynamicsControlResult3D& control) noexcept;

    // Creates lambda = [normal, tangent_1, tangent_2] for a material point on
    // the controlled articulation. Positive normal acts along
    // normal_force_direction_world. Tangential values obey the conservative
    // pyramid |t1| + |t2| <= friction_coefficient * normal.
    [[nodiscard]] TERMIN_PHYSICS_QOPT_API ContactForceVariableBlock3DResult
    inverse_dynamics_contact_force_block(Articulation3DDynamicsContribution& articulation,
                                         const ContactEndpoint3D& endpoint,
                                         termin::Vec3 normal_force_direction_world,
                                         double friction_coefficient,
                                         std::optional<double> maximum_normal_force = std::nullopt,
                                         std::string_view diagnostic_name = {}) noexcept;

} // namespace termin::physics_qopt
