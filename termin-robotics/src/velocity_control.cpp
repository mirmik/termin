#include <termin/robotics/velocity_control.hpp>

#include <termin/geom/se3.hpp>

#include <algorithm>
#include <cmath>
#include <cstdio>
#include <exception>
#include <map>
#include <utility>

namespace termin::robotics {
    namespace {
        bool finite(qopt::ConstDenseVectorView values) noexcept {
            if (values.size != 0 && values.data == nullptr) {
                return false;
            }
            for (std::size_t index = 0; index < values.size; ++index) {
                if (!std::isfinite(values[index])) {
                    return false;
                }
            }
            return true;
        }

        bool finite(const std::vector<double>& values) noexcept {
            return std::all_of(values.begin(), values.end(), [](double value) { return std::isfinite(value); });
        }

        VelocityControlResult3D failure(VelocityControlDiagnostic3D diagnostic, std::string_view message) noexcept {
            std::fprintf(stderr,
                         "[termin-robotics] velocity HQP failed: %.*s (%.*s)\n",
                         static_cast<int>(message.size()),
                         message.data(),
                         static_cast<int>(velocity_control_diagnostic_name(diagnostic).size()),
                         velocity_control_diagnostic_name(diagnostic).data());
            VelocityControlResult3D result;
            result.diagnostic = diagnostic;
            return result;
        }

        VelocityControlDiagnostic3D validate_linearization(const TaskLinearization3D& value,
                                                           std::size_t variable_count) noexcept {
            if (value.derivative_order != TaskDerivativeOrder3D::Velocity) {
                return VelocityControlDiagnostic3D::UnsupportedDerivativeOrder;
            }
            const std::size_t rows = value.target_storage.size();
            if (value.variable_count != variable_count || rows == 0 ||
                value.matrix_storage.size() != rows * variable_count ||
                (!value.weight_storage.empty() && value.weight_storage.size() != rows * rows)) {
                return VelocityControlDiagnostic3D::DimensionMismatch;
            }
            if (!finite(value.matrix_storage) || !finite(value.target_storage) || !finite(value.weight_storage)) {
                return VelocityControlDiagnostic3D::NonFiniteInput;
            }
            return VelocityControlDiagnostic3D::None;
        }

        VelocityIntegrationResult3D integration_failure(VelocityIntegrationDiagnostic3D diagnostic,
                                                        Articulation3DDiagnostic articulation_diagnostic,
                                                        std::string_view message) noexcept {
            std::fprintf(stderr,
                         "[termin-robotics] velocity integration failed: %.*s (%.*s)\n",
                         static_cast<int>(message.size()),
                         message.data(),
                         static_cast<int>(velocity_integration_diagnostic_name(diagnostic).size()),
                         velocity_integration_diagnostic_name(diagnostic).data());
            return {diagnostic, articulation_diagnostic};
        }
    } // namespace

    std::string_view velocity_control_diagnostic_name(VelocityControlDiagnostic3D diagnostic) noexcept {
        switch (diagnostic) {
        case VelocityControlDiagnostic3D::None:
            return "none";
        case VelocityControlDiagnostic3D::InvalidModel:
            return "invalid-model";
        case VelocityControlDiagnostic3D::InvalidTimeStep:
            return "invalid-time-step";
        case VelocityControlDiagnostic3D::NullTask:
            return "null-task";
        case VelocityControlDiagnostic3D::TaskLinearizationFailure:
            return "task-linearization-failure";
        case VelocityControlDiagnostic3D::UnsupportedDerivativeOrder:
            return "unsupported-derivative-order";
        case VelocityControlDiagnostic3D::DimensionMismatch:
            return "dimension-mismatch";
        case VelocityControlDiagnostic3D::NonFiniteInput:
            return "non-finite-input";
        case VelocityControlDiagnostic3D::RegistrationFailure:
            return "registration-failure";
        case VelocityControlDiagnostic3D::SolveFailure:
            return "solve-failure";
        case VelocityControlDiagnostic3D::InternalFailure:
            return "internal-failure";
        }
        return "unknown";
    }

    bool VelocityControlResult3D::ok() const noexcept {
        return diagnostic == VelocityControlDiagnostic3D::None && status == qopt::QpStatus::Optimal;
    }

    VelocityHqpController3D::VelocityHqpController3D(Articulation3D& articulation) noexcept
        : articulation_(&articulation) {}

    VelocityControlResult3D VelocityHqpController3D::solve(std::span<const ArticulationTask3D* const> tasks,
                                                           VelocityControlOptions3D options) noexcept {
        if (articulation_ == nullptr || articulation_->diagnostic() != Articulation3DDiagnostic::None) {
            return failure(VelocityControlDiagnostic3D::InvalidModel, "invalid articulation");
        }
        if (!std::isfinite(options.time_step) || options.time_step <= 0.0) {
            return failure(VelocityControlDiagnostic3D::InvalidTimeStep, "time step must be positive and finite");
        }

        try {
            const std::size_t variable_count = articulation_->dof_count();
            std::map<int, std::vector<TaskLinearization3D>> levels;
            VelocityControlResult3D result;
            result.generalized_velocity.assign(variable_count, 0.0);

            const TaskLinearizationContext3D context{
                articulation_,
                TaskDerivativeOrder3D::Velocity,
                options.time_step,
            };
            for (std::size_t index = 0; index < tasks.size(); ++index) {
                if (tasks[index] == nullptr) {
                    result = failure(VelocityControlDiagnostic3D::NullTask, "null task pointer");
                    result.failed_task = index;
                    return result;
                }
                TaskLinearization3DResult linearized = tasks[index]->linearize(context);
                if (!linearized.ok()) {
                    result =
                        failure(VelocityControlDiagnostic3D::TaskLinearizationFailure, "task could not be linearized");
                    result.task_diagnostic = linearized.diagnostic;
                    result.failed_task = index;
                    result.failed_task_name = std::move(linearized.value.diagnostic_name);
                    return result;
                }
                if (!linearized.value.active) {
                    continue;
                }
                const VelocityControlDiagnostic3D diagnostic = validate_linearization(linearized.value, variable_count);
                if (diagnostic != VelocityControlDiagnostic3D::None) {
                    result = failure(diagnostic, "invalid active task linearization");
                    result.failed_task = index;
                    result.failed_task_name = std::move(linearized.value.diagnostic_name);
                    return result;
                }
                ++result.active_task_count;
                levels[linearized.value.priority].push_back(std::move(linearized.value));
            }

            if (levels.empty()) {
                result.status = qopt::QpStatus::Optimal;
                result.hqp_result.status = qopt::QpStatus::Optimal;
                primal_warm_start_ = result.generalized_velocity;
                primal_warm_start_valid_ = true;
                return result;
            }

            qopt::HierarchicalQpSolver solver(variable_count);
            for (const auto& [priority, linearizations] : levels) {
                const qopt::HqpLevelRegistrationResult level = solver.add_level(priority);
                if (!level.ok()) {
                    result = failure(VelocityControlDiagnostic3D::RegistrationFailure, "HQP level registration failed");
                    result.hqp_diagnostic = level.diagnostic;
                    return result;
                }
                result.level_priorities.push_back(priority);
                for (const TaskLinearization3D& value : linearizations) {
                    qopt::HqpDiagnostic diagnostic = qopt::HqpDiagnostic::None;
                    switch (value.relation) {
                    case TaskRelation3D::Objective:
                        diagnostic = solver.add_task(level.handle, {value.matrix(), value.target(), value.weight()});
                        break;
                    case TaskRelation3D::Equality:
                        diagnostic = solver.add_equality(level.handle, {value.matrix(), value.target()});
                        break;
                    case TaskRelation3D::Inequality:
                        diagnostic = solver.add_inequality(level.handle, {value.matrix(), value.target()});
                        break;
                    }
                    if (diagnostic != qopt::HqpDiagnostic::None) {
                        result = failure(VelocityControlDiagnostic3D::RegistrationFailure,
                                         "HQP contribution registration failed");
                        result.hqp_diagnostic = diagnostic;
                        result.failed_task_name = value.diagnostic_name;
                        return result;
                    }
                }
            }

            result.level_task_residual_l2.assign(levels.size(), 0.0);
            qopt::ConstDenseVectorView initial_primal;
            if (options.use_primal_warm_start && primal_warm_start_valid_ &&
                primal_warm_start_.size() == variable_count) {
                initial_primal = {primal_warm_start_.data(), variable_count};
                result.primal_warm_start_used = true;
            }
            result.hqp_result =
                solver.solve({{result.generalized_velocity.data(), variable_count},
                              {result.level_task_residual_l2.data(), result.level_task_residual_l2.size()}},
                             initial_primal,
                             options.hqp);
            result.status = result.hqp_result.status;
            result.hqp_diagnostic = result.hqp_result.diagnostic;
            if (result.status != qopt::QpStatus::Optimal || result.hqp_diagnostic != qopt::HqpDiagnostic::None) {
                result.diagnostic = VelocityControlDiagnostic3D::SolveFailure;
                std::fprintf(stderr,
                             "[termin-robotics] velocity HQP solve failed (%s)\n",
                             qopt::hqp_diagnostic_name(result.hqp_diagnostic));
                return result;
            }
            primal_warm_start_ = result.generalized_velocity;
            primal_warm_start_valid_ = true;
            return result;
        } catch (const std::exception& error) {
            std::fprintf(stderr, "[termin-robotics] velocity HQP failed: %s\n", error.what());
        } catch (...) {
            std::fprintf(stderr,
                         "[termin-robotics] velocity HQP failed with an "
                         "unknown exception\n");
        }
        return failure(VelocityControlDiagnostic3D::InternalFailure, "unexpected controller exception");
    }

    void VelocityHqpController3D::reset_primal_warm_start() noexcept {
        primal_warm_start_.clear();
        primal_warm_start_valid_ = false;
    }

    const std::vector<double>& VelocityHqpController3D::primal_warm_start() const noexcept {
        return primal_warm_start_;
    }

    std::string_view velocity_integration_diagnostic_name(VelocityIntegrationDiagnostic3D diagnostic) noexcept {
        switch (diagnostic) {
        case VelocityIntegrationDiagnostic3D::None:
            return "none";
        case VelocityIntegrationDiagnostic3D::InvalidModel:
            return "invalid-model";
        case VelocityIntegrationDiagnostic3D::InvalidTimeStep:
            return "invalid-time-step";
        case VelocityIntegrationDiagnostic3D::DimensionMismatch:
            return "dimension-mismatch";
        case VelocityIntegrationDiagnostic3D::NonFiniteVelocity:
            return "non-finite-velocity";
        case VelocityIntegrationDiagnostic3D::StateUpdateFailure:
            return "state-update-failure";
        case VelocityIntegrationDiagnostic3D::InternalFailure:
            return "internal-failure";
        }
        return "unknown";
    }

    bool VelocityIntegrationResult3D::ok() const noexcept {
        return diagnostic == VelocityIntegrationDiagnostic3D::None;
    }

    VelocityIntegrationResult3D integrate_articulation_velocity(Articulation3D& articulation,
                                                                qopt::ConstDenseVectorView generalized_velocity,
                                                                double time_step) noexcept {
        if (articulation.diagnostic() != Articulation3DDiagnostic::None) {
            return integration_failure(
                VelocityIntegrationDiagnostic3D::InvalidModel, articulation.diagnostic(), "invalid articulation");
        }
        if (!std::isfinite(time_step) || time_step <= 0.0) {
            return integration_failure(VelocityIntegrationDiagnostic3D::InvalidTimeStep,
                                       Articulation3DDiagnostic::None,
                                       "time step must be positive and finite");
        }
        if (generalized_velocity.size != articulation.dof_count()) {
            return integration_failure(VelocityIntegrationDiagnostic3D::DimensionMismatch,
                                       Articulation3DDiagnostic::None,
                                       "generalized velocity size mismatch");
        }
        if (!finite(generalized_velocity)) {
            return integration_failure(VelocityIntegrationDiagnostic3D::NonFiniteVelocity,
                                       Articulation3DDiagnostic::None,
                                       "generalized velocity is not finite");
        }

        try {
            const std::size_t joint_offset = articulation.has_floating_base() ? 6 : 0;
            Articulation3DState next_state = articulation.state();
            for (std::size_t joint = 0; joint < next_state.coordinates.size(); ++joint) {
                const double velocity = generalized_velocity[joint_offset + joint];
                next_state.coordinates[joint] += time_step * velocity;
                next_state.velocities[joint] = velocity;
            }

            if (articulation.has_floating_base()) {
                const termin::Screw3 base_velocity_local{
                    {generalized_velocity[3], generalized_velocity[4], generalized_velocity[5]},
                    {generalized_velocity[0], generalized_velocity[1], generalized_velocity[2]},
                };
                const termin::Pose3 next_pose =
                    articulation.floating_base()->pose_world * termin::se3_exp(base_velocity_local * time_step);
                const Articulation3DDiagnostic base_diagnostic =
                    articulation.set_floating_base_state(next_pose, base_velocity_local);
                if (base_diagnostic != Articulation3DDiagnostic::None) {
                    return integration_failure(VelocityIntegrationDiagnostic3D::StateUpdateFailure,
                                               base_diagnostic,
                                               "floating-base update was rejected");
                }
            }

            const Articulation3DDiagnostic state_diagnostic = articulation.set_state(std::move(next_state));
            if (state_diagnostic != Articulation3DDiagnostic::None) {
                return integration_failure(VelocityIntegrationDiagnostic3D::StateUpdateFailure,
                                           state_diagnostic,
                                           "joint state update was rejected");
            }
            return {};
        } catch (const std::exception& error) {
            std::fprintf(stderr, "[termin-robotics] velocity integration failed: %s\n", error.what());
        } catch (...) {
            std::fprintf(stderr,
                         "[termin-robotics] velocity integration failed with "
                         "an unknown exception\n");
        }
        return integration_failure(VelocityIntegrationDiagnostic3D::InternalFailure,
                                   Articulation3DDiagnostic::InternalFailure,
                                   "unexpected integration exception");
    }

} // namespace termin::robotics
