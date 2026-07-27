#include <termin/qopt/equality_qp.hpp>

#include <Eigen/Core>
#include <Eigen/Eigenvalues>
#include <Eigen/SVD>

#include <algorithm>
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <exception>
#include <limits>
#include <utility>

namespace termin::qopt {
namespace {

using Matrix = Eigen::Matrix<double, Eigen::Dynamic, Eigen::Dynamic>;
using Vector = Eigen::Matrix<double, Eigen::Dynamic, 1>;

[[nodiscard]] QpSolveResult failure(QpStatus status,
                                    QpDiagnostic diagnostic) noexcept {
  QpSolveResult result;
  result.status = status;
  result.diagnostic = diagnostic;
  return result;
}

[[nodiscard]] QpDiagnostic validate_vector(ConstDenseVectorView view) noexcept {
  if (view.size == 0) {
    return QpDiagnostic::None;
  }
  if (view.data == nullptr) {
    return QpDiagnostic::NullData;
  }
  if (view.stride == 0) {
    return QpDiagnostic::InvalidStride;
  }
  return QpDiagnostic::None;
}

[[nodiscard]] QpDiagnostic validate_vector(DenseVectorView view) noexcept {
  return validate_vector(ConstDenseVectorView{view});
}

[[nodiscard]] QpDiagnostic validate_matrix(ConstDenseMatrixView view) noexcept {
  if (view.rows == 0 || view.columns == 0) {
    return QpDiagnostic::None;
  }
  if (view.data == nullptr) {
    return QpDiagnostic::NullData;
  }
  if (view.row_stride == 0 || view.column_stride == 0) {
    return QpDiagnostic::InvalidStride;
  }
  return QpDiagnostic::None;
}

[[nodiscard]] bool finite(ConstDenseVectorView view) noexcept {
  for (std::size_t index = 0; index < view.size; ++index) {
    if (!std::isfinite(view[index])) {
      return false;
    }
  }
  return true;
}

[[nodiscard]] bool finite(ConstDenseMatrixView view) noexcept {
  for (std::size_t row = 0; row < view.rows; ++row) {
    for (std::size_t column = 0; column < view.columns; ++column) {
      if (!std::isfinite(view(row, column))) {
        return false;
      }
    }
  }
  return true;
}

[[nodiscard]] Vector copy_vector(ConstDenseVectorView view) {
  Vector result(static_cast<Eigen::Index>(view.size));
  for (std::size_t index = 0; index < view.size; ++index) {
    result[static_cast<Eigen::Index>(index)] = view[index];
  }
  return result;
}

[[nodiscard]] Matrix copy_matrix(ConstDenseMatrixView view) {
  Matrix result(static_cast<Eigen::Index>(view.rows),
                static_cast<Eigen::Index>(view.columns));
  for (std::size_t row = 0; row < view.rows; ++row) {
    for (std::size_t column = 0; column < view.columns; ++column) {
      result(static_cast<Eigen::Index>(row),
             static_cast<Eigen::Index>(column)) = view(row, column);
    }
  }
  return result;
}

void copy_to_view(const Vector &source, DenseVectorView destination) noexcept {
  for (std::size_t index = 0; index < destination.size; ++index) {
    destination[index] = source[static_cast<Eigen::Index>(index)];
  }
}

[[nodiscard]] double linf(const Vector &value) noexcept {
  return value.size() == 0 ? 0.0 : value.cwiseAbs().maxCoeff();
}

[[nodiscard]] double matrix_linf(const Matrix &value) noexcept {
  return value.size() == 0 ? 0.0 : value.cwiseAbs().maxCoeff();
}

[[nodiscard]] double scaled_tolerance(QpTolerance tolerance,
                                      double scale) noexcept {
  return tolerance.absolute + tolerance.relative * std::max(1.0, scale);
}

[[nodiscard]] bool valid_tolerance(QpTolerance tolerance) noexcept {
  return std::isfinite(tolerance.absolute) &&
         std::isfinite(tolerance.relative) &&
         std::isfinite(tolerance.symmetry) && tolerance.absolute >= 0.0 &&
         tolerance.relative >= 0.0 && tolerance.symmetry >= 0.0;
}

struct AddressInterval {
  std::uintptr_t first = 0;
  std::uintptr_t last = 0;
  bool empty = true;
};

[[nodiscard]] AddressInterval address_interval(DenseVectorView view) noexcept {
  if (view.size == 0 || view.data == nullptr) {
    return {};
  }

  constexpr std::uintptr_t max_address =
      std::numeric_limits<std::uintptr_t>::max();
  const std::uintptr_t base = reinterpret_cast<std::uintptr_t>(view.data);
  const std::uintptr_t stride_magnitude =
      view.stride >= 0 ? static_cast<std::uintptr_t>(view.stride)
                       : static_cast<std::uintptr_t>(-(view.stride + 1)) + 1;
  const std::uintptr_t element_count = view.size - 1;
  if (stride_magnitude > max_address / sizeof(double) ||
      element_count > max_address / (stride_magnitude * sizeof(double))) {
    return {0, max_address, false};
  }

  const std::uintptr_t span = element_count * stride_magnitude * sizeof(double);
  const std::uintptr_t tail = sizeof(double) - 1;
  if (view.stride >= 0) {
    if (span > max_address - base || tail > max_address - base - span) {
      return {0, max_address, false};
    }
    return {base, base + span + tail, false};
  }
  if (span > base || tail > max_address - base) {
    return {0, max_address, false};
  }
  return {base - span, base + tail, false};
}

[[nodiscard]] bool overlaps(DenseVectorView left,
                            DenseVectorView right) noexcept {
  const AddressInterval left_interval = address_interval(left);
  const AddressInterval right_interval = address_interval(right);
  if (left_interval.empty || right_interval.empty) {
    return false;
  }
  return left_interval.first <= right_interval.last &&
         right_interval.first <= left_interval.last;
}

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
