#pragma once

#include <cstddef>
#include <cstdint>
#include <string>
#include <string_view>
#include <vector>

#include <termin/qopt/dense_views.hpp>
#include <termin/robotics/articulation3d.hpp>
#include <termin/robotics/termin_robotics_api.hpp>

namespace termin::robotics
{

    enum class TaskDerivativeOrder3D : std::uint8_t
    {
        Velocity,
        Acceleration,
    };

    enum class TaskRelation3D : std::uint8_t
    {
        Objective,
        Equality,
        Inequality,
    };

    enum class TaskDiagnostic3D : std::uint8_t
    {
        None,
        InvalidContext,
        InvalidModel,
        InvalidLink,
        InvalidJoint,
        DuplicateJoint,
        DimensionMismatch,
        NonFiniteInput,
        InvalidBounds,
        InvalidWeight,
        InvalidGain,
        InvalidTimeStep,
        InvalidNormal,
        UnsupportedDerivativeOrder,
        InternalFailure,
    };

    [[nodiscard]] TERMIN_ROBOTICS_API std::string_view
    task_diagnostic_name(TaskDiagnostic3D diagnostic) noexcept;

    struct TaskSettings3D
    {
        int priority = 0;
        bool enabled = true;
        // Empty means identity. Standard tasks interpret this as a diagonal
        // objective weight and copy it into the owned full weight matrix.
        std::vector<double> diagonal_weight;
        std::string diagnostic_name;
    };

    // Owned, solver-neutral linearization over one generalized derivative
    // vector. Inequalities always use matrix * x <= target. Empty weight means
    // identity and is meaningful only for Objective relations.
    struct TERMIN_ROBOTICS_API TaskLinearization3D
    {
        TaskRelation3D relation = TaskRelation3D::Objective;
        TaskDerivativeOrder3D derivative_order =
            TaskDerivativeOrder3D::Velocity;
        int priority = 0;
        bool active = true;
        std::string diagnostic_name;
        std::size_t variable_count = 0;
        std::vector<double> matrix_storage;
        std::vector<double> target_storage;
        std::vector<double> weight_storage;

        [[nodiscard]] std::size_t row_count() const noexcept;
        [[nodiscard]] qopt::ConstDenseMatrixView matrix() const noexcept;
        [[nodiscard]] qopt::ConstDenseVectorView target() const noexcept;
        [[nodiscard]] qopt::ConstDenseMatrixView weight() const noexcept;
    };

    struct TERMIN_ROBOTICS_API TaskLinearization3DResult
    {
        TaskLinearization3D value;
        TaskDiagnostic3D diagnostic = TaskDiagnostic3D::None;

        [[nodiscard]] bool ok() const noexcept;
    };

    struct TaskLinearizationContext3D
    {
        const Articulation3D* articulation = nullptr;
        TaskDerivativeOrder3D derivative_order =
            TaskDerivativeOrder3D::Velocity;
        // Required by predictive position and limit constraints.
        double time_step = 0.0;
    };

    class TERMIN_ROBOTICS_API ArticulationTask3D
    {
    public:
        virtual ~ArticulationTask3D() = default;

        [[nodiscard]] virtual TaskLinearization3DResult
        linearize(const TaskLinearizationContext3D& context) const noexcept = 0;
    };

    class TERMIN_ROBOTICS_API PointVelocityTask3D final
        : public ArticulationTask3D
    {
    public:
        PointVelocityTask3D(std::size_t link_index,
                            termin::Vec3 point_local,
                            termin::Vec3 target_velocity_world,
                            TaskSettings3D settings = {});

        [[nodiscard]] TaskLinearization3DResult linearize(
            const TaskLinearizationContext3D& context) const noexcept override;

    private:
        std::size_t link_index_;
        termin::Vec3 point_local_;
        termin::Vec3 target_velocity_world_;
        TaskSettings3D settings_;
    };

    class TERMIN_ROBOTICS_API PoseTrackingTask3D final
        : public ArticulationTask3D
    {
    public:
        PoseTrackingTask3D(
            std::size_t link_index,
            termin::Pose3 target_pose_world,
            termin::Screw3 target_velocity_world = termin::Screw3::zero(),
            double linear_gain = 1.0,
            double angular_gain = 1.0,
            TaskSettings3D settings = {});

        [[nodiscard]] TaskLinearization3DResult linearize(
            const TaskLinearizationContext3D& context) const noexcept override;

    private:
        std::size_t link_index_;
        termin::Pose3 target_pose_world_;
        termin::Screw3 target_velocity_world_;
        double linear_gain_;
        double angular_gain_;
        TaskSettings3D settings_;
    };

    class TERMIN_ROBOTICS_API JointPositionTask3D final
        : public ArticulationTask3D
    {
    public:
        JointPositionTask3D(std::vector<std::size_t> joint_indices,
                            std::vector<double> target_positions,
                            double gain = 1.0,
                            std::vector<double> feedforward_velocities = {},
                            TaskSettings3D settings = {});

        [[nodiscard]] TaskLinearization3DResult linearize(
            const TaskLinearizationContext3D& context) const noexcept override;

    private:
        std::vector<std::size_t> joint_indices_;
        std::vector<double> target_positions_;
        double gain_;
        std::vector<double> feedforward_velocities_;
        TaskSettings3D settings_;
    };

    class TERMIN_ROBOTICS_API JointVelocityTask3D final
        : public ArticulationTask3D
    {
    public:
        JointVelocityTask3D(std::vector<std::size_t> joint_indices,
                            std::vector<double> target_velocities,
                            double acceleration_gain = 1.0,
                            TaskSettings3D settings = {});

        [[nodiscard]] TaskLinearization3DResult linearize(
            const TaskLinearizationContext3D& context) const noexcept override;

    private:
        std::vector<std::size_t> joint_indices_;
        std::vector<double> target_velocities_;
        double acceleration_gain_;
        TaskSettings3D settings_;
    };

    class TERMIN_ROBOTICS_API JointLimitConstraint3D final
        : public ArticulationTask3D
    {
    public:
        explicit JointLimitConstraint3D(TaskSettings3D settings = {});

        [[nodiscard]] TaskLinearization3DResult linearize(
            const TaskLinearizationContext3D& context) const noexcept override;

    private:
        TaskSettings3D settings_;
    };

    class TERMIN_ROBOTICS_API JointVelocityLimitConstraint3D final
        : public ArticulationTask3D
    {
    public:
        JointVelocityLimitConstraint3D(std::vector<std::size_t> joint_indices,
                                       std::vector<double> minimum_velocities,
                                       std::vector<double> maximum_velocities,
                                       TaskSettings3D settings = {});

        [[nodiscard]] TaskLinearization3DResult linearize(
            const TaskLinearizationContext3D& context) const noexcept override;

    private:
        std::vector<std::size_t> joint_indices_;
        std::vector<double> minimum_velocities_;
        std::vector<double> maximum_velocities_;
        TaskSettings3D settings_;
    };

    // The normal points toward increasing signed distance. The velocity-level
    // inequality ensures that first-order distance prediction after horizon
    // seconds is not below minimum_distance.
    class TERMIN_ROBOTICS_API PointAvoidanceConstraint3D final
        : public ArticulationTask3D
    {
    public:
        PointAvoidanceConstraint3D(std::size_t link_index,
                                   termin::Vec3 point_local,
                                   termin::Vec3 normal_world,
                                   double signed_distance,
                                   double minimum_distance,
                                   double horizon,
                                   TaskSettings3D settings = {});

        [[nodiscard]] TaskLinearization3DResult linearize(
            const TaskLinearizationContext3D& context) const noexcept override;

    private:
        std::size_t link_index_;
        termin::Vec3 point_local_;
        termin::Vec3 normal_world_;
        double signed_distance_;
        double minimum_distance_;
        double horizon_;
        TaskSettings3D settings_;
    };

} // namespace termin::robotics
