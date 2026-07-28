#include <termin/qopt/dynamics.hpp>

#include "test_check.hpp"

#include <array>
#include <cmath>

using namespace termin::qopt;

int main() {
  DynamicsTopology topology;
  const auto first = topology.register_dofs(1, "first");
  const auto second = topology.register_dofs(1, "second");
  const auto coupling = topology.register_constraint(1, "coupling");
  TERMIN_QOPT_CHECK(first.ok());
  TERMIN_QOPT_CHECK(second.ok());
  TERMIN_QOPT_CHECK(coupling.ok());
  TERMIN_QOPT_CHECK(topology.finalize() == AssemblyDiagnostic::None);
  TERMIN_QOPT_CHECK(topology.dof_count() == 2);
  TERMIN_QOPT_CHECK(topology.constraint_count() == 1);

  std::array<double, 4> mass{};
  std::array<double, 2> load{};
  std::array<double, 2> jacobian{};
  std::array<double, 1> rhs{};
  DynamicsAssembly assembly(
      topology,
      {
          DenseMatrixView::row_major(mass.data(), 2, 2),
          {load.data(), load.size(), 1},
          DenseMatrixView::row_major(jacobian.data(), 1, 2),
          {rhs.data(), rhs.size(), 1},
      }
  );
  TERMIN_QOPT_CHECK(assembly.valid());
  TERMIN_QOPT_CHECK(assembly.clear() == AssemblyDiagnostic::None);

  const std::array<double, 1> mass_first{2.0};
  const std::array<double, 1> mass_second{3.0};
  const std::array<double, 1> load_first{4.0};
  const std::array<double, 1> zero{0.0};
  const std::array<double, 1> positive{1.0};
  const std::array<double, 1> negative{-1.0};
  TERMIN_QOPT_CHECK(
      assembly.add_mass(
          first.handle,
          first.handle,
          ConstDenseMatrixView::row_major(mass_first.data(), 1, 1)
      ) == AssemblyDiagnostic::None
  );
  TERMIN_QOPT_CHECK(
      assembly.add_mass(
          second.handle,
          second.handle,
          ConstDenseMatrixView::row_major(mass_second.data(), 1, 1)
      ) == AssemblyDiagnostic::None
  );
  TERMIN_QOPT_CHECK(
      assembly.add_load(
          first.handle, {load_first.data(), load_first.size(), 1}
      ) == AssemblyDiagnostic::None
  );
  TERMIN_QOPT_CHECK(
      assembly.add_constraint_jacobian(
          coupling.handle,
          first.handle,
          ConstDenseMatrixView::row_major(positive.data(), 1, 1)
      ) == AssemblyDiagnostic::None
  );
  TERMIN_QOPT_CHECK(
      assembly.add_constraint_jacobian(
          coupling.handle,
          second.handle,
          ConstDenseMatrixView::row_major(negative.data(), 1, 1)
      ) == AssemblyDiagnostic::None
  );
  TERMIN_QOPT_CHECK(
      assembly.add_constraint_rhs(
          coupling.handle, {zero.data(), zero.size(), 1}
      ) == AssemblyDiagnostic::None
  );

  std::array<double, 2> acceleration{-100.0, -100.0};
  std::array<double, 1> reaction{-100.0};
  const QpSolveResult solved = solve_constrained_dynamics(
      assembly.system(),
      {
          {acceleration.data(), acceleration.size(), 1},
          {reaction.data(), reaction.size(), 1},
      }
  );
  TERMIN_QOPT_CHECK(solved.status == QpStatus::Optimal);
  TERMIN_QOPT_CHECK(std::abs(acceleration[0] - 0.8) < 1e-10);
  TERMIN_QOPT_CHECK(std::abs(acceleration[1] - 0.8) < 1e-10);
  TERMIN_QOPT_CHECK(std::abs(reaction[0] + 2.4) < 1e-10);

  // A shifted coupling remains a regular feasible affine constraint.
  const std::array<double, 1> inconsistent_rhs{1.0};
  rhs[0] = inconsistent_rhs[0];
  acceleration = {-7.0, -8.0};
  reaction = {-9.0};
  const QpSolveResult shifted = solve_constrained_dynamics(
      assembly.system(),
      {
          {acceleration.data(), acceleration.size(), 1},
          {reaction.data(), reaction.size(), 1},
      }
  );
  TERMIN_QOPT_CHECK(shifted.status == QpStatus::Optimal);
  TERMIN_QOPT_CHECK(
      std::abs(acceleration[0] - acceleration[1] - 1.0) < 1e-10
  );

  std::array<double, 1> wrong_acceleration{-123.0};
  const QpSolveResult invalid = solve_constrained_dynamics(
      assembly.system(),
      {
          {wrong_acceleration.data(), wrong_acceleration.size(), 1},
          {reaction.data(), reaction.size(), 1},
      }
  );
  TERMIN_QOPT_CHECK(invalid.status == QpStatus::InvalidInput);
  TERMIN_QOPT_CHECK(wrong_acceleration[0] == -123.0);

  const ConstDynamicsSystemView null_load_system{
      ConstDenseMatrixView::row_major(mass.data(), 2, 2),
      {nullptr, load.size(), 1},
      ConstDenseMatrixView::row_major(jacobian.data(), 1, 2),
      {rhs.data(), rhs.size(), 1},
  };
  acceleration = {-31.0, -32.0};
  reaction = {-33.0};
  const QpSolveResult null_load = solve_constrained_dynamics(
      null_load_system,
      {
          {acceleration.data(), acceleration.size(), 1},
          {reaction.data(), reaction.size(), 1},
      }
  );
  TERMIN_QOPT_CHECK(null_load.status == QpStatus::InvalidInput);
  TERMIN_QOPT_CHECK(null_load.diagnostic == QpDiagnostic::NullData);
  TERMIN_QOPT_CHECK(acceleration[0] == -31.0);
  TERMIN_QOPT_CHECK(acceleration[1] == -32.0);
  TERMIN_QOPT_CHECK(reaction[0] == -33.0);

  // Redundant and inconsistent equalities preserve equality-QP semantics.
  const std::array<double, 1> scalar_mass{1.0};
  const std::array<double, 1> scalar_load{0.0};
  const std::array<double, 2> duplicate_jacobian{1.0, 1.0};
  std::array<double, 2> duplicate_rhs{0.0, 0.0};
  std::array<double, 1> scalar_acceleration{-11.0};
  std::array<double, 2> duplicate_reaction{-12.0, -13.0};
  const ConstDynamicsSystemView duplicate_system{
      ConstDenseMatrixView::row_major(scalar_mass.data(), 1, 1),
      {scalar_load.data(), scalar_load.size(), 1},
      ConstDenseMatrixView::row_major(duplicate_jacobian.data(), 2, 1),
      {duplicate_rhs.data(), duplicate_rhs.size(), 1},
  };
  const DynamicsSolutionView duplicate_solution{
      {scalar_acceleration.data(), scalar_acceleration.size(), 1},
      {duplicate_reaction.data(), duplicate_reaction.size(), 1},
  };
  const QpSolveResult redundant =
      solve_constrained_dynamics(duplicate_system, duplicate_solution);
  TERMIN_QOPT_CHECK(redundant.status == QpStatus::Optimal);
  TERMIN_QOPT_CHECK(redundant.constraint_rank == 1);

  duplicate_rhs[1] = 1.0;
  scalar_acceleration[0] = -21.0;
  duplicate_reaction = {-22.0, -23.0};
  const QpSolveResult inconsistent =
      solve_constrained_dynamics(duplicate_system, duplicate_solution);
  TERMIN_QOPT_CHECK(inconsistent.status == QpStatus::Infeasible);
  TERMIN_QOPT_CHECK(
      inconsistent.diagnostic == QpDiagnostic::InconsistentEqualities
  );
  TERMIN_QOPT_CHECK(scalar_acceleration[0] == -21.0);
  TERMIN_QOPT_CHECK(duplicate_reaction[0] == -22.0);
  TERMIN_QOPT_CHECK(duplicate_reaction[1] == -23.0);

  return 0;
}
