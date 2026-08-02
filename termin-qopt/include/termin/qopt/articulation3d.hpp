#pragma once

#include <cstddef>
#include <cstdint>
#include <limits>
#include <optional>
#include <string>
#include <string_view>
#include <vector>

#include <termin/geom/pose3.hpp>
#include <termin/geom/screw3.hpp>
#include <termin/geom/spatial_inertia3.hpp>
#include <termin/qopt/dynamics.hpp>
#include <termin/qopt/point_kinematics3d.hpp>
#include <termin/qopt/termin_qopt_api.hpp>

namespace termin::qopt
{

    inline constexpr std::size_t articulation_world_link =
        std::numeric_limits<std::size_t>::max();

    enum class Articulation3DDiagnostic : std::uint8_t
    {
        None,
        EmptyModel,
        InvalidParent,
        InvalidPose,
        InvalidMotionTwist,
        InvalidInertia,
        InvalidState,
        InvalidJointLimits,
        NonFiniteInput,
    };

    [[nodiscard]] TERMIN_QOPT_API std::string_view
    articulation3d_diagnostic_name(Articulation3DDiagnostic diagnostic) noexcept;

    struct ArticulationJointLimits3D
    {
        std::optional<double> minimum;
        std::optional<double> maximum;
    };

    struct ArticulationJointLimitState3D
    {
        double minimum_reaction = 0.0;
        double maximum_reaction = 0.0;
        bool minimum_active = false;
        bool maximum_active = false;

        [[nodiscard]] constexpr double signed_effort() const noexcept
        {
            return minimum_reaction - maximum_reaction;
        }
    };

    // One physical link and the one-DOF joint that attaches it to its parent.
    // Links must be stored in topological order. The world parent denotes a
    // fixed base frame, so this first vertical slice has one reduced DOF per
    // link and no floating-base coordinates.
    struct ArticulationLink3D
    {
        std::size_t parent_link = articulation_world_link;
        termin::Pose3 parent_to_joint_zero = termin::Pose3::identity();
        // Motion twist expressed at the moving joint-frame origin. A canonical
        // revolute joint uses {unit_axis, 0}; a prismatic joint uses
        // {0, unit_axis}. Coordinate scaling is therefore explicit in this
        // value and should normally be one radian or one metre.
        termin::Screw3 motion_twist_at_joint = termin::Screw3::zero();
        termin::Pose3 joint_to_link = termin::Pose3::identity();
        termin::SpatialInertia3 inertia;
        ArticulationJointLimits3D limits;
        std::string diagnostic_name;
    };

    struct Articulation3DState
    {
        std::vector<double> coordinates;
        std::vector<double> velocities;
    };

    // A reduced fixed-base tree contribution. Internal joints are satisfied by
    // construction: the generic DynamicsSystem sees one N-dimensional block,
    // not N maximal rigid bodies and their constraint rows.
    class TERMIN_QOPT_API Articulation3DContribution final : public DynamicsContribution
    {
      public:
        Articulation3DContribution(std::vector<ArticulationLink3D> links,
                                   Articulation3DState initial_state,
                                   termin::Vec3 gravity_world = termin::Vec3::zero(),
                                   std::string_view diagnostic_name = {});

        [[nodiscard]] Articulation3DDiagnostic diagnostic() const noexcept;
        [[nodiscard]] std::size_t link_count() const noexcept;
        [[nodiscard]] std::size_t dof_count() const noexcept;
        [[nodiscard]] const std::vector<ArticulationLink3D>& links() const noexcept;
        [[nodiscard]] const Articulation3DState& state() const noexcept;
        [[nodiscard]] const std::vector<double>& accelerations() const noexcept;
        [[nodiscard]] const std::vector<termin::Pose3>&
        link_poses_world() const noexcept;
        [[nodiscard]] const std::vector<termin::Screw3>&
        link_velocities_local() const noexcept;
        [[nodiscard]] const std::vector<ArticulationJointLimitState3D>&
        joint_limit_states() const noexcept;
        [[nodiscard]] DynamicsDofHandle dofs() const noexcept;
        [[nodiscard]] termin::Vec3 gravity_world() const noexcept;
        [[nodiscard]] PointKinematics3DResult
        point_kinematics(std::size_t link_index,
                         termin::Vec3 point_local) const noexcept;

        [[nodiscard]] Articulation3DDiagnostic
        set_state(Articulation3DState state) noexcept;
        [[nodiscard]] Articulation3DDiagnostic
        set_gravity_world(termin::Vec3 gravity) noexcept;
        [[nodiscard]] double total_energy() const noexcept;

        AssemblyDiagnostic
        register_topology(DynamicsTopology& topology) noexcept override;
        AssemblyDiagnostic
        register_unilateral_constraints(DynamicsUnilateralTopology& topology,
                                        double time_step) noexcept override;
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
        void
        apply_unilateral_solution(const DynamicsTopology& topology,
                                  const DynamicsUnilateralTopology& unilateral_topology,
                                  ConstDenseVectorView reactions,
                                  ConstDenseVectorView tight_mask) noexcept override;
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
        std::vector<ArticulationLink3D> links_;
        Articulation3DState state_;
        std::vector<double> accelerations_;
        termin::Vec3 gravity_world_;
        std::string diagnostic_name_;
        DynamicsDofHandle dofs_;
        Articulation3DDiagnostic diagnostic_ = Articulation3DDiagnostic::None;

        std::vector<termin::Pose3> parent_to_link_;
        std::vector<termin::Pose3> link_poses_world_;
        std::vector<termin::Screw3> motion_twists_at_link_;
        std::vector<termin::Screw3> link_velocities_local_;

        struct JointLimitRows
        {
            DynamicsUnilateralConstraintHandle minimum;
            DynamicsUnilateralConstraintHandle maximum;
        };

        std::vector<JointLimitRows> joint_limit_rows_;
        std::vector<ArticulationJointLimitState3D> joint_limit_states_;
        double unilateral_time_step_ = 0.0;

        Articulation3DState state_snapshot_;
        std::vector<double> acceleration_snapshot_;
        std::vector<ArticulationJointLimitState3D> joint_limit_state_snapshot_;
        bool snapshot_ready_ = false;

        [[nodiscard]] Articulation3DDiagnostic validate_model() const noexcept;
        [[nodiscard]] bool update_kinematics() noexcept;
        [[nodiscard]] bool inverse_dynamics(const std::vector<double>& velocities,
                                            const std::vector<double>& accelerations,
                                            termin::Vec3 gravity_world,
                                            std::vector<double>& effort) const;
        [[nodiscard]] bool assemble_mass_and_bias(std::vector<double>& mass,
                                                  std::vector<double>& bias) const;
    };

} // namespace termin::qopt
