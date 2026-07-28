#pragma once

#include <cstddef>
#include <string_view>

#include <termin/qopt/block_assembly.hpp>
#include <termin/qopt/equality_qp.hpp>
#include <termin/qopt/termin_qopt_api.hpp>

namespace termin::qopt {

struct DynamicsDofHandle {
  DenseBlockHandle block;
  [[nodiscard]] constexpr bool valid() const noexcept { return block.valid(); }
};

struct DynamicsConstraintHandle {
  DenseBlockHandle block;
  [[nodiscard]] constexpr bool valid() const noexcept { return block.valid(); }
};

template <typename Handle>
struct DynamicsRegistrationResult {
  Handle handle;
  AssemblyDiagnostic diagnostic = AssemblyDiagnostic::None;

  [[nodiscard]] constexpr bool ok() const noexcept {
    return diagnostic == AssemblyDiagnostic::None;
  }
};

// Two independent layouts make rectangular J assembly type-safe: DOF handles
// cannot accidentally address constraint rows and vice versa.
class TERMIN_QOPT_API DynamicsTopology {
public:
  [[nodiscard]] DynamicsRegistrationResult<DynamicsDofHandle> register_dofs(
      std::size_t size, std::string_view diagnostic_name
  ) noexcept;
  [[nodiscard]] DynamicsRegistrationResult<DynamicsConstraintHandle>
  register_constraint(
      std::size_t size, std::string_view diagnostic_name
  ) noexcept;
  [[nodiscard]] AssemblyDiagnostic finalize() noexcept;

  [[nodiscard]] bool finalized() const noexcept;
  [[nodiscard]] std::size_t dof_count() const noexcept;
  [[nodiscard]] std::size_t constraint_count() const noexcept;
  [[nodiscard]] const DenseBlockTopology& dof_topology() const noexcept;
  [[nodiscard]] const DenseBlockTopology& constraint_topology() const noexcept;

private:
  DenseBlockTopology dofs_;
  DenseBlockTopology constraints_;
  bool finalized_ = false;
};

struct DynamicsWorkspaceView {
  DenseMatrixView mass;
  DenseVectorView load;
  DenseMatrixView constraint_jacobian;
  DenseVectorView constraint_rhs;
};

struct ConstDynamicsSystemView {
  ConstDenseMatrixView mass;
  ConstDenseVectorView load;
  ConstDenseMatrixView constraint_jacobian;
  ConstDenseVectorView constraint_rhs;
};

// A checked per-step writer. The topology and numerical storage are borrowed;
// reuse the same workspace across steps when topology is unchanged.
class TERMIN_QOPT_API DynamicsAssembly {
public:
  DynamicsAssembly(
      const DynamicsTopology& topology, DynamicsWorkspaceView workspace
  ) noexcept;

  [[nodiscard]] AssemblyDiagnostic diagnostic() const noexcept;
  [[nodiscard]] bool valid() const noexcept;
  [[nodiscard]] AssemblyDiagnostic clear() noexcept;

  [[nodiscard]] AssemblyDiagnostic add_mass(
      DynamicsDofHandle row,
      DynamicsDofHandle column,
      ConstDenseMatrixView contribution
  ) noexcept;
  [[nodiscard]] AssemblyDiagnostic add_load(
      DynamicsDofHandle dofs, ConstDenseVectorView contribution
  ) noexcept;
  [[nodiscard]] AssemblyDiagnostic add_constraint_jacobian(
      DynamicsConstraintHandle constraint,
      DynamicsDofHandle dofs,
      ConstDenseMatrixView contribution
  ) noexcept;
  [[nodiscard]] AssemblyDiagnostic add_constraint_rhs(
      DynamicsConstraintHandle constraint,
      ConstDenseVectorView contribution
  ) noexcept;

  [[nodiscard]] ConstDynamicsSystemView system() const noexcept;

private:
  DynamicsWorkspaceView workspace_;
  DenseBlockMatrixAssembly mass_;
  DenseBlockVectorAssembly load_;
  DenseBlockMatrixAssembly constraint_jacobian_;
  DenseBlockVectorAssembly constraint_rhs_;
  AssemblyDiagnostic diagnostic_ = AssemblyDiagnostic::InternalFailure;
};

struct DynamicsSolutionView {
  DenseVectorView acceleration;
  // Physical generalized reaction is J^T * reaction. This is the negative of
  // the equality-QP dual because its stationarity convention is
  // M*a - f + J^T*dual = 0.
  DenseVectorView constraint_reaction;
};

[[nodiscard]] TERMIN_QOPT_API QpSolveResult solve_constrained_dynamics(
    ConstDynamicsSystemView system,
    DynamicsSolutionView solution,
    QpTolerance tolerance = {}
) noexcept;

} // namespace termin::qopt
