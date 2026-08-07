#include <termin/robotics/inverse_dynamics_control.hpp>

#include <algorithm>
#include <cmath>
#include <cstdio>
#include <exception>
#include <map>
#include <unordered_set>
#include <utility>

namespace termin::robotics {
    namespace {
        bool finite(const std::vector<double>& values) noexcept {
            return std::all_of(values.begin(), values.end(), [](double value) { return std::isfinite(value); });
        }

        InverseDynamicsControlResult3D failure(InverseDynamicsControlDiagnostic3D diagnostic,
                                               std::string_view message) noexcept {
            std::fprintf(stderr,
                         "[termin-robotics] inverse-dynamics HQP failed: %.*s "
                         "(%.*s)\n",
                         static_cast<int>(message.size()),
                         message.data(),
                         static_cast<int>(inverse_dynamics_control_diagnostic_name(diagnostic).size()),
                         inverse_dynamics_control_diagnostic_name(diagnostic).data());
            InverseDynamicsControlResult3D result;
            result.diagnostic = diagnostic;
            return result;
        }

        InverseDynamicsControlDiagnostic3D validate_linearization(const TaskLinearization3D& value,
                                                                  std::size_t variable_count) noexcept {
            if (value.derivative_order != TaskDerivativeOrder3D::Acceleration) {
                return InverseDynamicsControlDiagnostic3D::UnsupportedDerivativeOrder;
            }
            const std::size_t rows = value.target_storage.size();
            if (value.variable_count != variable_count || rows == 0 ||
                value.matrix_storage.size() != rows * variable_count ||
                (!value.weight_storage.empty() && value.weight_storage.size() != rows * rows)) {
                return InverseDynamicsControlDiagnostic3D::DimensionMismatch;
            }
            if (!finite(value.matrix_storage) || !finite(value.target_storage) || !finite(value.weight_storage)) {
                return InverseDynamicsControlDiagnostic3D::NonFiniteInput;
            }
            return InverseDynamicsControlDiagnostic3D::None;
        }

        std::vector<InverseDynamicsActuator3D> default_actuators(const Articulation3D& articulation) {
            const std::size_t offset = articulation.has_floating_base() ? 6 : 0;
            std::vector<InverseDynamicsActuator3D> result;
            result.reserve(articulation.unit_count());
            for (std::size_t joint = 0; joint < articulation.unit_count(); ++joint) {
                result.push_back({.dof_index = offset + joint});
            }
            return result;
        }

        InverseDynamicsControlDiagnostic3D validate_actuators(const std::vector<InverseDynamicsActuator3D>& actuators,
                                                              std::size_t dof_count) noexcept {
            std::unordered_set<std::size_t> indices;
            for (const InverseDynamicsActuator3D& actuator : actuators) {
                if (actuator.dof_index >= dof_count) {
                    return InverseDynamicsControlDiagnostic3D::InvalidActuator;
                }
                if (!indices.insert(actuator.dof_index).second) {
                    return InverseDynamicsControlDiagnostic3D::DuplicateActuator;
                }
                if ((actuator.minimum_effort.has_value() && !std::isfinite(*actuator.minimum_effort)) ||
                    (actuator.maximum_effort.has_value() && !std::isfinite(*actuator.maximum_effort)) ||
                    (actuator.minimum_effort.has_value() && actuator.maximum_effort.has_value() &&
                     *actuator.minimum_effort > *actuator.maximum_effort)) {
                    return InverseDynamicsControlDiagnostic3D::InvalidActuator;
                }
            }
            return InverseDynamicsControlDiagnostic3D::None;
        }

        InverseDynamicsControlDiagnostic3D
        validate_force_blocks(const std::vector<InverseDynamicsForceVariableBlock3D>& blocks,
                              std::size_t dof_count) noexcept {
            for (const InverseDynamicsForceVariableBlock3D& block : blocks) {
                if (block.variable_count == 0 ||
                    block.generalized_force_basis_storage.size() != dof_count * block.variable_count ||
                    block.inequality_matrix_storage.size() != block.inequality_row_count * block.variable_count ||
                    block.inequality_target_storage.size() != block.inequality_row_count ||
                    !finite(block.generalized_force_basis_storage) || !finite(block.inequality_matrix_storage) ||
                    !finite(block.inequality_target_storage)) {
                    return InverseDynamicsControlDiagnostic3D::InvalidForceVariableBlock;
                }
            }
            return InverseDynamicsControlDiagnostic3D::None;
        }

        std::vector<double> lift_task_matrix(const TaskLinearization3D& task, std::size_t decision_count) {
            const std::size_t rows = task.target_storage.size();
            std::vector<double> lifted(rows * decision_count, 0.0);
            for (std::size_t row = 0; row < rows; ++row) {
                std::copy_n(task.matrix_storage.data() + row * task.variable_count,
                            task.variable_count,
                            lifted.data() + row * decision_count);
            }
            return lifted;
        }

        std::vector<double> generalized_velocity(const Articulation3D& articulation) {
            std::vector<double> result(articulation.dof_count(), 0.0);
            std::size_t offset = 0;
            if (articulation.has_floating_base()) {
                const termin::Screw3& velocity = articulation.floating_base()->velocity_local;
                result[0] = velocity.lin.x;
                result[1] = velocity.lin.y;
                result[2] = velocity.lin.z;
                result[3] = velocity.ang.x;
                result[4] = velocity.ang.y;
                result[5] = velocity.ang.z;
                offset = 6;
            }
            std::copy(articulation.state().velocities.begin(),
                      articulation.state().velocities.end(),
                      result.begin() + static_cast<std::ptrdiff_t>(offset));
            return result;
        }

        double matrix_row_dot(const std::vector<double>& matrix,
                              std::size_t count,
                              std::size_t row,
                              const std::vector<double>& vector) noexcept {
            double result = 0.0;
            for (std::size_t column = 0; column < count; ++column) {
                result += matrix[row * count + column] * vector[column];
            }
            return result;
        }
    } // namespace

    std::string_view inverse_dynamics_control_diagnostic_name(InverseDynamicsControlDiagnostic3D diagnostic) noexcept {
        switch (diagnostic) {
        case InverseDynamicsControlDiagnostic3D::None:
            return "none";
        case InverseDynamicsControlDiagnostic3D::InvalidModel:
            return "invalid-model";
        case InverseDynamicsControlDiagnostic3D::InvalidTimeStep:
            return "invalid-time-step";
        case InverseDynamicsControlDiagnostic3D::InvalidGravity:
            return "invalid-gravity";
        case InverseDynamicsControlDiagnostic3D::InvalidActuator:
            return "invalid-actuator";
        case InverseDynamicsControlDiagnostic3D::DuplicateActuator:
            return "duplicate-actuator";
        case InverseDynamicsControlDiagnostic3D::NullTask:
            return "null-task";
        case InverseDynamicsControlDiagnostic3D::TaskLinearizationFailure:
            return "task-linearization-failure";
        case InverseDynamicsControlDiagnostic3D::UnsupportedDerivativeOrder:
            return "unsupported-derivative-order";
        case InverseDynamicsControlDiagnostic3D::DimensionMismatch:
            return "dimension-mismatch";
        case InverseDynamicsControlDiagnostic3D::NonFiniteInput:
            return "non-finite-input";
        case InverseDynamicsControlDiagnostic3D::InvalidForceVariableBlock:
            return "invalid-force-variable-block";
        case InverseDynamicsControlDiagnostic3D::DynamicsFailure:
            return "dynamics-failure";
        case InverseDynamicsControlDiagnostic3D::RegistrationFailure:
            return "registration-failure";
        case InverseDynamicsControlDiagnostic3D::SolveFailure:
            return "solve-failure";
        case InverseDynamicsControlDiagnostic3D::InternalFailure:
            return "internal-failure";
        }
        return "unknown";
    }

    bool InverseDynamicsControlResult3D::ok() const noexcept {
        return diagnostic == InverseDynamicsControlDiagnostic3D::None && status == qopt::QpStatus::Optimal;
    }

    InverseDynamicsHqpController3D::InverseDynamicsHqpController3D(Articulation3D& articulation,
                                                                   termin::Vec3 gravity_world)
        : articulation_(&articulation),
          actuators_(default_actuators(articulation)),
          gravity_world_(gravity_world) {}

    InverseDynamicsHqpController3D::InverseDynamicsHqpController3D(Articulation3D& articulation,
                                                                   std::vector<InverseDynamicsActuator3D> actuators,
                                                                   termin::Vec3 gravity_world)
        : articulation_(&articulation),
          actuators_(std::move(actuators)),
          gravity_world_(gravity_world) {}

    const std::vector<InverseDynamicsActuator3D>& InverseDynamicsHqpController3D::actuators() const noexcept {
        return actuators_;
    }

    termin::Vec3 InverseDynamicsHqpController3D::gravity_world() const noexcept {
        return gravity_world_;
    }

    InverseDynamicsControlDiagnostic3D
    InverseDynamicsHqpController3D::set_gravity_world(termin::Vec3 gravity_world) noexcept {
        if (!gravity_world.is_finite()) {
            std::fprintf(stderr,
                         "[termin-robotics] rejected non-finite inverse-"
                         "dynamics gravity\n");
            return InverseDynamicsControlDiagnostic3D::InvalidGravity;
        }
        gravity_world_ = gravity_world;
        reset_primal_warm_start();
        return InverseDynamicsControlDiagnostic3D::None;
    }

    InverseDynamicsControlResult3D
    InverseDynamicsHqpController3D::solve(std::span<const ArticulationTask3D* const> tasks,
                                          InverseDynamicsControlOptions3D options) noexcept {
        if (articulation_ == nullptr || articulation_->diagnostic() != Articulation3DDiagnostic::None) {
            return failure(InverseDynamicsControlDiagnostic3D::InvalidModel, "invalid articulation");
        }
        if (!std::isfinite(options.time_step) || options.time_step <= 0.0) {
            return failure(InverseDynamicsControlDiagnostic3D::InvalidTimeStep,
                           "time step must be positive and finite");
        }
        if (!gravity_world_.is_finite()) {
            return failure(InverseDynamicsControlDiagnostic3D::InvalidGravity, "gravity must be finite");
        }

        try {
            const std::size_t count = articulation_->dof_count();
            const InverseDynamicsControlDiagnostic3D actuator_diagnostic = validate_actuators(actuators_, count);
            if (actuator_diagnostic != InverseDynamicsControlDiagnostic3D::None) {
                return failure(actuator_diagnostic, "invalid actuator declaration");
            }
            const InverseDynamicsControlDiagnostic3D force_diagnostic =
                validate_force_blocks(options.force_variable_blocks, count);
            if (force_diagnostic != InverseDynamicsControlDiagnostic3D::None) {
                return failure(force_diagnostic, "invalid environmental force variable block");
            }
            std::size_t force_variable_count = 0;
            std::size_t force_inequality_count = 0;
            for (const InverseDynamicsForceVariableBlock3D& block : options.force_variable_blocks) {
                force_variable_count += block.variable_count;
                force_inequality_count += block.inequality_row_count;
            }
            const std::size_t decision_count = count + force_variable_count;
            if (!options.external_generalized_effort.empty() && options.external_generalized_effort.size() != count) {
                return failure(InverseDynamicsControlDiagnostic3D::DimensionMismatch, "external effort size mismatch");
            }
            if (!finite(options.external_generalized_effort)) {
                return failure(InverseDynamicsControlDiagnostic3D::NonFiniteInput, "external effort is not finite");
            }
            const std::vector<double> external = options.external_generalized_effort.empty()
                                                     ? std::vector<double>(count, 0.0)
                                                     : options.external_generalized_effort;

            std::vector<double> mass;
            if (!articulation_->mass_matrix(mass)) {
                return failure(InverseDynamicsControlDiagnostic3D::DynamicsFailure, "mass matrix construction failed");
            }
            const std::vector<double> velocity = generalized_velocity(*articulation_);
            const std::vector<double> zero(count, 0.0);
            std::vector<double> bias;
            if (!articulation_->inverse_dynamics(velocity, zero, gravity_world_, bias)) {
                return failure(InverseDynamicsControlDiagnostic3D::DynamicsFailure, "bias effort construction failed");
            }

            std::map<int, std::vector<TaskLinearization3D>> levels;
            InverseDynamicsControlResult3D result;
            result.generalized_acceleration.assign(count, 0.0);
            result.required_generalized_effort.assign(count, 0.0);
            result.force_variable_values.assign(force_variable_count, 0.0);
            result.force_variable_generalized_effort.assign(count, 0.0);
            result.force_variable_block_offsets.reserve(options.force_variable_blocks.size() + 1);
            result.force_variable_block_offsets.push_back(0);
            for (const InverseDynamicsForceVariableBlock3D& block : options.force_variable_blocks) {
                result.force_variable_block_offsets.push_back(result.force_variable_block_offsets.back() +
                                                              block.variable_count);
            }
            result.actuator_dofs.reserve(actuators_.size());
            result.actuator_effort.assign(actuators_.size(), 0.0);
            for (const InverseDynamicsActuator3D& actuator : actuators_) {
                result.actuator_dofs.push_back(actuator.dof_index);
            }
            const TaskLinearizationContext3D context{
                articulation_,
                TaskDerivativeOrder3D::Acceleration,
                options.time_step,
            };
            for (std::size_t index = 0; index < tasks.size(); ++index) {
                if (tasks[index] == nullptr) {
                    result = failure(InverseDynamicsControlDiagnostic3D::NullTask, "null task pointer");
                    result.failed_task = index;
                    return result;
                }
                TaskLinearization3DResult linearized = tasks[index]->linearize(context);
                if (!linearized.ok()) {
                    result = failure(InverseDynamicsControlDiagnostic3D::TaskLinearizationFailure,
                                     "task could not be linearized");
                    result.task_diagnostic = linearized.diagnostic;
                    result.failed_task = index;
                    result.failed_task_name = std::move(linearized.value.diagnostic_name);
                    return result;
                }
                if (!linearized.value.active) {
                    continue;
                }
                const InverseDynamicsControlDiagnostic3D diagnostic = validate_linearization(linearized.value, count);
                if (diagnostic != InverseDynamicsControlDiagnostic3D::None) {
                    result = failure(diagnostic, "invalid active task linearization");
                    result.failed_task = index;
                    result.failed_task_name = std::move(linearized.value.diagnostic_name);
                    return result;
                }
                ++result.active_task_count;
                levels[linearized.value.priority].push_back(std::move(linearized.value));
            }
            if (levels.empty()) {
                levels[0] = {};
            }

            std::vector<double> force_basis(count * force_variable_count, 0.0);
            std::vector<double> force_inequality_matrix(force_inequality_count * decision_count, 0.0);
            std::vector<double> force_inequality_target;
            force_inequality_target.reserve(force_inequality_count);
            std::size_t force_offset = 0;
            std::size_t force_row_offset = 0;
            for (const InverseDynamicsForceVariableBlock3D& block : options.force_variable_blocks) {
                for (std::size_t row = 0; row < count; ++row) {
                    std::copy_n(block.generalized_force_basis_storage.data() + row * block.variable_count,
                                block.variable_count,
                                force_basis.data() + row * force_variable_count + force_offset);
                }
                for (std::size_t row = 0; row < block.inequality_row_count; ++row) {
                    std::copy_n(block.inequality_matrix_storage.data() + row * block.variable_count,
                                block.variable_count,
                                force_inequality_matrix.data() + (force_row_offset + row) * decision_count + count +
                                    force_offset);
                    force_inequality_target.push_back(block.inequality_target_storage[row]);
                }
                force_offset += block.variable_count;
                force_row_offset += block.inequality_row_count;
            }

            std::vector<bool> actuated(count, false);
            for (const InverseDynamicsActuator3D& actuator : actuators_) {
                actuated[actuator.dof_index] = true;
            }
            std::size_t unactuated_rows = 0;
            for (bool value : actuated) {
                unactuated_rows += value ? 0 : 1;
            }
            std::vector<double> unactuated_matrix(unactuated_rows * decision_count, 0.0);
            std::vector<double> unactuated_target(unactuated_rows, 0.0);
            std::size_t unactuated_row = 0;
            for (std::size_t dof = 0; dof < count; ++dof) {
                if (actuated[dof]) {
                    continue;
                }
                std::copy_n(
                    mass.data() + dof * count, count, unactuated_matrix.data() + unactuated_row * decision_count);
                for (std::size_t variable = 0; variable < force_variable_count; ++variable) {
                    unactuated_matrix[unactuated_row * decision_count + count + variable] =
                        -force_basis[dof * force_variable_count + variable];
                }
                unactuated_target[unactuated_row] = external[dof] - bias[dof];
                ++unactuated_row;
            }

            std::size_t effort_rows = 0;
            for (const InverseDynamicsActuator3D& actuator : actuators_) {
                effort_rows += actuator.maximum_effort.has_value() ? 1 : 0;
                effort_rows += actuator.minimum_effort.has_value() ? 1 : 0;
            }
            std::vector<double> effort_matrix(effort_rows * decision_count, 0.0);
            std::vector<double> effort_target(effort_rows, 0.0);
            std::size_t effort_row = 0;
            for (const InverseDynamicsActuator3D& actuator : actuators_) {
                const std::size_t dof = actuator.dof_index;
                if (actuator.maximum_effort.has_value()) {
                    std::copy_n(mass.data() + dof * count, count, effort_matrix.data() + effort_row * decision_count);
                    for (std::size_t variable = 0; variable < force_variable_count; ++variable) {
                        effort_matrix[effort_row * decision_count + count + variable] =
                            -force_basis[dof * force_variable_count + variable];
                    }
                    effort_target[effort_row] = *actuator.maximum_effort - bias[dof] + external[dof];
                    ++effort_row;
                }
                if (actuator.minimum_effort.has_value()) {
                    for (std::size_t column = 0; column < count; ++column) {
                        effort_matrix[effort_row * decision_count + column] = -mass[dof * count + column];
                    }
                    for (std::size_t variable = 0; variable < force_variable_count; ++variable) {
                        effort_matrix[effort_row * decision_count + count + variable] =
                            force_basis[dof * force_variable_count + variable];
                    }
                    effort_target[effort_row] = -*actuator.minimum_effort + bias[dof] - external[dof];
                    ++effort_row;
                }
            }

            qopt::HierarchicalQpSolver solver(decision_count);
            bool first_level = true;
            for (const auto& [priority, linearizations] : levels) {
                const qopt::HqpLevelRegistrationResult level = solver.add_level(priority);
                if (!level.ok()) {
                    result = failure(InverseDynamicsControlDiagnostic3D::RegistrationFailure,
                                     "HQP level registration failed");
                    result.hqp_diagnostic = level.diagnostic;
                    return result;
                }
                result.level_priorities.push_back(priority);
                if (first_level) {
                    first_level = false;
                    if (unactuated_rows != 0) {
                        const qopt::HqpDiagnostic diagnostic =
                            solver.add_equality(level.handle,
                                                {qopt::ConstDenseMatrixView::row_major(
                                                     unactuated_matrix.data(), unactuated_rows, decision_count),
                                                 {unactuated_target.data(), unactuated_target.size()}});
                        if (diagnostic != qopt::HqpDiagnostic::None) {
                            result = failure(InverseDynamicsControlDiagnostic3D::RegistrationFailure,
                                             "unactuated dynamics registration failed");
                            result.hqp_diagnostic = diagnostic;
                            return result;
                        }
                    }
                    if (effort_rows != 0) {
                        const qopt::HqpDiagnostic diagnostic = solver.add_inequality(
                            level.handle,
                            {qopt::ConstDenseMatrixView::row_major(effort_matrix.data(), effort_rows, decision_count),
                             {effort_target.data(), effort_target.size()}});
                        if (diagnostic != qopt::HqpDiagnostic::None) {
                            result = failure(InverseDynamicsControlDiagnostic3D::RegistrationFailure,
                                             "actuator limit registration failed");
                            result.hqp_diagnostic = diagnostic;
                            return result;
                        }
                    }
                    if (force_inequality_count != 0) {
                        const qopt::HqpDiagnostic diagnostic = solver.add_inequality(
                            level.handle,
                            {qopt::ConstDenseMatrixView::row_major(
                                 force_inequality_matrix.data(), force_inequality_count, decision_count),
                             {force_inequality_target.data(), force_inequality_target.size()}});
                        if (diagnostic != qopt::HqpDiagnostic::None) {
                            result = failure(InverseDynamicsControlDiagnostic3D::RegistrationFailure,
                                             "force variable constraint "
                                             "registration failed");
                            result.hqp_diagnostic = diagnostic;
                            return result;
                        }
                    }
                }

                for (const TaskLinearization3D& value : linearizations) {
                    const std::vector<double> lifted = lift_task_matrix(value, decision_count);
                    const qopt::ConstDenseMatrixView lifted_view = qopt::ConstDenseMatrixView::row_major(
                        lifted.data(), value.target_storage.size(), decision_count);
                    qopt::HqpDiagnostic diagnostic = qopt::HqpDiagnostic::None;
                    switch (value.relation) {
                    case TaskRelation3D::Objective:
                        diagnostic = solver.add_task(level.handle, {lifted_view, value.target(), value.weight()});
                        break;
                    case TaskRelation3D::Equality:
                        diagnostic = solver.add_equality(level.handle, {lifted_view, value.target()});
                        break;
                    case TaskRelation3D::Inequality:
                        diagnostic = solver.add_inequality(level.handle, {lifted_view, value.target()});
                        break;
                    }
                    if (diagnostic != qopt::HqpDiagnostic::None) {
                        result = failure(InverseDynamicsControlDiagnostic3D::RegistrationFailure,
                                         "HQP contribution registration "
                                         "failed");
                        result.hqp_diagnostic = diagnostic;
                        result.failed_task_name = value.diagnostic_name;
                        return result;
                    }
                }
            }

            result.level_task_residual_l2.assign(levels.size(), 0.0);
            std::vector<double> decision(decision_count, 0.0);
            qopt::ConstDenseVectorView initial_primal;
            if (options.use_primal_warm_start && primal_warm_start_valid_ &&
                primal_warm_start_.size() == decision_count) {
                initial_primal = {primal_warm_start_.data(), decision_count};
                result.primal_warm_start_used = true;
            }
            result.hqp_result =
                solver.solve({{decision.data(), decision_count},
                              {result.level_task_residual_l2.data(), result.level_task_residual_l2.size()}},
                             initial_primal,
                             options.hqp);
            result.status = result.hqp_result.status;
            result.hqp_diagnostic = result.hqp_result.diagnostic;
            if (result.status != qopt::QpStatus::Optimal || result.hqp_diagnostic != qopt::HqpDiagnostic::None) {
                result.diagnostic = InverseDynamicsControlDiagnostic3D::SolveFailure;
                std::fprintf(stderr,
                             "[termin-robotics] inverse-dynamics HQP solve "
                             "failed (%s)\n",
                             qopt::hqp_diagnostic_name(result.hqp_diagnostic));
                return result;
            }

            std::copy_n(decision.data(), count, result.generalized_acceleration.data());
            if (force_variable_count != 0) {
                std::copy_n(decision.data() + count, force_variable_count, result.force_variable_values.data());
                for (std::size_t dof = 0; dof < count; ++dof) {
                    result.force_variable_generalized_effort[dof] =
                        matrix_row_dot(force_basis, force_variable_count, dof, result.force_variable_values);
                }
            }

            for (std::size_t dof = 0; dof < count; ++dof) {
                result.required_generalized_effort[dof] =
                    matrix_row_dot(mass, count, dof, result.generalized_acceleration) + bias[dof] - external[dof] -
                    result.force_variable_generalized_effort[dof];
                if (!actuated[dof]) {
                    result.unactuated_residual_linf =
                        std::max(result.unactuated_residual_linf, std::abs(result.required_generalized_effort[dof]));
                }
            }
            for (std::size_t index = 0; index < actuators_.size(); ++index) {
                result.actuator_effort[index] = result.required_generalized_effort[actuators_[index].dof_index];
            }
            primal_warm_start_ = std::move(decision);
            primal_warm_start_valid_ = true;
            return result;
        } catch (const std::exception& error) {
            std::fprintf(stderr, "[termin-robotics] inverse-dynamics HQP failed: %s\n", error.what());
        } catch (...) {
            std::fprintf(stderr,
                         "[termin-robotics] inverse-dynamics HQP failed with "
                         "an unknown exception\n");
        }
        return failure(InverseDynamicsControlDiagnostic3D::InternalFailure, "unexpected controller exception");
    }

    void InverseDynamicsHqpController3D::reset_primal_warm_start() noexcept {
        primal_warm_start_.clear();
        primal_warm_start_valid_ = false;
    }

    const std::vector<double>& InverseDynamicsHqpController3D::primal_warm_start() const noexcept {
        return primal_warm_start_;
    }

} // namespace termin::robotics
