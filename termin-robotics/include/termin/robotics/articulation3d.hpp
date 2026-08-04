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
#include <termin/qopt/dense_views.hpp>
#include <termin/robotics/termin_robotics_api.hpp>

namespace termin::robotics::detail
{
    class Articulation3DMutableAccess;
}

namespace termin::robotics
{

    inline constexpr std::size_t articulation_root_frame =
        std::numeric_limits<std::size_t>::max();
    // Compatibility spelling for fixed-base callers. New code should use the
    // formulation-neutral root-frame name.
    inline constexpr std::size_t articulation_world_link =
        articulation_root_frame;

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
        InvalidModel,
        InvalidLink,
        NonFinitePoint,
        InternalFailure,
    };

    [[nodiscard]] TERMIN_ROBOTICS_API std::string_view
    articulation3d_diagnostic_name(
        Articulation3DDiagnostic diagnostic) noexcept;

    struct ArticulationJointLimits3D
    {
        std::optional<double> minimum;
        std::optional<double> maximum;
    };

    // One physical link and the one-DOF joint that attaches it to its parent.
    // Links must be stored in topological order. The root-frame sentinel
    // denotes the articulation root frame: inertial world for a fixed base,
    // or the explicit root body frame for a floating base.
    struct ArticulationLink3D
    {
        std::size_t parent_link = articulation_root_frame;
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

    // The physical root body of a floating-base articulation. Its velocity is
    // the right-trivialized body twist at the base-frame origin. In the
    // generalized block the corresponding six entries precede all joint
    // velocities and use the standard vw order: linear, then angular.
    struct ArticulationFloatingBase3D
    {
        termin::SpatialInertia3 inertia;
        termin::Pose3 pose_world = termin::Pose3::identity();
        termin::Screw3 velocity_local = termin::Screw3::zero();
        std::string diagnostic_name;
    };

    // Solver-neutral differential kinematics of a material point. The dense
    // Jacobian maps the complete generalized velocity of this articulation to
    // world linear velocity. Solver adapters attach their own variable-block
    // handles instead of leaking a DynamicsDofHandle into the tree model.
    struct TERMIN_ROBOTICS_API ArticulationPointKinematics3D
    {
        termin::Vec3 position_world = termin::Vec3::zero();
        termin::Vec3 velocity_world = termin::Vec3::zero();
        // Jdot(q, qdot) * qdot in the inertial world frame. Consequently a
        // commanded point acceleration satisfies
        // J * qdd = acceleration_world - bias_acceleration_world.
        termin::Vec3 bias_acceleration_world = termin::Vec3::zero();
        std::vector<double> linear_jacobian_world_storage;

        [[nodiscard]] std::size_t dof_count() const noexcept;
        [[nodiscard]] qopt::ConstDenseMatrixView
        linear_jacobian_world() const noexcept;
    };

    struct TERMIN_ROBOTICS_API ArticulationPointKinematics3DResult
    {
        ArticulationPointKinematics3D value;
        Articulation3DDiagnostic diagnostic = Articulation3DDiagnostic::None;

        [[nodiscard]] bool ok() const noexcept;
    };

    // Differential kinematics of a link frame. World spatial velocity and
    // Jacobian use vw row order: linear velocity first, angular velocity
    // second. Both are taken at the link-frame origin.
    struct TERMIN_ROBOTICS_API ArticulationFrameKinematics3D
    {
        termin::Pose3 pose_world = termin::Pose3::identity();
        termin::Screw3 velocity_world = termin::Screw3::zero();
        // Spatial Jdot(q, qdot) * qdot at the frame origin, expressed in the
        // inertial world frame and using the same vw convention as velocity.
        termin::Screw3 bias_acceleration_world = termin::Screw3::zero();
        std::vector<double> spatial_jacobian_world_storage;

        [[nodiscard]] std::size_t dof_count() const noexcept;
        [[nodiscard]] qopt::ConstDenseMatrixView
        spatial_jacobian_world() const noexcept;
    };

    struct TERMIN_ROBOTICS_API ArticulationFrameKinematics3DResult
    {
        ArticulationFrameKinematics3D value;
        Articulation3DDiagnostic diagnostic = Articulation3DDiagnostic::None;

        [[nodiscard]] bool ok() const noexcept;
    };

    // Solver-neutral reduced-coordinate tree. It owns the mechanism topology,
    // configuration, velocity and kinematic cache. Inertial data stays on the
    // links, so dynamics algorithms can operate on the same compiled model
    // without owning a parallel tree representation.
    class TERMIN_ROBOTICS_API Articulation3D
    {
    public:
        Articulation3D(std::vector<ArticulationLink3D> links,
                       Articulation3DState initial_state,
                       std::string_view diagnostic_name = {});
        Articulation3D(ArticulationFloatingBase3D floating_base,
                       std::vector<ArticulationLink3D> links,
                       Articulation3DState initial_state,
                       std::string_view diagnostic_name = {});

        Articulation3D(const Articulation3D&) = delete;
        Articulation3D& operator=(const Articulation3D&) = delete;
        Articulation3D(Articulation3D&&) = delete;
        Articulation3D& operator=(Articulation3D&&) = delete;

        [[nodiscard]] Articulation3DDiagnostic diagnostic() const noexcept;
        [[nodiscard]] std::string_view diagnostic_name() const noexcept;
        [[nodiscard]] std::size_t link_count() const noexcept;
        [[nodiscard]] std::size_t dof_count() const noexcept;
        [[nodiscard]] const std::vector<ArticulationLink3D>&
        links() const noexcept;
        [[nodiscard]] const Articulation3DState& state() const noexcept;
        [[nodiscard]] bool has_floating_base() const noexcept;
        [[nodiscard]] const std::optional<ArticulationFloatingBase3D>&
        floating_base() const noexcept;
        [[nodiscard]] const std::vector<termin::Pose3>&
        link_poses_world() const noexcept;
        [[nodiscard]] const std::vector<termin::Screw3>&
        link_velocities_local() const noexcept;
        [[nodiscard]] ArticulationPointKinematics3DResult
        point_kinematics(std::size_t link_index,
                         termin::Vec3 point_local) const noexcept;
        [[nodiscard]] ArticulationPointKinematics3DResult
        floating_base_point_kinematics(termin::Vec3 point_local) const noexcept;
        [[nodiscard]] ArticulationFrameKinematics3DResult
        frame_kinematics(std::size_t link_index) const noexcept;
        [[nodiscard]] ArticulationFrameKinematics3DResult
        floating_base_frame_kinematics() const noexcept;

        [[nodiscard]] Articulation3DDiagnostic
        set_state(Articulation3DState state) noexcept;
        [[nodiscard]] Articulation3DDiagnostic
        set_floating_base_state(termin::Pose3 pose_world,
                                termin::Screw3 velocity_local) noexcept;

        // RNEA and energy remain tree algorithms: they consume the inertial
        // properties stored by the model but do not choose a solver or a time
        // integration policy.
        [[nodiscard]] bool
        inverse_dynamics(const std::vector<double>& velocities,
                         const std::vector<double>& accelerations,
                         termin::Vec3 gravity_world,
                         std::vector<double>& effort) const;
        [[nodiscard]] bool mass_matrix(std::vector<double>& mass) const;
        [[nodiscard]] double
        total_energy(termin::Vec3 gravity_world) const noexcept;

    private:
        friend class detail::Articulation3DMutableAccess;

        std::vector<ArticulationLink3D> links_;
        Articulation3DState state_;
        std::optional<ArticulationFloatingBase3D> floating_base_;
        std::string diagnostic_name_;
        Articulation3DDiagnostic diagnostic_ = Articulation3DDiagnostic::None;

        std::vector<termin::Pose3> parent_to_link_;
        std::vector<termin::Pose3> link_poses_world_;
        std::vector<termin::Screw3> motion_twists_at_link_;
        std::vector<termin::Screw3> link_velocities_local_;

        [[nodiscard]] Articulation3DDiagnostic validate_model() const noexcept;
        [[nodiscard]] bool update_kinematics() noexcept;
        [[nodiscard]] bool bias_accelerations_local(
            std::vector<termin::Screw3>& accelerations) const;
    };

} // namespace termin::robotics
