#include <termin/qopt/active_set_qp.hpp>

#include <termin/qopt/equality_qp.hpp>

#include "qp_internal.hpp"

#include <Eigen/Eigenvalues>
#include <Eigen/SVD>

#include <array>
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
  Vector row_scales;
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

struct PivotEvent {
  bool added = false;
  std::size_t constraint = 0;
  double value = 0.0;
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

using RowBasis = std::vector<Vector>;

[[nodiscard]] double structural_rank_tolerance(Eigen::Index variables) {
  return std::numeric_limits<double>::epsilon() * 128.0 *
         static_cast<double>(std::max<Eigen::Index>(1, variables));
}

[[nodiscard]] std::optional<Vector>
independent_row_direction(const Vector &input, const RowBasis &basis) {
  const double scale = linf(input);
  if (scale == 0.0) {
    return std::nullopt;
  }
  Vector residual = input / scale;
  for (int pass = 0; pass < 2; ++pass) {
    for (const Vector &direction : basis) {
      residual -= direction.dot(residual) * direction;
    }
  }
  if (residual.norm() <= structural_rank_tolerance(input.size())) {
    return std::nullopt;
  }
  return residual.normalized();
}

[[nodiscard]] bool append_independent_row(const Vector &input,
                                          RowBasis &basis) {
  std::optional<Vector> direction = independent_row_direction(input, basis);
  if (!direction.has_value()) {
    return false;
  }
  basis.push_back(std::move(*direction));
  return true;
}

[[nodiscard]] RowBasis row_basis(const Matrix &rows) {
  RowBasis basis;
  basis.reserve(static_cast<std::size_t>(rows.cols()));
  for (Eigen::Index row = 0;
       row < rows.rows() &&
       basis.size() < static_cast<std::size_t>(rows.cols());
       ++row) {
    (void)append_independent_row(rows.row(row).transpose(), basis);
  }
  return basis;
}

[[nodiscard]] std::vector<std::size_t> independent_active_set(
    const Matrix &equalities, const Matrix &inequalities,
    const std::vector<std::size_t> &candidates) {
  RowBasis basis = row_basis(equalities);
  std::vector<std::size_t> independent;
  independent.reserve(candidates.size());
  for (const std::size_t candidate : candidates) {
    if (basis.size() == static_cast<std::size_t>(inequalities.cols())) {
      break;
    }
    if (append_independent_row(
            inequalities.row(static_cast<Eigen::Index>(candidate)).transpose(),
            basis)) {
      independent.push_back(candidate);
    }
  }
  return independent;
}

[[nodiscard]] CoreResult solve_feasible_core(
    const Matrix &hessian, const Vector &gradient, const Matrix &equalities,
    const Vector &targets, const Matrix &inequalities, const Vector &limits,
    Vector primal, std::vector<std::size_t> active,
    const ActiveSetQpOptions &options, std::size_t &iterations) {
  const Eigen::Index equality_count = equalities.rows();
  active = independent_active_set(equalities, inequalities, active);
  std::array<PivotEvent, 16> pivot_trace{};
  std::size_t pivot_event_count = 0;
  std::optional<std::size_t> last_dropped_constraint;
  std::vector<std::uint8_t> zero_step_readded(
      static_cast<std::size_t>(inequalities.rows()), 0);
  std::vector<std::size_t> zero_step_readd_counts(
      static_cast<std::size_t>(inequalities.rows()), 0);
  Vector limit_perturbations = Vector::Zero(inequalities.rows());
  const auto record_pivot = [&](PivotEvent event) {
    pivot_trace[pivot_event_count % pivot_trace.size()] = event;
    ++pivot_event_count;
  };
  // Every inequality row is normalized before it reaches the core. Direction
  // tests can therefore use one dimensionless threshold without allowing an
  // unrelated, large row to hide a blocker.
  const double direction_tolerance = scaled_tolerance(options.tolerance, 1.0);

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
          limits[static_cast<Eigen::Index>(active[offset])] +
          limit_perturbations[static_cast<Eigen::Index>(active[offset])];
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
    const RowBasis working_basis = row_basis(working);
    for (Eigen::Index row = 0; row < inequalities.rows(); ++row) {
      const std::size_t index = static_cast<std::size_t>(row);
      if (contains(active, index)) {
        continue;
      }
      const double rate = inequalities.row(row).dot(direction);
      if (rate <= direction_tolerance) {
        continue;
      }
      if (!independent_row_direction(inequalities.row(row).transpose(),
                                     working_basis)
               .has_value()) {
        continue;
      }
      const double perturbed_limit = limits[row] + limit_perturbations[row];
      const double slack = perturbed_limit - inequalities.row(row).dot(primal);
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
      record_pivot({true, *blocker, step});
      const bool repeats_last_drop = last_dropped_constraint == blocker &&
                                     step <= step_tolerance;
      zero_step_readded[*blocker] = repeats_last_drop ? 1 : 0;
      last_dropped_constraint.reset();
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
    double most_negative =
        -scaled_tolerance(options.tolerance, 1.0);
    for (std::size_t offset = 0; offset < active.size(); ++offset) {
      const double multiplier =
          subproblem.dual[equality_count + static_cast<Eigen::Index>(offset)];
      if (multiplier < most_negative) {
        most_negative = multiplier;
        removal_offset = offset;
      }
    }
    if (removal_offset.has_value()) {
      const std::size_t removed_constraint = active[*removal_offset];
      record_pivot({
          false,
          removed_constraint,
          subproblem.dual[equality_count +
                          static_cast<Eigen::Index>(*removal_offset)],
      });
      if (zero_step_readded[removed_constraint] != 0) {
        std::size_t &repeat_count =
            zero_step_readd_counts[removed_constraint];
        ++repeat_count;
        if (repeat_count >= 2) {
          // Distinct row-specific perturbations break a repeated degenerate
          // drop/add tie. The largest shift remains strictly below
          // active_tolerance, and the final solution is still validated
          // against the original, unperturbed constraints.
          const double lexicographic_fraction =
              static_cast<double>(removed_constraint + 1) /
              static_cast<double>(zero_step_readd_counts.size() + 1);
          limit_perturbations[static_cast<Eigen::Index>(removed_constraint)] =
              options.active_tolerance * lexicographic_fraction;
        }
      }
      zero_step_readded[removed_constraint] = 0;
      last_dropped_constraint = removed_constraint;
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
  if (pivot_event_count != 0) {
    std::fprintf(stderr,
                 "[termin-qopt] active-set pivot trace at iteration limit: "
                 "constraints=%zu events=%zu\n",
                 active.size(), pivot_event_count);
    const std::size_t trace_begin = pivot_event_count > pivot_trace.size()
                                        ? pivot_event_count - pivot_trace.size()
                                        : 0;
    for (std::size_t index = trace_begin; index < pivot_event_count; ++index) {
      const PivotEvent &event = pivot_trace[index % pivot_trace.size()];
      std::fprintf(stderr, "  pivot[%zu]=%s constraint=%zu value=%.17g\n",
                   index, event.added ? "add" : "drop", event.constraint,
                   event.value);
    }
  }
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
  normalized.row_scales = Vector::Ones(rows);
  normalized.origins.reserve(static_cast<std::size_t>(rows));

  Eigen::Index row = 0;
  for (Eigen::Index index = 0; index < inequalities.rows(); ++index, ++row) {
    normalized.matrix.row(row) = inequalities.row(index);
    normalized.limits[row] = limits[index];
    const double coefficient_scale =
        normalized.matrix.row(row).cwiseAbs().maxCoeff();
    if (coefficient_scale > 0.0) {
      normalized.row_scales[row] = coefficient_scale;
      normalized.matrix.row(row) /= coefficient_scale;
      normalized.limits[row] /= coefficient_scale;
    } else if (normalized.limits[row] != 0.0) {
      // A constant constraint has no coefficient scale. Canonicalizing
      // its nonzero limit still makes 0 <= d invariant to positive row
      // scaling.
      normalized.row_scales[row] = std::abs(normalized.limits[row]);
      normalized.limits[row] /= normalized.row_scales[row];
    }
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

struct ConstraintResidual {
  double value = 0.0;
  double residual = 0.0;
  double tolerance = 0.0;
};

[[nodiscard]] ConstraintResidual constraint_residual(const Matrix &inequalities,
                                                     const Vector &limits,
                                                     const Vector &primal,
                                                     Eigen::Index row,
                                                     QpTolerance tolerance) {
  const double value = inequalities.row(row).dot(primal);
  return {
      value,
      value - limits[row],
      scaled_tolerance(tolerance,
                       std::max(std::abs(value), std::abs(limits[row]))),
  };
}

[[nodiscard]] std::vector<std::size_t>
tight_constraints(const Matrix &inequalities, const Vector &limits,
                  const Vector &primal, QpTolerance tolerance) {
  std::vector<std::size_t> active;
  for (Eigen::Index row = 0; row < inequalities.rows(); ++row) {
    const ConstraintResidual checked =
        constraint_residual(inequalities, limits, primal, row, tolerance);
    if (std::abs(checked.residual) <= checked.tolerance) {
      active.push_back(static_cast<std::size_t>(row));
    }
  }
  return active;
}

[[nodiscard]] bool constraints_feasible(const Matrix &inequalities,
                                        const Vector &limits,
                                        const Vector &primal,
                                        double active_tolerance,
                                        QpTolerance tolerance) {
  for (Eigen::Index row = 0; row < inequalities.rows(); ++row) {
    const ConstraintResidual checked =
        constraint_residual(inequalities, limits, primal, row, tolerance);
    if (checked.residual > std::max(active_tolerance, checked.tolerance)) {
      return false;
    }
  }
  return true;
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

  std::vector<std::size_t> active = tight_constraints(
      phase_inequalities, phase_limits, phase_start, options.tolerance);
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
    if (equality_error > options.active_tolerance ||
        !constraints_feasible(normalized.matrix, normalized.limits, primal,
                              options.active_tolerance, options.tolerance)) {
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
        const ConstraintResidual checked = constraint_residual(
            normalized.matrix, normalized.limits, primal,
            static_cast<Eigen::Index>(row), options.tolerance);
        if (std::abs(checked.residual) >
            std::max(options.active_tolerance, checked.tolerance)) {
          return failure(QpStatus::InvalidInput,
                         QpDiagnostic::InvalidWarmStart);
        }
        if (std::abs(checked.residual) <= checked.tolerance) {
          initial_active.push_back(row);
        }
      }
    } else {
      initial_active = tight_constraints(normalized.matrix, normalized.limits,
                                         primal, options.tolerance);
    }
  } else {
    // Start Phase I from the equality-constrained objective minimizer when it
    // exists. The old minimum-norm origin can force a feasible active-set walk
    // through every intermediate facet of a fine polygon before reaching the
    // relevant face. Phase I retains feasibility guarantees while this seed
    // preserves the objective's useful directional information.
    const EqualityResult objective_seed = solve_equalities(
        hessian, gradient, equalities, equality_targets, options.tolerance);
    primal = objective_seed.result.status == QpStatus::Optimal
                 ? objective_seed.primal
                 : equality_feasible.primal;
    if (!constraints_feasible(normalized.matrix, normalized.limits, primal, 0.0,
                              options.tolerance)) {
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
                                       primal, options.tolerance);
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
    const double multiplier =
        solved.active_dual[static_cast<Eigen::Index>(offset)];
    normalized_dual[static_cast<Eigen::Index>(solved.active[offset])] =
        multiplier;
  }
  Vector inequality_dual = Vector::Zero(inequalities.rows());
  Vector lower_dual = Vector::Zero(lower.size());
  Vector upper_dual = Vector::Zero(upper.size());
  for (std::size_t row = 0; row < normalized.origins.size(); ++row) {
    const double multiplier =
        normalized_dual[static_cast<Eigen::Index>(row)] /
        normalized.row_scales[static_cast<Eigen::Index>(row)];
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
  const Vector normalized_inequality_slack =
      normalized.matrix * solved.primal - normalized.limits;
  const Vector complementarity =
      normalized_dual.cwiseProduct(normalized_inequality_slack);

  double original_inequality_violation = 0.0;
  if (inequalities.rows() > 0) {
    original_inequality_violation = std::max(
        0.0, (inequalities * solved.primal - inequality_limits).maxCoeff());
  }
  for (Eigen::Index index = 0; index < lower.size(); ++index) {
    if (std::isfinite(lower[index])) {
      original_inequality_violation = std::max(
          original_inequality_violation, lower[index] - solved.primal[index]);
    }
  }
  for (Eigen::Index index = 0; index < upper.size(); ++index) {
    if (std::isfinite(upper[index])) {
      original_inequality_violation = std::max(
          original_inequality_violation, solved.primal[index] - upper[index]);
    }
  }

  solved.result.stationarity_linf = linf(stationarity);
  solved.result.equality_linf = linf(equality_error);
  solved.result.inequality_linf = original_inequality_violation;
  solved.result.dual_linf = std::max({
      inequality_dual.size() == 0 ? 0.0
                                  : std::max(0.0, -inequality_dual.minCoeff()),
      lower_dual.size() == 0 ? 0.0 : std::max(0.0, -lower_dual.minCoeff()),
      upper_dual.size() == 0 ? 0.0 : std::max(0.0, -upper_dual.minCoeff()),
  });
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
  const double normalized_dual_violation =
      normalized_dual.size() == 0 ? 0.0
                                  : std::max(0.0, -normalized_dual.minCoeff());
  if (solved.result.stationarity_linf > residual_tolerance ||
      solved.result.equality_linf > feasibility_tolerance ||
      !constraints_feasible(normalized.matrix, normalized.limits, solved.primal,
                            options.active_tolerance, options.tolerance) ||
      normalized_dual_violation > residual_tolerance ||
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
