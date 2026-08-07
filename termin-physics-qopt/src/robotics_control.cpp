#include <termin/physics_qopt/articulation3d_dynamics.hpp>
#include <termin/physics_qopt/robotics_control.hpp>

#include <array>
#include <cmath>
#include <cstdio>
#include <exception>

namespace termin::physics_qopt {
    namespace {
        RoboticsControlAdapterDiagnostic3D failure(RoboticsControlAdapterDiagnostic3D diagnostic,
                                                   std::string_view message) noexcept {
            std::fprintf(stderr,
                         "[termin-physics-qopt] robotics control adapter failed: "
                         "%.*s (%.*s)\n",
                         static_cast<int>(message.size()),
                         message.data(),
                         static_cast<int>(robotics_control_adapter_diagnostic_name(diagnostic).size()),
                         robotics_control_adapter_diagnostic_name(diagnostic).data());
            return diagnostic;
        }
    } // namespace

    std::string_view robotics_control_adapter_diagnostic_name(RoboticsControlAdapterDiagnostic3D diagnostic) noexcept {
        switch (diagnostic) {
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
        case RoboticsControlAdapterDiagnostic3D::InvalidContactEndpoint:
            return "invalid-contact-endpoint";
        case RoboticsControlAdapterDiagnostic3D::InvalidContactNormal:
            return "invalid-contact-normal";
        case RoboticsControlAdapterDiagnostic3D::InvalidFrictionCoefficient:
            return "invalid-friction-coefficient";
        case RoboticsControlAdapterDiagnostic3D::InvalidNormalForceLimit:
            return "invalid-normal-force-limit";
        case RoboticsControlAdapterDiagnostic3D::PointKinematicsFailure:
            return "point-kinematics-failure";
        case RoboticsControlAdapterDiagnostic3D::CommandFailure:
            return "command-failure";
        case RoboticsControlAdapterDiagnostic3D::InternalFailure:
            return "internal-failure";
        }
        return "unknown";
    }

    bool MotorActuatorModel3DResult::ok() const noexcept {
        return diagnostic == RoboticsControlAdapterDiagnostic3D::None;
    }

    bool ContactForceVariableBlock3DResult::ok() const noexcept {
        return diagnostic == RoboticsControlAdapterDiagnostic3D::None;
    }

    MotorActuatorModel3DResult
    inverse_dynamics_actuators_from_motor(const ArticulationMotorContribution& motor) noexcept {
        if (motor.diagnostic() != ArticulationMotorDiagnostic::None) {
            failure(RoboticsControlAdapterDiagnostic3D::InvalidMotor, "motor contribution is invalid");
            return {{}, RoboticsControlAdapterDiagnostic3D::InvalidMotor};
        }
        try {
            MotorActuatorModel3DResult result;
            result.actuators.reserve(motor.channel_count());
            for (const ArticulationMotorChannel& channel : motor.channels()) {
                result.actuators.push_back({.dof_index = channel.dof_index,
                                            .minimum_effort = -channel.effort_limit,
                                            .maximum_effort = channel.effort_limit,
                                            .diagnostic_name = channel.diagnostic_name});
            }
            return result;
        } catch (const std::exception& error) {
            std::fprintf(stderr,
                         "[termin-physics-qopt] motor actuator conversion "
                         "failed: %s\n",
                         error.what());
        } catch (...) {
            std::fprintf(stderr,
                         "[termin-physics-qopt] motor actuator conversion "
                         "failed with an unknown exception\n");
        }
        return {{}, RoboticsControlAdapterDiagnostic3D::InternalFailure};
    }

    RoboticsControlAdapterDiagnostic3D
    apply_inverse_dynamics_motor_commands(ArticulationMotorContribution& motor,
                                          const robotics::InverseDynamicsControlResult3D& control) noexcept {
        if (motor.diagnostic() != ArticulationMotorDiagnostic::None) {
            return failure(RoboticsControlAdapterDiagnostic3D::InvalidMotor, "motor contribution is invalid");
        }
        if (!control.ok()) {
            return failure(RoboticsControlAdapterDiagnostic3D::InvalidControlResult,
                           "controller result is not optimal");
        }
        if (control.actuator_dofs.size() != motor.channel_count() ||
            control.actuator_effort.size() != motor.channel_count()) {
            return failure(RoboticsControlAdapterDiagnostic3D::DimensionMismatch,
                           "controller and motor channel counts differ");
        }
        for (std::size_t index = 0; index < motor.channel_count(); ++index) {
            if (control.actuator_dofs[index] != motor.channels()[index].dof_index) {
                return failure(RoboticsControlAdapterDiagnostic3D::DofMismatch,
                               "controller and motor DOF order differs");
            }
            if (!std::isfinite(control.actuator_effort[index])) {
                return failure(RoboticsControlAdapterDiagnostic3D::InvalidControlResult,
                               "controller effort is not finite");
            }
        }
        for (std::size_t index = 0; index < motor.channel_count(); ++index) {
            if (motor.set_command(index, control.actuator_effort[index]) != ArticulationMotorDiagnostic::None) {
                return failure(RoboticsControlAdapterDiagnostic3D::CommandFailure, "motor rejected controller effort");
            }
        }
        return RoboticsControlAdapterDiagnostic3D::None;
    }

    ContactForceVariableBlock3DResult
    inverse_dynamics_contact_force_block(Articulation3DDynamicsContribution& articulation,
                                         const ContactEndpoint3D& endpoint,
                                         termin::Vec3 normal_force_direction_world,
                                         double friction_coefficient,
                                         std::optional<double> maximum_normal_force,
                                         std::string_view diagnostic_name) noexcept {
        auto rejected = [](RoboticsControlAdapterDiagnostic3D diagnostic, std::string_view message) {
            failure(diagnostic, message);
            ContactForceVariableBlock3DResult result;
            result.diagnostic = diagnostic;
            return result;
        };
        if (!endpoint.valid() || !endpoint.belongs_to(articulation)) {
            return rejected(RoboticsControlAdapterDiagnostic3D::InvalidContactEndpoint,
                            "contact endpoint does not belong to controlled articulation");
        }
        const double normal_length = normal_force_direction_world.norm();
        if (!normal_force_direction_world.is_finite() || !std::isfinite(normal_length) || normal_length <= 1.0e-12) {
            return rejected(RoboticsControlAdapterDiagnostic3D::InvalidContactNormal,
                            "contact force normal has no finite direction");
        }
        if (!std::isfinite(friction_coefficient) || friction_coefficient < 0.0) {
            return rejected(RoboticsControlAdapterDiagnostic3D::InvalidFrictionCoefficient,
                            "friction coefficient must be finite and non-negative");
        }
        if (maximum_normal_force.has_value() &&
            (!std::isfinite(*maximum_normal_force) || *maximum_normal_force < 0.0)) {
            return rejected(RoboticsControlAdapterDiagnostic3D::InvalidNormalForceLimit,
                            "maximum normal force must be finite and non-negative");
        }
        const PointKinematics3DResult point = endpoint.point_kinematics();
        if (!point.ok() || point.value.dof_count() != articulation.dof_count()) {
            return rejected(RoboticsControlAdapterDiagnostic3D::PointKinematicsFailure,
                            "contact point kinematics are unavailable or stale");
        }

        try {
            ContactForceVariableBlock3DResult result;
            result.normal_force_direction_world = normal_force_direction_world / normal_length;
            const termin::Vec3 normal = result.normal_force_direction_world;
            const double ax = std::abs(normal.x);
            const double ay = std::abs(normal.y);
            const double az = std::abs(normal.z);
            termin::Vec3 reference = termin::Vec3::unit_x();
            if (ay <= ax && ay <= az) {
                reference = termin::Vec3::unit_y();
            } else if (az <= ax && az <= ay) {
                reference = termin::Vec3::unit_z();
            }
            result.tangent_1_world = normal.cross(reference).normalized();
            result.tangent_2_world = normal.cross(result.tangent_1_world);

            robotics::InverseDynamicsForceVariableBlock3D& block = result.block;
            block.variable_count = 3;
            block.diagnostic_name = diagnostic_name;
            block.generalized_force_basis_storage.assign(articulation.dof_count() * 3, 0.0);
            const qopt::ConstDenseMatrixView jacobian = point.value.linear_jacobian_world();
            const std::array<termin::Vec3, 3> directions{
                result.normal_force_direction_world,
                result.tangent_1_world,
                result.tangent_2_world,
            };
            for (std::size_t dof = 0; dof < articulation.dof_count(); ++dof) {
                for (std::size_t variable = 0; variable < 3; ++variable) {
                    block.generalized_force_basis_storage[dof * 3 + variable] =
                        directions[variable].x * jacobian(0, dof) + directions[variable].y * jacobian(1, dof) +
                        directions[variable].z * jacobian(2, dof);
                }
            }

            block.inequality_row_count = maximum_normal_force.has_value() ? 6 : 5;
            block.inequality_matrix_storage.assign(block.inequality_row_count * 3, 0.0);
            block.inequality_target_storage.assign(block.inequality_row_count, 0.0);
            block.inequality_matrix_storage[0] = -1.0;
            constexpr std::array<std::array<double, 2>, 4> signs{{
                {{1.0, 1.0}},
                {{1.0, -1.0}},
                {{-1.0, 1.0}},
                {{-1.0, -1.0}},
            }};
            for (std::size_t row = 0; row < signs.size(); ++row) {
                block.inequality_matrix_storage[(row + 1) * 3] = -friction_coefficient;
                block.inequality_matrix_storage[(row + 1) * 3 + 1] = signs[row][0];
                block.inequality_matrix_storage[(row + 1) * 3 + 2] = signs[row][1];
            }
            if (maximum_normal_force.has_value()) {
                block.inequality_matrix_storage[5 * 3] = 1.0;
                block.inequality_target_storage[5] = *maximum_normal_force;
            }
            return result;
        } catch (const std::exception& error) {
            std::fprintf(stderr, "[termin-physics-qopt] contact force adapter failed: %s\n", error.what());
        } catch (...) {
            std::fprintf(stderr,
                         "[termin-physics-qopt] contact force adapter failed "
                         "with an unknown exception\n");
        }
        return {{},
                termin::Vec3::zero(),
                termin::Vec3::zero(),
                termin::Vec3::zero(),
                RoboticsControlAdapterDiagnostic3D::InternalFailure};
    }

} // namespace termin::physics_qopt
