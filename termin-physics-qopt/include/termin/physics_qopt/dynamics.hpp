#pragma once

#include <cstddef>
#include <cstdint>
#include <memory>
#include <string_view>

#include <termin/physics_qopt/termin_physics_qopt_api.hpp>
#include <termin/qopt/active_set_qp.hpp>
#include <termin/qopt/block_assembly.hpp>
#include <termin/qopt/equality_qp.hpp>

namespace termin::physics_qopt
{
    using namespace termin::qopt;

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

    struct DynamicsUnilateralConstraintHandle
    {
        DenseBlockHandle block;

        [[nodiscard]] constexpr bool valid() const noexcept
        {
            return block.valid();
        }
    };

    struct DynamicsFrictionContactHandle
    {
        DenseBlockHandle contact_block;
        DenseBlockHandle tangent_block;

        [[nodiscard]] constexpr bool valid() const noexcept
        {
            return contact_block.valid() && tangent_block.valid();
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
    class TERMIN_PHYSICS_QOPT_API DynamicsTopology
    {
    public:
        [[nodiscard]] DynamicsRegistrationResult<DynamicsDofHandle>
        register_dofs(std::size_t size,
                      std::string_view diagnostic_name) noexcept;
        [[nodiscard]] DynamicsRegistrationResult<DynamicsConstraintHandle>
        register_constraint(std::size_t size,
                            std::string_view diagnostic_name) noexcept;
        [[nodiscard]] AssemblyDiagnostic finalize() noexcept;

        [[nodiscard]] bool finalized() const noexcept;
        [[nodiscard]] std::size_t dof_count() const noexcept;
        [[nodiscard]] std::size_t constraint_count() const noexcept;
        [[nodiscard]] const DenseBlockTopology& dof_topology() const noexcept;
        [[nodiscard]] const DenseBlockTopology&
        constraint_topology() const noexcept;

    private:
        DenseBlockTopology dofs_;
        DenseBlockTopology constraints_;
        bool finalized_ = false;
    };

    // The unilateral row layout is rebuilt for every transactional step. It
    // deliberately owns no permanent DOFs or equality rows: contacts and
    // other active-set constraints may appear and disappear without
    // invalidating the finalized model topology.
    class TERMIN_PHYSICS_QOPT_API DynamicsUnilateralTopology
    {
    public:
        [[nodiscard]]
        DynamicsRegistrationResult<DynamicsUnilateralConstraintHandle>
        register_constraint(std::size_t size,
                            std::string_view diagnostic_name) noexcept;
        [[nodiscard]] AssemblyDiagnostic finalize() noexcept;

        [[nodiscard]] bool finalized() const noexcept;
        [[nodiscard]] std::size_t constraint_count() const noexcept;
        [[nodiscard]] const DenseBlockTopology&
        constraint_topology() const noexcept;

    private:
        DenseBlockTopology constraints_;
        bool finalized_ = false;
    };

    // Transient friction contacts are rebuilt beside unilateral rows. Each
    // registered contact owns one scalar parameter slot and two tangent rows.
    class TERMIN_PHYSICS_QOPT_API DynamicsFrictionTopology
    {
    public:
        [[nodiscard]] DynamicsRegistrationResult<DynamicsFrictionContactHandle>
        register_contact(std::string_view diagnostic_name) noexcept;
        [[nodiscard]] AssemblyDiagnostic finalize() noexcept;

        [[nodiscard]] bool finalized() const noexcept;
        [[nodiscard]] std::size_t contact_count() const noexcept;
        [[nodiscard]] std::size_t tangent_count() const noexcept;
        [[nodiscard]] const DenseBlockTopology&
        contact_topology() const noexcept;
        [[nodiscard]] const DenseBlockTopology&
        tangent_topology() const noexcept;

    private:
        DenseBlockTopology contacts_;
        DenseBlockTopology tangents_;
        bool finalized_ = false;
    };

    struct DynamicsFrictionWorkspaceView
    {
        DenseMatrixView contact_normal_jacobian;
        DenseMatrixView tangent_jacobian;
        DenseVectorView normal_impulse;
        DenseVectorView friction_coefficient;
    };

    class TERMIN_PHYSICS_QOPT_API DynamicsFrictionAssembly
    {
    public:
        DynamicsFrictionAssembly(
            const DynamicsTopology& topology,
            const DynamicsFrictionTopology& friction_topology,
            DynamicsFrictionWorkspaceView workspace) noexcept;

        [[nodiscard]] AssemblyDiagnostic diagnostic() const noexcept;
        [[nodiscard]] bool valid() const noexcept;
        [[nodiscard]] AssemblyDiagnostic clear() noexcept;
        [[nodiscard]] AssemblyDiagnostic
        add_tangent_jacobian(DynamicsFrictionContactHandle contact,
                             DynamicsDofHandle dofs,
                             ConstDenseMatrixView contribution) noexcept;
        [[nodiscard]] AssemblyDiagnostic
        add_contact_normal_jacobian(DynamicsFrictionContactHandle contact,
                                    DynamicsDofHandle dofs,
                                    ConstDenseMatrixView contribution) noexcept;
        [[nodiscard]] AssemblyDiagnostic
        add_normal_impulse(DynamicsFrictionContactHandle contact,
                           double impulse) noexcept;
        [[nodiscard]] AssemblyDiagnostic
        add_friction_coefficient(DynamicsFrictionContactHandle contact,
                                 double coefficient) noexcept;

    private:
        DynamicsFrictionWorkspaceView workspace_;
        DenseBlockMatrixAssembly contact_normal_jacobian_;
        DenseBlockMatrixAssembly tangent_jacobian_;
        DenseBlockVectorAssembly normal_impulse_;
        DenseBlockVectorAssembly friction_coefficient_;
        AssemblyDiagnostic diagnostic_ = AssemblyDiagnostic::InternalFailure;
    };

    struct DynamicsWorkspaceView
    {
        DenseMatrixView mass;
        DenseVectorView load;
        DenseMatrixView constraint_jacobian;
        DenseVectorView constraint_rhs;
        DenseMatrixView unilateral_jacobian;
        DenseVectorView unilateral_limit;
    };

    struct ConstDynamicsSystemView
    {
        ConstDenseMatrixView mass;
        ConstDenseVectorView load;
        ConstDenseMatrixView constraint_jacobian;
        ConstDenseVectorView constraint_rhs;
    };

    struct ConstDynamicsUnilateralView
    {
        // C * x <= d, matching ActiveSetQpProblemView conventions.
        ConstDenseMatrixView jacobian;
        ConstDenseVectorView limit;
    };

    // A checked per-step writer. The topology and numerical storage are
    // borrowed; reuse the same workspace across steps when topology is
    // unchanged.
    class TERMIN_PHYSICS_QOPT_API DynamicsAssembly
    {
    public:
        DynamicsAssembly(const DynamicsTopology& topology,
                         DynamicsWorkspaceView workspace) noexcept;
        DynamicsAssembly(const DynamicsTopology& topology,
                         const DynamicsUnilateralTopology& unilateral_topology,
                         DynamicsWorkspaceView workspace) noexcept;

        [[nodiscard]] AssemblyDiagnostic diagnostic() const noexcept;
        [[nodiscard]] bool valid() const noexcept;
        [[nodiscard]] AssemblyDiagnostic clear() noexcept;

        [[nodiscard]] AssemblyDiagnostic
        add_mass(DynamicsDofHandle row,
                 DynamicsDofHandle column,
                 ConstDenseMatrixView contribution) noexcept;
        [[nodiscard]] AssemblyDiagnostic
        add_load(DynamicsDofHandle dofs,
                 ConstDenseVectorView contribution) noexcept;
        [[nodiscard]] AssemblyDiagnostic
        add_constraint_jacobian(DynamicsConstraintHandle constraint,
                                DynamicsDofHandle dofs,
                                ConstDenseMatrixView contribution) noexcept;
        [[nodiscard]] AssemblyDiagnostic
        add_constraint_rhs(DynamicsConstraintHandle constraint,
                           ConstDenseVectorView contribution) noexcept;
        [[nodiscard]] AssemblyDiagnostic
        add_unilateral_jacobian(DynamicsUnilateralConstraintHandle constraint,
                                DynamicsDofHandle dofs,
                                ConstDenseMatrixView contribution) noexcept;
        [[nodiscard]] AssemblyDiagnostic
        add_unilateral_limit(DynamicsUnilateralConstraintHandle constraint,
                             ConstDenseVectorView contribution) noexcept;

        [[nodiscard]] ConstDynamicsSystemView system() const noexcept;
        [[nodiscard]] ConstDynamicsUnilateralView
        unilateral_constraints() const noexcept;

    private:
        DynamicsWorkspaceView workspace_;
        DenseBlockMatrixAssembly mass_;
        DenseBlockVectorAssembly load_;
        DenseBlockMatrixAssembly constraint_jacobian_;
        DenseBlockVectorAssembly constraint_rhs_;
        std::unique_ptr<DenseBlockMatrixAssembly> unilateral_jacobian_;
        std::unique_ptr<DenseBlockVectorAssembly> unilateral_limit_;
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
    class TERMIN_PHYSICS_QOPT_API DynamicsContribution
    {
    public:
        virtual ~DynamicsContribution() = default;

        [[nodiscard]] virtual AssemblyDiagnostic
        register_topology(DynamicsTopology& topology) noexcept = 0;

        // Resolve references to blocks owned by other contributions after all
        // registrations have completed and the topology is immutable.
        [[nodiscard]] virtual AssemblyDiagnostic
        bind_topology(const DynamicsTopology& topology) noexcept
        {
            (void)topology;
            return AssemblyDiagnostic::None;
        }

        [[nodiscard]] virtual AssemblyDiagnostic
        assemble(DynamicsAssembly& assembly,
                 DynamicsAssemblyPhase phase) noexcept = 0;

        [[nodiscard]] virtual AssemblyDiagnostic begin_step() noexcept
        {
            return AssemblyDiagnostic::None;
        }

        // Register rows which exist only for the current step. Handles from a
        // previous call are stale by construction and are rejected by the
        // checked assembly. The time step lets a contribution convert a
        // position margin into a velocity-level limit.
        [[nodiscard]] virtual AssemblyDiagnostic
        register_unilateral_constraints(DynamicsUnilateralTopology& topology,
                                        double time_step) noexcept
        {
            (void)topology;
            (void)time_step;
            return AssemblyDiagnostic::None;
        }

        [[nodiscard]] virtual AssemblyDiagnostic
        register_friction_contacts(DynamicsFrictionTopology& topology,
                                   double time_step) noexcept
        {
            (void)topology;
            (void)time_step;
            return AssemblyDiagnostic::None;
        }

        [[nodiscard]] virtual AssemblyDiagnostic
        assemble_friction(DynamicsFrictionAssembly& assembly) noexcept
        {
            (void)assembly;
            return AssemblyDiagnostic::None;
        }

        virtual void commit_step() noexcept {}

        virtual void rollback_step() noexcept {}

        virtual void
        apply_solution(DynamicsAssemblyPhase phase,
                       const DynamicsTopology& topology,
                       ConstDenseVectorView dof_values,
                       ConstDenseVectorView constraint_reactions) noexcept
        {
            (void)phase;
            (void)topology;
            (void)dof_values;
            (void)constraint_reactions;
        }

        // Unilateral reactions are non-negative QP multipliers for C*v <= d.
        // Their physical generalized impulse is -C^T*reaction. The tight mask
        // contains 1 for rows at their limit and 0 otherwise, and can be kept
        // by a persistent-contact contribution as a later warm-start hint.
        virtual void apply_unilateral_solution(
            const DynamicsTopology& topology,
            const DynamicsUnilateralTopology& unilateral_topology,
            ConstDenseVectorView reactions,
            ConstDenseVectorView tight_mask) noexcept
        {
            (void)topology;
            (void)unilateral_topology;
            (void)reactions;
            (void)tight_mask;
        }

        // Writes cached 0/1 activity hints into this contribution's current
        // unilateral rows. True means at least one hint was supplied; the
        // system pairs it with a generic previously projected velocity and
        // falls back to a cold solve if that primal is no longer feasible.
        [[nodiscard]] virtual bool
        write_unilateral_warm_start(const DynamicsUnilateralTopology& topology,
                                    DenseVectorView active_mask) const noexcept
        {
            (void)topology;
            (void)active_mask;
            return false;
        }

        virtual void
        apply_friction_solution(const DynamicsFrictionTopology& topology,
                                ConstDenseVectorView normal_impulses,
                                ConstDenseVectorView tangent_impulses,
                                ConstDenseVectorView friction_work) noexcept
        {
            (void)topology;
            (void)normal_impulses;
            (void)tangent_impulses;
            (void)friction_work;
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
        write_corrected_midpoint_velocity(
            const DynamicsTopology& topology,
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

    [[nodiscard]] TERMIN_PHYSICS_QOPT_API std::string_view
    dynamics_system_diagnostic_name(
        DynamicsSystemDiagnostic diagnostic) noexcept;

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
        QpSolveResult velocity_projection;
        double position_constraint_linf = 0.0;
        double velocity_constraint_linf = 0.0;
        std::size_t position_iterations = 0;
        std::size_t unilateral_constraint_count = 0;
        std::size_t endpoint_equality_factorizations = 0;
        std::size_t endpoint_equality_factorization_reuses = 0;

        [[nodiscard]] constexpr bool ok() const noexcept
        {
            return status == QpStatus::Optimal &&
                   diagnostic == DynamicsSystemDiagnostic::None;
        }
    };

    class TERMIN_PHYSICS_QOPT_API DynamicsSystem
    {
    public:
        DynamicsSystem();
        ~DynamicsSystem();

        DynamicsSystem(DynamicsSystem&&) noexcept;
        DynamicsSystem& operator=(DynamicsSystem&&) noexcept;
        DynamicsSystem(const DynamicsSystem&) = delete;
        DynamicsSystem& operator=(const DynamicsSystem&) = delete;

        [[nodiscard]] DynamicsSystemDiagnostic add_contribution(
            std::unique_ptr<DynamicsContribution> contribution) noexcept;
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

    [[nodiscard]] TERMIN_PHYSICS_QOPT_API QpSolveResult
    solve_constrained_dynamics(ConstDynamicsSystemView system,
                               DynamicsSolutionView solution,
                               QpTolerance tolerance = {}) noexcept;

    struct DynamicsVelocitySolutionView
    {
        DenseVectorView velocity;
        // Physical generalized equality impulse is J^T*reaction.
        DenseVectorView constraint_reaction;
        // Non-negative multiplier for C*v <= d. The physical generalized
        // unilateral impulse is -C^T*reaction.
        DenseVectorView unilateral_reaction;
        // Optional 0/1 output. A row is tight when |C*v-d| is within the
        // active tolerance. Empty means that the caller does not need it.
        DenseVectorView tight_unilateral_mask;
    };

    // Mass-metric velocity projection:
    //
    //   minimize 0.5*v^T*M*v - load^T*v
    //   subject to J*v = rhs
    //              C*v <= d
    //
    // For an unconstrained trial velocity v*, contributions normally assemble
    // load=M*v*. Optional warm-start storage is borrowed and contact-agnostic.
    // Outputs are transactional and are modified only for an Optimal result.
    [[nodiscard]] TERMIN_PHYSICS_QOPT_API QpSolveResult
    solve_unilateral_velocity(ConstDynamicsSystemView system,
                              ConstDynamicsUnilateralView unilateral,
                              DynamicsVelocitySolutionView solution,
                              ActiveSetQpWarmStartView warm_start = {},
                              ActiveSetQpOptions options = {}) noexcept;

} // namespace termin::physics_qopt
