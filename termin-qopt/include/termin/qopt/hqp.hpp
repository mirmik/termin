#pragma once

#include <cstddef>
#include <cstdint>
#include <limits>
#include <memory>

#include <termin/qopt/active_set_qp.hpp>
#include <termin/qopt/dense_views.hpp>
#include <termin/qopt/subspaces.hpp>
#include <termin/qopt/termin_qopt_api.hpp>

namespace termin::qopt {

enum class HqpDiagnostic : std::uint8_t {
  None,
  InvalidVariableCount,
  InvalidLevel,
  DuplicatePriority,
  DimensionMismatch,
  NonFiniteInput,
  InvalidWeight,
  InvalidOptions,
  LevelSolveFailure,
  PriorityViolation,
  InternalFailure,
};

[[nodiscard]] TERMIN_QOPT_API const char*
hqp_diagnostic_name(HqpDiagnostic diagnostic) noexcept;

struct HqpLevelHandle {
  std::uint64_t solver_id = 0;
  std::size_t index = std::numeric_limits<std::size_t>::max();

  [[nodiscard]] constexpr bool valid() const noexcept {
    return solver_id != 0
        && index != std::numeric_limits<std::size_t>::max();
  }
};

struct HqpLevelRegistrationResult {
  HqpLevelHandle handle;
  HqpDiagnostic diagnostic = HqpDiagnostic::None;

  [[nodiscard]] constexpr bool ok() const noexcept {
    return diagnostic == HqpDiagnostic::None;
  }
};

struct QuadraticTaskView {
  ConstDenseMatrixView jacobian;
  ConstDenseVectorView target;
  // Empty means identity. Otherwise this is a symmetric PSD rows x rows
  // matrix.
  ConstDenseMatrixView weight;
};

struct EqualityConstraintView {
  ConstDenseMatrixView matrix;
  ConstDenseVectorView target;
};

struct InequalityConstraintView {
  ConstDenseMatrixView matrix;
  ConstDenseVectorView limit;
};

struct HqpOptions {
  ActiveSetQpOptions qp;
  NullspaceOptions nullspace;
  double priority_tolerance = 1e-8;
};

struct HqpSolutionView {
  DenseVectorView primal;
  // One entry per registered level, in ascending priority order.
  DenseVectorView level_task_residual_l2;
};

struct HqpSolveResult {
  QpStatus status = QpStatus::InvalidInput;
  HqpDiagnostic diagnostic = HqpDiagnostic::None;
  QpSolveResult level_result;
  std::size_t failed_level = std::numeric_limits<std::size_t>::max();
  std::size_t levels_solved = 0;
  std::size_t remaining_dofs = 0;
  double priority_violation_linf =
      std::numeric_limits<double>::infinity();
};

class TERMIN_QOPT_API HierarchicalQpSolver {
public:
  explicit HierarchicalQpSolver(std::size_t variable_count);
  ~HierarchicalQpSolver();

  HierarchicalQpSolver(HierarchicalQpSolver&&) noexcept;
  HierarchicalQpSolver& operator=(HierarchicalQpSolver&&) noexcept;

  HierarchicalQpSolver(const HierarchicalQpSolver&) = delete;
  HierarchicalQpSolver& operator=(const HierarchicalQpSolver&) = delete;

  [[nodiscard]] std::size_t variable_count() const noexcept;
  [[nodiscard]] std::size_t level_count() const noexcept;

  [[nodiscard]] HqpLevelRegistrationResult add_level(
      int priority
  ) noexcept;
  [[nodiscard]] HqpDiagnostic add_task(
      HqpLevelHandle level, QuadraticTaskView task
  ) noexcept;
  [[nodiscard]] HqpDiagnostic add_equality(
      HqpLevelHandle level, EqualityConstraintView constraint
  ) noexcept;
  [[nodiscard]] HqpDiagnostic add_inequality(
      HqpLevelHandle level, InequalityConstraintView constraint
  ) noexcept;

  [[nodiscard]] HqpSolveResult solve(
      HqpSolutionView solution,
      ConstDenseVectorView initial_primal = {},
      HqpOptions options = {}
  ) const noexcept;

private:
  struct Impl;
  std::unique_ptr<Impl> impl_;
};

} // namespace termin::qopt
