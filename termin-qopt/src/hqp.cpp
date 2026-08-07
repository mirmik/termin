#include <termin/qopt/hqp.hpp>

#include "qp_internal.hpp"

#include <Eigen/Eigenvalues>

#include <algorithm>
#include <atomic>
#include <cmath>
#include <cstdio>
#include <exception>
#include <numeric>
#include <utility>
#include <vector>

namespace termin::qopt {
    namespace {

        using namespace detail;

        std::atomic<std::uint64_t> next_hqp_solver_id{1};

        struct Task {
            Matrix jacobian;
            Vector target;
            Matrix weight;
            Matrix protected_jacobian;
        };

        struct Constraint {
            Matrix matrix;
            Vector target;
        };

        struct Level {
            int priority = 0;
            std::vector<Task> tasks;
            std::vector<Constraint> equalities;
            std::vector<Constraint> inequalities;
        };

        [[nodiscard]] HqpSolveResult failure(QpStatus status,
                                             HqpDiagnostic diagnostic,
                                             std::size_t failed_level = std::numeric_limits<std::size_t>::max(),
                                             QpSolveResult level_result = {}) noexcept {
            HqpSolveResult result;
            result.status = status;
            result.diagnostic = diagnostic;
            result.failed_level = failed_level;
            result.level_result = level_result;
            return result;
        }

        [[nodiscard]] Matrix stack_matrices(const std::vector<Constraint>& constraints, Eigen::Index columns) {
            Eigen::Index rows = 0;
            for (const Constraint& constraint : constraints) {
                rows += constraint.matrix.rows();
            }
            Matrix result(rows, columns);
            Eigen::Index offset = 0;
            for (const Constraint& constraint : constraints) {
                result.middleRows(offset, constraint.matrix.rows()) = constraint.matrix;
                offset += constraint.matrix.rows();
            }
            return result;
        }

        [[nodiscard]] Vector stack_targets(const std::vector<Constraint>& constraints) {
            Eigen::Index size = 0;
            for (const Constraint& constraint : constraints) {
                size += constraint.target.size();
            }
            Vector result(size);
            Eigen::Index offset = 0;
            for (const Constraint& constraint : constraints) {
                result.segment(offset, constraint.target.size()) = constraint.target;
                offset += constraint.target.size();
            }
            return result;
        }

        [[nodiscard]] Matrix nullspace(const Matrix& matrix, NullspaceOptions options, NullspaceResult& result) {
            const std::size_t variables = static_cast<std::size_t>(matrix.cols());
            std::vector<double> storage(variables * variables);
            result = write_nullspace_basis(
                view(matrix), DenseMatrixView::column_major(storage.data(), variables, variables), options);
            if (result.status != QpStatus::Optimal) {
                return {};
            }
            Eigen::Map<const Matrix> full(
                storage.data(), static_cast<Eigen::Index>(variables), static_cast<Eigen::Index>(variables));
            return full.leftCols(static_cast<Eigen::Index>(result.nullity));
        }

        [[nodiscard]] double task_residual_l2(const Level& level, const Vector& primal) {
            double squared = 0.0;
            for (const Task& task : level.tasks) {
                squared += (task.jacobian * primal - task.target).squaredNorm();
            }
            return std::sqrt(squared);
        }

        [[nodiscard]] HqpDiagnostic validate_task(QuadraticTaskView task, std::size_t variables) noexcept {
            const QpDiagnostic jacobian_diagnostic = validate_matrix(task.jacobian);
            const QpDiagnostic target_diagnostic = validate_vector(task.target);
            const QpDiagnostic weight_diagnostic = validate_matrix(task.weight);
            if (jacobian_diagnostic != QpDiagnostic::None || target_diagnostic != QpDiagnostic::None ||
                weight_diagnostic != QpDiagnostic::None) {
                return HqpDiagnostic::DimensionMismatch;
            }
            if (task.jacobian.columns != variables || task.target.size != task.jacobian.rows ||
                (!task.weight.empty() &&
                 (task.weight.rows != task.jacobian.rows || task.weight.columns != task.jacobian.rows))) {
                return HqpDiagnostic::DimensionMismatch;
            }
            if (!finite(task.jacobian) || !finite(task.target) || !finite(task.weight)) {
                return HqpDiagnostic::NonFiniteInput;
            }
            return HqpDiagnostic::None;
        }

        [[nodiscard]] HqpDiagnostic
        validate_constraint(ConstDenseMatrixView matrix, ConstDenseVectorView target, std::size_t variables) noexcept {
            if (validate_matrix(matrix) != QpDiagnostic::None || validate_vector(target) != QpDiagnostic::None ||
                matrix.columns != variables || target.size != matrix.rows) {
                return HqpDiagnostic::DimensionMismatch;
            }
            if (!finite(matrix) || !finite(target)) {
                return HqpDiagnostic::NonFiniteInput;
            }
            return HqpDiagnostic::None;
        }

    } // namespace

    struct HierarchicalQpSolver::Impl {
        std::uint64_t id = next_hqp_solver_id.fetch_add(1, std::memory_order_relaxed);
        std::size_t variables = 0;
        std::vector<Level> levels;

        [[nodiscard]] bool valid(HqpLevelHandle handle) const noexcept {
            return handle.solver_id == id && handle.index < levels.size();
        }
    };

    const char* hqp_diagnostic_name(HqpDiagnostic diagnostic) noexcept {
        switch (diagnostic) {
        case HqpDiagnostic::None:
            return "none";
        case HqpDiagnostic::InvalidVariableCount:
            return "invalid_variable_count";
        case HqpDiagnostic::InvalidLevel:
            return "invalid_level";
        case HqpDiagnostic::DuplicatePriority:
            return "duplicate_priority";
        case HqpDiagnostic::DimensionMismatch:
            return "dimension_mismatch";
        case HqpDiagnostic::NonFiniteInput:
            return "non_finite_input";
        case HqpDiagnostic::InvalidWeight:
            return "invalid_weight";
        case HqpDiagnostic::InvalidOptions:
            return "invalid_options";
        case HqpDiagnostic::LevelSolveFailure:
            return "level_solve_failure";
        case HqpDiagnostic::PriorityViolation:
            return "priority_violation";
        case HqpDiagnostic::InternalFailure:
            return "internal_failure";
        }
        return "unknown";
    }

    HierarchicalQpSolver::HierarchicalQpSolver(std::size_t variable_count)
        : impl_(std::make_unique<Impl>()) {
        impl_->variables = variable_count;
    }

    HierarchicalQpSolver::~HierarchicalQpSolver() = default;
    HierarchicalQpSolver::HierarchicalQpSolver(HierarchicalQpSolver&&) noexcept = default;
    HierarchicalQpSolver& HierarchicalQpSolver::operator=(HierarchicalQpSolver&&) noexcept = default;

    std::size_t HierarchicalQpSolver::variable_count() const noexcept {
        return impl_ == nullptr ? 0 : impl_->variables;
    }

    std::size_t HierarchicalQpSolver::level_count() const noexcept {
        return impl_ == nullptr ? 0 : impl_->levels.size();
    }

    HqpLevelRegistrationResult HierarchicalQpSolver::add_level(int priority) noexcept {
        if (impl_ == nullptr || impl_->variables == 0) {
            return {{}, HqpDiagnostic::InvalidVariableCount};
        }
        for (const Level& level : impl_->levels) {
            if (level.priority == priority) {
                return {{}, HqpDiagnostic::DuplicatePriority};
            }
        }
        try {
            const std::size_t index = impl_->levels.size();
            impl_->levels.push_back({priority, {}, {}, {}});
            return {{impl_->id, index}, HqpDiagnostic::None};
        } catch (const std::exception& error) {
            std::fprintf(stderr, "[termin-qopt] add HQP level failed: %s\n", error.what());
        } catch (...) {
            std::fprintf(stderr, "[termin-qopt] add HQP level failed with unknown exception\n");
        }
        return {{}, HqpDiagnostic::InternalFailure};
    }

    HqpDiagnostic HierarchicalQpSolver::add_task(HqpLevelHandle level, QuadraticTaskView task) noexcept {
        if (impl_ == nullptr || !impl_->valid(level)) {
            return HqpDiagnostic::InvalidLevel;
        }
        const HqpDiagnostic diagnostic = validate_task(task, impl_->variables);
        if (diagnostic != HqpDiagnostic::None) {
            return diagnostic;
        }
        try {
            Matrix weight = task.weight.empty() ? Matrix::Identity(static_cast<Eigen::Index>(task.jacobian.rows),
                                                                   static_cast<Eigen::Index>(task.jacobian.rows))
                                                : copy_matrix(task.weight);
            const double symmetry_error = matrix_linf(weight - weight.transpose());
            if (symmetry_error > 1e-10) {
                return HqpDiagnostic::InvalidWeight;
            }
            weight = 0.5 * (weight + weight.transpose());
            Eigen::SelfAdjointEigenSolver<Matrix> eigensolver(weight);
            if (eigensolver.info() != Eigen::Success ||
                (eigensolver.eigenvalues().size() > 0 && eigensolver.eigenvalues().minCoeff() < -1e-12)) {
                return HqpDiagnostic::InvalidWeight;
            }
            const Vector& eigenvalues = eigensolver.eigenvalues();
            const double spectral_scale =
                eigenvalues.size() == 0 ? 1.0 : std::max(1.0, eigenvalues.cwiseAbs().maxCoeff());
            const double rank_tolerance = 1e-12 * spectral_scale;
            const Eigen::Index protected_rows = (eigenvalues.array() > rank_tolerance).count();
            Matrix weight_root(protected_rows, weight.rows());
            Eigen::Index protected_row = 0;
            for (Eigen::Index index = 0; index < eigenvalues.size(); ++index) {
                if (eigenvalues[index] <= rank_tolerance) {
                    continue;
                }
                weight_root.row(protected_row) =
                    std::sqrt(eigenvalues[index]) * eigensolver.eigenvectors().col(index).transpose();
                ++protected_row;
            }
            Matrix jacobian = copy_matrix(task.jacobian);
            impl_->levels[level.index].tasks.push_back({
                jacobian,
                copy_vector(task.target),
                std::move(weight),
                weight_root * jacobian,
            });
            return HqpDiagnostic::None;
        } catch (const std::exception& error) {
            std::fprintf(stderr, "[termin-qopt] add HQP task failed: %s\n", error.what());
        } catch (...) {
            std::fprintf(stderr, "[termin-qopt] add HQP task failed with unknown exception\n");
        }
        return HqpDiagnostic::InternalFailure;
    }

    HqpDiagnostic HierarchicalQpSolver::add_equality(HqpLevelHandle level, EqualityConstraintView constraint) noexcept {
        if (impl_ == nullptr || !impl_->valid(level)) {
            return HqpDiagnostic::InvalidLevel;
        }
        const HqpDiagnostic diagnostic = validate_constraint(constraint.matrix, constraint.target, impl_->variables);
        if (diagnostic != HqpDiagnostic::None) {
            return diagnostic;
        }
        try {
            impl_->levels[level.index].equalities.push_back({
                copy_matrix(constraint.matrix),
                copy_vector(constraint.target),
            });
            return HqpDiagnostic::None;
        } catch (const std::exception& error) {
            std::fprintf(stderr, "[termin-qopt] add HQP equality failed: %s\n", error.what());
        } catch (...) {
            std::fprintf(stderr, "[termin-qopt] add HQP equality failed with unknown exception\n");
        }
        return HqpDiagnostic::InternalFailure;
    }

    HqpDiagnostic HierarchicalQpSolver::add_inequality(HqpLevelHandle level,
                                                       InequalityConstraintView constraint) noexcept {
        if (impl_ == nullptr || !impl_->valid(level)) {
            return HqpDiagnostic::InvalidLevel;
        }
        const HqpDiagnostic diagnostic = validate_constraint(constraint.matrix, constraint.limit, impl_->variables);
        if (diagnostic != HqpDiagnostic::None) {
            return diagnostic;
        }
        try {
            impl_->levels[level.index].inequalities.push_back({
                copy_matrix(constraint.matrix),
                copy_vector(constraint.limit),
            });
            return HqpDiagnostic::None;
        } catch (const std::exception& error) {
            std::fprintf(stderr, "[termin-qopt] add HQP inequality failed: %s\n", error.what());
        } catch (...) {
            std::fprintf(stderr, "[termin-qopt] add HQP inequality failed with unknown exception\n");
        }
        return HqpDiagnostic::InternalFailure;
    }

    HqpSolveResult HierarchicalQpSolver::solve(HqpSolutionView solution,
                                               ConstDenseVectorView initial_primal,
                                               HqpOptions options) const noexcept {
        if (impl_ == nullptr || impl_->variables == 0) {
            return failure(QpStatus::InvalidInput, HqpDiagnostic::InvalidVariableCount);
        }
        if (validate_vector(solution.primal) != QpDiagnostic::None ||
            validate_vector(solution.level_task_residual_l2) != QpDiagnostic::None ||
            solution.primal.size != impl_->variables || solution.level_task_residual_l2.size != impl_->levels.size() ||
            (!initial_primal.empty() && initial_primal.size != impl_->variables)) {
            return failure(QpStatus::InvalidInput, HqpDiagnostic::DimensionMismatch);
        }
        if (validate_vector(initial_primal) != QpDiagnostic::None || !finite(initial_primal)) {
            return failure(QpStatus::InvalidInput, HqpDiagnostic::NonFiniteInput);
        }
        if (!valid_tolerance(options.qp.tolerance) || !valid_tolerance(options.nullspace.tolerance) ||
            !std::isfinite(options.priority_tolerance) || options.priority_tolerance < 0.0) {
            return failure(QpStatus::InvalidInput, HqpDiagnostic::InvalidOptions);
        }

        try {
            const Eigen::Index variables = static_cast<Eigen::Index>(impl_->variables);
            Vector primal = initial_primal.empty() ? Vector::Zero(variables) : copy_vector(initial_primal);
            Matrix directions = Matrix::Identity(variables, variables);
            std::vector<std::size_t> order(impl_->levels.size());
            std::iota(order.begin(), order.end(), 0);
            std::sort(order.begin(), order.end(), [&](std::size_t left, std::size_t right) {
                return impl_->levels[left].priority < impl_->levels[right].priority;
            });

            std::vector<Constraint> equalities;
            std::vector<Constraint> inequalities;
            std::vector<std::pair<Matrix, Vector>> frozen_tasks;
            std::vector<double> residuals(order.size(), 0.0);
            HqpSolveResult result;
            result.status = QpStatus::Optimal;
            result.priority_violation_linf = 0.0;

            for (std::size_t ordered_index = 0; ordered_index < order.size(); ++ordered_index) {
                const Level& level = impl_->levels[order[ordered_index]];
                equalities.insert(equalities.end(), level.equalities.begin(), level.equalities.end());
                inequalities.insert(inequalities.end(), level.inequalities.begin(), level.inequalities.end());

                Matrix hessian = Matrix::Zero(variables, variables);
                Vector gradient = Vector::Zero(variables);
                for (const Task& task : level.tasks) {
                    hessian += task.jacobian.transpose() * task.weight * task.jacobian;
                    gradient -= task.jacobian.transpose() * task.weight * task.target;
                }

                const Matrix equality_matrix = stack_matrices(equalities, variables);
                const Vector equality_target = stack_targets(equalities);
                const Matrix inequality_matrix = stack_matrices(inequalities, variables);
                const Vector inequality_limit = stack_targets(inequalities);

                if (directions.cols() > 0) {
                    const Matrix reduced_hessian = directions.transpose() * hessian * directions;
                    const Vector reduced_gradient = directions.transpose() * (hessian * primal + gradient);
                    const Matrix reduced_equalities = equality_matrix * directions;
                    const Vector reduced_equality_targets = equality_target - equality_matrix * primal;
                    const Matrix reduced_inequalities = inequality_matrix * directions;
                    const Vector reduced_inequality_limits = inequality_limit - inequality_matrix * primal;
                    Vector increment = Vector::Zero(directions.cols());
                    Vector equality_dual = Vector::Zero(reduced_equalities.rows());
                    Vector inequality_dual = Vector::Zero(reduced_inequalities.rows());
                    Vector empty;
                    const QpSolveResult level_result = solve_active_set_qp(
                        {
                            view(reduced_hessian),
                            view(reduced_gradient),
                            view(reduced_equalities),
                            view(reduced_equality_targets),
                            view(reduced_inequalities),
                            view(reduced_inequality_limits),
                            {},
                            {},
                        },
                        {
                            view(increment),
                            view(equality_dual),
                            view(inequality_dual),
                            view(empty),
                            view(empty),
                        },
                        {},
                        options.qp);
                    result.level_result = level_result;
                    if (level_result.status != QpStatus::Optimal) {
                        HqpSolveResult failed =
                            failure(level_result.status, HqpDiagnostic::LevelSolveFailure, ordered_index, level_result);
                        failed.levels_solved = ordered_index;
                        failed.remaining_dofs = static_cast<std::size_t>(directions.cols());
                        return failed;
                    }
                    primal += directions * increment;
                } else {
                    const double equality_error = linf(equality_matrix * primal - equality_target);
                    const Vector inequality_error = inequality_matrix * primal - inequality_limit;
                    const double inequality_violation =
                        inequality_error.size() == 0 ? 0.0 : std::max(0.0, inequality_error.maxCoeff());
                    const double tolerance = scaled_tolerance(
                        options.qp.tolerance, std::max(matrix_linf(equality_matrix), matrix_linf(inequality_matrix)));
                    if (equality_error > tolerance || inequality_violation > tolerance) {
                        QpSolveResult level_result;
                        level_result.status = QpStatus::Infeasible;
                        level_result.diagnostic = QpDiagnostic::InconsistentEqualities;
                        HqpSolveResult failed = failure(
                            QpStatus::Infeasible, HqpDiagnostic::LevelSolveFailure, ordered_index, level_result);
                        failed.levels_solved = ordered_index;
                        failed.remaining_dofs = 0;
                        return failed;
                    }
                }

                residuals[ordered_index] = task_residual_l2(level, primal);
                for (const auto& [jacobian, frozen_value] : frozen_tasks) {
                    result.priority_violation_linf =
                        std::max(result.priority_violation_linf, linf(jacobian * primal - frozen_value));
                }
                if (result.priority_violation_linf > options.priority_tolerance) {
                    result.status = QpStatus::NumericalFailure;
                    result.diagnostic = HqpDiagnostic::PriorityViolation;
                    result.failed_level = ordered_index;
                    result.levels_solved = ordered_index;
                    result.remaining_dofs = static_cast<std::size_t>(directions.cols());
                    return result;
                }

                std::vector<Constraint> preserve;
                preserve.reserve(level.equalities.size() + level.tasks.size());
                preserve.insert(preserve.end(), level.equalities.begin(), level.equalities.end());
                for (const Task& task : level.tasks) {
                    preserve.push_back({
                        task.protected_jacobian,
                        task.protected_jacobian * primal,
                    });
                    frozen_tasks.emplace_back(task.protected_jacobian, task.protected_jacobian * primal);
                }
                if (!preserve.empty() && directions.cols() > 0) {
                    const Matrix reduced_preserve = stack_matrices(preserve, variables) * directions;
                    NullspaceResult nullspace_result;
                    const Matrix reduced_nullspace = nullspace(reduced_preserve, options.nullspace, nullspace_result);
                    if (nullspace_result.status != QpStatus::Optimal) {
                        return failure(nullspace_result.status, HqpDiagnostic::LevelSolveFailure, ordered_index);
                    }
                    directions *= reduced_nullspace;
                }
                ++result.levels_solved;
            }

            copy_to_view(primal, solution.primal);
            for (std::size_t index = 0; index < residuals.size(); ++index) {
                solution.level_task_residual_l2[index] = residuals[index];
            }
            result.remaining_dofs = static_cast<std::size_t>(directions.cols());
            return result;
        } catch (const std::exception& error) {
            std::fprintf(stderr, "[termin-qopt] HQP solve failed: %s\n", error.what());
        } catch (...) {
            std::fprintf(stderr, "[termin-qopt] HQP solve failed with unknown exception\n");
        }
        return failure(QpStatus::NumericalFailure, HqpDiagnostic::InternalFailure);
    }

} // namespace termin::qopt
