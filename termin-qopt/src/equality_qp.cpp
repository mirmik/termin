#include <termin/qopt/equality_qp.hpp>

#include "qp_internal.hpp"

#include <Eigen/Cholesky>
#include <Eigen/Eigenvalues>
#include <Eigen/SVD>

#include <algorithm>
#include <cmath>
#include <cstdio>
#include <exception>
#include <utility>

namespace termin::qopt {
namespace {

using namespace detail;

[[nodiscard]] QpSolveResult solve_impl(EqualityQpProblemView problem,
                                       EqualityQpSolutionView solution,
                                       QpTolerance tolerance,
                                       bool try_spd_fast_path) {
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
  if (variables == 0 || problem.hessian.columns != variables ||
      problem.gradient.size != variables ||
      problem.equalities.columns != variables ||
      problem.equality_targets.size != constraints ||
      solution.primal.size != variables ||
      solution.equality_dual.size != constraints) {
    return failure(QpStatus::InvalidInput, QpDiagnostic::DimensionMismatch);
  }
  if (overlaps(solution.primal, solution.equality_dual)) {
    return failure(QpStatus::InvalidInput, QpDiagnostic::OverlappingOutputs);
  }
  if (!finite(problem.hessian) || !finite(problem.gradient) ||
      !finite(problem.equalities) || !finite(problem.equality_targets)) {
    return failure(QpStatus::InvalidInput, QpDiagnostic::NonFiniteInput);
  }

  const Matrix input_hessian = copy_matrix(problem.hessian);
  const Vector gradient = copy_vector(problem.gradient);
  const Matrix input_equalities = copy_matrix(problem.equalities);
  const Vector input_equality_targets = copy_vector(problem.equality_targets);

  const double hessian_scale = matrix_linf(input_hessian);
  const double symmetry_residual =
      matrix_linf(input_hessian - input_hessian.transpose());
  if (symmetry_residual > tolerance.symmetry * std::max(1.0, hessian_scale)) {
    return failure(QpStatus::InvalidInput, QpDiagnostic::NonSymmetricHessian);
  }
  const Matrix hessian = 0.5 * (input_hessian + input_hessian.transpose());

  const Eigen::Index variable_count = static_cast<Eigen::Index>(variables);
  const Eigen::Index constraint_count = static_cast<Eigen::Index>(constraints);
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
  if (try_spd_fast_path && constraint_count > 0 &&
      constraint_count <= variable_count) {
    Eigen::LLT<Matrix> hessian_factor(hessian);
    if (hessian_factor.info() == Eigen::Success) {
      const Vector hessian_pivots =
          hessian_factor.matrixL().toDenseMatrix().diagonal().array().square();
      const double hessian_rank_tolerance =
          scaled_tolerance(tolerance, hessian_scale);
      if (hessian_pivots.size() > 0 &&
          hessian_pivots.minCoeff() > hessian_rank_tolerance) {
        const Vector free_primal = hessian_factor.solve(-gradient);
        const Matrix constraint_response =
            hessian_factor.solve(equalities.transpose());
        const Matrix raw_schur = equalities * constraint_response;
        const Matrix schur = 0.5 * (raw_schur + raw_schur.transpose());

        Eigen::LLT<Matrix> schur_factor(schur);
        bool schur_full_rank = false;
        if (schur_factor.info() == Eigen::Success) {
          const Vector schur_pivots = schur_factor.matrixL()
                                            .toDenseMatrix()
                                            .diagonal()
                                            .array()
                                            .square();
          schur_full_rank =
              schur_pivots.minCoeff() >
              scaled_tolerance(tolerance, matrix_linf(schur));
        }

        if (schur_full_rank) {
          const Vector normalized_dual = schur_factor.solve(
              equalities * free_primal - equality_targets);
          const Vector primal =
              free_primal - constraint_response * normalized_dual;
          Vector equality_dual = normalized_dual;
          equality_dual.array() /= equality_row_scales.array();

          const Vector objective_gradient = hessian * primal + gradient;
          const Vector stationarity_error =
              objective_gradient +
              input_equalities.transpose() * equality_dual;
          const Vector equality_error =
              input_equalities * primal - input_equality_targets;
          const double feasibility_scale =
              std::max(linf(input_equalities * primal),
                       linf(input_equality_targets));
          const double feasibility_tolerance =
              scaled_tolerance(tolerance, feasibility_scale);
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
          if (result.stationarity_linf <=
                  scaled_tolerance(tolerance, stationarity_scale) &&
              result.equality_linf <= feasibility_tolerance) {
            copy_to_view(primal, solution.primal);
            copy_to_view(equality_dual, solution.equality_dual);
            return result;
          }
        }
      }
    }
  }

  Matrix nullspace;
  Vector feasible = Vector::Zero(variable_count);
  Matrix left_range;
  Matrix right_range;
  Vector inverse_singular_values;
  std::size_t constraint_rank = 0;

  if (constraint_count == 0) {
    nullspace = Matrix::Identity(variable_count, variable_count);
    left_range.resize(0, 0);
    right_range.resize(variable_count, 0);
    inverse_singular_values.resize(0);
  } else {
    Eigen::JacobiSVD<Matrix> svd(equalities,
                                 Eigen::ComputeFullU | Eigen::ComputeFullV);
    if (svd.info() != Eigen::Success) {
      std::fprintf(stderr,
                   "[termin-qopt] equality QP constraint SVD failed: "
                   "variables=%zu constraints=%zu scale=%g\n",
                   variables, constraints, matrix_linf(equalities));
      return failure(QpStatus::NumericalFailure,
                     QpDiagnostic::DecompositionFailure);
    }

    const Vector singular_values = svd.singularValues();
    const double singular_scale = singular_values.size() == 0
                                      ? 0.0
                                      : singular_values.cwiseAbs().maxCoeff();
    const double rank_tolerance = scaled_tolerance(tolerance, singular_scale);
    for (Eigen::Index index = 0; index < singular_values.size(); ++index) {
      if (singular_values[index] > rank_tolerance) {
        ++constraint_rank;
      }
    }

    const Eigen::Index rank = static_cast<Eigen::Index>(constraint_rank);
    left_range = svd.matrixU().leftCols(rank);
    right_range = svd.matrixV().leftCols(rank);
    inverse_singular_values.resize(rank);
    for (Eigen::Index index = 0; index < rank; ++index) {
      inverse_singular_values[index] = 1.0 / singular_values[index];
    }

    if (rank > 0) {
      feasible = right_range * inverse_singular_values.asDiagonal() *
                 left_range.transpose() * equality_targets;
    }
    nullspace = svd.matrixV().rightCols(variable_count - rank);
  }

  const Vector feasibility_error =
      input_equalities * feasible - input_equality_targets;
  const double feasibility_scale =
      std::max(linf(input_equalities * feasible),
               linf(input_equality_targets));
  const double feasibility_tolerance =
      scaled_tolerance(tolerance, feasibility_scale);
  if (linf(feasibility_error) > feasibility_tolerance) {
    QpSolveResult result =
        failure(QpStatus::Infeasible, QpDiagnostic::InconsistentEqualities);
    result.equality_linf = linf(feasibility_error);
    result.constraint_rank = constraint_rank;
    return result;
  }

  Vector primal = feasible;
  const Eigen::Index reduced_variables = nullspace.cols();
  std::size_t reduced_rank = 0;
  if (reduced_variables > 0) {
    const Matrix raw_reduced_hessian =
        nullspace.transpose() * hessian * nullspace;
    const Matrix reduced_hessian =
        0.5 * (raw_reduced_hessian + raw_reduced_hessian.transpose());
    const Vector reduced_gradient =
        nullspace.transpose() * (hessian * feasible + gradient);

    Eigen::SelfAdjointEigenSolver<Matrix> eigensolver(reduced_hessian);
    if (eigensolver.info() != Eigen::Success) {
      std::fprintf(stderr,
                   "[termin-qopt] equality QP reduced Hessian decomposition "
                   "failed: variables=%zu constraints=%zu rank=%zu "
                   "reduced=%td scale=%g finite=%d\n",
                   variables, constraints, constraint_rank,
                   static_cast<std::ptrdiff_t>(reduced_variables),
                   matrix_linf(reduced_hessian),
                   reduced_hessian.allFinite() ? 1 : 0);
      return failure(QpStatus::NumericalFailure,
                     QpDiagnostic::DecompositionFailure);
    }

    const Vector eigenvalues = eigensolver.eigenvalues();
    const Matrix eigenvectors = eigensolver.eigenvectors();
    const double eigenvalue_scale = linf(eigenvalues);
    const double curvature_tolerance =
        scaled_tolerance(tolerance, eigenvalue_scale);
    const Vector spectral_gradient =
        eigenvectors.transpose() * reduced_gradient;
    const double gradient_tolerance =
        scaled_tolerance(tolerance, linf(reduced_gradient));
    Vector spectral_solution = Vector::Zero(reduced_variables);

    for (Eigen::Index index = 0; index < reduced_variables; ++index) {
      if (eigenvalues[index] > curvature_tolerance) {
        ++reduced_rank;
      }
    }
    for (Eigen::Index index = 0; index < reduced_variables; ++index) {
      const double eigenvalue = eigenvalues[index];
      if (eigenvalue < -curvature_tolerance) {
        QpSolveResult result =
            failure(QpStatus::NonConvex, QpDiagnostic::NegativeCurvature);
        result.constraint_rank = constraint_rank;
        return result;
      }
      if (eigenvalue > curvature_tolerance) {
        spectral_solution[index] = -spectral_gradient[index] / eigenvalue;
      } else if (std::abs(spectral_gradient[index]) > gradient_tolerance) {
        QpSolveResult result = failure(QpStatus::Unbounded,
                                       QpDiagnostic::LinearDescentInNullspace);
        result.constraint_rank = constraint_rank;
        result.reduced_hessian_rank = reduced_rank;
        return result;
      }
    }

    primal += nullspace * eigenvectors * spectral_solution;
  }

  const Vector objective_gradient = hessian * primal + gradient;
  Vector equality_dual = Vector::Zero(constraint_count);
  if (constraint_rank > 0) {
    equality_dual = -left_range * inverse_singular_values.asDiagonal() *
                    right_range.transpose() * objective_gradient;
    equality_dual.array() /= equality_row_scales.array();
  }

  const Vector stationarity_error =
      objective_gradient + input_equalities.transpose() * equality_dual;
  const Vector equality_error =
      input_equalities * primal - input_equality_targets;
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
  result.constraint_rank = constraint_rank;
  result.reduced_hessian_rank = reduced_rank;

  if (result.stationarity_linf >
          scaled_tolerance(tolerance, stationarity_scale) ||
      result.equality_linf > feasibility_tolerance) {
    result.status = QpStatus::NumericalFailure;
    result.diagnostic = QpDiagnostic::ResidualTooLarge;
    return result;
  }

  copy_to_view(primal, solution.primal);
  copy_to_view(equality_dual, solution.equality_dual);
  return result;
}

} // namespace

QpSolveResult solve_equality_qp(EqualityQpProblemView problem,
                                EqualityQpSolutionView solution,
                                QpTolerance tolerance) noexcept {
  try {
    return solve_impl(problem, solution, tolerance, false);
  } catch (const std::exception &error) {
    std::fprintf(stderr,
                 "[termin-qopt] equality QP failed with an exception: %s\n",
                 error.what());
  } catch (...) {
    std::fprintf(
        stderr, "[termin-qopt] equality QP failed with an unknown exception\n");
  }
  return failure(QpStatus::NumericalFailure,
                 QpDiagnostic::DecompositionFailure);
}

QpSolveResult detail::solve_equality_qp_spd_first(
    EqualityQpProblemView problem, EqualityQpSolutionView solution,
    QpTolerance tolerance) noexcept {
  try {
    return solve_impl(problem, solution, tolerance, true);
  } catch (const std::exception &error) {
    std::fprintf(stderr,
                 "[termin-qopt] SPD-first equality QP failed with an "
                 "exception: %s\n",
                 error.what());
  } catch (...) {
    std::fprintf(stderr,
                 "[termin-qopt] SPD-first equality QP failed with an unknown "
                 "exception\n");
  }
  return failure(QpStatus::NumericalFailure,
                 QpDiagnostic::DecompositionFailure);
}

} // namespace termin::qopt
