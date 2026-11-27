#include <termin/qopt/equality_qp.hpp>

#include "qp_internal.hpp"

#include <Eigen/Cholesky>
#include <Eigen/Eigenvalues>
#include <Eigen/SVD>

#include <algorithm>
#include <cmath>
#include <cstdio>
#include <exception>
#include <numeric>
#include <utility>

namespace termin::qopt {
    namespace {

        using namespace detail;

        struct RankRevealingFactorization {
            Matrix input_hessian;
            Matrix input_equalities;
            Matrix hessian;
            Matrix equalities;
            Vector equality_row_scales;
            Matrix nullspace;
            Matrix left_range;
            Matrix right_range;
            Vector inverse_singular_values;
            Vector eigenvalues;
            Matrix eigenvectors;
            QpTolerance tolerance;
            std::size_t constraint_rank = 0;
            std::size_t reduced_rank = 0;
            double curvature_tolerance = 0.0;
            bool valid = false;
            bool reduced_valid = false;
        };

        [[nodiscard]] bool same_tolerance(QpTolerance left, QpTolerance right) noexcept {
            return left.absolute == right.absolute && left.relative == right.relative &&
                   left.symmetry == right.symmetry;
        }

        [[nodiscard]] bool same_matrix(const Matrix& left, const Matrix& right) noexcept {
            return left.rows() == right.rows() && left.cols() == right.cols() && (left.array() == right.array()).all();
        }

        [[nodiscard]] bool compatible(const RankRevealingFactorization& factor,
                                      const Matrix& hessian,
                                      const Matrix& equalities,
                                      QpTolerance tolerance) noexcept {
            return factor.valid && same_tolerance(factor.tolerance, tolerance) &&
                   same_matrix(factor.input_hessian, hessian) && same_matrix(factor.input_equalities, equalities);
        }

        [[nodiscard]] QpSolveResult solve_factored_gradient(const RankRevealingFactorization& factor,
                                                            const Vector& gradient,
                                                            const Vector& feasible,
                                                            const Vector& input_equality_targets,
                                                            double feasibility_tolerance,
                                                            EqualityQpSolutionView solution) {
            const Eigen::Index constraint_count = factor.input_equalities.rows();
            const bool unconstrained = constraint_count == 0;
            const Eigen::Index reduced_variables = factor.eigenvalues.size();
            const QpTolerance tolerance = factor.tolerance;
            Vector primal;
            if (!unconstrained)
                primal = feasible;
            if (reduced_variables > 0) {
                Vector reduced_gradient;
                if (unconstrained)
                    reduced_gradient = gradient;
                else
                    reduced_gradient = factor.nullspace.transpose() * (factor.hessian * feasible + gradient);
                const Vector spectral_gradient = factor.eigenvectors.transpose() * reduced_gradient;
                const double gradient_tolerance = scaled_tolerance(tolerance, linf(reduced_gradient));
                Vector spectral_solution = Vector::Zero(reduced_variables);

                for (Eigen::Index index = 0; index < reduced_variables; ++index) {
                    const double eigenvalue = factor.eigenvalues[index];
                    if (eigenvalue < -factor.curvature_tolerance) {
                        QpSolveResult result = failure(QpStatus::NonConvex, QpDiagnostic::NegativeCurvature);
                        result.constraint_rank = factor.constraint_rank;
                        return result;
                    }
                    if (eigenvalue > factor.curvature_tolerance) {
                        spectral_solution[index] = -spectral_gradient[index] / eigenvalue;
                    } else if (std::abs(spectral_gradient[index]) > gradient_tolerance) {
                        QpSolveResult result = failure(QpStatus::Unbounded, QpDiagnostic::LinearDescentInNullspace);
                        result.constraint_rank = factor.constraint_rank;
                        result.reduced_hessian_rank = factor.reduced_rank;
                        return result;
                    }
                }

                if (unconstrained)
                    primal = factor.eigenvectors * spectral_solution;
                else
                    primal += factor.nullspace * factor.eigenvectors * spectral_solution;
            }

            const Vector hessian_primal = factor.hessian * primal;
            const Vector objective_gradient = hessian_primal + gradient;
            Vector equality_dual;
            double stationarity_linf = linf(objective_gradient);
            double equality_linf = 0.0;
            double stationarity_scale = std::max({
                1.0,
                linf(hessian_primal),
                linf(gradient),
            });
            if (!unconstrained) {
                equality_dual = Vector::Zero(constraint_count);
                if (factor.constraint_rank > 0) {
                    equality_dual = -factor.left_range * factor.inverse_singular_values.asDiagonal() *
                                    factor.right_range.transpose() * objective_gradient;
                    equality_dual.array() /= factor.equality_row_scales.array();
                }
                const Vector dual_gradient = factor.input_equalities.transpose() * equality_dual;
                stationarity_linf = linf(objective_gradient + dual_gradient);
                equality_linf = linf(factor.input_equalities * primal - input_equality_targets);
                stationarity_scale = std::max(stationarity_scale, linf(dual_gradient));
            }

            QpSolveResult result;
            result.status = QpStatus::Optimal;
            result.diagnostic = QpDiagnostic::None;
            result.stationarity_linf = stationarity_linf;
            result.equality_linf = equality_linf;
            result.constraint_rank = factor.constraint_rank;
            result.reduced_hessian_rank = factor.reduced_rank;

            if (!primal.allFinite() || !equality_dual.allFinite() || !std::isfinite(result.stationarity_linf) ||
                !std::isfinite(result.equality_linf) ||
                result.stationarity_linf > scaled_tolerance(tolerance, stationarity_scale) ||
                result.equality_linf > feasibility_tolerance) {
                result.status = QpStatus::NumericalFailure;
                result.diagnostic = QpDiagnostic::ResidualTooLarge;
                return result;
            }

            copy_to_view(primal, solution.primal);
            copy_to_view(equality_dual, solution.equality_dual);
            return result;
        }

        [[nodiscard]] QpSolveResult solve_impl(EqualityQpProblemView problem,
                                               EqualityQpSolutionView solution,
                                               QpTolerance tolerance,
                                               bool try_spd_fast_path,
                                               RankRevealingFactorization* cache,
                                               EqualityQpFactorizationCounters* counters) {
            if (!valid_tolerance(tolerance)) {
                return failure(QpStatus::InvalidInput, QpDiagnostic::InvalidTolerance);
            }

            const QpDiagnostic view_diagnostics[] = {
                validate_matrix(problem.hessian),
                validate_matrix(problem.equalities),
                validate_vector(problem.gradient),
                validate_vector(problem.equality_targets),
                validate_vector(solution.primal),
                validate_vector(solution.equality_dual),
            };
            for (QpDiagnostic diagnostic : view_diagnostics) {
                if (diagnostic != QpDiagnostic::None) {
                    return failure(QpStatus::InvalidInput, diagnostic);
                }
            }

            const std::size_t variables = problem.hessian.rows;
            const std::size_t constraints = problem.equalities.rows;
            if (variables == 0 || problem.hessian.columns != variables || problem.gradient.size != variables ||
                problem.equalities.columns != variables || problem.equality_targets.size != constraints ||
                solution.primal.size != variables || solution.equality_dual.size != constraints) {
                return failure(QpStatus::InvalidInput, QpDiagnostic::DimensionMismatch);
            }
            if (overlaps(solution.primal, solution.equality_dual)) {
                return failure(QpStatus::InvalidInput, QpDiagnostic::OverlappingOutputs);
            }
            if (!finite(problem.hessian) || !finite(problem.gradient) || !finite(problem.equalities) ||
                !finite(problem.equality_targets)) {
                return failure(QpStatus::InvalidInput, QpDiagnostic::NonFiniteInput);
            }

            const Matrix input_hessian = copy_matrix(problem.hessian);
            const Vector gradient = copy_vector(problem.gradient);
            const Matrix input_equalities = copy_matrix(problem.equalities);
            const Vector input_equality_targets = copy_vector(problem.equality_targets);

            const double hessian_scale = matrix_linf(input_hessian);
            const double symmetry_residual = matrix_linf(input_hessian - input_hessian.transpose());
            if (symmetry_residual > tolerance.symmetry * std::max(1.0, hessian_scale)) {
                return failure(QpStatus::InvalidInput, QpDiagnostic::NonSymmetricHessian);
            }
            const Matrix hessian = 0.5 * (input_hessian + input_hessian.transpose());

            const Eigen::Index variable_count = static_cast<Eigen::Index>(variables);
            const Eigen::Index constraint_count = static_cast<Eigen::Index>(constraints);
            const bool unconstrained = constraint_count == 0;
            Matrix equalities = input_equalities;
            Vector equality_targets = input_equality_targets;
            Vector equality_row_scales = Vector::Ones(constraint_count);
            for (Eigen::Index row = 0; row < constraint_count; ++row) {
                const double row_scale = equalities.row(row).cwiseAbs().maxCoeff();
                if (row_scale > 0.0) {
                    equality_row_scales[row] = row_scale;
                    equalities.row(row) /= row_scale;
                    equality_targets[row] /= row_scale;
                }
            }

            // Dynamics subproblems normally have a positive-definite mass matrix and
            // independent active constraints. Solve that common case through the Schur
            // complement, while retaining the rank-revealing path below for singular,
            // semidefinite, or inconsistent problems.
            if (try_spd_fast_path && constraint_count > 0 && constraint_count <= variable_count) {
                Eigen::LLT<Matrix> hessian_factor(hessian);
                if (hessian_factor.info() == Eigen::Success) {
                    const Vector hessian_pivots = hessian_factor.matrixL().toDenseMatrix().diagonal().array().square();
                    const double hessian_rank_tolerance = scaled_tolerance(tolerance, hessian_scale);
                    if (hessian_pivots.size() > 0 && hessian_pivots.minCoeff() > hessian_rank_tolerance) {
                        const Vector free_primal = hessian_factor.solve(-gradient);
                        const Matrix constraint_response = hessian_factor.solve(equalities.transpose());
                        const Matrix raw_schur = equalities * constraint_response;
                        const Matrix schur = 0.5 * (raw_schur + raw_schur.transpose());

                        Eigen::LLT<Matrix> schur_factor(schur);
                        bool schur_full_rank = false;
                        if (schur_factor.info() == Eigen::Success) {
                            const Vector schur_pivots =
                                schur_factor.matrixL().toDenseMatrix().diagonal().array().square();
                            schur_full_rank = schur_pivots.minCoeff() > scaled_tolerance(tolerance, matrix_linf(schur));
                        }

                        if (schur_full_rank) {
                            const Vector normalized_dual =
                                schur_factor.solve(equalities * free_primal - equality_targets);
                            const Vector primal = free_primal - constraint_response * normalized_dual;
                            Vector equality_dual = normalized_dual;
                            equality_dual.array() /= equality_row_scales.array();

                            const Vector objective_gradient = hessian * primal + gradient;
                            const Vector stationarity_error =
                                objective_gradient + input_equalities.transpose() * equality_dual;
                            const Vector equality_error = input_equalities * primal - input_equality_targets;
                            const double feasibility_scale =
                                std::max(linf(input_equalities * primal), linf(input_equality_targets));
                            const double feasibility_tolerance = scaled_tolerance(tolerance, feasibility_scale);
                            const double stationarity_scale = std::max({
                                1.0,
                                linf(hessian * primal),
                                linf(gradient),
                                linf(input_equalities.transpose() * equality_dual),
                            });

                            QpSolveResult result;
                            result.status = QpStatus::Optimal;
                            result.diagnostic = QpDiagnostic::None;
                            result.stationarity_linf = linf(stationarity_error);
                            result.equality_linf = linf(equality_error);
                            result.constraint_rank = constraints;
                            result.reduced_hessian_rank = variables - constraints;
                            if (result.stationarity_linf <= scaled_tolerance(tolerance, stationarity_scale) &&
                                result.equality_linf <= feasibility_tolerance) {
                                copy_to_view(primal, solution.primal);
                                copy_to_view(equality_dual, solution.equality_dual);
                                return result;
                            }
                        }
                    }
                }
            }

            RankRevealingFactorization local_factor;
            RankRevealingFactorization& factor = cache == nullptr ? local_factor : *cache;
            if (compatible(factor, input_hessian, input_equalities, tolerance)) {
                if (counters != nullptr) {
                    ++counters->reuse_hits;
                }
            } else {
                if (counters != nullptr) {
                    ++counters->factorizations;
                }
                factor.valid = false;
                factor.input_hessian = input_hessian;
                factor.input_equalities = input_equalities;
                factor.hessian = hessian;
                factor.equalities = equalities;
                factor.equality_row_scales = equality_row_scales;
                factor.tolerance = tolerance;
                factor.constraint_rank = 0;
                factor.reduced_rank = 0;
                factor.curvature_tolerance = 0.0;
                factor.reduced_valid = false;

                if (unconstrained) {
                    // The whole variable space is free. Represent its identity
                    // basis implicitly, including after a constrained cache use.
                    factor.nullspace.resize(0, 0);
                    factor.left_range.resize(0, 0);
                    factor.right_range.resize(variable_count, 0);
                    factor.inverse_singular_values.resize(0);
                } else {
                    Eigen::JacobiSVD<Matrix> svd(factor.equalities, Eigen::ComputeFullU | Eigen::ComputeFullV);
                    if (svd.info() != Eigen::Success) {
                        std::fprintf(stderr,
                                     "[termin-qopt] equality QP constraint SVD failed: "
                                     "variables=%zu constraints=%zu scale=%g\n",
                                     variables,
                                     constraints,
                                     matrix_linf(factor.equalities));
                        return failure(QpStatus::NumericalFailure, QpDiagnostic::DecompositionFailure);
                    }

                    const Vector singular_values = svd.singularValues();
                    const double singular_scale =
                        singular_values.size() == 0 ? 0.0 : singular_values.cwiseAbs().maxCoeff();
                    const double rank_tolerance = scaled_tolerance(tolerance, singular_scale);
                    for (Eigen::Index index = 0; index < singular_values.size(); ++index) {
                        if (singular_values[index] > rank_tolerance) {
                            ++factor.constraint_rank;
                        }
                    }

                    const Eigen::Index rank = static_cast<Eigen::Index>(factor.constraint_rank);
                    factor.left_range = svd.matrixU().leftCols(rank);
                    factor.right_range = svd.matrixV().leftCols(rank);
                    factor.inverse_singular_values.resize(rank);
                    for (Eigen::Index index = 0; index < rank; ++index) {
                        factor.inverse_singular_values[index] = 1.0 / singular_values[index];
                    }
                    factor.nullspace = svd.matrixV().rightCols(variable_count - rank);
                }

                factor.valid = true;
            }

            Vector feasible;
            double feasibility_tolerance = scaled_tolerance(tolerance, 0.0);
            if (!unconstrained) {
                feasible = Vector::Zero(variable_count);
                if (factor.constraint_rank > 0) {
                    feasible = factor.right_range * factor.inverse_singular_values.asDiagonal() *
                               factor.left_range.transpose() * equality_targets;
                }

                const Vector feasibility_error = input_equalities * feasible - input_equality_targets;
                const double feasibility_scale =
                    std::max(linf(input_equalities * feasible), linf(input_equality_targets));
                feasibility_tolerance = scaled_tolerance(tolerance, feasibility_scale);
                if (linf(feasibility_error) > feasibility_tolerance) {
                    QpSolveResult result = failure(QpStatus::Infeasible, QpDiagnostic::InconsistentEqualities);
                    result.equality_linf = linf(feasibility_error);
                    result.constraint_rank = factor.constraint_rank;
                    return result;
                }
            }

            const Eigen::Index reduced_variables = unconstrained ? variable_count : factor.nullspace.cols();
            if (!factor.reduced_valid) {
                factor.reduced_rank = 0;
                if (reduced_variables > 0) {
                    Matrix reduced_hessian;
                    if (unconstrained) {
                        // Already symmetrized during input validation. Keep the
                        // same spectral decomposition and rank/curvature tests.
                        reduced_hessian = factor.hessian;
                    } else {
                        const Matrix raw_reduced_hessian =
                            factor.nullspace.transpose() * factor.hessian * factor.nullspace;
                        reduced_hessian = 0.5 * (raw_reduced_hessian + raw_reduced_hessian.transpose());
                    }
                    Eigen::SelfAdjointEigenSolver<Matrix> eigensolver(reduced_hessian);
                    if (eigensolver.info() != Eigen::Success) {
                        std::fprintf(stderr,
                                     "[termin-qopt] equality QP reduced Hessian decomposition "
                                     "failed: variables=%zu constraints=%zu rank=%zu "
                                     "reduced=%td scale=%g finite=%d\n",
                                     variables,
                                     constraints,
                                     factor.constraint_rank,
                                     static_cast<std::ptrdiff_t>(reduced_variables),
                                     matrix_linf(reduced_hessian),
                                     reduced_hessian.allFinite() ? 1 : 0);
                        return failure(QpStatus::NumericalFailure, QpDiagnostic::DecompositionFailure);
                    }
                    factor.eigenvalues = eigensolver.eigenvalues();
                    factor.eigenvectors = eigensolver.eigenvectors();
                    factor.curvature_tolerance = scaled_tolerance(tolerance, linf(factor.eigenvalues));
                    for (Eigen::Index index = 0; index < reduced_variables; ++index) {
                        if (factor.eigenvalues[index] > factor.curvature_tolerance) {
                            ++factor.reduced_rank;
                        }
                    }
                } else {
                    factor.eigenvalues.resize(0);
                    factor.eigenvectors.resize(0, 0);
                }
                factor.reduced_valid = true;
            }

            return solve_factored_gradient(
                factor, gradient, feasible, input_equality_targets, feasibility_tolerance, solution);
        }

        // For a valid strided view the four corners bound all storage addresses.
        [[nodiscard]] AddressInterval storage_interval(DenseMatrixView view) {
            if (view.empty()) {
                return {};
            }
            const std::size_t last_row = view.rows - 1;
            const std::size_t last_column = view.columns - 1;
            const auto first = reinterpret_cast<std::uintptr_t>(
                &view(view.row_stride < 0 ? last_row : 0, view.column_stride < 0 ? last_column : 0));
            const auto last = reinterpret_cast<std::uintptr_t>(
                &view(view.row_stride > 0 ? last_row : 0, view.column_stride > 0 ? last_column : 0));
            return {first, last + sizeof(double) - 1, false};
        }

        [[nodiscard]] bool repeats_elements(DenseMatrixView view) {
            if (view.rows < 2 || view.columns < 2) {
                return false;
            }
            const auto magnitude = [](DenseIndex stride) -> std::size_t {
                return stride < 0 ? static_cast<std::size_t>(-(stride + 1)) + 1 : static_cast<std::size_t>(stride);
            };
            const auto row = magnitude(view.row_stride);
            const auto column = magnitude(view.column_stride);
            const auto divisor = std::gcd(row, column);
            // Smallest displacement mapping two coordinates to the same address.
            return column / divisor < view.rows && row / divisor < view.columns;
        }

    } // namespace

    struct EqualityQpFactorizationCache::Impl {
        RankRevealingFactorization factor;
        EqualityQpFactorizationCounters counters;
    };

    EqualityQpFactorizationCache::EqualityQpFactorizationCache()
        : impl_(std::make_unique<Impl>()) {}

    EqualityQpFactorizationCache::~EqualityQpFactorizationCache() = default;

    EqualityQpFactorizationCache::EqualityQpFactorizationCache(EqualityQpFactorizationCache&&) noexcept = default;

    EqualityQpFactorizationCache&
    EqualityQpFactorizationCache::operator=(EqualityQpFactorizationCache&&) noexcept = default;

    QpSolveResult EqualityQpFactorizationCache::solve(EqualityQpProblemView problem,
                                                      EqualityQpSolutionView solution,
                                                      QpTolerance tolerance) noexcept {
        try {
            if (impl_ == nullptr) {
                impl_ = std::make_unique<Impl>();
            }
            return solve_impl(problem, solution, tolerance, false, &impl_->factor, &impl_->counters);
        } catch (const std::exception& error) {
            std::fprintf(stderr,
                         "[termin-qopt] cached equality QP failed with an exception: "
                         "%s\n",
                         error.what());
        } catch (...) {
            std::fprintf(stderr,
                         "[termin-qopt] cached equality QP failed with an unknown "
                         "exception\n");
        }
        return failure(QpStatus::NumericalFailure, QpDiagnostic::DecompositionFailure);
    }

    void EqualityQpFactorizationCache::clear() noexcept {
        if (impl_ != nullptr) {
            impl_->factor.valid = false;
        }
    }

    EqualityQpFactorizationCounters EqualityQpFactorizationCache::counters() const noexcept {
        return impl_ == nullptr ? EqualityQpFactorizationCounters{} : impl_->counters;
    }

    void EqualityQpFactorizationCache::reset_counters() noexcept {
        if (impl_ != nullptr) {
            impl_->counters = {};
        }
    }

    QpSolveResult
    solve_equality_qp(EqualityQpProblemView problem, EqualityQpSolutionView solution, QpTolerance tolerance) noexcept {
        try {
            return solve_impl(problem, solution, tolerance, false, nullptr, nullptr);
        } catch (const std::exception& error) {
            std::fprintf(stderr, "[termin-qopt] equality QP failed with an exception: %s\n", error.what());
        } catch (...) {
            std::fprintf(stderr, "[termin-qopt] equality QP failed with an unknown exception\n");
        }
        return failure(QpStatus::NumericalFailure, QpDiagnostic::DecompositionFailure);
    }

    QpSolveResult solve_homogeneous_equality_qp_batch(ConstDenseMatrixView hessian,
                                                      ConstDenseMatrixView equalities,
                                                      ConstDenseMatrixView gradients,
                                                      DenseMatrixView primal,
                                                      DenseMatrixView equality_dual,
                                                      QpTolerance tolerance) noexcept {
        try {
            if (!valid_tolerance(tolerance)) {
                return failure(QpStatus::InvalidInput, QpDiagnostic::InvalidTolerance);
            }
            for (const auto view :
                 {hessian, equalities, gradients, ConstDenseMatrixView(primal), ConstDenseMatrixView(equality_dual)}) {
                const QpDiagnostic diagnostic = validate_matrix(view);
                if (diagnostic != QpDiagnostic::None) {
                    return failure(QpStatus::InvalidInput, diagnostic);
                }
            }
            const std::size_t n = hessian.rows;
            const std::size_t m = equalities.rows;
            const std::size_t columns = gradients.columns;
            if (n == 0 || columns == 0 || hessian.columns != n || equalities.columns != n || gradients.rows != n ||
                primal.rows != n || primal.columns != columns || equality_dual.rows != m ||
                equality_dual.columns != columns) {
                return failure(QpStatus::InvalidInput, QpDiagnostic::DimensionMismatch);
            }
            const auto x_storage = storage_interval(primal);
            const auto dual_storage = storage_interval(equality_dual);
            if (repeats_elements(primal) || repeats_elements(equality_dual) ||
                (!dual_storage.empty && x_storage.first <= dual_storage.last && dual_storage.first <= x_storage.last)) {
                return failure(QpStatus::InvalidInput, QpDiagnostic::OverlappingOutputs);
            }
            if (!finite(gradients)) {
                return failure(QpStatus::InvalidInput, QpDiagnostic::NonFiniteInput);
            }

            // Stage every column so failures are transactional even when inputs alias outputs.
            Matrix responses(n, columns);
            Matrix duals(m, columns);
            const Vector targets = Vector::Zero(m);
            const auto outputs = [&](std::size_t col) -> EqualityQpSolutionView {
                return {{responses.col(col).data(), n, 1}, {m ? duals.col(col).data() : nullptr, m, 1}};
            };
            RankRevealingFactorization factor;
            // The first column prepares exactly the same coefficients and rank thresholds as the scalar solver.
            auto result = solve_impl({hessian, {gradients.data, n, gradients.row_stride}, equalities, view(targets)},
                                     outputs(0),
                                     tolerance,
                                     false,
                                     &factor,
                                     nullptr);
            if (result.status != QpStatus::Optimal) {
                return result;
            }
            const Vector feasible = Vector::Zero(m ? n : 0);
            const double feasibility_tolerance = scaled_tolerance(tolerance, 0.0);
            for (std::size_t col = 1; col < columns; ++col) {
                const Vector gradient = copy_vector({&gradients(0, col), n, gradients.row_stride});
                const auto current =
                    solve_factored_gradient(factor, gradient, feasible, targets, feasibility_tolerance, outputs(col));
                if (current.status != QpStatus::Optimal) {
                    return current;
                }
                result.stationarity_linf = std::max(result.stationarity_linf, current.stationarity_linf);
                result.equality_linf = std::max(result.equality_linf, current.equality_linf);
            }
            for (std::size_t col = 0; col < columns; ++col) {
                for (std::size_t row = 0; row < n; ++row) {
                    primal(row, col) = responses(row, col);
                }
                for (std::size_t row = 0; row < m; ++row) {
                    equality_dual(row, col) = duals(row, col);
                }
            }
            return result;
        } catch (const std::exception& error) {
            std::fprintf(stderr, "[termin-qopt] batch equality QP failed: %s\n", error.what());
        } catch (...) {
            std::fprintf(stderr, "[termin-qopt] batch equality QP failed with an unknown exception\n");
        }
        return failure(QpStatus::NumericalFailure, QpDiagnostic::DecompositionFailure);
    }

    QpSolveResult detail::solve_equality_qp_spd_first(EqualityQpProblemView problem,
                                                      EqualityQpSolutionView solution,
                                                      QpTolerance tolerance) noexcept {
        try {
            return solve_impl(problem, solution, tolerance, true, nullptr, nullptr);
        } catch (const std::exception& error) {
            std::fprintf(stderr,
                         "[termin-qopt] SPD-first equality QP failed with an "
                         "exception: %s\n",
                         error.what());
        } catch (...) {
            std::fprintf(stderr,
                         "[termin-qopt] SPD-first equality QP failed with an unknown "
                         "exception\n");
        }
        return failure(QpStatus::NumericalFailure, QpDiagnostic::DecompositionFailure);
    }

} // namespace termin::qopt
