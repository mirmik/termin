#pragma once

#include <cstdint>
#include <string>
#include <string_view>

#include <termin/geom/pose3.hpp>
#include <termin/geom/screw3.hpp>
#include <termin/geom/spatial_inertia3.hpp>
#include <termin/qopt/dynamics.hpp>
#include <termin/qopt/termin_qopt_api.hpp>

namespace termin::qopt
{

    // Multibody3DSystem deliberately knows no concrete 3D model elements. It is
    // the generic two-pass contribution collector: topology registration
    // happens at finalize(), numerical assembly happens for every solve phase.
    using Multibody3DSystem = DynamicsSystem;
    using Multibody3DStepOptions = DynamicsSystemStepOptions;
    using Multibody3DStepResult = DynamicsSystemStepResult;

    enum class Multibody3DDiagnostic : std::uint8_t
    {
        None,
        InvalidMass,
        InvalidInertia,
        NonFiniteInput,
        InvalidJointAxis,
    };

    [[nodiscard]] TERMIN_QOPT_API std::string_view
    multibody3d_diagnostic_name(Multibody3DDiagnostic diagnostic) noexcept;

    struct RigidBody3DState
    {
        termin::Pose3 pose = termin::Pose3::identity();
        // Right-trivialized body twist at the body-frame origin.
        termin::Screw3 velocity_local = termin::Screw3::zero();
    };

    // Registers one six-DOF block. Assembly contributes spatial inertia M and
    // the gravity/velocity-bias load f. It owns state integration and
    // projection application, but no constraints.
    class TERMIN_QOPT_API RigidBody3DContribution final : public DynamicsContribution
    {
      public:
        RigidBody3DContribution(termin::SpatialInertia3 inertia,
                                RigidBody3DState initial_state = {},
                                termin::Vec3 gravity_world = termin::Vec3::zero(),
                                std::string_view diagnostic_name = {});

        [[nodiscard]] Multibody3DDiagnostic diagnostic() const noexcept;
        [[nodiscard]] const termin::SpatialInertia3& inertia() const noexcept;
        [[nodiscard]] const RigidBody3DState& state() const noexcept;
        [[nodiscard]] const termin::Screw3&
        twist_rate_at_body_origin_local() const noexcept;
        [[nodiscard]] termin::Screw3 velocity_at_body_origin_world() const noexcept;
        [[nodiscard]] DynamicsDofHandle dofs() const noexcept;
        [[nodiscard]] termin::Vec3 gravity_world() const noexcept;
        [[nodiscard]] Multibody3DDiagnostic set_state(RigidBody3DState state) noexcept;
        [[nodiscard]] Multibody3DDiagnostic
        set_gravity_world(termin::Vec3 gravity) noexcept;
        [[nodiscard]] double total_energy() const noexcept;

        AssemblyDiagnostic
        register_topology(DynamicsTopology& topology) noexcept override;
        AssemblyDiagnostic assemble(DynamicsAssembly& assembly,
                                    DynamicsAssemblyPhase phase) noexcept override;
        AssemblyDiagnostic begin_step() noexcept override;
        void commit_step() noexcept override;
        void rollback_step() noexcept override;
        void
        apply_solution(DynamicsAssemblyPhase phase,
                       const DynamicsTopology& topology,
                       ConstDenseVectorView dof_values,
                       ConstDenseVectorView constraint_reactions) noexcept override;
        AssemblyDiagnostic
        write_velocity(const DynamicsTopology& topology,
                       DenseVectorView destination) const noexcept override;
        AssemblyDiagnostic
        set_velocity(const DynamicsTopology& topology,
                     ConstDenseVectorView velocity) noexcept override;
        AssemblyDiagnostic
        set_trial_configuration(const DynamicsTopology& topology,
                                ConstDenseVectorView midpoint_velocity,
                                double time_step) noexcept override;
        AssemblyDiagnostic write_corrected_midpoint_velocity(
            const DynamicsTopology& topology,
            ConstDenseVectorView midpoint_velocity,
            ConstDenseVectorView trial_tangent_correction,
            double time_step,
            DenseVectorView destination) const noexcept override;

      private:
        termin::SpatialInertia3 inertia_;
        RigidBody3DState state_;
        termin::Screw3 twist_rate_at_body_origin_local_ = termin::Screw3::zero();
        termin::Vec3 gravity_world_;
        std::string diagnostic_name_;
        DynamicsDofHandle dofs_;
        Multibody3DDiagnostic diagnostic_ = Multibody3DDiagnostic::None;
        RigidBody3DState state_snapshot_;
        termin::Screw3 twist_rate_snapshot_ = termin::Screw3::zero();
        bool snapshot_ready_ = false;
    };

    // Adds an independently mutable world-frame wrench f to an existing body
    // DOF block. It owns no variables and therefore registers no topology
    // blocks.
    class TERMIN_QOPT_API ForceOnBody3DContribution final : public DynamicsContribution
    {
      public:
        explicit ForceOnBody3DContribution(
            RigidBody3DContribution& body,
            termin::Screw3 wrench_at_body_origin_world = {}) noexcept;

        void set_wrench_at_body_origin_world(termin::Screw3 wrench) noexcept;
        [[nodiscard]] const termin::Screw3&
        wrench_at_body_origin_world() const noexcept;

        AssemblyDiagnostic
        register_topology(DynamicsTopology& topology) noexcept override;
        AssemblyDiagnostic assemble(DynamicsAssembly& assembly,
                                    DynamicsAssemblyPhase phase) noexcept override;

      private:
        RigidBody3DContribution* body_;
        termin::Screw3 wrench_at_body_origin_world_;
    };

    // Three equations constrain a body-local point to a fixed world point:
    // J [a, alpha] = gamma. All body rotations remain free.
    class TERMIN_QOPT_API FixedPointJoint3DContribution final
        : public DynamicsContribution
    {
      public:
        FixedPointJoint3DContribution(RigidBody3DContribution& body,
                                      termin::Vec3 body_anchor_local,
                                      termin::Vec3 world_anchor,
                                      std::string_view diagnostic_name = {});

        // World-frame reaction wrench at the joint anchor. ang is the
        // constraint moment about that anchor; lin is the anchor force.
        [[nodiscard]] const termin::Screw3&
        reaction_at_joint_anchor_world() const noexcept;
        AssemblyDiagnostic
        register_topology(DynamicsTopology& topology) noexcept override;
        AssemblyDiagnostic assemble(DynamicsAssembly& assembly,
                                    DynamicsAssemblyPhase phase) noexcept override;
        AssemblyDiagnostic begin_step() noexcept override;
        void commit_step() noexcept override;
        void rollback_step() noexcept override;
        void
        apply_solution(DynamicsAssemblyPhase phase,
                       const DynamicsTopology& topology,
                       ConstDenseVectorView dof_values,
                       ConstDenseVectorView constraint_reactions) noexcept override;
        double position_error_linf() const noexcept override;
        double velocity_error_linf() const noexcept override;

      private:
        RigidBody3DContribution* body_;
        termin::Vec3 body_anchor_local_;
        termin::Vec3 world_anchor_;
        std::string diagnostic_name_;
        DynamicsConstraintHandle constraint_;
        termin::Screw3 reaction_at_joint_anchor_world_ = termin::Screw3::zero();
        termin::Screw3 reaction_snapshot_ = termin::Screw3::zero();
    };

    // Three equations make two body-local anchor points coincide while leaving
    // all three relative rotations free (a ball/point joint).
    class TERMIN_QOPT_API PointJoint3DContribution final : public DynamicsContribution
    {
      public:
        PointJoint3DContribution(RigidBody3DContribution& body_a,
                                 termin::Vec3 body_a_anchor_local,
                                 RigidBody3DContribution& body_b,
                                 termin::Vec3 body_b_anchor_local,
                                 std::string_view diagnostic_name = {});

        [[nodiscard]] const termin::Screw3&
        reaction_at_joint_anchor_world() const noexcept;
        AssemblyDiagnostic
        register_topology(DynamicsTopology& topology) noexcept override;
        AssemblyDiagnostic assemble(DynamicsAssembly& assembly,
                                    DynamicsAssemblyPhase phase) noexcept override;
        AssemblyDiagnostic begin_step() noexcept override;
        void commit_step() noexcept override;
        void rollback_step() noexcept override;
        void
        apply_solution(DynamicsAssemblyPhase phase,
                       const DynamicsTopology& topology,
                       ConstDenseVectorView dof_values,
                       ConstDenseVectorView constraint_reactions) noexcept override;
        double position_error_linf() const noexcept override;
        double velocity_error_linf() const noexcept override;

      private:
        RigidBody3DContribution* body_a_;
        RigidBody3DContribution* body_b_;
        termin::Vec3 body_a_anchor_local_;
        termin::Vec3 body_b_anchor_local_;
        std::string diagnostic_name_;
        DynamicsConstraintHandle constraint_;
        termin::Screw3 reaction_at_joint_anchor_world_ = termin::Screw3::zero();
        termin::Screw3 reaction_snapshot_ = termin::Screw3::zero();
    };

    // Five equations pin an anchor and align a body-local hinge axis with a
    // fixed world axis, leaving only rotation around that axis free.
    class TERMIN_QOPT_API FixedRevoluteJoint3DContribution final
        : public DynamicsContribution
    {
      public:
        FixedRevoluteJoint3DContribution(RigidBody3DContribution& body,
                                         termin::Vec3 body_anchor_local,
                                         termin::Vec3 body_axis_local,
                                         termin::Vec3 world_anchor,
                                         termin::Vec3 world_axis,
                                         std::string_view diagnostic_name = {});

        [[nodiscard]] Multibody3DDiagnostic diagnostic() const noexcept;
        [[nodiscard]] const termin::Screw3&
        reaction_at_joint_anchor_world() const noexcept;
        AssemblyDiagnostic
        register_topology(DynamicsTopology& topology) noexcept override;
        AssemblyDiagnostic assemble(DynamicsAssembly& assembly,
                                    DynamicsAssemblyPhase phase) noexcept override;
        AssemblyDiagnostic begin_step() noexcept override;
        void commit_step() noexcept override;
        void rollback_step() noexcept override;
        void
        apply_solution(DynamicsAssemblyPhase phase,
                       const DynamicsTopology& topology,
                       ConstDenseVectorView dof_values,
                       ConstDenseVectorView constraint_reactions) noexcept override;
        double position_error_linf() const noexcept override;
        double velocity_error_linf() const noexcept override;

      private:
        RigidBody3DContribution* body_;
        termin::Vec3 body_anchor_local_;
        termin::Vec3 body_axis_local_;
        termin::Vec3 world_anchor_;
        termin::Vec3 world_axis_;
        std::string diagnostic_name_;
        DynamicsConstraintHandle constraint_;
        termin::Screw3 reaction_at_joint_anchor_world_ = termin::Screw3::zero();
        termin::Screw3 reaction_snapshot_ = termin::Screw3::zero();
        Multibody3DDiagnostic diagnostic_ = Multibody3DDiagnostic::None;
    };

    // Five equations: three anchor-coincidence rows and two axis-alignment
    // rows. Exactly one relative twist around the hinge axis remains
    // unconstrained.
    class TERMIN_QOPT_API RevoluteJoint3DContribution final
        : public DynamicsContribution
    {
      public:
        RevoluteJoint3DContribution(RigidBody3DContribution& body_a,
                                    termin::Vec3 body_a_anchor_local,
                                    termin::Vec3 body_a_axis_local,
                                    RigidBody3DContribution& body_b,
                                    termin::Vec3 body_b_anchor_local,
                                    termin::Vec3 body_b_axis_local,
                                    std::string_view diagnostic_name = {});

        [[nodiscard]] Multibody3DDiagnostic diagnostic() const noexcept;
        [[nodiscard]] const termin::Screw3&
        reaction_at_joint_anchor_world() const noexcept;
        AssemblyDiagnostic
        register_topology(DynamicsTopology& topology) noexcept override;
        AssemblyDiagnostic assemble(DynamicsAssembly& assembly,
                                    DynamicsAssemblyPhase phase) noexcept override;
        AssemblyDiagnostic begin_step() noexcept override;
        void commit_step() noexcept override;
        void rollback_step() noexcept override;
        void
        apply_solution(DynamicsAssemblyPhase phase,
                       const DynamicsTopology& topology,
                       ConstDenseVectorView dof_values,
                       ConstDenseVectorView constraint_reactions) noexcept override;
        double position_error_linf() const noexcept override;
        double velocity_error_linf() const noexcept override;

      private:
        RigidBody3DContribution* body_a_;
        RigidBody3DContribution* body_b_;
        termin::Vec3 body_a_anchor_local_;
        termin::Vec3 body_a_axis_local_;
        termin::Vec3 body_b_anchor_local_;
        termin::Vec3 body_b_axis_local_;
        std::string diagnostic_name_;
        DynamicsConstraintHandle constraint_;
        termin::Screw3 reaction_at_joint_anchor_world_ = termin::Screw3::zero();
        termin::Screw3 reaction_snapshot_ = termin::Screw3::zero();
        Multibody3DDiagnostic diagnostic_ = Multibody3DDiagnostic::None;
    };

} // namespace termin::qopt
