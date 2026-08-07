#include <termin/physics_qopt/dynamics.hpp>

#include <termin/physics_qopt/contact_friction.hpp>

#include <algorithm>
#include <array>
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <exception>
#include <limits>
#include <unordered_set>
#include <vector>

namespace termin::physics_qopt
{
    namespace
    {

        [[nodiscard]] AssemblyDiagnostic first_diagnostic(
            std::initializer_list<AssemblyDiagnostic> diagnostics) noexcept
        {
            for (const AssemblyDiagnostic diagnostic : diagnostics)
            {
                if (diagnostic != AssemblyDiagnostic::None)
                {
                    return diagnostic;
                }
            }
            return AssemblyDiagnostic::None;
        }

        [[nodiscard]] QpDiagnostic
        validate_output(DenseVectorView view,
                        std::size_t expected_size) noexcept
        {
            if (view.size != expected_size)
            {
                return QpDiagnostic::DimensionMismatch;
            }
            if (view.empty())
            {
                return QpDiagnostic::None;
            }
            if (view.data == nullptr)
            {
                return QpDiagnostic::NullData;
            }
            if (view.stride <= 0)
            {
                return QpDiagnostic::InvalidStride;
            }
            return QpDiagnostic::None;
        }

        [[nodiscard]] QpDiagnostic
        validate_optional_output(DenseVectorView view,
                                 std::size_t expected_size) noexcept
        {
            if (view.empty())
            {
                return QpDiagnostic::None;
            }
            return validate_output(view, expected_size);
        }

        [[nodiscard]] QpDiagnostic
        validate_system(ConstDynamicsSystemView system) noexcept
        {
            const std::size_t dof_count = system.load.size;
            const std::size_t constraint_count = system.constraint_rhs.size;
            if (system.mass.rows != dof_count ||
                system.mass.columns != dof_count ||
                system.constraint_jacobian.rows != constraint_count ||
                system.constraint_jacobian.columns != dof_count)
            {
                return QpDiagnostic::DimensionMismatch;
            }
            if ((!system.load.empty() && system.load.data == nullptr) ||
                (!system.mass.empty() && system.mass.data == nullptr) ||
                (!system.constraint_jacobian.empty() &&
                 system.constraint_jacobian.data == nullptr) ||
                (!system.constraint_rhs.empty() &&
                 system.constraint_rhs.data == nullptr))
            {
                return QpDiagnostic::NullData;
            }
            if ((!system.load.empty() && system.load.stride <= 0) ||
                (!system.mass.empty() && (system.mass.row_stride <= 0 ||
                                          system.mass.column_stride <= 0)) ||
                (!system.constraint_jacobian.empty() &&
                 (system.constraint_jacobian.row_stride <= 0 ||
                  system.constraint_jacobian.column_stride <= 0)) ||
                (!system.constraint_rhs.empty() &&
                 system.constraint_rhs.stride <= 0))
            {
                return QpDiagnostic::InvalidStride;
            }
            return QpDiagnostic::None;
        }

        [[nodiscard]] bool outputs_overlap(DenseVectorView first,
                                           DenseVectorView second)
        {
            if (first.empty() || second.empty())
            {
                return false;
            }
            std::unordered_set<std::uintptr_t> addresses;
            addresses.reserve(first.size);
            for (std::size_t index = 0; index < first.size; ++index)
            {
                addresses.insert(
                    reinterpret_cast<std::uintptr_t>(&first[index]));
            }
            for (std::size_t index = 0; index < second.size; ++index)
            {
                if (addresses.contains(
                        reinterpret_cast<std::uintptr_t>(&second[index])))
                {
                    return true;
                }
            }
            return false;
        }

        [[nodiscard]] bool
        any_outputs_overlap(std::initializer_list<DenseVectorView> outputs)
        {
            for (auto first = outputs.begin(); first != outputs.end(); ++first)
            {
                for (auto second = first + 1; second != outputs.end(); ++second)
                {
                    if (outputs_overlap(*first, *second))
                    {
                        return true;
                    }
                }
            }
            return false;
        }

        [[nodiscard]] QpSolveResult
        invalid_result(QpDiagnostic diagnostic) noexcept
        {
            QpSolveResult result;
            result.status = QpStatus::InvalidInput;
            result.diagnostic = diagnostic;
            return result;
        }

    } // namespace
    DynamicsFrictionAssembly::DynamicsFrictionAssembly(
        const DynamicsTopology& topology,
        const DynamicsFrictionTopology& friction_topology,
        DynamicsFrictionWorkspaceView workspace) noexcept
        : workspace_(workspace),
          contact_normal_jacobian_(friction_topology.contact_topology(),
                                   topology.dof_topology(),
                                   workspace.contact_normal_jacobian),
          tangent_jacobian_(friction_topology.tangent_topology(),
                            topology.dof_topology(),
                            workspace.tangent_jacobian),
          normal_impulse_(friction_topology.contact_topology(),
                          workspace.normal_impulse),
          friction_coefficient_(friction_topology.contact_topology(),
                                workspace.friction_coefficient)
    {
        if (!topology.finalized() || !friction_topology.finalized())
        {
            diagnostic_ = AssemblyDiagnostic::TopologyNotFinalized;
            return;
        }
        diagnostic_ = first_diagnostic({
            contact_normal_jacobian_.diagnostic(),
            tangent_jacobian_.diagnostic(),
            normal_impulse_.diagnostic(),
            friction_coefficient_.diagnostic(),
        });
    }

    AssemblyDiagnostic DynamicsFrictionAssembly::diagnostic() const noexcept
    {
        return diagnostic_;
    }

    bool DynamicsFrictionAssembly::valid() const noexcept
    {
        return diagnostic_ == AssemblyDiagnostic::None;
    }

    AssemblyDiagnostic DynamicsFrictionAssembly::clear() noexcept
    {
        if (!valid())
        {
            return diagnostic_;
        }
        return first_diagnostic({
            contact_normal_jacobian_.clear(),
            tangent_jacobian_.clear(),
            normal_impulse_.clear(),
            friction_coefficient_.clear(),
        });
    }

    AssemblyDiagnostic DynamicsFrictionAssembly::add_tangent_jacobian(
        DynamicsFrictionContactHandle contact,
        DynamicsDofHandle dofs,
        ConstDenseMatrixView contribution) noexcept
    {
        return tangent_jacobian_.add(
            contact.tangent_block, dofs.block, contribution);
    }

    AssemblyDiagnostic DynamicsFrictionAssembly::add_contact_normal_jacobian(
        DynamicsFrictionContactHandle contact,
        DynamicsDofHandle dofs,
        ConstDenseMatrixView contribution) noexcept
    {
        return contact_normal_jacobian_.add(
            contact.contact_block, dofs.block, contribution);
    }

    AssemblyDiagnostic DynamicsFrictionAssembly::add_normal_impulse(
        DynamicsFrictionContactHandle contact, double impulse) noexcept
    {
        const std::array<double, 1> value{impulse};
        return normal_impulse_.add(contact.contact_block,
                                   {value.data(), value.size(), 1});
    }

    AssemblyDiagnostic DynamicsFrictionAssembly::add_friction_coefficient(
        DynamicsFrictionContactHandle contact, double coefficient) noexcept
    {
        const std::array<double, 1> value{coefficient};
        return friction_coefficient_.add(contact.contact_block,
                                         {value.data(), value.size(), 1});
    }

    DynamicsAssembly::DynamicsAssembly(const DynamicsTopology& topology,
                                       DynamicsWorkspaceView workspace) noexcept
        : workspace_(workspace),
          mass_(
              topology.dof_topology(), topology.dof_topology(), workspace.mass),
          load_(topology.dof_topology(), workspace.load),
          constraint_jacobian_(topology.constraint_topology(),
                               topology.dof_topology(),
                               workspace.constraint_jacobian),
          constraint_rhs_(topology.constraint_topology(),
                          workspace.constraint_rhs)
    {
        if (!topology.finalized())
        {
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

    DynamicsAssembly::DynamicsAssembly(
        const DynamicsTopology& topology,
        const DynamicsUnilateralTopology& unilateral_topology,
        DynamicsWorkspaceView workspace) noexcept
        : workspace_(workspace),
          mass_(
              topology.dof_topology(), topology.dof_topology(), workspace.mass),
          load_(topology.dof_topology(), workspace.load),
          constraint_jacobian_(topology.constraint_topology(),
                               topology.dof_topology(),
                               workspace.constraint_jacobian),
          constraint_rhs_(topology.constraint_topology(),
                          workspace.constraint_rhs)
    {
        if (!topology.finalized() || !unilateral_topology.finalized())
        {
            diagnostic_ = AssemblyDiagnostic::TopologyNotFinalized;
            return;
        }
        diagnostic_ = first_diagnostic({
            mass_.diagnostic(),
            load_.diagnostic(),
            constraint_jacobian_.diagnostic(),
            constraint_rhs_.diagnostic(),
        });
        if (diagnostic_ != AssemblyDiagnostic::None)
        {
            return;
        }
        try
        {
            unilateral_jacobian_ = std::make_unique<DenseBlockMatrixAssembly>(
                unilateral_topology.constraint_topology(),
                topology.dof_topology(),
                workspace.unilateral_jacobian);
            unilateral_limit_ = std::make_unique<DenseBlockVectorAssembly>(
                unilateral_topology.constraint_topology(),
                workspace.unilateral_limit);
            diagnostic_ = first_diagnostic({
                unilateral_jacobian_->diagnostic(),
                unilateral_limit_->diagnostic(),
            });
        }
        catch (const std::exception& error)
        {
            std::fprintf(stderr,
                         "[termin-qopt] unilateral assembly construction "
                         "failed: %s\n",
                         error.what());
            diagnostic_ = AssemblyDiagnostic::InternalFailure;
        }
        catch (...)
        {
            std::fprintf(stderr,
                         "[termin-qopt] unilateral assembly construction "
                         "failed with unknown exception\n");
            diagnostic_ = AssemblyDiagnostic::InternalFailure;
        }
    }

    AssemblyDiagnostic DynamicsAssembly::diagnostic() const noexcept
    {
        return diagnostic_;
    }

    bool DynamicsAssembly::valid() const noexcept
    {
        return diagnostic_ == AssemblyDiagnostic::None;
    }

    AssemblyDiagnostic DynamicsAssembly::clear() noexcept
    {
        if (!valid())
        {
            return diagnostic_;
        }
        const AssemblyDiagnostic permanent = first_diagnostic({
            mass_.clear(),
            load_.clear(),
            constraint_jacobian_.clear(),
            constraint_rhs_.clear(),
        });
        if (permanent != AssemblyDiagnostic::None ||
            unilateral_jacobian_ == nullptr)
        {
            return permanent;
        }
        return first_diagnostic({
            unilateral_jacobian_->clear(),
            unilateral_limit_->clear(),
        });
    }

    AssemblyDiagnostic
    DynamicsAssembly::add_mass(DynamicsDofHandle row,
                               DynamicsDofHandle column,
                               ConstDenseMatrixView contribution) noexcept
    {
        return mass_.add(row.block, column.block, contribution);
    }

    AssemblyDiagnostic
    DynamicsAssembly::add_load(DynamicsDofHandle dofs,
                               ConstDenseVectorView contribution) noexcept
    {
        return load_.add(dofs.block, contribution);
    }

    AssemblyDiagnostic DynamicsAssembly::add_constraint_jacobian(
        DynamicsConstraintHandle constraint,
        DynamicsDofHandle dofs,
        ConstDenseMatrixView contribution) noexcept
    {
        return constraint_jacobian_.add(
            constraint.block, dofs.block, contribution);
    }

    AssemblyDiagnostic DynamicsAssembly::add_constraint_rhs(
        DynamicsConstraintHandle constraint,
        ConstDenseVectorView contribution) noexcept
    {
        return constraint_rhs_.add(constraint.block, contribution);
    }

    AssemblyDiagnostic DynamicsAssembly::add_unilateral_jacobian(
        DynamicsUnilateralConstraintHandle constraint,
        DynamicsDofHandle dofs,
        ConstDenseMatrixView contribution) noexcept
    {
        if (unilateral_jacobian_ == nullptr)
        {
            return AssemblyDiagnostic::InvalidBlock;
        }
        return unilateral_jacobian_->add(
            constraint.block, dofs.block, contribution);
    }

    AssemblyDiagnostic DynamicsAssembly::add_unilateral_limit(
        DynamicsUnilateralConstraintHandle constraint,
        ConstDenseVectorView contribution) noexcept
    {
        if (unilateral_limit_ == nullptr)
        {
            return AssemblyDiagnostic::InvalidBlock;
        }
        return unilateral_limit_->add(constraint.block, contribution);
    }

    ConstDynamicsSystemView DynamicsAssembly::system() const noexcept
    {
        return {
            workspace_.mass,
            workspace_.load,
            workspace_.constraint_jacobian,
            workspace_.constraint_rhs,
        };
    }

    ConstDynamicsUnilateralView
    DynamicsAssembly::unilateral_constraints() const noexcept
    {
        return {
            workspace_.unilateral_jacobian,
            workspace_.unilateral_limit,
        };
    }

    static QpSolveResult solve_constrained_dynamics_impl(
        ConstDynamicsSystemView system,
        DynamicsSolutionView solution,
        QpTolerance tolerance,
        EqualityQpFactorizationCache* factorization_cache) noexcept
    {
        const std::size_t dof_count = system.load.size;
        const std::size_t constraint_count = system.constraint_rhs.size;
        const QpDiagnostic system_diagnostic = validate_system(system);
        if (system_diagnostic != QpDiagnostic::None)
        {
            return invalid_result(system_diagnostic);
        }
        const QpDiagnostic acceleration_diagnostic =
            validate_output(solution.acceleration, dof_count);
        if (acceleration_diagnostic != QpDiagnostic::None)
        {
            return invalid_result(acceleration_diagnostic);
        }
        const QpDiagnostic reaction_diagnostic =
            validate_output(solution.constraint_reaction, constraint_count);
        if (reaction_diagnostic != QpDiagnostic::None)
        {
            return invalid_result(reaction_diagnostic);
        }

        try
        {
            if (outputs_overlap(solution.acceleration,
                                solution.constraint_reaction))
            {
                return invalid_result(QpDiagnostic::OverlappingOutputs);
            }

            std::vector<double> gradient(dof_count);
            std::vector<double> acceleration(dof_count);
            std::vector<double> equality_dual(constraint_count);
            for (std::size_t index = 0; index < dof_count; ++index)
            {
                if (!std::isfinite(system.load[index]))
                {
                    return invalid_result(QpDiagnostic::NonFiniteInput);
                }
                gradient[index] = -system.load[index];
            }

            const EqualityQpProblemView problem = {
                system.mass,
                {gradient.data(), gradient.size(), 1},
                system.constraint_jacobian,
                system.constraint_rhs,
            };
            const EqualityQpSolutionView qp_solution = {
                {acceleration.data(), acceleration.size(), 1},
                {equality_dual.data(), equality_dual.size(), 1},
            };
            const QpSolveResult result =
                factorization_cache == nullptr
                    ? solve_equality_qp(problem, qp_solution, tolerance)
                    : factorization_cache->solve(
                          problem, qp_solution, tolerance);
            if (result.status != QpStatus::Optimal)
            {
                return result;
            }
            for (std::size_t index = 0; index < dof_count; ++index)
            {
                solution.acceleration[index] = acceleration[index];
            }
            for (std::size_t index = 0; index < constraint_count; ++index)
            {
                solution.constraint_reaction[index] = -equality_dual[index];
            }
            return result;
        }
        catch (const std::exception& error)
        {
            std::fprintf(
                stderr,
                "[termin-qopt] constrained dynamics solve failed: %s\n",
                error.what());
        }
        catch (...)
        {
            std::fprintf(stderr,
                         "[termin-qopt] constrained dynamics solve failed with "
                         "an unknown exception\n");
        }

        QpSolveResult result;
        result.status = QpStatus::NumericalFailure;
        result.diagnostic = QpDiagnostic::DecompositionFailure;
        return result;
    }

    QpSolveResult solve_constrained_dynamics(
        ConstDynamicsSystemView system,
        DynamicsSolutionView solution,
        QpTolerance tolerance) noexcept
    {
        return solve_constrained_dynamics_impl(
            system, solution, tolerance, nullptr);
    }

    QpSolveResult
    solve_unilateral_velocity(ConstDynamicsSystemView system,
                              ConstDynamicsUnilateralView unilateral,
                              DynamicsVelocitySolutionView solution,
                              ActiveSetQpWarmStartView warm_start,
                              ActiveSetQpOptions options) noexcept
    {
        const std::size_t dof_count = system.load.size;
        const std::size_t equality_count = system.constraint_rhs.size;
        const std::size_t unilateral_count = unilateral.limit.size;
        const QpDiagnostic system_diagnostic = validate_system(system);
        if (system_diagnostic != QpDiagnostic::None)
        {
            return invalid_result(system_diagnostic);
        }
        if (unilateral.jacobian.rows != unilateral_count ||
            unilateral.jacobian.columns != dof_count)
        {
            return invalid_result(QpDiagnostic::DimensionMismatch);
        }
        if ((!unilateral.jacobian.empty() &&
             unilateral.jacobian.data == nullptr) ||
            (!unilateral.limit.empty() && unilateral.limit.data == nullptr))
        {
            return invalid_result(QpDiagnostic::NullData);
        }
        if ((!unilateral.jacobian.empty() &&
             (unilateral.jacobian.row_stride <= 0 ||
              unilateral.jacobian.column_stride <= 0)) ||
            (!unilateral.limit.empty() && unilateral.limit.stride <= 0))
        {
            return invalid_result(QpDiagnostic::InvalidStride);
        }

        const QpDiagnostic output_diagnostics[] = {
            validate_output(solution.velocity, dof_count),
            validate_output(solution.constraint_reaction, equality_count),
            validate_output(solution.unilateral_reaction, unilateral_count),
            validate_optional_output(solution.tight_unilateral_mask,
                                     unilateral_count),
        };
        for (const QpDiagnostic diagnostic : output_diagnostics)
        {
            if (diagnostic != QpDiagnostic::None)
            {
                return invalid_result(diagnostic);
            }
        }
        if (any_outputs_overlap({
                solution.velocity,
                solution.constraint_reaction,
                solution.unilateral_reaction,
                solution.tight_unilateral_mask,
            }))
        {
            return invalid_result(QpDiagnostic::OverlappingOutputs);
        }

        try
        {
            std::vector<double> gradient(dof_count);
            std::vector<double> velocity(dof_count);
            std::vector<double> equality_dual(equality_count);
            std::vector<double> unilateral_dual(unilateral_count);
            std::vector<double> tight_mask(unilateral_count);
            for (std::size_t index = 0; index < dof_count; ++index)
            {
                if (!std::isfinite(system.load[index]))
                {
                    return invalid_result(QpDiagnostic::NonFiniteInput);
                }
                gradient[index] = -system.load[index];
            }

            const QpSolveResult result = solve_active_set_qp(
                {
                    system.mass,
                    {gradient.data(), gradient.size(), 1},
                    system.constraint_jacobian,
                    system.constraint_rhs,
                    unilateral.jacobian,
                    unilateral.limit,
                    {},
                    {},
                },
                {
                    {velocity.data(), velocity.size(), 1},
                    {equality_dual.data(), equality_dual.size(), 1},
                    {unilateral_dual.data(), unilateral_dual.size(), 1},
                    {},
                    {},
                },
                warm_start,
                options);
            if (result.status != QpStatus::Optimal)
            {
                return result;
            }

            for (std::size_t row = 0; row < unilateral_count; ++row)
            {
                double value = -unilateral.limit[row];
                for (std::size_t column = 0; column < dof_count; ++column)
                {
                    value +=
                        unilateral.jacobian(row, column) * velocity[column];
                }
                tight_mask[row] =
                    std::abs(value) <= options.active_tolerance ? 1.0 : 0.0;
            }
            for (std::size_t index = 0; index < dof_count; ++index)
            {
                solution.velocity[index] = velocity[index];
            }
            for (std::size_t index = 0; index < equality_count; ++index)
            {
                solution.constraint_reaction[index] = -equality_dual[index];
            }
            for (std::size_t index = 0; index < unilateral_count; ++index)
            {
                solution.unilateral_reaction[index] = unilateral_dual[index];
                if (!solution.tight_unilateral_mask.empty())
                {
                    solution.tight_unilateral_mask[index] = tight_mask[index];
                }
            }
            return result;
        }
        catch (const std::exception& error)
        {
            std::fprintf(stderr,
                         "[termin-qopt] unilateral velocity solve failed: %s\n",
                         error.what());
        }
        catch (...)
        {
            std::fprintf(stderr,
                         "[termin-qopt] unilateral velocity solve failed with "
                         "an unknown exception\n");
        }

        QpSolveResult result;
        result.status = QpStatus::NumericalFailure;
        result.diagnostic = QpDiagnostic::DecompositionFailure;
        return result;
    }

    namespace
    {

        [[nodiscard]] DynamicsSystemStepResult dynamics_system_failure(
            QpStatus status,
            DynamicsSystemDiagnostic diagnostic,
            QpSolveResult dynamics = {},
            std::size_t unilateral_constraint_count = 0) noexcept
        {
            DynamicsSystemStepResult result;
            result.status = status;
            result.diagnostic = diagnostic;
            result.dynamics = dynamics;
            result.unilateral_constraint_count = unilateral_constraint_count;
            return result;
        }

    } // namespace

    struct DynamicsSystem::Impl
    {
        DynamicsTopology topology;
        DynamicsUnilateralTopology unilateral_topology;
        DynamicsFrictionTopology friction_topology;
        std::vector<std::unique_ptr<DynamicsContribution>> contributions;
        std::vector<double> mass;
        std::vector<double> load;
        std::vector<double> jacobian;
        std::vector<double> constraint_rhs;
        std::vector<double> unilateral_jacobian;
        std::vector<double> unilateral_limit;
        std::vector<double> unilateral_reaction;
        std::vector<double> unilateral_tight_mask;
        std::vector<double> unilateral_warm_mask;
        std::vector<double> friction_tangent_jacobian;
        std::vector<double> friction_contact_normal_jacobian;
        std::vector<double> friction_normal_jacobian;
        std::vector<double> friction_minimum_normal_velocity;
        std::vector<double> friction_normal_impulse;
        std::vector<double> friction_coefficient;
        std::vector<double> friction_tangent_impulse;
        std::vector<double> friction_work;
        std::vector<double> friction_bilateral_impulse;
        std::vector<double> velocity_warm_primal;
        std::vector<double> dof_solution;
        std::vector<double> constraint_reaction;
        std::vector<double> velocity;
        std::vector<double> midpoint_velocity;
        std::vector<double> corrected_midpoint_velocity;
        std::vector<double> configuration_velocity;
        std::vector<double> corrected_configuration_velocity;
        std::vector<double> pre_friction_velocity;
        std::vector<double> post_friction_velocity;
        std::vector<double> endpoint_velocity_predictor;
        std::size_t step_contribution_count = 0;
        bool finalized = false;
        bool velocity_warm_primal_valid = false;

        [[nodiscard]] DynamicsSystemDiagnostic
        assemble(DynamicsAssembly& assembly,
                 DynamicsAssemblyPhase phase) noexcept
        {
            if (assembly.clear() != AssemblyDiagnostic::None)
            {
                return DynamicsSystemDiagnostic::AssemblyFailure;
            }
            for (std::size_t index = 0; index < contributions.size(); ++index)
            {
                const AssemblyDiagnostic diagnostic =
                    contributions[index]->assemble(assembly, phase);
                if (diagnostic != AssemblyDiagnostic::None)
                {
                    std::fprintf(stderr,
                                 "[termin-qopt] contribution %zu assembly "
                                 "failed in phase %u: %s\n",
                                 index,
                                 static_cast<unsigned>(phase),
                                 assembly_diagnostic_name(diagnostic).data());
                    return DynamicsSystemDiagnostic::AssemblyFailure;
                }
            }
            return DynamicsSystemDiagnostic::None;
        }

        [[nodiscard]] DynamicsSystemDiagnostic begin_step() noexcept
        {
            step_contribution_count = 0;
            for (const auto& contribution : contributions)
            {
                if (contribution->begin_step() != AssemblyDiagnostic::None)
                {
                    std::fprintf(stderr,
                                 "[termin-qopt] contribution %zu failed to "
                                 "begin a transactional step\n",
                                 step_contribution_count);
                    return DynamicsSystemDiagnostic::InternalFailure;
                }
                ++step_contribution_count;
            }
            return DynamicsSystemDiagnostic::None;
        }

        [[nodiscard]] DynamicsSystemDiagnostic
        prepare_unilateral_topology(double time_step)
        {
            unilateral_topology = DynamicsUnilateralTopology{};
            for (std::size_t index = 0; index < contributions.size(); ++index)
            {
                const AssemblyDiagnostic diagnostic =
                    contributions[index]->register_unilateral_constraints(
                        unilateral_topology, time_step);
                if (diagnostic != AssemblyDiagnostic::None)
                {
                    std::fprintf(
                        stderr,
                        "[termin-qopt] contribution %zu transient "
                        "unilateral topology registration failed: %s\n",
                        index,
                        assembly_diagnostic_name(diagnostic).data());
                    return DynamicsSystemDiagnostic::TopologyFailure;
                }
            }
            const AssemblyDiagnostic finalize_diagnostic =
                unilateral_topology.finalize();
            if (finalize_diagnostic != AssemblyDiagnostic::None)
            {
                std::fprintf(
                    stderr,
                    "[termin-qopt] transient unilateral topology "
                    "finalization failed: %s\n",
                    assembly_diagnostic_name(finalize_diagnostic).data());
                return DynamicsSystemDiagnostic::TopologyFailure;
            }
            const std::size_t constraints =
                unilateral_topology.constraint_count();
            const std::size_t dofs = topology.dof_count();
            if (dofs != 0 &&
                constraints > std::numeric_limits<std::size_t>::max() / dofs)
            {
                std::fprintf(stderr,
                             "[termin-qopt] transient unilateral workspace "
                             "size overflow\n");
                return DynamicsSystemDiagnostic::InternalFailure;
            }
            unilateral_jacobian.assign(constraints * dofs, 0.0);
            unilateral_limit.assign(constraints, 0.0);
            unilateral_reaction.assign(constraints, 0.0);
            unilateral_tight_mask.assign(constraints, 0.0);
            unilateral_warm_mask.assign(constraints, 0.0);
            return DynamicsSystemDiagnostic::None;
        }

        [[nodiscard]] DynamicsSystemDiagnostic
        prepare_friction_topology(double time_step)
        {
            friction_topology = DynamicsFrictionTopology{};
            for (std::size_t index = 0; index < contributions.size(); ++index)
            {
                const AssemblyDiagnostic diagnostic =
                    contributions[index]->register_friction_contacts(
                        friction_topology, time_step);
                if (diagnostic != AssemblyDiagnostic::None)
                {
                    std::fprintf(stderr,
                                 "[termin-qopt] contribution %zu transient "
                                 "friction topology registration failed: %s\n",
                                 index,
                                 assembly_diagnostic_name(diagnostic).data());
                    return DynamicsSystemDiagnostic::TopologyFailure;
                }
            }
            const AssemblyDiagnostic finalize_diagnostic =
                friction_topology.finalize();
            if (finalize_diagnostic != AssemblyDiagnostic::None)
            {
                std::fprintf(
                    stderr,
                    "[termin-qopt] transient friction topology "
                    "finalization failed: %s\n",
                    assembly_diagnostic_name(finalize_diagnostic).data());
                return DynamicsSystemDiagnostic::TopologyFailure;
            }

            const std::size_t dofs = topology.dof_count();
            const std::size_t tangents = friction_topology.tangent_count();
            const std::size_t contacts = friction_topology.contact_count();
            if (dofs != 0 &&
                tangents > std::numeric_limits<std::size_t>::max() / dofs)
            {
                std::fprintf(stderr,
                             "[termin-qopt] transient friction workspace size "
                             "overflow\n");
                return DynamicsSystemDiagnostic::InternalFailure;
            }
            friction_tangent_jacobian.assign(tangents * dofs, 0.0);
            friction_contact_normal_jacobian.assign(contacts * dofs, 0.0);
            friction_normal_impulse.assign(contacts, 0.0);
            friction_coefficient.assign(contacts, 0.0);
            friction_tangent_impulse.assign(tangents, 0.0);
            friction_work.assign(contacts, 0.0);
            friction_bilateral_impulse.assign(topology.constraint_count(), 0.0);
            return DynamicsSystemDiagnostic::None;
        }

        [[nodiscard]] DynamicsSystemDiagnostic
        assemble_friction(DynamicsFrictionAssembly& assembly) noexcept
        {
            if (assembly.clear() != AssemblyDiagnostic::None)
            {
                return DynamicsSystemDiagnostic::AssemblyFailure;
            }
            for (std::size_t index = 0; index < contributions.size(); ++index)
            {
                const AssemblyDiagnostic diagnostic =
                    contributions[index]->assemble_friction(assembly);
                if (diagnostic != AssemblyDiagnostic::None)
                {
                    std::fprintf(stderr,
                                 "[termin-qopt] contribution %zu friction "
                                 "assembly failed: %s\n",
                                 index,
                                 assembly_diagnostic_name(diagnostic).data());
                    return DynamicsSystemDiagnostic::AssemblyFailure;
                }
            }
            return DynamicsSystemDiagnostic::None;
        }

        [[nodiscard]] ActiveSetQpWarmStartView unilateral_warm_start() noexcept
        {
            if (!velocity_warm_primal_valid ||
                velocity_warm_primal.size() != topology.dof_count() ||
                unilateral_warm_mask.size() !=
                    unilateral_topology.constraint_count())
            {
                return {};
            }
            std::fill(
                unilateral_warm_mask.begin(), unilateral_warm_mask.end(), 0.0);
            bool has_hint = false;
            const DenseVectorView mask{
                unilateral_warm_mask.data(),
                unilateral_warm_mask.size(),
                1,
            };
            for (const auto& contribution : contributions)
            {
                has_hint |= contribution->write_unilateral_warm_start(
                    unilateral_topology, mask);
            }
            if (!has_hint)
            {
                return {};
            }
            return {
                {velocity_warm_primal.data(), velocity_warm_primal.size(), 1},
                {unilateral_warm_mask.data(), unilateral_warm_mask.size(), 1},
                {},
                {},
            };
        }

        void commit_step() noexcept
        {
            for (std::size_t index = 0; index < step_contribution_count;
                 ++index)
            {
                contributions[index]->commit_step();
            }
            step_contribution_count = 0;
        }

        void rollback_step() noexcept
        {
            while (step_contribution_count != 0)
            {
                --step_contribution_count;
                contributions[step_contribution_count]->rollback_step();
            }
        }

        void apply_solution(DynamicsAssemblyPhase phase) noexcept
        {
            const ConstDenseVectorView dofs{
                dof_solution.data(),
                dof_solution.size(),
                1,
            };
            const ConstDenseVectorView reactions{
                constraint_reaction.data(),
                constraint_reaction.size(),
                1,
            };
            for (const auto& contribution : contributions)
            {
                contribution->apply_solution(phase, topology, dofs, reactions);
            }
        }

        void apply_unilateral_solution() noexcept
        {
            const ConstDenseVectorView reactions{
                unilateral_reaction.data(),
                unilateral_reaction.size(),
                1,
            };
            const ConstDenseVectorView tight_mask{
                unilateral_tight_mask.data(),
                unilateral_tight_mask.size(),
                1,
            };
            for (const auto& contribution : contributions)
            {
                contribution->apply_unilateral_solution(
                    topology, unilateral_topology, reactions, tight_mask);
            }
        }

        void apply_friction_solution() noexcept
        {
            const ConstDenseVectorView impulses{
                friction_tangent_impulse.data(),
                friction_tangent_impulse.size(),
                1,
            };
            const ConstDenseVectorView normal_impulses{
                friction_normal_impulse.data(),
                friction_normal_impulse.size(),
                1,
            };
            const ConstDenseVectorView work{
                friction_work.data(),
                friction_work.size(),
                1,
            };
            for (const auto& contribution : contributions)
            {
                contribution->apply_friction_solution(
                    friction_topology, normal_impulses, impulses, work);
            }
        }

        [[nodiscard]] DynamicsSystemDiagnostic read_velocity() noexcept
        {
            std::fill(velocity.begin(),
                      velocity.end(),
                      std::numeric_limits<double>::quiet_NaN());
            const DenseVectorView destination{
                velocity.data(),
                velocity.size(),
                1,
            };
            for (std::size_t index = 0; index < contributions.size(); ++index)
            {
                const AssemblyDiagnostic diagnostic =
                    contributions[index]->write_velocity(topology, destination);
                if (diagnostic != AssemblyDiagnostic::None)
                {
                    std::fprintf(stderr,
                                 "[termin-qopt] contribution %zu failed to "
                                 "write generalized velocity: %s\n",
                                 index,
                                 assembly_diagnostic_name(diagnostic).data());
                    return DynamicsSystemDiagnostic::InternalFailure;
                }
            }
            if (!std::all_of(velocity.begin(),
                             velocity.end(),
                             [](double value) { return std::isfinite(value); }))
            {
                std::fprintf(stderr,
                             "[termin-qopt] one or more generalized DOFs have "
                             "no finite velocity owner\n");
                return DynamicsSystemDiagnostic::InternalFailure;
            }
            return DynamicsSystemDiagnostic::None;
        }

        [[nodiscard]] DynamicsSystemDiagnostic
        write_velocity(ConstDenseVectorView source) noexcept
        {
            for (std::size_t index = 0; index < contributions.size(); ++index)
            {
                const AssemblyDiagnostic diagnostic =
                    contributions[index]->set_velocity(topology, source);
                if (diagnostic != AssemblyDiagnostic::None)
                {
                    std::fprintf(stderr,
                                 "[termin-qopt] contribution %zu rejected "
                                 "generalized velocity: %s\n",
                                 index,
                                 assembly_diagnostic_name(diagnostic).data());
                    return DynamicsSystemDiagnostic::InternalFailure;
                }
            }
            return DynamicsSystemDiagnostic::None;
        }

        [[nodiscard]] DynamicsSystemDiagnostic
        set_trial_configuration(ConstDenseVectorView source,
                                double time_step) noexcept
        {
            for (std::size_t index = 0; index < contributions.size(); ++index)
            {
                const AssemblyDiagnostic diagnostic =
                    contributions[index]->set_trial_configuration(
                        topology, source, time_step);
                if (diagnostic != AssemblyDiagnostic::None)
                {
                    std::fprintf(stderr,
                                 "[termin-qopt] contribution %zu rejected "
                                 "trial configuration: %s\n",
                                 index,
                                 assembly_diagnostic_name(diagnostic).data());
                    return DynamicsSystemDiagnostic::InternalFailure;
                }
            }
            return DynamicsSystemDiagnostic::None;
        }

        [[nodiscard]] DynamicsSystemDiagnostic
        apply_position_correction(double time_step) noexcept
        {
            std::fill(corrected_configuration_velocity.begin(),
                      corrected_configuration_velocity.end(),
                      std::numeric_limits<double>::quiet_NaN());
            const ConstDenseVectorView configuration{
                configuration_velocity.data(),
                configuration_velocity.size(),
                1,
            };
            const ConstDenseVectorView correction{
                dof_solution.data(),
                dof_solution.size(),
                1,
            };
            const DenseVectorView destination{
                corrected_configuration_velocity.data(),
                corrected_configuration_velocity.size(),
                1,
            };
            for (std::size_t index = 0; index < contributions.size(); ++index)
            {
                const AssemblyDiagnostic diagnostic =
                    contributions[index]->write_corrected_midpoint_velocity(
                        topology,
                        configuration,
                        correction,
                        time_step,
                        destination);
                if (diagnostic != AssemblyDiagnostic::None)
                {
                    std::fprintf(stderr,
                                 "[termin-qopt] contribution %zu failed to map "
                                 "a trial tangent correction: %s\n",
                                 index,
                                 assembly_diagnostic_name(diagnostic).data());
                    return DynamicsSystemDiagnostic::InternalFailure;
                }
            }
            if (!std::all_of(corrected_configuration_velocity.begin(),
                             corrected_configuration_velocity.end(),
                             [](double value) { return std::isfinite(value); }))
            {
                std::fprintf(stderr,
                             "[termin-qopt] one or more generalized DOFs have "
                             "no position-correction owner\n");
                return DynamicsSystemDiagnostic::InternalFailure;
            }
            configuration_velocity.swap(corrected_configuration_velocity);
            return DynamicsSystemDiagnostic::None;
        }

        [[nodiscard]] DynamicsSystemDiagnostic
        apply_friction_configuration_correction(double time_step) noexcept
        {
            if (pre_friction_velocity.size() != dof_solution.size() ||
                post_friction_velocity.size() != dof_solution.size())
            {
                std::fprintf(stderr,
                             "[termin-qopt] friction configuration correction "
                             "has inconsistent velocity sizes\n");
                return DynamicsSystemDiagnostic::InternalFailure;
            }

            // The unconstrained midpoint has already advanced the trial
            // configuration. Friction changes the endpoint velocity later in
            // the step, so the trapezoidal configuration midpoint needs half
            // of that velocity change. The correction is expressed as a
            // tangent increment so each contribution can map it through its
            // own configuration geometry.
            for (std::size_t index = 0; index < dof_solution.size(); ++index)
            {
                dof_solution[index] =
                    0.5 * time_step *
                    (post_friction_velocity[index] -
                     pre_friction_velocity[index]);
            }
            if (apply_position_correction(time_step) !=
                    DynamicsSystemDiagnostic::None ||
                set_trial_configuration(
                    {configuration_velocity.data(),
                     configuration_velocity.size(),
                     1},
                    time_step) != DynamicsSystemDiagnostic::None ||
                write_velocity({post_friction_velocity.data(),
                                post_friction_velocity.size(),
                                1}) != DynamicsSystemDiagnostic::None)
            {
                return DynamicsSystemDiagnostic::InternalFailure;
            }

            dof_solution = post_friction_velocity;
            return DynamicsSystemDiagnostic::None;
        }

        [[nodiscard]] double max_position_error() const noexcept
        {
            double result = 0.0;
            for (const auto& contribution : contributions)
            {
                result = std::max(result, contribution->position_error_linf());
            }
            return result;
        }

        [[nodiscard]] double max_velocity_error() const noexcept
        {
            double result = 0.0;
            for (const auto& contribution : contributions)
            {
                result = std::max(result, contribution->velocity_error_linf());
            }
            return result;
        }
    };

    std::string_view dynamics_system_diagnostic_name(
        DynamicsSystemDiagnostic diagnostic) noexcept
    {
        switch (diagnostic)
        {
        case DynamicsSystemDiagnostic::None:
            return "none";
        case DynamicsSystemDiagnostic::ModelFinalized:
            return "model_finalized";
        case DynamicsSystemDiagnostic::ModelNotFinalized:
            return "model_not_finalized";
        case DynamicsSystemDiagnostic::NullContribution:
            return "null_contribution";
        case DynamicsSystemDiagnostic::InvalidTimeStep:
            return "invalid_time_step";
        case DynamicsSystemDiagnostic::InvalidProjectionOptions:
            return "invalid_projection_options";
        case DynamicsSystemDiagnostic::TopologyFailure:
            return "topology_failure";
        case DynamicsSystemDiagnostic::AssemblyFailure:
            return "assembly_failure";
        case DynamicsSystemDiagnostic::DynamicsFailure:
            return "dynamics_failure";
        case DynamicsSystemDiagnostic::PositionProjectionFailure:
            return "position_projection_failure";
        case DynamicsSystemDiagnostic::VelocityProjectionFailure:
            return "velocity_projection_failure";
        case DynamicsSystemDiagnostic::FrictionProjectionFailure:
            return "friction_projection_failure";
        case DynamicsSystemDiagnostic::InternalFailure:
            return "internal_failure";
        }
        return "unknown";
    }

    DynamicsSystem::DynamicsSystem() : impl_(std::make_unique<Impl>()) {}

    DynamicsSystem::~DynamicsSystem() = default;
    DynamicsSystem::DynamicsSystem(DynamicsSystem&&) noexcept = default;
    DynamicsSystem&
    DynamicsSystem::operator=(DynamicsSystem&&) noexcept = default;

    DynamicsSystemDiagnostic DynamicsSystem::add_contribution(
        std::unique_ptr<DynamicsContribution> contribution) noexcept
    {
        if (impl_ == nullptr)
        {
            return DynamicsSystemDiagnostic::InternalFailure;
        }
        if (impl_->finalized)
        {
            return DynamicsSystemDiagnostic::ModelFinalized;
        }
        if (contribution == nullptr)
        {
            return DynamicsSystemDiagnostic::NullContribution;
        }
        try
        {
            impl_->contributions.push_back(std::move(contribution));
            return DynamicsSystemDiagnostic::None;
        }
        catch (const std::exception& error)
        {
            std::fprintf(
                stderr,
                "[termin-qopt] adding dynamics contribution failed: %s\n",
                error.what());
        }
        catch (...)
        {
            std::fprintf(stderr,
                         "[termin-qopt] adding dynamics contribution failed "
                         "with unknown exception\n");
        }
        return DynamicsSystemDiagnostic::InternalFailure;
    }

    DynamicsSystemDiagnostic DynamicsSystem::finalize() noexcept
    {
        if (impl_ == nullptr)
        {
            return DynamicsSystemDiagnostic::InternalFailure;
        }
        if (impl_->finalized)
        {
            return DynamicsSystemDiagnostic::ModelFinalized;
        }
        for (std::size_t index = 0; index < impl_->contributions.size();
             ++index)
        {
            const AssemblyDiagnostic diagnostic =
                impl_->contributions[index]->register_topology(impl_->topology);
            if (diagnostic != AssemblyDiagnostic::None)
            {
                std::fprintf(stderr,
                             "[termin-qopt] contribution %zu topology "
                             "registration failed: %s\n",
                             index,
                             assembly_diagnostic_name(diagnostic).data());
                return DynamicsSystemDiagnostic::TopologyFailure;
            }
        }
        if (impl_->topology.finalize() != AssemblyDiagnostic::None)
        {
            return DynamicsSystemDiagnostic::TopologyFailure;
        }
        for (std::size_t index = 0; index < impl_->contributions.size();
             ++index)
        {
            const AssemblyDiagnostic diagnostic =
                impl_->contributions[index]->bind_topology(impl_->topology);
            if (diagnostic != AssemblyDiagnostic::None)
            {
                std::fprintf(stderr,
                             "[termin-qopt] contribution %zu topology binding "
                             "failed: %s\n",
                             index,
                             assembly_diagnostic_name(diagnostic).data());
                return DynamicsSystemDiagnostic::TopologyFailure;
            }
        }
        try
        {
            const std::size_t dofs = impl_->topology.dof_count();
            const std::size_t constraints = impl_->topology.constraint_count();
            impl_->mass.assign(dofs * dofs, 0.0);
            impl_->load.assign(dofs, 0.0);
            impl_->jacobian.assign(constraints * dofs, 0.0);
            impl_->constraint_rhs.assign(constraints, 0.0);
            impl_->dof_solution.assign(dofs, 0.0);
            impl_->constraint_reaction.assign(constraints, 0.0);
            impl_->velocity.assign(dofs, 0.0);
            impl_->midpoint_velocity.assign(dofs, 0.0);
            impl_->corrected_midpoint_velocity.assign(dofs, 0.0);
            impl_->configuration_velocity.assign(dofs, 0.0);
            impl_->corrected_configuration_velocity.assign(dofs, 0.0);
            impl_->pre_friction_velocity.assign(dofs, 0.0);
            impl_->post_friction_velocity.assign(dofs, 0.0);
            impl_->endpoint_velocity_predictor.assign(dofs, 0.0);
            impl_->velocity_warm_primal.assign(dofs, 0.0);
            impl_->velocity_warm_primal_valid = false;
            impl_->finalized = true;
            return DynamicsSystemDiagnostic::None;
        }
        catch (const std::exception& error)
        {
            std::fprintf(
                stderr,
                "[termin-qopt] finalizing dynamics system failed: %s\n",
                error.what());
        }
        catch (...)
        {
            std::fprintf(stderr,
                         "[termin-qopt] finalizing dynamics system failed with "
                         "unknown exception\n");
        }
        return DynamicsSystemDiagnostic::InternalFailure;
    }

    DynamicsSystemStepResult
    DynamicsSystem::step(DynamicsSystemStepOptions options) noexcept
    {
        if (impl_ == nullptr || !impl_->finalized)
        {
            return dynamics_system_failure(
                QpStatus::InvalidInput,
                DynamicsSystemDiagnostic::ModelNotFinalized);
        }
        if (!std::isfinite(options.time_step) || options.time_step <= 0.0)
        {
            return dynamics_system_failure(
                QpStatus::InvalidInput,
                DynamicsSystemDiagnostic::InvalidTimeStep);
        }
        if (!std::isfinite(options.position_tolerance) ||
            !std::isfinite(options.velocity_tolerance) ||
            options.position_tolerance < 0.0 ||
            options.velocity_tolerance < 0.0 ||
            (impl_->topology.constraint_count() != 0 &&
             options.max_position_iterations == 0) ||
            options.friction_cone_facets < 4 ||
            options.friction_cone_facets % 2 != 0)
        {
            return dynamics_system_failure(
                QpStatus::InvalidInput,
                DynamicsSystemDiagnostic::InvalidProjectionOptions);
        }

        if (impl_->begin_step() != DynamicsSystemDiagnostic::None)
        {
            impl_->rollback_step();
            return dynamics_system_failure(
                QpStatus::NumericalFailure,
                DynamicsSystemDiagnostic::InternalFailure);
        }
        bool step_open = true;
        const auto rollback = [&]() noexcept
        {
            if (step_open)
            {
                impl_->rollback_step();
                step_open = false;
            }
        };

        try
        {
            const DynamicsSystemDiagnostic unilateral_topology_diagnostic =
                impl_->prepare_unilateral_topology(options.time_step);
            if (unilateral_topology_diagnostic !=
                DynamicsSystemDiagnostic::None)
            {
                rollback();
                return dynamics_system_failure(QpStatus::InvalidInput,
                                               unilateral_topology_diagnostic);
            }
            const std::size_t unilateral_constraint_count =
                impl_->unilateral_topology.constraint_count();
            const DynamicsSystemDiagnostic friction_topology_diagnostic =
                impl_->prepare_friction_topology(options.time_step);
            if (friction_topology_diagnostic != DynamicsSystemDiagnostic::None)
            {
                rollback();
                return dynamics_system_failure(QpStatus::InvalidInput,
                                               friction_topology_diagnostic,
                                               {},
                                               unilateral_constraint_count);
            }
            DynamicsAssembly assembly(
                impl_->topology,
                impl_->unilateral_topology,
                {
                    DenseMatrixView::row_major(impl_->mass.data(),
                                               impl_->topology.dof_count(),
                                               impl_->topology.dof_count()),
                    {impl_->load.data(), impl_->load.size(), 1},
                    DenseMatrixView::row_major(
                        impl_->jacobian.data(),
                        impl_->topology.constraint_count(),
                        impl_->topology.dof_count()),
                    {
                        impl_->constraint_rhs.data(),
                        impl_->constraint_rhs.size(),
                        1,
                    },
                    DenseMatrixView::row_major(
                        impl_->unilateral_jacobian.data(),
                        unilateral_constraint_count,
                        impl_->topology.dof_count()),
                    {
                        impl_->unilateral_limit.data(),
                        impl_->unilateral_limit.size(),
                        1,
                    },
                });
            if (!assembly.valid() ||
                impl_->read_velocity() != DynamicsSystemDiagnostic::None ||
                impl_->assemble(assembly,
                                DynamicsAssemblyPhase::Acceleration) !=
                    DynamicsSystemDiagnostic::None)
            {
                rollback();
                return dynamics_system_failure(
                    QpStatus::InvalidInput,
                    DynamicsSystemDiagnostic::AssemblyFailure);
            }

            const QpSolveResult first_dynamics = solve_constrained_dynamics(
                assembly.system(),
                {
                    {
                        impl_->dof_solution.data(),
                        impl_->dof_solution.size(),
                        1,
                    },
                    {
                        impl_->constraint_reaction.data(),
                        impl_->constraint_reaction.size(),
                        1,
                    },
                },
                options.qp_tolerance);
            if (first_dynamics.status != QpStatus::Optimal)
            {
                rollback();
                return dynamics_system_failure(
                    first_dynamics.status,
                    DynamicsSystemDiagnostic::DynamicsFailure,
                    first_dynamics);
            }
            impl_->apply_solution(DynamicsAssemblyPhase::Acceleration);
            for (std::size_t index = 0; index < impl_->velocity.size(); ++index)
            {
                impl_->midpoint_velocity[index] =
                    impl_->velocity[index] +
                    0.5 * options.time_step * impl_->dof_solution[index];
            }
            impl_->configuration_velocity = impl_->midpoint_velocity;
            const auto midpoint_view = [&]() noexcept
            {
                return ConstDenseVectorView{
                    impl_->midpoint_velocity.data(),
                    impl_->midpoint_velocity.size(),
                    1,
                };
            };
            const auto configuration_view = [&]() noexcept
            {
                return ConstDenseVectorView{
                    impl_->configuration_velocity.data(),
                    impl_->configuration_velocity.size(),
                    1,
                };
            };
            if (impl_->write_velocity(midpoint_view()) !=
                    DynamicsSystemDiagnostic::None ||
                impl_->set_trial_configuration(configuration_view(),
                                               options.time_step) !=
                    DynamicsSystemDiagnostic::None)
            {
                rollback();
                return dynamics_system_failure(
                    QpStatus::NumericalFailure,
                    DynamicsSystemDiagnostic::InternalFailure,
                    first_dynamics);
            }

            DynamicsSystemStepResult result;
            result.status = QpStatus::Optimal;
            result.diagnostic = DynamicsSystemDiagnostic::None;
            result.dynamics = first_dynamics;
            result.unilateral_constraint_count = unilateral_constraint_count;
            result.friction_cone_facets = options.friction_cone_facets;
            QpSolveResult second_dynamics;

            // The first pass predicts the endpoint configuration and solves
            // contact velocities there. Friction can then correct the
            // configuration midpoint. A second, final pass rebuilds all
            // position, acceleration, unilateral, and friction equations on
            // that corrected configuration without changing it afterward.
            constexpr std::size_t kMaximumConfigurationPasses = 2;
            for (std::size_t configuration_pass = 0;
                 configuration_pass < kMaximumConfigurationPasses;
                 ++configuration_pass)
            {
                bool configuration_corrected = false;
            for (std::size_t iteration = 0;
                 iteration < options.max_position_iterations;
                 ++iteration)
            {
                result.position_constraint_linf = impl_->max_position_error();
                if (result.position_constraint_linf <=
                    options.position_tolerance)
                {
                    break;
                }
                if (impl_->assemble(
                        assembly, DynamicsAssemblyPhase::PositionProjection) !=
                    DynamicsSystemDiagnostic::None)
                {
                    rollback();
                    return dynamics_system_failure(
                        QpStatus::InvalidInput,
                        DynamicsSystemDiagnostic::AssemblyFailure,
                        first_dynamics);
                }
                QpSolveResult projection;
                if (unilateral_constraint_count == 0)
                {
                    projection = solve_constrained_dynamics(
                        assembly.system(),
                        {
                            {
                                impl_->dof_solution.data(),
                                impl_->dof_solution.size(),
                                1,
                            },
                            {
                                impl_->constraint_reaction.data(),
                                impl_->constraint_reaction.size(),
                                1,
                            },
                        },
                        options.qp_tolerance);
                }
                else
                {
                    projection = solve_unilateral_velocity(
                        assembly.system(),
                        assembly.unilateral_constraints(),
                        {
                            {
                                impl_->dof_solution.data(),
                                impl_->dof_solution.size(),
                                1,
                            },
                            {
                                impl_->constraint_reaction.data(),
                                impl_->constraint_reaction.size(),
                                1,
                            },
                            {
                                impl_->unilateral_reaction.data(),
                                impl_->unilateral_reaction.size(),
                                1,
                            },
                            {
                                impl_->unilateral_tight_mask.data(),
                                impl_->unilateral_tight_mask.size(),
                                1,
                            },
                        },
                        {},
                        {.tolerance = options.qp_tolerance});
                }
                ++result.position_iterations;
                if (projection.status != QpStatus::Optimal)
                {
                    rollback();
                    return dynamics_system_failure(
                        projection.status,
                        DynamicsSystemDiagnostic::PositionProjectionFailure,
                        first_dynamics);
                }
                if (impl_->apply_position_correction(options.time_step) !=
                        DynamicsSystemDiagnostic::None ||
                    impl_->write_velocity(configuration_view()) !=
                        DynamicsSystemDiagnostic::None ||
                    impl_->set_trial_configuration(configuration_view(),
                                                   options.time_step) !=
                        DynamicsSystemDiagnostic::None)
                {
                    rollback();
                    return dynamics_system_failure(
                        QpStatus::NumericalFailure,
                        DynamicsSystemDiagnostic::InternalFailure,
                        first_dynamics);
                }
            }
            result.position_constraint_linf = impl_->max_position_error();
            if (result.position_constraint_linf > options.position_tolerance)
            {
                rollback();
                return dynamics_system_failure(
                    QpStatus::NumericalFailure,
                    DynamicsSystemDiagnostic::PositionProjectionFailure,
                    first_dynamics);
            }

            // Position projection changes only the trial configuration. The
            // physical midpoint velocity remains the unconstrained dynamics
            // result and is restored before the endpoint acceleration solve.
            const ConstDenseVectorView endpoint_velocity_seed =
                configuration_pass == 0
                    ? midpoint_view()
                    : ConstDenseVectorView{
                          impl_->endpoint_velocity_predictor.data(),
                          impl_->endpoint_velocity_predictor.size(),
                          1,
                      };
            if (impl_->write_velocity(endpoint_velocity_seed) !=
                DynamicsSystemDiagnostic::None)
            {
                rollback();
                return dynamics_system_failure(
                    QpStatus::NumericalFailure,
                    DynamicsSystemDiagnostic::InternalFailure,
                    first_dynamics);
            }

            // The body-fixed bias ad*_v Mv depends on the endpoint velocity.
            // Therefore the second kick is an implicit trapezoidal half-step. A
            // small fixed-point solve keeps this generic: concrete
            // contributions merely reassemble their equations at the current
            // endpoint-velocity candidate.
            impl_->velocity = configuration_pass == 0
                                  ? impl_->midpoint_velocity
                                  : impl_->endpoint_velocity_predictor;
            bool endpoint_velocity_converged = false;
            constexpr std::size_t kMaximumVelocityIterations = 20;
            const double endpoint_velocity_tolerance =
                std::max(1e-12, options.velocity_tolerance * 0.1);
            EqualityQpFactorizationCache endpoint_factorization;
            for (std::size_t iteration = 0;
                 iteration < kMaximumVelocityIterations;
                 ++iteration)
            {
                if (impl_->assemble(assembly,
                                    DynamicsAssemblyPhase::Acceleration) !=
                    DynamicsSystemDiagnostic::None)
                {
                    rollback();
                    return dynamics_system_failure(
                        QpStatus::InvalidInput,
                        DynamicsSystemDiagnostic::AssemblyFailure,
                        first_dynamics);
                }
                second_dynamics = solve_constrained_dynamics_impl(
                    assembly.system(),
                    {
                        {
                            impl_->dof_solution.data(),
                            impl_->dof_solution.size(),
                            1,
                        },
                        {
                            impl_->constraint_reaction.data(),
                            impl_->constraint_reaction.size(),
                            1,
                        },
                    },
                    options.qp_tolerance,
                    &endpoint_factorization);
                if (second_dynamics.status != QpStatus::Optimal)
                {
                    rollback();
                    return dynamics_system_failure(
                        second_dynamics.status,
                        DynamicsSystemDiagnostic::DynamicsFailure,
                        second_dynamics);
                }
                double change_linf = 0.0;
                for (std::size_t index = 0; index < impl_->velocity.size();
                     ++index)
                {
                    impl_->corrected_midpoint_velocity[index] =
                        impl_->midpoint_velocity[index] +
                        0.5 * options.time_step * impl_->dof_solution[index];
                    change_linf = std::max(
                        change_linf,
                        std::abs(impl_->corrected_midpoint_velocity[index] -
                                 impl_->velocity[index]));
                }
                if (impl_->write_velocity({
                        impl_->corrected_midpoint_velocity.data(),
                        impl_->corrected_midpoint_velocity.size(),
                        1,
                    }) != DynamicsSystemDiagnostic::None)
                {
                    rollback();
                    return dynamics_system_failure(
                        QpStatus::NumericalFailure,
                        DynamicsSystemDiagnostic::InternalFailure,
                        second_dynamics);
                }
                impl_->velocity.swap(impl_->corrected_midpoint_velocity);
                if (change_linf <= endpoint_velocity_tolerance)
                {
                    endpoint_velocity_converged = true;
                    break;
                }
            }
            const EqualityQpFactorizationCounters endpoint_counters =
                endpoint_factorization.counters();
            result.endpoint_equality_factorizations +=
                endpoint_counters.factorizations;
            result.endpoint_equality_factorization_reuses +=
                endpoint_counters.reuse_hits;
            if (!endpoint_velocity_converged)
            {
                std::fprintf(stderr,
                             "[termin-qopt] implicit endpoint-velocity solve "
                             "did not converge\n");
                rollback();
                return dynamics_system_failure(
                    QpStatus::NumericalFailure,
                    DynamicsSystemDiagnostic::DynamicsFailure,
                    second_dynamics);
            }
            if (configuration_pass == 0)
            {
                impl_->endpoint_velocity_predictor = impl_->velocity;
            }
            impl_->apply_solution(DynamicsAssemblyPhase::Acceleration);
            result.dynamics = second_dynamics;

            if (impl_->topology.constraint_count() != 0 ||
                unilateral_constraint_count != 0)
            {
                if (impl_->assemble(
                        assembly, DynamicsAssemblyPhase::VelocityProjection) !=
                    DynamicsSystemDiagnostic::None)
                {
                    rollback();
                    return dynamics_system_failure(
                        QpStatus::InvalidInput,
                        DynamicsSystemDiagnostic::AssemblyFailure,
                        second_dynamics);
                }
                const ActiveSetQpWarmStartView warm_start =
                    impl_->unilateral_warm_start();
                QpSolveResult velocity_projection = solve_unilateral_velocity(
                    assembly.system(),
                    assembly.unilateral_constraints(),
                    {
                        {
                            impl_->dof_solution.data(),
                            impl_->dof_solution.size(),
                            1,
                        },
                        {
                            impl_->constraint_reaction.data(),
                            impl_->constraint_reaction.size(),
                            1,
                        },
                        {
                            impl_->unilateral_reaction.data(),
                            impl_->unilateral_reaction.size(),
                            1,
                        },
                        {
                            impl_->unilateral_tight_mask.data(),
                            impl_->unilateral_tight_mask.size(),
                            1,
                        },
                    },
                    warm_start,
                    {.tolerance = options.qp_tolerance});
                if (velocity_projection.status != QpStatus::Optimal &&
                    velocity_projection.diagnostic ==
                        QpDiagnostic::InvalidWarmStart &&
                    !warm_start.primal.empty())
                {
                    velocity_projection = solve_unilateral_velocity(
                        assembly.system(),
                        assembly.unilateral_constraints(),
                        {
                            {impl_->dof_solution.data(),
                             impl_->dof_solution.size(),
                             1},
                            {impl_->constraint_reaction.data(),
                             impl_->constraint_reaction.size(),
                             1},
                            {impl_->unilateral_reaction.data(),
                             impl_->unilateral_reaction.size(),
                             1},
                            {impl_->unilateral_tight_mask.data(),
                             impl_->unilateral_tight_mask.size(),
                             1},
                        },
                        {},
                        {.tolerance = options.qp_tolerance});
                }
                result.velocity_projection = velocity_projection;
                if (velocity_projection.status != QpStatus::Optimal)
                {
                    rollback();
                    DynamicsSystemStepResult failure = dynamics_system_failure(
                        velocity_projection.status,
                        DynamicsSystemDiagnostic::VelocityProjectionFailure,
                        second_dynamics,
                        unilateral_constraint_count);
                    failure.velocity_projection = velocity_projection;
                    return failure;
                }
                impl_->apply_solution(
                    DynamicsAssemblyPhase::VelocityProjection);
                impl_->apply_unilateral_solution();

                const std::size_t friction_contact_count =
                    impl_->friction_topology.contact_count();
                result.friction_contact_count = friction_contact_count;
                if (friction_contact_count != 0)
                {
                    impl_->pre_friction_velocity = impl_->dof_solution;
                    DynamicsFrictionAssembly friction_assembly(
                        impl_->topology,
                        impl_->friction_topology,
                        {
                            DenseMatrixView::row_major(
                                impl_->friction_contact_normal_jacobian.data(),
                                friction_contact_count,
                                impl_->topology.dof_count()),
                            DenseMatrixView::row_major(
                                impl_->friction_tangent_jacobian.data(),
                                impl_->friction_topology.tangent_count(),
                                impl_->topology.dof_count()),
                            {impl_->friction_normal_impulse.data(),
                             impl_->friction_normal_impulse.size(),
                             1},
                            {impl_->friction_coefficient.data(),
                             impl_->friction_coefficient.size(),
                             1},
                        });
                    if (!friction_assembly.valid() ||
                        impl_->assemble_friction(friction_assembly) !=
                            DynamicsSystemDiagnostic::None)
                    {
                        rollback();
                        return dynamics_system_failure(
                            QpStatus::InvalidInput,
                            DynamicsSystemDiagnostic::AssemblyFailure,
                            second_dynamics,
                            unilateral_constraint_count);
                    }

                    const std::size_t dofs = impl_->topology.dof_count();
                    impl_->friction_normal_jacobian.resize(
                        unilateral_constraint_count * dofs);
                    impl_->friction_minimum_normal_velocity.resize(
                        unilateral_constraint_count);
                    for (std::size_t row = 0; row < unilateral_constraint_count;
                         ++row)
                    {
                        impl_->friction_minimum_normal_velocity[row] =
                            -impl_->unilateral_limit[row];
                        for (std::size_t dof = 0; dof < dofs; ++dof)
                        {
                            impl_->friction_normal_jacobian[row * dofs + dof] =
                                -impl_->unilateral_jacobian[row * dofs + dof];
                        }
                    }

                    QpTolerance friction_tolerance = options.qp_tolerance;
                    const double friction_accuracy =
                        options.velocity_tolerance * 1.0e-2;
                    friction_tolerance.absolute = std::max(
                        friction_tolerance.absolute, friction_accuracy);
                    friction_tolerance.relative = std::max(
                        friction_tolerance.relative, friction_accuracy);
                    const QpSolveResult friction_result =
                        solve_contact_friction(
                            {
                                ConstDenseMatrixView::row_major(
                                    impl_->mass.data(), dofs, dofs),
                                ConstDenseMatrixView::row_major(
                                    impl_->jacobian.data(),
                                    impl_->topology.constraint_count(),
                                    dofs),
                                {impl_->dof_solution.data(),
                                 impl_->dof_solution.size(),
                                 1},
                                ConstDenseMatrixView::row_major(
                                    impl_->friction_normal_jacobian.data(),
                                    unilateral_constraint_count,
                                    dofs),
                                {impl_->friction_minimum_normal_velocity.data(),
                                 impl_->friction_minimum_normal_velocity.size(),
                                 1},
                                ConstDenseMatrixView::row_major(
                                    impl_->friction_contact_normal_jacobian
                                        .data(),
                                    friction_contact_count,
                                    dofs),
                                ConstDenseMatrixView::row_major(
                                    impl_->friction_tangent_jacobian.data(),
                                    impl_->friction_topology.tangent_count(),
                                    dofs),
                                {impl_->friction_normal_impulse.data(),
                                 impl_->friction_normal_impulse.size(),
                                 1},
                                {impl_->friction_coefficient.data(),
                                 impl_->friction_coefficient.size(),
                                 1},
                            },
                            {
                                {impl_->dof_solution.data(),
                                 impl_->dof_solution.size(),
                                 1},
                                {impl_->friction_tangent_impulse.data(),
                                 impl_->friction_tangent_impulse.size(),
                                 1},
                                {impl_->friction_normal_impulse.data(),
                                 impl_->friction_normal_impulse.size(),
                                 1},
                                {impl_->friction_work.data(),
                                 impl_->friction_work.size(),
                                 1},
                                {impl_->friction_bilateral_impulse.data(),
                                 impl_->friction_bilateral_impulse.size(),
                                 1},
                            },
                            {
                                .cone_facets = options.friction_cone_facets,
                                .qp = {.tolerance = friction_tolerance},
                            });
                    result.friction_projection = friction_result;
                    if (friction_result.status != QpStatus::Optimal)
                    {
                        if (friction_result.diagnostic ==
                            QpDiagnostic::IterationLimit)
                        {
                            std::fprintf(
                                stderr,
                                "[termin-qopt] contact friction solve failed: "
                                "iteration_limit residuals=unavailable "
                                "contacts=%zu facets=%zu inequalities=%zu "
                                "iterations=%zu active=%zu\n",
                                friction_contact_count,
                                options.friction_cone_facets,
                                unilateral_constraint_count +
                                    friction_contact_count *
                                        (options.friction_cone_facets + 2),
                                friction_result.iterations,
                                friction_result.active_set_size);
                        }
                        else
                        {
                            std::fprintf(
                                stderr,
                                "[termin-qopt] contact friction solve failed: "
                                "%s stationarity=%g equality=%g inequality=%g "
                                "dual=%g complementarity=%g contacts=%zu "
                                "facets=%zu iterations=%zu active=%zu\n",
                                qp_diagnostic_name(friction_result.diagnostic)
                                    .data(),
                                friction_result.stationarity_linf,
                                friction_result.equality_linf,
                                friction_result.inequality_linf,
                                friction_result.dual_linf,
                                friction_result.complementarity_linf,
                                friction_contact_count,
                                options.friction_cone_facets,
                                friction_result.iterations,
                                friction_result.active_set_size);
                        }
                        rollback();
                        DynamicsSystemStepResult failure =
                            dynamics_system_failure(
                                friction_result.status,
                                DynamicsSystemDiagnostic::
                                    FrictionProjectionFailure,
                                second_dynamics,
                                unilateral_constraint_count);
                        failure.friction_projection = friction_result;
                        failure.friction_contact_count = friction_contact_count;
                        failure.friction_cone_facets =
                            options.friction_cone_facets;
                        return failure;
                    }
                    impl_->post_friction_velocity = impl_->dof_solution;
                    for (std::size_t row = 0;
                         row < impl_->constraint_reaction.size();
                         ++row)
                    {
                        impl_->constraint_reaction[row] +=
                            impl_->friction_bilateral_impulse[row];
                    }
                    impl_->apply_solution(
                        DynamicsAssemblyPhase::VelocityProjection);
                    impl_->apply_friction_solution();
                    if (configuration_pass == 0 &&
                        impl_->apply_friction_configuration_correction(
                            options.time_step) !=
                            DynamicsSystemDiagnostic::None)
                    {
                        rollback();
                        return dynamics_system_failure(
                            QpStatus::NumericalFailure,
                            DynamicsSystemDiagnostic::InternalFailure,
                            second_dynamics,
                            unilateral_constraint_count);
                    }
                    configuration_corrected = configuration_pass == 0;
                }
            }
                if (!configuration_corrected)
                {
                    break;
                }
            }
            result.velocity_constraint_linf = impl_->max_velocity_error();
            if (result.velocity_constraint_linf > options.velocity_tolerance)
            {
                rollback();
                DynamicsSystemStepResult failure = dynamics_system_failure(
                    QpStatus::NumericalFailure,
                    DynamicsSystemDiagnostic::VelocityProjectionFailure,
                    second_dynamics,
                    unilateral_constraint_count);
                failure.velocity_projection = result.velocity_projection;
                failure.friction_projection = result.friction_projection;
                failure.friction_contact_count = result.friction_contact_count;
                failure.friction_cone_facets = result.friction_cone_facets;
                return failure;
            }

            impl_->velocity_warm_primal = impl_->dof_solution;
            impl_->velocity_warm_primal_valid = true;

            impl_->commit_step();
            step_open = false;
            return result;
        }
        catch (const std::exception& error)
        {
            std::fprintf(stderr,
                         "[termin-qopt] dynamics system step failed: %s\n",
                         error.what());
        }
        catch (...)
        {
            std::fprintf(stderr,
                         "[termin-qopt] dynamics system step failed with "
                         "unknown exception\n");
        }
        rollback();
        return dynamics_system_failure(
            QpStatus::NumericalFailure,
            DynamicsSystemDiagnostic::InternalFailure);
    }

    bool DynamicsSystem::finalized() const noexcept
    {
        return impl_ != nullptr && impl_->finalized;
    }

    std::size_t DynamicsSystem::contribution_count() const noexcept
    {
        return impl_ == nullptr ? 0 : impl_->contributions.size();
    }

    const DynamicsTopology& DynamicsSystem::topology() const noexcept
    {
        return impl_->topology;
    }

    double DynamicsSystem::max_position_constraint_error() const noexcept
    {
        return impl_ == nullptr ? 0.0 : impl_->max_position_error();
    }

    double DynamicsSystem::max_velocity_constraint_error() const noexcept
    {
        return impl_ == nullptr ? 0.0 : impl_->max_velocity_error();
    }

} // namespace termin::physics_qopt
