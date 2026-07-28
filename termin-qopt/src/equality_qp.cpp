#include <termin/qopt/equality_qp.hpp>

#include "qp_internal.hpp"

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
                                       QpTolerance tolerance) {
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
  const Matrix equalities = copy_matrix(problem.equalities);
  const Vector equality_targets = copy_vector(problem.equality_targets);

  const double hessian_scale = matrix_linf(input_hessian);
  const double symmetry_residual =
      matrix_linf(input_hessian - input_hessian.transpose());
  if (symmetry_residual > tolerance.symmetry * std::max(1.0, hessian_scale)) {
    return failure(QpStatus::InvalidInput, QpDiagnostic::NonSymmetricHessian);
  }
  const Matrix hessian = 0.5 * (input_hessian + input_hessian.transpose());

  const Eigen::Index variable_count = static_cast<Eigen::Index>(variables);
  const Eigen::Index constraint_count = static_cast<Eigen::Index>(constraints);
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

  const Vector feasibility_error = equalities * feasible - equality_targets;
  const double feasibility_scale =
      std::max(linf(equalities * feasible), linf(equality_targets));
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
  }

  const Vector stationarity_error =
      objective_gradient + equalities.transpose() * equality_dual;
  const Vector equality_error = equalities * primal - equality_targets;
  const double stationarity_scale = std::max({
      1.0,
      linf(hessian * primal),
      linf(gradient),
      linf(equalities.transpose() * equality_dual),
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
    return solve_impl(problem, solution, tolerance);
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

} // namespace termin::qopt
