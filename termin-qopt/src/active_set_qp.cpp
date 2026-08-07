#include <termin/qopt/active_set_qp.hpp>

#include <termin/qopt/equality_qp.hpp>

#include "qp_internal.hpp"

#include <Eigen/Eigenvalues>
#include <Eigen/SVD>

#include <cmath>
#include <cstdint>
#include <cstdio>
#include <exception>
#include <iterator>
#include <limits>
#include <optional>
#include <utility>
#include <vector>

namespace termin::qopt {
namespace {

using namespace detail;

enum class ConstraintFamily : std::uint8_t {
  Inequality,
  LowerBound,
  UpperBound,
};

struct ConstraintOrigin {
  ConstraintFamily family;
  std::size_t index;
};

struct NormalizedInequalities {
  Matrix matrix;
  Vector limits;
  std::vector<ConstraintOrigin> origins;
};

struct EqualityResult {
  QpSolveResult result;
  Vector primal;
  Vector dual;
};

struct CoreResult {
  QpSolveResult result;
  Vector primal;
  Vector equality_dual;
  Vector active_dual;
  std::vector<std::size_t> active;
};

struct DirectionResult {
  QpStatus status = QpStatus::NumericalFailure;
  QpDiagnostic diagnostic = QpDiagnostic::DecompositionFailure;
  Vector direction;
};

[[nodiscard]] bool
any_outputs_overlap(ActiveSetQpSolutionView solution) noexcept {
  const DenseVectorView outputs[] = {
      solution.primal,           solution.equality_dual,
      solution.inequality_dual,  solution.lower_bound_dual,
      solution.upper_bound_dual,
  };
  for (std::size_t left = 0; left < std::size(outputs); ++left) {
    for (std::size_t right = left + 1; right < std::size(outputs); ++right) {
      if (overlaps(outputs[left], outputs[right])) {
        return true;
      }
    }
  }
  return false;
}

[[nodiscard]] EqualityResult solve_equalities(const Matrix &hessian,
                                              const Vector &gradient,
                                              const Matrix &equalities,
                                              const Vector &targets,
                                              QpTolerance tolerance,
                                              bool prefer_spd = false) {
  EqualityResult solved;
  solved.primal = Vector::Zero(hessian.rows());
  solved.dual = Vector::Zero(equalities.rows());
  const EqualityQpProblemView problem = {
      view(hessian), view(gradient), view(equalities), view(targets)};
  const EqualityQpSolutionView solution = {view(solved.primal),
                                           view(solved.dual)};
  solved.result =
      prefer_spd ? solve_equality_qp_spd_first(problem, solution, tolerance)
                 : solve_equality_qp(problem, solution, tolerance);
  return solved;
}

[[nodiscard]] Matrix nullspace_basis(const Matrix &matrix,
                                     QpTolerance tolerance, bool &success) {
  const Eigen::Index variables = matrix.cols();
  if (matrix.rows() == 0) {
    success = true;
    return Matrix::Identity(variables, variables);
  }

  Matrix normalized = matrix;
  for (Eigen::Index row = 0; row < normalized.rows(); ++row) {
    const double row_scale = normalized.row(row).cwiseAbs().maxCoeff();
    if (row_scale > 0.0) {
      normalized.row(row) /= row_scale;
    }
  }

  Eigen::JacobiSVD<Matrix> svd(normalized,
                               Eigen::ComputeFullU | Eigen::ComputeFullV);
  if (svd.info() != Eigen::Success) {
    success = false;
    return {};
  }
  const Vector singular_values = svd.singularValues();
  const double scale = linf(singular_values);
  const double rank_tolerance = scaled_tolerance(tolerance, scale);
  Eigen::Index rank = 0;
  for (Eigen::Index index = 0; index < singular_values.size(); ++index) {
    if (singular_values[index] > rank_tolerance) {
      ++rank;
    }
  }
  success = true;
  return svd.matrixV().rightCols(variables - rank);
}

[[nodiscard]] QpSolveResult check_convexity(const Matrix &hessian,
                                            const Matrix &equalities,
                                            QpTolerance tolerance) {
  bool success = false;
  const Matrix nullspace = nullspace_basis(equalities, tolerance, success);
  if (!success) {
    return failure(QpStatus::NumericalFailure,
                   QpDiagnostic::DecompositionFailure);
  }
  if (nullspace.cols() == 0) {
    QpSolveResult result;
    result.status = QpStatus::Optimal;
    return result;
  }

  const Matrix raw_reduced = nullspace.transpose() * hessian * nullspace;
  const Matrix reduced = 0.5 * (raw_reduced + raw_reduced.transpose());
  Eigen::SelfAdjointEigenSolver<Matrix> eigensolver(reduced);
  if (eigensolver.info() != Eigen::Success) {
    return failure(QpStatus::NumericalFailure,
                   QpDiagnostic::DecompositionFailure);
  }
  const Vector eigenvalues = eigensolver.eigenvalues();
  const double curvature_tolerance =
      scaled_tolerance(tolerance, linf(eigenvalues));
  if (eigenvalues.size() > 0 && eigenvalues.minCoeff() < -curvature_tolerance) {
    return failure(QpStatus::NonConvex, QpDiagnostic::NegativeCurvature);
  }

  QpSolveResult result;
  result.status = QpStatus::Optimal;
  return result;
}

[[nodiscard]] DirectionResult recession_direction(const Matrix &hessian,
                                                  const Vector &gradient,
                                                  const Matrix &working,
                                                  const Vector &primal,
                                                  QpTolerance tolerance) {
  bool success = false;
  const Matrix nullspace = nullspace_basis(working, tolerance, success);
  if (!success) {
    std::fprintf(stderr,
                 "[termin-qopt] active-set recession nullspace SVD failed: "
                 "variables=%td constraints=%td scale=%g\n",
                 working.cols(), working.rows(), matrix_linf(working));
    return {};
  }
  if (nullspace.cols() == 0) {
    std::fprintf(stderr,
                 "[termin-qopt] active-set recession has empty nullspace: "
                 "variables=%td constraints=%td\n",
                 working.cols(), working.rows());
    return {};
  }

  const Matrix raw_reduced = nullspace.transpose() * hessian * nullspace;
  const Matrix reduced = 0.5 * (raw_reduced + raw_reduced.transpose());
  Eigen::SelfAdjointEigenSolver<Matrix> eigensolver(reduced);
  if (eigensolver.info() != Eigen::Success) {
    std::fprintf(stderr,
                 "[termin-qopt] active-set recession reduced Hessian "
                 "decomposition failed: variables=%td constraints=%td "
                 "reduced=%td scale=%g finite=%d\n",
                 working.cols(), working.rows(), nullspace.cols(),
                 matrix_linf(reduced), reduced.allFinite() ? 1 : 0);
    return {};
  }

  const Vector eigenvalues = eigensolver.eigenvalues();
  const Matrix eigenvectors = eigensolver.eigenvectors();
  const double curvature_tolerance =
      scaled_tolerance(tolerance, linf(eigenvalues));
  if (eigenvalues.size() > 0 && eigenvalues.minCoeff() < -curvature_tolerance) {
    DirectionResult result;
    result.status = QpStatus::NonConvex;
    result.diagnostic = QpDiagnostic::NegativeCurvature;
    return result;
  }

  const Vector objective_gradient = hessian * primal + gradient;
  const Vector spectral_gradient =
      eigenvectors.transpose() * nullspace.transpose() * objective_gradient;
  Vector coefficients = Vector::Zero(eigenvalues.size());
  for (Eigen::Index index = 0; index < eigenvalues.size(); ++index) {
    if (std::abs(eigenvalues[index]) <= curvature_tolerance) {
      coefficients[index] = -spectral_gradient[index];
    }
  }

  Vector direction = nullspace * eigenvectors * coefficients;
  const double scale = linf(direction);
  if (scale == 0.0) {
    std::fprintf(stderr,
                 "[termin-qopt] active-set equality subproblem reported an "
                 "unbounded direction, but its recomputed nullspace "
                 "projection is zero\n");
    return {};
  }
  direction /= scale;

  DirectionResult result;
  result.status = QpStatus::Unbounded;
  result.diagnostic = QpDiagnostic::LinearDescentInNullspace;
  result.direction = std::move(direction);
  return result;
}

[[nodiscard]] bool contains(const std::vector<std::size_t> &indices,
                            std::size_t index) {
  return std::find(indices.begin(), indices.end(), index) != indices.end();
}

[[nodiscard]] CoreResult solve_feasible_core(
    const Matrix &hessian, const Vector &gradient, const Matrix &equalities,
    const Vector &targets, const Matrix &inequalities, const Vector &limits,
    Vector primal, std::vector<std::size_t> active,
    const ActiveSetQpOptions &options, std::size_t &iterations) {
  const Eigen::Index equality_count = equalities.rows();
  const double direction_tolerance =
      scaled_tolerance(options.tolerance, matrix_linf(inequalities));

  while (iterations < options.max_iterations) {
    ++iterations;

    Matrix working(equalities.rows() + static_cast<Eigen::Index>(active.size()),
                   hessian.rows());
    Vector working_targets(targets.size() +
                           static_cast<Eigen::Index>(active.size()));
    if (equalities.rows() > 0) {
      working.topRows(equalities.rows()) = equalities;
      working_targets.head(targets.size()) = targets;
    }
    for (std::size_t offset = 0; offset < active.size(); ++offset) {
      working.row(equality_count + static_cast<Eigen::Index>(offset)) =
          inequalities.row(static_cast<Eigen::Index>(active[offset]));
      working_targets[equality_count + static_cast<Eigen::Index>(offset)] =
          limits[static_cast<Eigen::Index>(active[offset])];
    }

    const EqualityResult subproblem = solve_equalities(
        hessian, gradient, working, working_targets, options.tolerance,
        !active.empty());
    Vector direction;
    bool finite_target = false;
    if (subproblem.result.status == QpStatus::Optimal) {
      direction = subproblem.primal - primal;
      finite_target = true;
    } else if (subproblem.result.status == QpStatus::Unbounded) {
      DirectionResult recession = recession_direction(
          hessian, gradient, working, primal, options.tolerance);
      if (recession.status != QpStatus::Unbounded) {
        CoreResult result;
        result.result =
            failure(recession.status, recession.diagnostic, iterations);
        result.result.active_set_size = active.size();
        return result;
      }
      direction = std::move(recession.direction);
    } else {
      CoreResult result;
      result.result = subproblem.result;
      result.result.iterations = iterations;
      result.result.active_set_size = active.size();
      if (result.result.status == QpStatus::Infeasible) {
        result.result.status = QpStatus::NumericalFailure;
        result.result.diagnostic = QpDiagnostic::ResidualTooLarge;
      }
      return result;
    }

    double step = finite_target ? 1.0 : std::numeric_limits<double>::infinity();
    std::optional<std::size_t> blocker;
    for (Eigen::Index row = 0; row < inequalities.rows(); ++row) {
      const std::size_t index = static_cast<std::size_t>(row);
      if (contains(active, index)) {
        continue;
      }
      const double rate = inequalities.row(row).dot(direction);
      if (rate <= direction_tolerance) {
        continue;
      }
      const double slack = limits[row] - inequalities.row(row).dot(primal);
      const double candidate = std::max(0.0, slack / rate);
      const double tie_tolerance =
          scaled_tolerance(options.tolerance, std::max(step, candidate));
      if (candidate < step - tie_tolerance ||
          (!blocker.has_value() && !finite_target &&
           std::isfinite(candidate)) ||
          (std::abs(candidate - step) <= tie_tolerance && blocker.has_value() &&
           index < *blocker)) {
        step = candidate;
        blocker = index;
      }
    }

    const double step_tolerance =
        scaled_tolerance(options.tolerance, std::max(1.0, std::abs(step)));
    const bool blocked_before_target =
        blocker.has_value() && (!finite_target || step < 1.0 - step_tolerance);
    if (blocked_before_target) {
      primal += step * direction;
      active.push_back(*blocker);
      continue;
    }

    if (!finite_target) {
      CoreResult result;
      result.result =
          failure(QpStatus::Unbounded, QpDiagnostic::LinearDescentInNullspace,
                  iterations);
      result.result.active_set_size = active.size();
      return result;
    }

    primal = subproblem.primal;
    std::optional<std::size_t> removal_offset;
    double most_negative = -scaled_tolerance(options.tolerance, 1.0);
    for (std::size_t offset = 0; offset < active.size(); ++offset) {
      const double multiplier =
          subproblem.dual[equality_count + static_cast<Eigen::Index>(offset)];
      if (multiplier < most_negative) {
        most_negative = multiplier;
        removal_offset = offset;
      }
    }
    if (removal_offset.has_value()) {
      active.erase(active.begin() +
                   static_cast<std::ptrdiff_t>(*removal_offset));
      continue;
    }

    CoreResult result;
    result.result = subproblem.result;
    result.result.iterations = iterations;
    result.result.active_set_size = active.size();
    result.primal = std::move(primal);
    result.equality_dual = subproblem.dual.head(equality_count);
    result.active_dual.resize(static_cast<Eigen::Index>(active.size()));
    for (std::size_t offset = 0; offset < active.size(); ++offset) {
      result.active_dual[static_cast<Eigen::Index>(offset)] =
          subproblem.dual[equality_count + static_cast<Eigen::Index>(offset)];
    }
    result.active = std::move(active);
    return result;
  }

  CoreResult result;
  result.result = failure(QpStatus::NumericalFailure,
                          QpDiagnostic::IterationLimit, iterations);
  result.result.active_set_size = active.size();
  return result;
}

[[nodiscard]] NormalizedInequalities
normalize_inequalities(const Matrix &inequalities, const Vector &limits,
                       const Vector &lower, const Vector &upper) {
  std::size_t finite_lower = 0;
  std::size_t finite_upper = 0;
  for (Eigen::Index index = 0; index < lower.size(); ++index) {
    finite_lower += std::isfinite(lower[index]) ? 1 : 0;
  }
  for (Eigen::Index index = 0; index < upper.size(); ++index) {
    finite_upper += std::isfinite(upper[index]) ? 1 : 0;
  }

  const Eigen::Index rows = inequalities.rows() +
                            static_cast<Eigen::Index>(finite_lower) +
                            static_cast<Eigen::Index>(finite_upper);
  NormalizedInequalities normalized;
  normalized.matrix = Matrix::Zero(rows, inequalities.cols());
  normalized.limits.resize(rows);
  normalized.origins.reserve(static_cast<std::size_t>(rows));

  Eigen::Index row = 0;
  for (Eigen::Index index = 0; index < inequalities.rows(); ++index, ++row) {
    normalized.matrix.row(row) = inequalities.row(index);
    normalized.limits[row] = limits[index];
    normalized.origins.push_back(
        {ConstraintFamily::Inequality, static_cast<std::size_t>(index)});
  }
  for (Eigen::Index index = 0; index < lower.size(); ++index) {
    if (!std::isfinite(lower[index])) {
      continue;
    }
    normalized.matrix(row, index) = -1.0;
    normalized.limits[row] = -lower[index];
    normalized.origins.push_back(
        {ConstraintFamily::LowerBound, static_cast<std::size_t>(index)});
    ++row;
  }
  for (Eigen::Index index = 0; index < upper.size(); ++index) {
    if (!std::isfinite(upper[index])) {
      continue;
    }
    normalized.matrix(row, index) = 1.0;
    normalized.limits[row] = upper[index];
    normalized.origins.push_back(
        {ConstraintFamily::UpperBound, static_cast<std::size_t>(index)});
    ++row;
  }
  return normalized;
}

[[nodiscard]] bool warm_mask_selected(ConstraintOrigin origin,
                                      ConstDenseVectorView inequality_mask,
                                      ConstDenseVectorView lower_mask,
                                      ConstDenseVectorView upper_mask) {
  switch (origin.family) {
  case ConstraintFamily::Inequality:
    return !inequality_mask.empty() && inequality_mask[origin.index] == 1.0;
  case ConstraintFamily::LowerBound:
    return !lower_mask.empty() && lower_mask[origin.index] == 1.0;
  case ConstraintFamily::UpperBound:
    return !upper_mask.empty() && upper_mask[origin.index] == 1.0;
  }
  return false;
}

[[nodiscard]] bool valid_mask(ConstDenseVectorView mask) noexcept {
  for (std::size_t index = 0; index < mask.size; ++index) {
    if (mask[index] != 0.0 && mask[index] != 1.0) {
      return false;
    }
  }
  return true;
}

[[nodiscard]] std::vector<std::size_t>
tight_constraints(const Matrix &inequalities, const Vector &limits,
                  const Vector &primal, double active_tolerance) {
  std::vector<std::size_t> active;
  for (Eigen::Index row = 0; row < inequalities.rows(); ++row) {
    if (std::abs(inequalities.row(row).dot(primal) - limits[row]) <=
        active_tolerance) {
      active.push_back(static_cast<std::size_t>(row));
    }
  }
  return active;
}

[[nodiscard]] CoreResult
find_feasible_point(const Matrix &equalities, const Vector &targets,
                    const Matrix &inequalities, const Vector &limits,
                    const Vector &seed, const ActiveSetQpOptions &options,
                    std::size_t &iterations) {
  const Eigen::Index variables = equalities.cols();
  Matrix phase_hessian = Matrix::Zero(variables + 1, variables + 1);
  phase_hessian(variables, variables) = 1.0;
  const Vector phase_gradient = Vector::Zero(variables + 1);

  Matrix phase_equalities = Matrix::Zero(equalities.rows(), variables + 1);
  if (equalities.rows() > 0) {
    phase_equalities.leftCols(variables) = equalities;
  }

  Matrix phase_inequalities =
      Matrix::Zero(inequalities.rows() + 1, variables + 1);
  Vector phase_limits(limits.size() + 1);
  if (inequalities.rows() > 0) {
    phase_inequalities.topLeftCorner(inequalities.rows(), variables) =
        inequalities;
    phase_inequalities.topRightCorner(inequalities.rows(), 1).setConstant(-1.0);
    phase_limits.head(limits.size()) = limits;
  }
  phase_inequalities(inequalities.rows(), variables) = -1.0;
  phase_limits[limits.size()] = 0.0;

  double maximum_violation = 0.0;
  if (inequalities.rows() > 0) {
    maximum_violation =
        std::max(0.0, (inequalities * seed - limits).maxCoeff());
  }
  const double margin =
      10.0 * scaled_tolerance(options.tolerance, maximum_violation);
  Vector phase_start(variables + 1);
  phase_start.head(variables) = seed;
  phase_start[variables] = maximum_violation + margin;

  const double working_set_tolerance = scaled_tolerance(
      options.tolerance,
      std::max(matrix_linf(phase_inequalities), linf(phase_limits)));
  std::vector<std::size_t> active = tight_constraints(
      phase_inequalities, phase_limits, phase_start, working_set_tolerance);
  return solve_feasible_core(phase_hessian, phase_gradient, phase_equalities,
                             targets, phase_inequalities, phase_limits,
                             std::move(phase_start), std::move(active), options,
                             iterations);
}

[[nodiscard]] QpSolveResult solve_impl(ActiveSetQpProblemView problem,
                                       ActiveSetQpSolutionView solution,
                                       ActiveSetQpWarmStartView warm_start,
                                       ActiveSetQpOptions options) {
  if (!valid_tolerance(options.tolerance)) {
    return failure(QpStatus::InvalidInput, QpDiagnostic::InvalidTolerance);
  }
  if (!std::isfinite(options.active_tolerance) ||
      options.active_tolerance < 0.0 || options.max_iterations == 0) {
    return failure(QpStatus::InvalidInput, QpDiagnostic::InvalidOptions);
  }

  const QpDiagnostic view_diagnostics[] = {
      validate_matrix(problem.hessian),
      validate_vector(problem.gradient),
      validate_matrix(problem.equalities),
      validate_vector(problem.equality_targets),
      validate_matrix(problem.inequalities),
      validate_vector(problem.inequality_limits),
      validate_vector(problem.lower_bounds),
      validate_vector(problem.upper_bounds),
      validate_vector(warm_start.primal),
      validate_vector(warm_start.active_inequalities),
      validate_vector(warm_start.active_lower_bounds),
      validate_vector(warm_start.active_upper_bounds),
      validate_vector(solution.primal),
      validate_vector(solution.equality_dual),
      validate_vector(solution.inequality_dual),
      validate_vector(solution.lower_bound_dual),
      validate_vector(solution.upper_bound_dual),
  };
  for (QpDiagnostic diagnostic : view_diagnostics) {
    if (diagnostic != QpDiagnostic::None) {
      return failure(QpStatus::InvalidInput, diagnostic);
    }
  }

  const std::size_t variables = problem.hessian.rows;
  const std::size_t equality_count = problem.equalities.rows;
  const std::size_t inequality_count = problem.inequalities.rows;
  const bool has_lower_bounds = !problem.lower_bounds.empty();
  const bool has_upper_bounds = !problem.upper_bounds.empty();
  if (variables == 0 || problem.hessian.columns != variables ||
      problem.gradient.size != variables ||
      problem.equalities.columns != variables ||
      problem.equality_targets.size != equality_count ||
      problem.inequalities.columns != variables ||
      problem.inequality_limits.size != inequality_count ||
      (has_lower_bounds && problem.lower_bounds.size != variables) ||
      (has_upper_bounds && problem.upper_bounds.size != variables) ||
      solution.primal.size != variables ||
      solution.equality_dual.size != equality_count ||
      solution.inequality_dual.size != inequality_count ||
      solution.lower_bound_dual.size != problem.lower_bounds.size ||
      solution.upper_bound_dual.size != problem.upper_bounds.size ||
      (!warm_start.primal.empty() && warm_start.primal.size != variables) ||
      (!warm_start.active_inequalities.empty() &&
       warm_start.active_inequalities.size != inequality_count) ||
      (!warm_start.active_lower_bounds.empty() &&
       warm_start.active_lower_bounds.size != problem.lower_bounds.size) ||
      (!warm_start.active_upper_bounds.empty() &&
       warm_start.active_upper_bounds.size != problem.upper_bounds.size)) {
    return failure(QpStatus::InvalidInput, QpDiagnostic::DimensionMismatch);
  }
  if (any_outputs_overlap(solution)) {
    return failure(QpStatus::InvalidInput, QpDiagnostic::OverlappingOutputs);
  }
  if (!finite(problem.hessian) || !finite(problem.gradient) ||
      !finite(problem.equalities) || !finite(problem.equality_targets) ||
      !finite(problem.inequalities) || !finite(problem.inequality_limits) ||
      (!warm_start.primal.empty() && !finite(warm_start.primal)) ||
      !finite(warm_start.active_inequalities) ||
      !finite(warm_start.active_lower_bounds) ||
      !finite(warm_start.active_upper_bounds)) {
    return failure(QpStatus::InvalidInput, QpDiagnostic::NonFiniteInput);
  }
  if (!valid_mask(warm_start.active_inequalities) ||
      !valid_mask(warm_start.active_lower_bounds) ||
      !valid_mask(warm_start.active_upper_bounds)) {
    return failure(QpStatus::InvalidInput, QpDiagnostic::InvalidWarmStart);
  }

  for (std::size_t index = 0; index < variables; ++index) {
    const double lower = has_lower_bounds
                             ? problem.lower_bounds[index]
                             : -std::numeric_limits<double>::infinity();
    const double upper = has_upper_bounds
                             ? problem.upper_bounds[index]
                             : std::numeric_limits<double>::infinity();
    if (std::isnan(lower) || std::isnan(upper) ||
        lower == std::numeric_limits<double>::infinity() ||
        upper == -std::numeric_limits<double>::infinity()) {
      return failure(QpStatus::InvalidInput, QpDiagnostic::InvalidBounds);
    }
  }

  const bool has_warm_masks = !warm_start.active_inequalities.empty() ||
                              !warm_start.active_lower_bounds.empty() ||
                              !warm_start.active_upper_bounds.empty();
  if (has_warm_masks && warm_start.primal.empty()) {
    return failure(QpStatus::InvalidInput, QpDiagnostic::InvalidWarmStart);
  }
  if (!warm_start.active_lower_bounds.empty()) {
    for (std::size_t index = 0; index < variables; ++index) {
      if (warm_start.active_lower_bounds[index] == 1.0 &&
          !std::isfinite(problem.lower_bounds[index])) {
        return failure(QpStatus::InvalidInput, QpDiagnostic::InvalidWarmStart);
      }
    }
  }
  if (!warm_start.active_upper_bounds.empty()) {
    for (std::size_t index = 0; index < variables; ++index) {
      if (warm_start.active_upper_bounds[index] == 1.0 &&
          !std::isfinite(problem.upper_bounds[index])) {
        return failure(QpStatus::InvalidInput, QpDiagnostic::InvalidWarmStart);
      }
    }
  }

  const Matrix input_hessian = copy_matrix(problem.hessian);
  const Vector gradient = copy_vector(problem.gradient);
  const Matrix equalities = copy_matrix(problem.equalities);
  const Vector equality_targets = copy_vector(problem.equality_targets);
  const Matrix inequalities = copy_matrix(problem.inequalities);
  const Vector inequality_limits = copy_vector(problem.inequality_limits);
  const Vector lower = copy_vector(problem.lower_bounds);
  const Vector upper = copy_vector(problem.upper_bounds);
  const Vector warm_primal = copy_vector(warm_start.primal);

  const double hessian_scale = matrix_linf(input_hessian);
  const double symmetry_residual =
      matrix_linf(input_hessian - input_hessian.transpose());
  if (symmetry_residual >
      options.tolerance.symmetry * std::max(1.0, hessian_scale)) {
    return failure(QpStatus::InvalidInput, QpDiagnostic::NonSymmetricHessian);
  }
  const Matrix hessian = 0.5 * (input_hessian + input_hessian.transpose());

  const NormalizedInequalities normalized =
      normalize_inequalities(inequalities, inequality_limits, lower, upper);
  const double working_set_tolerance = scaled_tolerance(
      options.tolerance,
      std::max(matrix_linf(normalized.matrix), linf(normalized.limits)));

  Matrix feasibility_hessian =
      Matrix::Identity(static_cast<Eigen::Index>(variables),
                       static_cast<Eigen::Index>(variables));
  const Vector feasibility_gradient =
      Vector::Zero(static_cast<Eigen::Index>(variables));
  const EqualityResult equality_feasible =
      solve_equalities(feasibility_hessian, feasibility_gradient, equalities,
                       equality_targets, options.tolerance);
  if (equality_feasible.result.status != QpStatus::Optimal) {
    QpSolveResult result = equality_feasible.result;
    if (result.status == QpStatus::Infeasible) {
      result.diagnostic = QpDiagnostic::InconsistentEqualities;
    }
    return result;
  }

  const QpSolveResult convexity =
      check_convexity(hessian, equalities, options.tolerance);
  if (convexity.status != QpStatus::Optimal) {
    return convexity;
  }

  std::size_t iterations = 0;
  Vector primal;
  std::vector<std::size_t> initial_active;
  if (!warm_start.primal.empty()) {
    primal = warm_primal;
    const double equality_error = linf(equalities * primal - equality_targets);
    const double inequality_error =
        normalized.matrix.rows() == 0
            ? 0.0
            : std::max(
                  0.0,
                  (normalized.matrix * primal - normalized.limits).maxCoeff());
    if (equality_error > options.active_tolerance ||
        inequality_error > options.active_tolerance) {
      return failure(QpStatus::InvalidInput, QpDiagnostic::InvalidWarmStart);
    }

    if (has_warm_masks) {
      for (std::size_t row = 0; row < normalized.origins.size(); ++row) {
        if (!warm_mask_selected(normalized.origins[row],
                                warm_start.active_inequalities,
                                warm_start.active_lower_bounds,
                                warm_start.active_upper_bounds)) {
          continue;
        }
        const double residual = std::abs(
            normalized.matrix.row(static_cast<Eigen::Index>(row)).dot(primal) -
            normalized.limits[static_cast<Eigen::Index>(row)]);
        if (residual > options.active_tolerance) {
          return failure(QpStatus::InvalidInput,
                         QpDiagnostic::InvalidWarmStart);
        }
        if (residual <= working_set_tolerance) {
          initial_active.push_back(row);
        }
      }
    } else {
      initial_active = tight_constraints(normalized.matrix, normalized.limits,
                                         primal, working_set_tolerance);
    }
  } else {
    primal = equality_feasible.primal;
    const double seed_violation =
        normalized.matrix.rows() == 0
            ? 0.0
            : std::max(
                  0.0,
                  (normalized.matrix * primal - normalized.limits).maxCoeff());
    const double seed_tolerance =
        scaled_tolerance(options.tolerance, std::max(1.0, seed_violation));
    if (seed_violation > seed_tolerance) {
      CoreResult phase =
          find_feasible_point(equalities, equality_targets, normalized.matrix,
                              normalized.limits, primal, options, iterations);
      if (phase.result.status != QpStatus::Optimal) {
        phase.result.iterations = iterations;
        return phase.result;
      }
      primal = phase.primal.head(static_cast<Eigen::Index>(variables));
      const double phase_slack =
          phase.primal[static_cast<Eigen::Index>(variables)];
      const double feasibility_tolerance = scaled_tolerance(
          options.tolerance, std::max(1.0, std::abs(phase_slack)));
      if (phase_slack > feasibility_tolerance) {
        QpSolveResult result =
            failure(QpStatus::Infeasible,
                    QpDiagnostic::InconsistentInequalities, iterations);
        result.inequality_linf = phase_slack;
        return result;
      }
    }
    initial_active = tight_constraints(normalized.matrix, normalized.limits,
                                       primal, working_set_tolerance);
  }

  CoreResult solved = solve_feasible_core(
      hessian, gradient, equalities, equality_targets, normalized.matrix,
      normalized.limits, std::move(primal), std::move(initial_active), options,
      iterations);
  if (solved.result.status != QpStatus::Optimal) {
    solved.result.iterations = iterations;
    return solved.result;
  }

  Vector normalized_dual = Vector::Zero(normalized.matrix.rows());
  for (std::size_t offset = 0; offset < solved.active.size(); ++offset) {
    normalized_dual[static_cast<Eigen::Index>(solved.active[offset])] =
        solved.active_dual[static_cast<Eigen::Index>(offset)];
  }
  Vector inequality_dual = Vector::Zero(inequalities.rows());
  Vector lower_dual = Vector::Zero(lower.size());
  Vector upper_dual = Vector::Zero(upper.size());
  for (std::size_t row = 0; row < normalized.origins.size(); ++row) {
    const double multiplier = normalized_dual[static_cast<Eigen::Index>(row)];
    const ConstraintOrigin origin = normalized.origins[row];
    switch (origin.family) {
    case ConstraintFamily::Inequality:
      inequality_dual[static_cast<Eigen::Index>(origin.index)] = multiplier;
      break;
    case ConstraintFamily::LowerBound:
      lower_dual[static_cast<Eigen::Index>(origin.index)] = multiplier;
      break;
    case ConstraintFamily::UpperBound:
      upper_dual[static_cast<Eigen::Index>(origin.index)] = multiplier;
      break;
    }
  }

  const Vector stationarity = hessian * solved.primal + gradient +
                              equalities.transpose() * solved.equality_dual +
                              normalized.matrix.transpose() * normalized_dual;
  const Vector equality_error = equalities * solved.primal - equality_targets;
  const Vector inequality_slack =
      normalized.matrix * solved.primal - normalized.limits;
  const Vector complementarity = normalized_dual.cwiseProduct(inequality_slack);

  solved.result.stationarity_linf = linf(stationarity);
  solved.result.equality_linf = linf(equality_error);
  solved.result.inequality_linf =
      inequality_slack.size() == 0 ? 0.0
                                   : std::max(0.0, inequality_slack.maxCoeff());
  solved.result.dual_linf = normalized_dual.size() == 0
                                ? 0.0
                                : std::max(0.0, -normalized_dual.minCoeff());
  solved.result.complementarity_linf = linf(complementarity);
  solved.result.iterations = iterations;

  const double residual_scale = std::max({
      1.0,
      linf(hessian * solved.primal),
      linf(gradient),
      linf(equalities.transpose() * solved.equality_dual),
      linf(normalized.matrix.transpose() * normalized_dual),
  });
  const double residual_tolerance =
      scaled_tolerance(options.tolerance, residual_scale);
  const double feasibility_tolerance =
      std::max(options.active_tolerance, residual_tolerance);
  if (solved.result.stationarity_linf > residual_tolerance ||
      solved.result.equality_linf > feasibility_tolerance ||
      solved.result.inequality_linf > feasibility_tolerance ||
      solved.result.dual_linf > residual_tolerance ||
      solved.result.complementarity_linf > feasibility_tolerance) {
    solved.result.status = QpStatus::NumericalFailure;
    solved.result.diagnostic = QpDiagnostic::ResidualTooLarge;
    return solved.result;
  }

  copy_to_view(solved.primal, solution.primal);
  copy_to_view(solved.equality_dual, solution.equality_dual);
  copy_to_view(inequality_dual, solution.inequality_dual);
  copy_to_view(lower_dual, solution.lower_bound_dual);
  copy_to_view(upper_dual, solution.upper_bound_dual);
  return solved.result;
}

} // namespace

QpSolveResult solve_active_set_qp(ActiveSetQpProblemView problem,
                                  ActiveSetQpSolutionView solution,
                                  ActiveSetQpWarmStartView warm_start,
                                  ActiveSetQpOptions options) noexcept {
  try {
    return solve_impl(problem, solution, warm_start, options);
  } catch (const std::exception &error) {
    std::fprintf(stderr,
                 "[termin-qopt] active-set QP failed with an exception: %s\n",
                 error.what());
  } catch (...) {
    std::fprintf(
        stderr,
        "[termin-qopt] active-set QP failed with an unknown exception\n");
  }
  return failure(QpStatus::NumericalFailure,
                 QpDiagnostic::DecompositionFailure);
}

} // namespace termin::qopt
