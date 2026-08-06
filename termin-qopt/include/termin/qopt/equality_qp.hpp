#pragma once

#include <termin/qopt/dense_views.hpp>
#include <termin/qopt/qp_types.hpp>
#include <termin/qopt/termin_qopt_api.hpp>

#include <cstddef>
#include <memory>

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

struct EqualityQpFactorizationCounters {
  std::size_t factorizations = 0;
  std::size_t reuse_hits = 0;
};

// Explicitly scoped cache for repeated equality QPs whose Hessian and
// equality Jacobian remain exactly unchanged while their right-hand sides
// vary. The cache always revalidates the coefficient matrices and
// automatically refactorizes on any coefficient or tolerance change.
class TERMIN_QOPT_API EqualityQpFactorizationCache {
public:
  EqualityQpFactorizationCache();
  ~EqualityQpFactorizationCache();

  EqualityQpFactorizationCache(EqualityQpFactorizationCache &&) noexcept;
  EqualityQpFactorizationCache &
  operator=(EqualityQpFactorizationCache &&) noexcept;
  EqualityQpFactorizationCache(const EqualityQpFactorizationCache &) = delete;
  EqualityQpFactorizationCache &
  operator=(const EqualityQpFactorizationCache &) = delete;

  [[nodiscard]] QpSolveResult solve(
      EqualityQpProblemView problem, EqualityQpSolutionView solution,
      QpTolerance tolerance = {}) noexcept;
  void clear() noexcept;
  [[nodiscard]] EqualityQpFactorizationCounters counters() const noexcept;
  void reset_counters() noexcept;

private:
  struct Impl;
  std::unique_ptr<Impl> impl_;
};

[[nodiscard]] TERMIN_QOPT_API QpSolveResult solve_equality_qp(
    EqualityQpProblemView problem, EqualityQpSolutionView solution,
    QpTolerance tolerance = {}) noexcept;

} // namespace termin::qopt
