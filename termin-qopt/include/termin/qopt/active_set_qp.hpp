#pragma once

#include <cstddef>

#include <termin/qopt/dense_views.hpp>
#include <termin/qopt/qp_types.hpp>
#include <termin/qopt/termin_qopt_api.hpp>

namespace termin::qopt {

// Provisional dense convex-QP contract:
//
//   minimize 0.5 * x^T H x + g^T x
//   subject to A x = b
//              C x <= d
//              lower <= x <= upper
//
// Empty lower/upper views mean that the corresponding bound family is absent.
// Individual absent bounds are encoded as -infinity for lower and +infinity
// for upper. All dual output views have the same size as their input family.
struct ActiveSetQpProblemView {
  ConstDenseMatrixView hessian;
  ConstDenseVectorView gradient;
  ConstDenseMatrixView equalities;
  ConstDenseVectorView equality_targets;
  ConstDenseMatrixView inequalities;
  ConstDenseVectorView inequality_limits;
  ConstDenseVectorView lower_bounds;
  ConstDenseVectorView upper_bounds;
};

// A warm primal is a checked feasible point, not an arbitrary initial guess.
// Active masks are optional dense 0/1 hints and require a warm primal. Empty
// masks request automatic active-set reconstruction from the warm primal.
struct ActiveSetQpWarmStartView {
  ConstDenseVectorView primal;
  ConstDenseVectorView active_inequalities;
  ConstDenseVectorView active_lower_bounds;
  ConstDenseVectorView active_upper_bounds;
};

struct ActiveSetQpSolutionView {
  DenseVectorView primal;
  DenseVectorView equality_dual;
  DenseVectorView inequality_dual;
  DenseVectorView lower_bound_dual;
  DenseVectorView upper_bound_dual;
};

struct ActiveSetQpOptions {
  QpTolerance tolerance;
  // Inequality feasibility and warm-start validity tolerance in row-normalized
  // constraint units. Equality warm-start residuals use the original units. A
  // constraint enters the exact working set only at the tighter
  // absolute/relative QP tolerance.
  double active_tolerance = 1e-9;
  std::size_t max_iterations = 128;
};

// Inputs are snapshotted before outputs are written, so input/output aliasing
// is supported. Output buffers must not overlap each other. Outputs are
// modified only when the returned status is Optimal.
[[nodiscard]] TERMIN_QOPT_API QpSolveResult solve_active_set_qp(
    ActiveSetQpProblemView problem, ActiveSetQpSolutionView solution,
    ActiveSetQpWarmStartView warm_start = {},
    ActiveSetQpOptions options = {}) noexcept;

} // namespace termin::qopt
