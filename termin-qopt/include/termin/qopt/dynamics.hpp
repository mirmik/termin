#pragma once

#include <cstddef>
#include <cstdint>
#include <memory>
#include <string_view>

#include <termin/qopt/block_assembly.hpp>
#include <termin/qopt/equality_qp.hpp>
#include <termin/qopt/termin_qopt_api.hpp>

namespace termin::qopt
{

    struct DynamicsDofHandle
    {
        DenseBlockHandle block;

        [[nodiscard]] constexpr bool valid() const noexcept
        {
            return block.valid();
        }
    };

    struct DynamicsConstraintHandle
    {
        DenseBlockHandle block;

        [[nodiscard]] constexpr bool valid() const noexcept
        {
            return block.valid();
        }
    };

    template <typename Handle> struct DynamicsRegistrationResult
    {
        Handle handle;
        AssemblyDiagnostic diagnostic = AssemblyDiagnostic::None;

        [[nodiscard]] constexpr bool ok() const noexcept
        {
            return diagnostic == AssemblyDiagnostic::None;
        }
    };

    // Two independent layouts make rectangular J assembly type-safe: DOF
    // handles cannot accidentally address constraint rows and vice versa.
    class TERMIN_QOPT_API DynamicsTopology
    {
      public:
        [[nodiscard]] DynamicsRegistrationResult<DynamicsDofHandle>
        register_dofs(std::size_t size, std::string_view diagnostic_name) noexcept;
        [[nodiscard]] DynamicsRegistrationResult<DynamicsConstraintHandle>
        register_constraint(std::size_t size,
                            std::string_view diagnostic_name) noexcept;
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

    struct DynamicsWorkspaceView
    {
        DenseMatrixView mass;
        DenseVectorView load;
        DenseMatrixView constraint_jacobian;
        DenseVectorView constraint_rhs;
    };

    struct ConstDynamicsSystemView
    {
        ConstDenseMatrixView mass;
        ConstDenseVectorView load;
        ConstDenseMatrixView constraint_jacobian;
        ConstDenseVectorView constraint_rhs;
    };

    // A checked per-step writer. The topology and numerical storage are
    // borrowed; reuse the same workspace across steps when topology is
    // unchanged.
    class TERMIN_QOPT_API DynamicsAssembly
    {
      public:
        DynamicsAssembly(const DynamicsTopology& topology,
                         DynamicsWorkspaceView workspace) noexcept;

        [[nodiscard]] AssemblyDiagnostic diagnostic() const noexcept;
        [[nodiscard]] bool valid() const noexcept;
        [[nodiscard]] AssemblyDiagnostic clear() noexcept;

        [[nodiscard]] AssemblyDiagnostic
        add_mass(DynamicsDofHandle row,
                 DynamicsDofHandle column,
                 ConstDenseMatrixView contribution) noexcept;
        [[nodiscard]] AssemblyDiagnostic
        add_load(DynamicsDofHandle dofs, ConstDenseVectorView contribution) noexcept;
        [[nodiscard]] AssemblyDiagnostic
        add_constraint_jacobian(DynamicsConstraintHandle constraint,
                                DynamicsDofHandle dofs,
                                ConstDenseMatrixView contribution) noexcept;
        [[nodiscard]] AssemblyDiagnostic
        add_constraint_rhs(DynamicsConstraintHandle constraint,
                           ConstDenseVectorView contribution) noexcept;

        [[nodiscard]] ConstDynamicsSystemView system() const noexcept;

      private:
        DynamicsWorkspaceView workspace_;
        DenseBlockMatrixAssembly mass_;
        DenseBlockVectorAssembly load_;
        DenseBlockMatrixAssembly constraint_jacobian_;
        DenseBlockVectorAssembly constraint_rhs_;
        AssemblyDiagnostic diagnostic_ = AssemblyDiagnostic::InternalFailure;
    };

    enum class DynamicsAssemblyPhase : std::uint8_t
    {
        Acceleration,
        PositionProjection,
        VelocityProjection,
    };

    // One model element participating in a dynamics solve. Contributions own
    // their model state and topology-bound handles; DynamicsSystem owns their
    // lifetime and orchestrates the transactional step lifecycle.
    class TERMIN_QOPT_API DynamicsContribution
    {
      public:
        virtual ~DynamicsContribution() = default;

        [[nodiscard]] virtual AssemblyDiagnostic
        register_topology(DynamicsTopology& topology) noexcept = 0;

        [[nodiscard]] virtual AssemblyDiagnostic
        assemble(DynamicsAssembly& assembly, DynamicsAssemblyPhase phase) noexcept = 0;

        [[nodiscard]] virtual AssemblyDiagnostic begin_step() noexcept
        {
            return AssemblyDiagnostic::None;
        }

        virtual void commit_step() noexcept {}

        virtual void rollback_step() noexcept {}

        virtual void apply_solution(DynamicsAssemblyPhase phase,
                                    const DynamicsTopology& topology,
                                    ConstDenseVectorView dof_values,
                                    ConstDenseVectorView constraint_reactions) noexcept
        {
            (void)phase;
            (void)topology;
            (void)dof_values;
            (void)constraint_reactions;
        }

        // State-owning contributions write their generalized velocity block.
        // The collector initializes the destination with NaNs, so every
        // registered DOF must have exactly one owner that supplies finite
        // values.
        [[nodiscard]] virtual AssemblyDiagnostic
        write_velocity(const DynamicsTopology& topology,
                       DenseVectorView destination) const noexcept
        {
            (void)topology;
            (void)destination;
            return AssemblyDiagnostic::None;
        }

        [[nodiscard]] virtual AssemblyDiagnostic
        set_velocity(const DynamicsTopology& topology,
                     ConstDenseVectorView velocity) noexcept
        {
            (void)topology;
            (void)velocity;
            return AssemblyDiagnostic::None;
        }

        // Rebuild a trial configuration from the begin_step() snapshot using
        // the supplied midpoint velocity. Rigid rotations must use their
        // Lie-group exponential; the collector never interprets concrete
        // coordinates.
        [[nodiscard]] virtual AssemblyDiagnostic
        set_trial_configuration(const DynamicsTopology& topology,
                                ConstDenseVectorView midpoint_velocity,
                                double time_step) noexcept
        {
            (void)topology;
            (void)midpoint_velocity;
            (void)time_step;
            return AssemblyDiagnostic::None;
        }

        // State-owning contributions map a tangent correction computed at the
        // trial configuration back to the midpoint-velocity coordinates used to
        // generate that configuration. Euclidean owners write v + dq / h. Lie
        // group owners perform the corresponding Exp/Log composition instead.
        // As with write_velocity(), the collector validates that every DOF
        // block has one finite owner.
        [[nodiscard]] virtual AssemblyDiagnostic
        write_corrected_midpoint_velocity(const DynamicsTopology& topology,
                                          ConstDenseVectorView midpoint_velocity,
                                          ConstDenseVectorView trial_tangent_correction,
                                          double time_step,
                                          DenseVectorView destination) const noexcept
        {
            (void)topology;
            (void)midpoint_velocity;
            (void)trial_tangent_correction;
            (void)time_step;
            (void)destination;
            return AssemblyDiagnostic::None;
        }

        [[nodiscard]] virtual double position_error_linf() const noexcept
        {
            return 0.0;
        }

        [[nodiscard]] virtual double velocity_error_linf() const noexcept
        {
            return 0.0;
        }
    };

    enum class DynamicsSystemDiagnostic : std::uint8_t
    {
        None,
        ModelFinalized,
        ModelNotFinalized,
        NullContribution,
        InvalidTimeStep,
        InvalidProjectionOptions,
        TopologyFailure,
        AssemblyFailure,
        DynamicsFailure,
        PositionProjectionFailure,
        VelocityProjectionFailure,
        InternalFailure,
    };

    [[nodiscard]] TERMIN_QOPT_API std::string_view
    dynamics_system_diagnostic_name(DynamicsSystemDiagnostic diagnostic) noexcept;

    struct DynamicsSystemStepOptions
    {
        double time_step = 0.001;
        double position_tolerance = 1e-9;
        double velocity_tolerance = 1e-9;
        std::size_t max_position_iterations = 6;
        QpTolerance qp_tolerance;
    };

    struct DynamicsSystemStepResult
    {
        QpStatus status = QpStatus::InvalidInput;
        DynamicsSystemDiagnostic diagnostic =
            DynamicsSystemDiagnostic::ModelNotFinalized;
        QpSolveResult dynamics;
        double position_constraint_linf = 0.0;
        double velocity_constraint_linf = 0.0;
        std::size_t position_iterations = 0;

        [[nodiscard]] constexpr bool ok() const noexcept
        {
            return status == QpStatus::Optimal &&
                   diagnostic == DynamicsSystemDiagnostic::None;
        }
    };

    class TERMIN_QOPT_API DynamicsSystem
    {
      public:
        DynamicsSystem();
        ~DynamicsSystem();

        DynamicsSystem(DynamicsSystem&&) noexcept;
        DynamicsSystem& operator=(DynamicsSystem&&) noexcept;
        DynamicsSystem(const DynamicsSystem&) = delete;
        DynamicsSystem& operator=(const DynamicsSystem&) = delete;

        [[nodiscard]] DynamicsSystemDiagnostic
        add_contribution(std::unique_ptr<DynamicsContribution> contribution) noexcept;
        [[nodiscard]] DynamicsSystemDiagnostic finalize() noexcept;
        [[nodiscard]] DynamicsSystemStepResult
        step(DynamicsSystemStepOptions options = {}) noexcept;

        [[nodiscard]] bool finalized() const noexcept;
        [[nodiscard]] std::size_t contribution_count() const noexcept;
        [[nodiscard]] const DynamicsTopology& topology() const noexcept;
        [[nodiscard]] double max_position_constraint_error() const noexcept;
        [[nodiscard]] double max_velocity_constraint_error() const noexcept;

      private:
        struct Impl;
        std::unique_ptr<Impl> impl_;
    };

    struct DynamicsSolutionView
    {
        DenseVectorView acceleration;
        // Physical generalized reaction is J^T * reaction. This is the negative
        // of the equality-QP dual because its stationarity convention is M*a -
        // f + J^T*dual = 0.
        DenseVectorView constraint_reaction;
    };

    [[nodiscard]] TERMIN_QOPT_API QpSolveResult
    solve_constrained_dynamics(ConstDynamicsSystemView system,
                               DynamicsSolutionView solution,
                               QpTolerance tolerance = {}) noexcept;

} // namespace termin::qopt
