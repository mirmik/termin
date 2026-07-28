#include <termin/qopt/dynamics.hpp>

#include <cmath>
#include <cstdio>
#include <cstdint>
#include <exception>
#include <unordered_set>
#include <vector>

namespace termin::qopt {
namespace {

[[nodiscard]] AssemblyDiagnostic first_diagnostic(
    std::initializer_list<AssemblyDiagnostic> diagnostics
) noexcept {
  for (const AssemblyDiagnostic diagnostic : diagnostics) {
    if (diagnostic != AssemblyDiagnostic::None) {
      return diagnostic;
    }
  }
  return AssemblyDiagnostic::None;
}

[[nodiscard]] QpDiagnostic validate_output(
    DenseVectorView view, std::size_t expected_size
) noexcept {
  if (view.size != expected_size) {
    return QpDiagnostic::DimensionMismatch;
  }
  if (view.empty()) {
    return QpDiagnostic::None;
  }
  if (view.data == nullptr) {
    return QpDiagnostic::NullData;
  }
  if (view.stride <= 0) {
    return QpDiagnostic::InvalidStride;
  }
  return QpDiagnostic::None;
}

[[nodiscard]] QpDiagnostic validate_system(
    ConstDynamicsSystemView system
) noexcept {
  const std::size_t dof_count = system.load.size;
  const std::size_t constraint_count = system.constraint_rhs.size;
  if (system.mass.rows != dof_count
      || system.mass.columns != dof_count
      || system.constraint_jacobian.rows != constraint_count
      || system.constraint_jacobian.columns != dof_count) {
    return QpDiagnostic::DimensionMismatch;
  }
  if ((!system.load.empty() && system.load.data == nullptr)
      || (!system.mass.empty() && system.mass.data == nullptr)
      || (!system.constraint_jacobian.empty()
          && system.constraint_jacobian.data == nullptr)
      || (!system.constraint_rhs.empty()
          && system.constraint_rhs.data == nullptr)) {
    return QpDiagnostic::NullData;
  }
  if ((!system.load.empty() && system.load.stride <= 0)
      || (!system.mass.empty()
          && (system.mass.row_stride <= 0
              || system.mass.column_stride <= 0))
      || (!system.constraint_jacobian.empty()
          && (system.constraint_jacobian.row_stride <= 0
              || system.constraint_jacobian.column_stride <= 0))
      || (!system.constraint_rhs.empty()
          && system.constraint_rhs.stride <= 0)) {
    return QpDiagnostic::InvalidStride;
  }
  return QpDiagnostic::None;
}

[[nodiscard]] bool outputs_overlap(
    DenseVectorView first, DenseVectorView second
) {
  if (first.empty() || second.empty()) {
    return false;
  }
  std::unordered_set<std::uintptr_t> addresses;
  addresses.reserve(first.size);
  for (std::size_t index = 0; index < first.size; ++index) {
    addresses.insert(reinterpret_cast<std::uintptr_t>(&first[index]));
  }
  for (std::size_t index = 0; index < second.size; ++index) {
    if (addresses.contains(reinterpret_cast<std::uintptr_t>(&second[index]))) {
      return true;
    }
  }
  return false;
}

[[nodiscard]] QpSolveResult invalid_result(
    QpDiagnostic diagnostic
) noexcept {
  QpSolveResult result;
  result.status = QpStatus::InvalidInput;
  result.diagnostic = diagnostic;
  return result;
}

} // namespace

DynamicsRegistrationResult<DynamicsDofHandle>
DynamicsTopology::register_dofs(
    std::size_t size, std::string_view diagnostic_name
) noexcept {
  if (finalized_) {
    return {{}, AssemblyDiagnostic::TopologyFinalized};
  }
  const DenseBlockRegistrationResult result =
      dofs_.register_block(size, diagnostic_name);
  return {{result.handle}, result.diagnostic};
}

DynamicsRegistrationResult<DynamicsConstraintHandle>
DynamicsTopology::register_constraint(
    std::size_t size, std::string_view diagnostic_name
) noexcept {
  if (finalized_) {
    return {{}, AssemblyDiagnostic::TopologyFinalized};
  }
  const DenseBlockRegistrationResult result =
      constraints_.register_block(size, diagnostic_name);
  return {{result.handle}, result.diagnostic};
}

AssemblyDiagnostic DynamicsTopology::finalize() noexcept {
  if (finalized_) {
    return AssemblyDiagnostic::TopologyFinalized;
  }
  const AssemblyDiagnostic dof_result = dofs_.finalize();
  if (dof_result != AssemblyDiagnostic::None) {
    return dof_result;
  }
  const AssemblyDiagnostic constraint_result = constraints_.finalize();
  if (constraint_result != AssemblyDiagnostic::None) {
    return constraint_result;
  }
  finalized_ = true;
  return AssemblyDiagnostic::None;
}

bool DynamicsTopology::finalized() const noexcept {
  return finalized_;
}

std::size_t DynamicsTopology::dof_count() const noexcept {
  return dofs_.total_size();
}

std::size_t DynamicsTopology::constraint_count() const noexcept {
  return constraints_.total_size();
}

const DenseBlockTopology& DynamicsTopology::dof_topology() const noexcept {
  return dofs_;
}

const DenseBlockTopology&
DynamicsTopology::constraint_topology() const noexcept {
  return constraints_;
}

DynamicsAssembly::DynamicsAssembly(
    const DynamicsTopology& topology, DynamicsWorkspaceView workspace
) noexcept
    : workspace_(workspace),
      mass_(
          topology.dof_topology(),
          topology.dof_topology(),
          workspace.mass
      ),
      load_(topology.dof_topology(), workspace.load),
      constraint_jacobian_(
          topology.constraint_topology(),
          topology.dof_topology(),
          workspace.constraint_jacobian
      ),
      constraint_rhs_(
          topology.constraint_topology(), workspace.constraint_rhs
      ) {
  if (!topology.finalized()) {
    diagnostic_ = AssemblyDiagnostic::TopologyNotFinalized;
    return;
  }
  diagnostic_ = first_diagnostic({
      mass_.diagnostic(),
      load_.diagnostic(),
      constraint_jacobian_.diagnostic(),
      constraint_rhs_.diagnostic(),
  });
}

AssemblyDiagnostic DynamicsAssembly::diagnostic() const noexcept {
  return diagnostic_;
}

bool DynamicsAssembly::valid() const noexcept {
  return diagnostic_ == AssemblyDiagnostic::None;
}

AssemblyDiagnostic DynamicsAssembly::clear() noexcept {
  if (!valid()) {
    return diagnostic_;
  }
  return first_diagnostic({
      mass_.clear(),
      load_.clear(),
      constraint_jacobian_.clear(),
      constraint_rhs_.clear(),
  });
}

AssemblyDiagnostic DynamicsAssembly::add_mass(
    DynamicsDofHandle row,
    DynamicsDofHandle column,
    ConstDenseMatrixView contribution
) noexcept {
  return mass_.add(row.block, column.block, contribution);
}

AssemblyDiagnostic DynamicsAssembly::add_load(
    DynamicsDofHandle dofs, ConstDenseVectorView contribution
) noexcept {
  return load_.add(dofs.block, contribution);
}

AssemblyDiagnostic DynamicsAssembly::add_constraint_jacobian(
    DynamicsConstraintHandle constraint,
    DynamicsDofHandle dofs,
    ConstDenseMatrixView contribution
) noexcept {
  return constraint_jacobian_.add(
      constraint.block, dofs.block, contribution
  );
}

AssemblyDiagnostic DynamicsAssembly::add_constraint_rhs(
    DynamicsConstraintHandle constraint,
    ConstDenseVectorView contribution
) noexcept {
  return constraint_rhs_.add(constraint.block, contribution);
}

ConstDynamicsSystemView DynamicsAssembly::system() const noexcept {
  return {
      workspace_.mass,
      workspace_.load,
      workspace_.constraint_jacobian,
      workspace_.constraint_rhs,
  };
}

QpSolveResult solve_constrained_dynamics(
    ConstDynamicsSystemView system,
    DynamicsSolutionView solution,
    QpTolerance tolerance
) noexcept {
  const std::size_t dof_count = system.load.size;
  const std::size_t constraint_count = system.constraint_rhs.size;
  const QpDiagnostic system_diagnostic = validate_system(system);
  if (system_diagnostic != QpDiagnostic::None) {
    return invalid_result(system_diagnostic);
  }
  const QpDiagnostic acceleration_diagnostic =
      validate_output(solution.acceleration, dof_count);
  if (acceleration_diagnostic != QpDiagnostic::None) {
    return invalid_result(acceleration_diagnostic);
  }
  const QpDiagnostic reaction_diagnostic =
      validate_output(solution.constraint_reaction, constraint_count);
  if (reaction_diagnostic != QpDiagnostic::None) {
    return invalid_result(reaction_diagnostic);
  }

  try {
    if (outputs_overlap(
            solution.acceleration, solution.constraint_reaction
        )) {
      return invalid_result(QpDiagnostic::OverlappingOutputs);
    }

    std::vector<double> gradient(dof_count);
    std::vector<double> acceleration(dof_count);
    std::vector<double> equality_dual(constraint_count);
    for (std::size_t index = 0; index < dof_count; ++index) {
      if (!std::isfinite(system.load[index])) {
        return invalid_result(QpDiagnostic::NonFiniteInput);
      }
      gradient[index] = -system.load[index];
    }

    const QpSolveResult result = solve_equality_qp(
        {
            system.mass,
            {gradient.data(), gradient.size(), 1},
            system.constraint_jacobian,
            system.constraint_rhs,
        },
        {
            {acceleration.data(), acceleration.size(), 1},
            {equality_dual.data(), equality_dual.size(), 1},
        },
        tolerance
    );
    if (result.status != QpStatus::Optimal) {
      return result;
    }
    for (std::size_t index = 0; index < dof_count; ++index) {
      solution.acceleration[index] = acceleration[index];
    }
    for (std::size_t index = 0; index < constraint_count; ++index) {
      solution.constraint_reaction[index] = -equality_dual[index];
    }
    return result;
  } catch (const std::exception& error) {
    std::fprintf(
        stderr,
        "[termin-qopt] constrained dynamics solve failed: %s\n",
        error.what()
    );
  } catch (...) {
    std::fprintf(
        stderr,
        "[termin-qopt] constrained dynamics solve failed with an unknown exception\n"
    );
  }

  QpSolveResult result;
  result.status = QpStatus::NumericalFailure;
  result.diagnostic = QpDiagnostic::DecompositionFailure;
  return result;
}

} // namespace termin::qopt
