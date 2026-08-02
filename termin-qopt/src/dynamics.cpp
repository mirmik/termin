#include <termin/qopt/dynamics.hpp>

#include <algorithm>
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <exception>
#include <limits>
#include <unordered_set>
#include <vector>

namespace termin::qopt
{
    namespace
    {

        [[nodiscard]] AssemblyDiagnostic
        first_diagnostic(std::initializer_list<AssemblyDiagnostic> diagnostics) noexcept
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

        [[nodiscard]] QpDiagnostic validate_output(DenseVectorView view,
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
        validate_system(ConstDynamicsSystemView system) noexcept
        {
            const std::size_t dof_count = system.load.size;
            const std::size_t constraint_count = system.constraint_rhs.size;
            if (system.mass.rows != dof_count || system.mass.columns != dof_count ||
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
                (!system.mass.empty() &&
                 (system.mass.row_stride <= 0 || system.mass.column_stride <= 0)) ||
                (!system.constraint_jacobian.empty() &&
                 (system.constraint_jacobian.row_stride <= 0 ||
                  system.constraint_jacobian.column_stride <= 0)) ||
                (!system.constraint_rhs.empty() && system.constraint_rhs.stride <= 0))
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
                addresses.insert(reinterpret_cast<std::uintptr_t>(&first[index]));
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

        [[nodiscard]] QpSolveResult invalid_result(QpDiagnostic diagnostic) noexcept
        {
            QpSolveResult result;
            result.status = QpStatus::InvalidInput;
            result.diagnostic = diagnostic;
            return result;
        }

    } // namespace

    DynamicsRegistrationResult<DynamicsDofHandle>
    DynamicsTopology::register_dofs(std::size_t size,
                                    std::string_view diagnostic_name) noexcept
    {
        if (finalized_)
        {
            return {{}, AssemblyDiagnostic::TopologyFinalized};
        }
        const DenseBlockRegistrationResult result =
            dofs_.register_block(size, diagnostic_name);
        return {{result.handle}, result.diagnostic};
    }

    DynamicsRegistrationResult<DynamicsConstraintHandle>
    DynamicsTopology::register_constraint(std::size_t size,
                                          std::string_view diagnostic_name) noexcept
    {
        if (finalized_)
        {
            return {{}, AssemblyDiagnostic::TopologyFinalized};
        }
        const DenseBlockRegistrationResult result =
            constraints_.register_block(size, diagnostic_name);
        return {{result.handle}, result.diagnostic};
    }

    AssemblyDiagnostic DynamicsTopology::finalize() noexcept
    {
        if (finalized_)
        {
            return AssemblyDiagnostic::TopologyFinalized;
        }
        const AssemblyDiagnostic dof_result = dofs_.finalize();
        if (dof_result != AssemblyDiagnostic::None)
        {
            return dof_result;
        }
        const AssemblyDiagnostic constraint_result = constraints_.finalize();
        if (constraint_result != AssemblyDiagnostic::None)
        {
            return constraint_result;
        }
        finalized_ = true;
        return AssemblyDiagnostic::None;
    }

    bool DynamicsTopology::finalized() const noexcept
    {
        return finalized_;
    }

    std::size_t DynamicsTopology::dof_count() const noexcept
    {
        return dofs_.total_size();
    }

    std::size_t DynamicsTopology::constraint_count() const noexcept
    {
        return constraints_.total_size();
    }

    const DenseBlockTopology& DynamicsTopology::dof_topology() const noexcept
    {
        return dofs_;
    }

    const DenseBlockTopology& DynamicsTopology::constraint_topology() const noexcept
    {
        return constraints_;
    }

    DynamicsAssembly::DynamicsAssembly(const DynamicsTopology& topology,
                                       DynamicsWorkspaceView workspace) noexcept
        : workspace_(workspace),
          mass_(topology.dof_topology(), topology.dof_topology(), workspace.mass),
          load_(topology.dof_topology(), workspace.load),
          constraint_jacobian_(topology.constraint_topology(),
                               topology.dof_topology(),
                               workspace.constraint_jacobian),
          constraint_rhs_(topology.constraint_topology(), workspace.constraint_rhs)
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
        return first_diagnostic({
            mass_.clear(),
            load_.clear(),
            constraint_jacobian_.clear(),
            constraint_rhs_.clear(),
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
        return constraint_jacobian_.add(constraint.block, dofs.block, contribution);
    }

    AssemblyDiagnostic
    DynamicsAssembly::add_constraint_rhs(DynamicsConstraintHandle constraint,
                                         ConstDenseVectorView contribution) noexcept
    {
        return constraint_rhs_.add(constraint.block, contribution);
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

    QpSolveResult solve_constrained_dynamics(ConstDynamicsSystemView system,
                                             DynamicsSolutionView solution,
                                             QpTolerance tolerance) noexcept
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
            if (outputs_overlap(solution.acceleration, solution.constraint_reaction))
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
                tolerance);
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
            std::fprintf(stderr,
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

    namespace
    {

        [[nodiscard]] DynamicsSystemStepResult
        dynamics_system_failure(QpStatus status,
                                DynamicsSystemDiagnostic diagnostic,
                                QpSolveResult dynamics = {}) noexcept
        {
            DynamicsSystemStepResult result;
            result.status = status;
            result.diagnostic = diagnostic;
            result.dynamics = dynamics;
            return result;
        }

    } // namespace

    struct DynamicsSystem::Impl
    {
        DynamicsTopology topology;
        std::vector<std::unique_ptr<DynamicsContribution>> contributions;
        std::vector<double> mass;
        std::vector<double> load;
        std::vector<double> jacobian;
        std::vector<double> constraint_rhs;
        std::vector<double> dof_solution;
        std::vector<double> constraint_reaction;
        std::vector<double> velocity;
        std::vector<double> midpoint_velocity;
        std::vector<double> corrected_midpoint_velocity;
        std::size_t step_contribution_count = 0;
        bool finalized = false;

        [[nodiscard]] DynamicsSystemDiagnostic
        assemble(DynamicsAssembly& assembly, DynamicsAssemblyPhase phase) noexcept
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

        void commit_step() noexcept
        {
            for (std::size_t index = 0; index < step_contribution_count; ++index)
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
        set_trial_configuration(ConstDenseVectorView source, double time_step) noexcept
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
            std::fill(corrected_midpoint_velocity.begin(),
                      corrected_midpoint_velocity.end(),
                      std::numeric_limits<double>::quiet_NaN());
            const ConstDenseVectorView midpoint{
                midpoint_velocity.data(),
                midpoint_velocity.size(),
                1,
            };
            const ConstDenseVectorView correction{
                dof_solution.data(),
                dof_solution.size(),
                1,
            };
            const DenseVectorView destination{
                corrected_midpoint_velocity.data(),
                corrected_midpoint_velocity.size(),
                1,
            };
            for (std::size_t index = 0; index < contributions.size(); ++index)
            {
                const AssemblyDiagnostic diagnostic =
                    contributions[index]->write_corrected_midpoint_velocity(
                        topology, midpoint, correction, time_step, destination);
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
            if (!std::all_of(corrected_midpoint_velocity.begin(),
                             corrected_midpoint_velocity.end(),
                             [](double value) { return std::isfinite(value); }))
            {
                std::fprintf(stderr,
                             "[termin-qopt] one or more generalized DOFs have "
                             "no position-correction owner\n");
                return DynamicsSystemDiagnostic::InternalFailure;
            }
            midpoint_velocity.swap(corrected_midpoint_velocity);
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

    std::string_view
    dynamics_system_diagnostic_name(DynamicsSystemDiagnostic diagnostic) noexcept
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
        case DynamicsSystemDiagnostic::InternalFailure:
            return "internal_failure";
        }
        return "unknown";
    }

    DynamicsSystem::DynamicsSystem() : impl_(std::make_unique<Impl>()) {}

    DynamicsSystem::~DynamicsSystem() = default;
    DynamicsSystem::DynamicsSystem(DynamicsSystem&&) noexcept = default;
    DynamicsSystem& DynamicsSystem::operator=(DynamicsSystem&&) noexcept = default;

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
            std::fprintf(stderr,
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
        for (std::size_t index = 0; index < impl_->contributions.size(); ++index)
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
        for (std::size_t index = 0; index < impl_->contributions.size(); ++index)
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
            impl_->finalized = true;
            return DynamicsSystemDiagnostic::None;
        }
        catch (const std::exception& error)
        {
            std::fprintf(stderr,
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
            return dynamics_system_failure(QpStatus::InvalidInput,
                                           DynamicsSystemDiagnostic::ModelNotFinalized);
        }
        if (!std::isfinite(options.time_step) || options.time_step <= 0.0)
        {
            return dynamics_system_failure(QpStatus::InvalidInput,
                                           DynamicsSystemDiagnostic::InvalidTimeStep);
        }
        if (!std::isfinite(options.position_tolerance) ||
            !std::isfinite(options.velocity_tolerance) ||
            options.position_tolerance < 0.0 || options.velocity_tolerance < 0.0 ||
            (impl_->topology.constraint_count() != 0 &&
             options.max_position_iterations == 0))
        {
            return dynamics_system_failure(
                QpStatus::InvalidInput,
                DynamicsSystemDiagnostic::InvalidProjectionOptions);
        }

        if (impl_->begin_step() != DynamicsSystemDiagnostic::None)
        {
            impl_->rollback_step();
            return dynamics_system_failure(QpStatus::NumericalFailure,
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
            DynamicsAssembly assembly(
                impl_->topology,
                {
                    DenseMatrixView::row_major(impl_->mass.data(),
                                               impl_->topology.dof_count(),
                                               impl_->topology.dof_count()),
                    {impl_->load.data(), impl_->load.size(), 1},
                    DenseMatrixView::row_major(impl_->jacobian.data(),
                                               impl_->topology.constraint_count(),
                                               impl_->topology.dof_count()),
                    {
                        impl_->constraint_rhs.data(),
                        impl_->constraint_rhs.size(),
                        1,
                    },
                });
            if (!assembly.valid() ||
                impl_->read_velocity() != DynamicsSystemDiagnostic::None ||
                impl_->assemble(assembly, DynamicsAssemblyPhase::Acceleration) !=
                    DynamicsSystemDiagnostic::None)
            {
                rollback();
                return dynamics_system_failure(
                    QpStatus::InvalidInput, DynamicsSystemDiagnostic::AssemblyFailure);
            }

            const QpSolveResult first_dynamics =
                solve_constrained_dynamics(assembly.system(),
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
            const auto midpoint_view = [&]() noexcept
            {
                return ConstDenseVectorView{
                    impl_->midpoint_velocity.data(),
                    impl_->midpoint_velocity.size(),
                    1,
                };
            };
            if (impl_->write_velocity(midpoint_view()) !=
                    DynamicsSystemDiagnostic::None ||
                impl_->set_trial_configuration(midpoint_view(), options.time_step) !=
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

            for (std::size_t iteration = 0; iteration < options.max_position_iterations;
                 ++iteration)
            {
                result.position_constraint_linf = impl_->max_position_error();
                if (result.position_constraint_linf <= options.position_tolerance)
                {
                    break;
                }
                if (impl_->assemble(assembly,
                                    DynamicsAssemblyPhase::PositionProjection) !=
                    DynamicsSystemDiagnostic::None)
                {
                    rollback();
                    return dynamics_system_failure(
                        QpStatus::InvalidInput,
                        DynamicsSystemDiagnostic::AssemblyFailure,
                        first_dynamics);
                }
                const QpSolveResult projection = solve_constrained_dynamics(
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
                    impl_->write_velocity(midpoint_view()) !=
                        DynamicsSystemDiagnostic::None ||
                    impl_->set_trial_configuration(midpoint_view(),
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

            // The body-fixed bias ad*_v Mv depends on the endpoint velocity.
            // Therefore the second kick is an implicit trapezoidal half-step. A
            // small fixed-point solve keeps this generic: concrete
            // contributions merely reassemble their equations at the current
            // endpoint-velocity candidate.
            impl_->velocity = impl_->midpoint_velocity;
            QpSolveResult second_dynamics;
            bool endpoint_velocity_converged = false;
            constexpr std::size_t kMaximumVelocityIterations = 20;
            const double endpoint_velocity_tolerance =
                std::max(1e-12, options.velocity_tolerance * 0.1);
            for (std::size_t iteration = 0; iteration < kMaximumVelocityIterations;
                 ++iteration)
            {
                if (impl_->assemble(assembly, DynamicsAssemblyPhase::Acceleration) !=
                    DynamicsSystemDiagnostic::None)
                {
                    rollback();
                    return dynamics_system_failure(
                        QpStatus::InvalidInput,
                        DynamicsSystemDiagnostic::AssemblyFailure,
                        first_dynamics);
                }
                second_dynamics = solve_constrained_dynamics(
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
                if (second_dynamics.status != QpStatus::Optimal)
                {
                    rollback();
                    return dynamics_system_failure(
                        second_dynamics.status,
                        DynamicsSystemDiagnostic::DynamicsFailure,
                        second_dynamics);
                }
                double change_linf = 0.0;
                for (std::size_t index = 0; index < impl_->velocity.size(); ++index)
                {
                    impl_->corrected_midpoint_velocity[index] =
                        impl_->midpoint_velocity[index] +
                        0.5 * options.time_step * impl_->dof_solution[index];
                    change_linf =
                        std::max(change_linf,
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
            impl_->apply_solution(DynamicsAssemblyPhase::Acceleration);
            result.dynamics = second_dynamics;

            if (impl_->topology.constraint_count() != 0)
            {
                if (impl_->assemble(assembly,
                                    DynamicsAssemblyPhase::VelocityProjection) !=
                    DynamicsSystemDiagnostic::None)
                {
                    rollback();
                    return dynamics_system_failure(
                        QpStatus::InvalidInput,
                        DynamicsSystemDiagnostic::AssemblyFailure,
                        second_dynamics);
                }
                const QpSolveResult velocity_projection = solve_constrained_dynamics(
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
                if (velocity_projection.status != QpStatus::Optimal)
                {
                    rollback();
                    return dynamics_system_failure(
                        velocity_projection.status,
                        DynamicsSystemDiagnostic::VelocityProjectionFailure,
                        second_dynamics);
                }
                impl_->apply_solution(DynamicsAssemblyPhase::VelocityProjection);
            }
            result.velocity_constraint_linf = impl_->max_velocity_error();
            if (result.velocity_constraint_linf > options.velocity_tolerance)
            {
                rollback();
                return dynamics_system_failure(
                    QpStatus::NumericalFailure,
                    DynamicsSystemDiagnostic::VelocityProjectionFailure,
                    second_dynamics);
            }

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
        return dynamics_system_failure(QpStatus::NumericalFailure,
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

} // namespace termin::qopt
