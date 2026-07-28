#pragma once

#include <termin/qopt/dense_views.hpp>
#include <termin/qopt/qp_types.hpp>
#include <termin/qopt/termin_qopt_api.hpp>

namespace termin::qopt {

// Provisional dense equality-QP contract:
//
//   minimize 0.5 * x^T H x + g^T x
//   subject to A x = b
//
// Inputs are snapshotted before outputs are written, so input/output aliasing
// is supported. The primal and equality-dual output buffers must not overlap.
// Outputs are modified only when the returned status is Optimal.
struct EqualityQpProblemView {
  ConstDenseMatrixView hessian;
  ConstDenseVectorView gradient;
  ConstDenseMatrixView equalities;
  ConstDenseVectorView equality_targets;
};

struct EqualityQpSolutionView {
  DenseVectorView primal;
  DenseVectorView equality_dual;
};

[[nodiscard]] TERMIN_QOPT_API QpSolveResult solve_equality_qp(
    EqualityQpProblemView problem, EqualityQpSolutionView solution,
    QpTolerance tolerance = {}) noexcept;

} // namespace termin::qopt
