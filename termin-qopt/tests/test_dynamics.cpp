#include <termin/qopt/dynamics.hpp>

#include "test_check.hpp"

#include <array>
#include <cmath>
#include <limits>
#include <memory>
#include <string>

using namespace termin::qopt;

namespace
{

    class AnchoredScalarContribution final : public DynamicsContribution
    {
      public:
        explicit AnchoredScalarContribution(std::string name)
            : dof_name_(name + "_scalar"), constraint_name_(name + "_anchor")
        {
        }

        double position = 1.0;
        double velocity = 0.0;
        double acceleration = 0.0;
        double reaction = 0.0;
        bool topology_bound = false;

        AssemblyDiagnostic
        register_topology(DynamicsTopology& topology) noexcept override
        {
            const auto dofs = topology.register_dofs(1, dof_name_);
            const auto constraint = topology.register_constraint(1, constraint_name_);
            if (!dofs.ok())
            {
                return dofs.diagnostic;
            }
            if (!constraint.ok())
            {
                return constraint.diagnostic;
            }
            dofs_ = dofs.handle;
            constraint_ = constraint.handle;
            return AssemblyDiagnostic::None;
        }

        AssemblyDiagnostic
        bind_topology(const DynamicsTopology& topology) noexcept override
        {
            if (!topology.finalized() || !dofs_.valid() || !constraint_.valid())
            {
                return AssemblyDiagnostic::InvalidBlock;
            }
            topology_bound = true;
            return AssemblyDiagnostic::None;
        }

        AssemblyDiagnostic assemble(DynamicsAssembly& assembly,
                                    DynamicsAssemblyPhase phase) noexcept override
        {
            const std::array<double, 1> mass{2.0};
            const std::array<double, 1> jacobian{1.0};
            const std::array<double, 1> load{
                phase == DynamicsAssemblyPhase::VelocityProjection ? 2.0 * velocity
                                                                   : 0.0,
            };
            const std::array<double, 1> rhs{
                phase == DynamicsAssemblyPhase::PositionProjection ? -position : 0.0,
            };
            AssemblyDiagnostic diagnostic = assembly.add_mass(
                dofs_, dofs_, ConstDenseMatrixView::row_major(mass.data(), 1, 1));
            if (diagnostic != AssemblyDiagnostic::None)
            {
                return diagnostic;
            }
            diagnostic = assembly.add_load(dofs_, {load.data(), load.size(), 1});
            if (diagnostic != AssemblyDiagnostic::None)
            {
                return diagnostic;
            }
            diagnostic = assembly.add_constraint_jacobian(
                constraint_,
                dofs_,
                ConstDenseMatrixView::row_major(jacobian.data(), 1, 1));
            if (diagnostic != AssemblyDiagnostic::None)
            {
                return diagnostic;
            }
            return assembly.add_constraint_rhs(constraint_,
                                               {rhs.data(), rhs.size(), 1});
        }

        AssemblyDiagnostic begin_step() noexcept override
        {
            snapshot_ = {position, velocity, acceleration, reaction};
            return AssemblyDiagnostic::None;
        }

        void rollback_step() noexcept override
        {
            position = snapshot_[0];
            velocity = snapshot_[1];
            acceleration = snapshot_[2];
            reaction = snapshot_[3];
        }

        void apply_solution(DynamicsAssemblyPhase phase,
                            const DynamicsTopology& topology,
                            ConstDenseVectorView dof_values,
                            ConstDenseVectorView constraint_reactions) noexcept override
        {
            const DenseBlockInfo dof_info =
                topology.dof_topology().block_info(dofs_.block);
            const DenseBlockInfo constraint_info =
                topology.constraint_topology().block_info(constraint_.block);
            if (phase == DynamicsAssemblyPhase::Acceleration)
            {
                acceleration = dof_values[dof_info.offset];
                reaction = constraint_reactions[constraint_info.offset];
            }
            else if (phase == DynamicsAssemblyPhase::VelocityProjection)
            {
                velocity = dof_values[dof_info.offset];
            }
        }

        AssemblyDiagnostic
        write_velocity(const DynamicsTopology& topology,
                       DenseVectorView destination) const noexcept override
        {
            const DenseBlockInfo info = topology.dof_topology().block_info(dofs_.block);
            destination[info.offset] = velocity;
            return AssemblyDiagnostic::None;
        }

        AssemblyDiagnostic set_velocity(const DynamicsTopology& topology,
                                        ConstDenseVectorView source) noexcept override
        {
            const DenseBlockInfo info = topology.dof_topology().block_info(dofs_.block);
            velocity = source[info.offset];
            return AssemblyDiagnostic::None;
        }

        AssemblyDiagnostic
        set_trial_configuration(const DynamicsTopology& topology,
                                ConstDenseVectorView midpoint_velocity,
                                double time_step) noexcept override
        {
            const DenseBlockInfo info = topology.dof_topology().block_info(dofs_.block);
            position = snapshot_[0] + midpoint_velocity[info.offset] * time_step;
            return AssemblyDiagnostic::None;
        }

        AssemblyDiagnostic write_corrected_midpoint_velocity(
            const DynamicsTopology& topology,
            ConstDenseVectorView midpoint_velocity,
            ConstDenseVectorView correction,
            double time_step,
            DenseVectorView destination) const noexcept override
        {
            const DenseBlockInfo info = topology.dof_topology().block_info(dofs_.block);
            destination[info.offset] =
                midpoint_velocity[info.offset] + correction[info.offset] / time_step;
            return AssemblyDiagnostic::None;
        }

        double position_error_linf() const noexcept override
        {
            return std::abs(position);
        }

        double velocity_error_linf() const noexcept override
        {
            return std::abs(velocity);
        }

      private:
        std::string dof_name_;
        std::string constraint_name_;
        DynamicsDofHandle dofs_;
        DynamicsConstraintHandle constraint_;
        std::array<double, 4> snapshot_{};
    };

    class TransientRowsContribution final : public DynamicsContribution
    {
      public:
        std::size_t requested_rows = 0;
        std::size_t registration_count = 0;
        std::size_t rollback_count = 0;

        AssemblyDiagnostic
        register_topology(DynamicsTopology& topology) noexcept override
        {
            const auto result = topology.register_dofs(1, "transient_owner");
            if (result.ok())
            {
                dofs_ = result.handle;
            }
            return result.diagnostic;
        }

        AssemblyDiagnostic register_unilateral_constraints(
            DynamicsUnilateralTopology& topology) noexcept override
        {
            ++registration_count;
            unilateral_ = {};
            if (requested_rows == 0)
            {
                return AssemblyDiagnostic::None;
            }
            const auto result =
                topology.register_constraint(requested_rows, "transient_test_rows");
            if (result.ok())
            {
                unilateral_ = result.handle;
            }
            return result.diagnostic;
        }

        AssemblyDiagnostic assemble(DynamicsAssembly& assembly,
                                    DynamicsAssemblyPhase) noexcept override
        {
            const std::array<double, 1> mass{1.0};
            const std::array<double, 1> load{0.0};
            AssemblyDiagnostic diagnostic = assembly.add_mass(
                dofs_, dofs_, ConstDenseMatrixView::row_major(mass.data(), 1, 1));
            if (diagnostic != AssemblyDiagnostic::None)
            {
                return diagnostic;
            }
            diagnostic = assembly.add_load(dofs_, {load.data(), load.size(), 1});
            if (diagnostic != AssemblyDiagnostic::None || requested_rows == 0)
            {
                return diagnostic;
            }
            const std::array<double, 3> jacobian{-1.0, -2.0, -3.0};
            const std::array<double, 3> limit{0.0, 1.0, 2.0};
            diagnostic = assembly.add_unilateral_jacobian(
                unilateral_,
                dofs_,
                ConstDenseMatrixView::row_major(jacobian.data(), requested_rows, 1));
            if (diagnostic != AssemblyDiagnostic::None)
            {
                return diagnostic;
            }
            return assembly.add_unilateral_limit(unilateral_,
                                                 {limit.data(), requested_rows, 1});
        }

        AssemblyDiagnostic begin_step() noexcept override
        {
            velocity_snapshot_ = velocity_;
            return AssemblyDiagnostic::None;
        }

        void rollback_step() noexcept override
        {
            velocity_ = velocity_snapshot_;
            ++rollback_count;
        }

        AssemblyDiagnostic
        write_velocity(const DynamicsTopology& topology,
                       DenseVectorView destination) const noexcept override
        {
            const DenseBlockInfo info = topology.dof_topology().block_info(dofs_.block);
            if (!info.ok())
            {
                return info.diagnostic;
            }
            destination[info.offset] = velocity_;
            return AssemblyDiagnostic::None;
        }

        AssemblyDiagnostic set_velocity(const DynamicsTopology& topology,
                                        ConstDenseVectorView source) noexcept override
        {
            const DenseBlockInfo info = topology.dof_topology().block_info(dofs_.block);
            if (!info.ok())
            {
                return info.diagnostic;
            }
            velocity_ = source[info.offset];
            return AssemblyDiagnostic::None;
        }

        AssemblyDiagnostic set_trial_configuration(const DynamicsTopology&,
                                                   ConstDenseVectorView,
                                                   double) noexcept override
        {
            return AssemblyDiagnostic::None;
        }

      private:
        DynamicsDofHandle dofs_;
        DynamicsUnilateralConstraintHandle unilateral_;
        double velocity_ = 0.0;
        double velocity_snapshot_ = 0.0;
    };

} // namespace

int main()
{
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

    DynamicsUnilateralTopology unilateral_topology;
    const auto contact_rows =
        unilateral_topology.register_constraint(2, "contact_rows");
    TERMIN_QOPT_CHECK(contact_rows.ok());
    TERMIN_QOPT_CHECK(
        unilateral_topology.register_constraint(1, "contact_rows").diagnostic ==
        AssemblyDiagnostic::DuplicateBlockName);
    TERMIN_QOPT_CHECK(unilateral_topology.finalize() == AssemblyDiagnostic::None);
    TERMIN_QOPT_CHECK(unilateral_topology.constraint_count() == 2);
    TERMIN_QOPT_CHECK(unilateral_topology.register_constraint(1, "late").diagnostic ==
                      AssemblyDiagnostic::TopologyFinalized);

    std::array<double, 4> mass{};
    std::array<double, 2> load{};
    std::array<double, 2> jacobian{};
    std::array<double, 1> rhs{};
    std::array<double, 4> unilateral_jacobian{};
    std::array<double, 2> unilateral_limit{};
    DynamicsAssembly assembly(
        topology,
        unilateral_topology,
        {
            DenseMatrixView::row_major(mass.data(), 2, 2),
            {load.data(), load.size(), 1},
            DenseMatrixView::row_major(jacobian.data(), 1, 2),
            {rhs.data(), rhs.size(), 1},
            DenseMatrixView::row_major(unilateral_jacobian.data(), 2, 2),
            {
                unilateral_limit.data(),
                unilateral_limit.size(),
                1,
            },
        });
    TERMIN_QOPT_CHECK(assembly.valid());
    TERMIN_QOPT_CHECK(assembly.clear() == AssemblyDiagnostic::None);

    const std::array<double, 1> mass_first{2.0};
    const std::array<double, 1> mass_second{3.0};
    const std::array<double, 1> load_first{4.0};
    const std::array<double, 1> zero{0.0};
    const std::array<double, 1> positive{1.0};
    const std::array<double, 1> negative{-1.0};
    TERMIN_QOPT_CHECK(
        assembly.add_mass(first.handle,
                          first.handle,
                          ConstDenseMatrixView::row_major(mass_first.data(), 1, 1)) ==
        AssemblyDiagnostic::None);
    TERMIN_QOPT_CHECK(
        assembly.add_mass(second.handle,
                          second.handle,
                          ConstDenseMatrixView::row_major(mass_second.data(), 1, 1)) ==
        AssemblyDiagnostic::None);
    TERMIN_QOPT_CHECK(
        assembly.add_load(first.handle, {load_first.data(), load_first.size(), 1}) ==
        AssemblyDiagnostic::None);
    TERMIN_QOPT_CHECK(assembly.add_constraint_jacobian(
                          coupling.handle,
                          first.handle,
                          ConstDenseMatrixView::row_major(positive.data(), 1, 1)) ==
                      AssemblyDiagnostic::None);
    TERMIN_QOPT_CHECK(assembly.add_constraint_jacobian(
                          coupling.handle,
                          second.handle,
                          ConstDenseMatrixView::row_major(negative.data(), 1, 1)) ==
                      AssemblyDiagnostic::None);
    TERMIN_QOPT_CHECK(
        assembly.add_constraint_rhs(coupling.handle, {zero.data(), zero.size(), 1}) ==
        AssemblyDiagnostic::None);
    const std::array<double, 2> unilateral_first{1.0, 2.0};
    const std::array<double, 2> unilateral_second{-1.0, -2.0};
    const std::array<double, 2> unilateral_limits{3.0, 4.0};
    TERMIN_QOPT_CHECK(
        assembly.add_unilateral_jacobian(
            contact_rows.handle,
            first.handle,
            ConstDenseMatrixView::row_major(unilateral_first.data(), 2, 1)) ==
        AssemblyDiagnostic::None);
    TERMIN_QOPT_CHECK(
        assembly.add_unilateral_jacobian(
            contact_rows.handle,
            second.handle,
            ConstDenseMatrixView::row_major(unilateral_second.data(), 2, 1)) ==
        AssemblyDiagnostic::None);
    TERMIN_QOPT_CHECK(assembly.add_unilateral_limit(contact_rows.handle,
                                                    {
                                                        unilateral_limits.data(),
                                                        unilateral_limits.size(),
                                                        1,
                                                    }) == AssemblyDiagnostic::None);
    TERMIN_QOPT_CHECK(unilateral_jacobian[0] == 1.0);
    TERMIN_QOPT_CHECK(unilateral_jacobian[1] == -1.0);
    TERMIN_QOPT_CHECK(unilateral_jacobian[2] == 2.0);
    TERMIN_QOPT_CHECK(unilateral_jacobian[3] == -2.0);
    TERMIN_QOPT_CHECK(unilateral_limit == unilateral_limits);

    DynamicsUnilateralTopology next_unilateral_topology;
    const auto next_contact =
        next_unilateral_topology.register_constraint(1, "next_contact");
    TERMIN_QOPT_CHECK(next_contact.ok());
    TERMIN_QOPT_CHECK(next_unilateral_topology.finalize() == AssemblyDiagnostic::None);
    std::array<double, 2> next_jacobian{};
    std::array<double, 1> next_limit{};
    DynamicsAssembly next_assembly(
        topology,
        next_unilateral_topology,
        {
            DenseMatrixView::row_major(mass.data(), 2, 2),
            {load.data(), load.size(), 1},
            DenseMatrixView::row_major(jacobian.data(), 1, 2),
            {rhs.data(), rhs.size(), 1},
            DenseMatrixView::row_major(next_jacobian.data(), 1, 2),
            {next_limit.data(), next_limit.size(), 1},
        });
    TERMIN_QOPT_CHECK(next_assembly.valid());
    TERMIN_QOPT_CHECK(next_assembly.add_unilateral_limit(contact_rows.handle,
                                                         {next_limit.data(), 1, 1}) ==
                      AssemblyDiagnostic::InvalidBlock);
    TERMIN_QOPT_CHECK(
        next_assembly.add_unilateral_jacobian(
            next_contact.handle,
            first.handle,
            ConstDenseMatrixView::row_major(unilateral_first.data(), 2, 1)) ==
        AssemblyDiagnostic::DimensionMismatch);
    const std::array<double, 1> non_finite_limit{
        std::numeric_limits<double>::quiet_NaN(),
    };
    TERMIN_QOPT_CHECK(next_assembly.add_unilateral_limit(
                          next_contact.handle,
                          {non_finite_limit.data(), non_finite_limit.size(), 1}) ==
                      AssemblyDiagnostic::NonFiniteContribution);

    std::array<double, 2> acceleration{-100.0, -100.0};
    std::array<double, 1> reaction{-100.0};
    const QpSolveResult solved =
        solve_constrained_dynamics(assembly.system(),
                                   {
                                       {acceleration.data(), acceleration.size(), 1},
                                       {reaction.data(), reaction.size(), 1},
                                   });
    TERMIN_QOPT_CHECK(solved.status == QpStatus::Optimal);
    TERMIN_QOPT_CHECK(std::abs(acceleration[0] - 0.8) < 1e-10);
    TERMIN_QOPT_CHECK(std::abs(acceleration[1] - 0.8) < 1e-10);
    TERMIN_QOPT_CHECK(std::abs(reaction[0] + 2.4) < 1e-10);

    // A shifted coupling remains a regular feasible affine constraint.
    const std::array<double, 1> inconsistent_rhs{1.0};
    rhs[0] = inconsistent_rhs[0];
    acceleration = {-7.0, -8.0};
    reaction = {-9.0};
    const QpSolveResult shifted =
        solve_constrained_dynamics(assembly.system(),
                                   {
                                       {acceleration.data(), acceleration.size(), 1},
                                       {reaction.data(), reaction.size(), 1},
                                   });
    TERMIN_QOPT_CHECK(shifted.status == QpStatus::Optimal);
    TERMIN_QOPT_CHECK(std::abs(acceleration[0] - acceleration[1] - 1.0) < 1e-10);

    std::array<double, 1> wrong_acceleration{-123.0};
    const QpSolveResult invalid = solve_constrained_dynamics(
        assembly.system(),
        {
            {wrong_acceleration.data(), wrong_acceleration.size(), 1},
            {reaction.data(), reaction.size(), 1},
        });
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
    const QpSolveResult null_load =
        solve_constrained_dynamics(null_load_system,
                                   {
                                       {acceleration.data(), acceleration.size(), 1},
                                       {reaction.data(), reaction.size(), 1},
                                   });
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
    TERMIN_QOPT_CHECK(inconsistent.diagnostic == QpDiagnostic::InconsistentEqualities);
    TERMIN_QOPT_CHECK(scalar_acceleration[0] == -21.0);
    TERMIN_QOPT_CHECK(duplicate_reaction[0] == -22.0);
    TERMIN_QOPT_CHECK(duplicate_reaction[1] == -23.0);

    DynamicsSystem system;
    auto scalar = std::make_unique<AnchoredScalarContribution>("first");
    AnchoredScalarContribution* scalar_state = scalar.get();
    auto second_scalar = std::make_unique<AnchoredScalarContribution>("second");
    second_scalar->position = -2.0;
    AnchoredScalarContribution* second_scalar_state = second_scalar.get();
    TERMIN_QOPT_CHECK(system.add_contribution(std::move(scalar)) ==
                      DynamicsSystemDiagnostic::None);
    TERMIN_QOPT_CHECK(system.add_contribution(std::move(second_scalar)) ==
                      DynamicsSystemDiagnostic::None);
    TERMIN_QOPT_CHECK(system.contribution_count() == 2);
    TERMIN_QOPT_CHECK(system.finalize() == DynamicsSystemDiagnostic::None);
    TERMIN_QOPT_CHECK(scalar_state->topology_bound);
    TERMIN_QOPT_CHECK(second_scalar_state->topology_bound);
    const DynamicsSystemStepResult system_step = system.step({
        .time_step = 0.01,
        .position_tolerance = 1e-12,
        .velocity_tolerance = 1e-12,
        .max_position_iterations = 2,
    });
    TERMIN_QOPT_CHECK(system_step.ok());
    TERMIN_QOPT_CHECK(system_step.position_iterations == 1);
    TERMIN_QOPT_CHECK(std::abs(scalar_state->position) < 1e-12);
    TERMIN_QOPT_CHECK(std::abs(scalar_state->velocity) < 1e-12);
    TERMIN_QOPT_CHECK(std::abs(scalar_state->acceleration) < 1e-12);
    TERMIN_QOPT_CHECK(std::abs(second_scalar_state->position) < 1e-12);
    TERMIN_QOPT_CHECK(std::abs(second_scalar_state->velocity) < 1e-12);
    TERMIN_QOPT_CHECK(std::abs(second_scalar_state->acceleration) < 1e-12);

    DynamicsSystem transient_system;
    auto transient = std::make_unique<TransientRowsContribution>();
    TransientRowsContribution* transient_state = transient.get();
    TERMIN_QOPT_CHECK(transient_system.add_contribution(std::move(transient)) ==
                      DynamicsSystemDiagnostic::None);
    TERMIN_QOPT_CHECK(transient_system.finalize() == DynamicsSystemDiagnostic::None);
    transient_state->requested_rows = 2;
    const DynamicsSystemStepResult unsupported = transient_system.step();
    TERMIN_QOPT_CHECK(unsupported.status == QpStatus::InvalidInput);
    TERMIN_QOPT_CHECK(unsupported.diagnostic ==
                      DynamicsSystemDiagnostic::UnilateralSolveUnavailable);
    TERMIN_QOPT_CHECK(unsupported.unilateral_constraint_count == 2);
    TERMIN_QOPT_CHECK(transient_state->rollback_count == 1);

    transient_state->requested_rows = 0;
    const DynamicsSystemStepResult zero_rows = transient_system.step();
    TERMIN_QOPT_CHECK(zero_rows.ok());
    TERMIN_QOPT_CHECK(zero_rows.unilateral_constraint_count == 0);
    TERMIN_QOPT_CHECK(transient_state->registration_count == 2);

    return 0;
}
