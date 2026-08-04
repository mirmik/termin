#include <termin/robotics/tasks.hpp>

#include <termin/geom/se3.hpp>

#include <algorithm>
#include <cmath>
#include <cstdio>
#include <exception>
#include <utility>

namespace termin::robotics
{
    namespace
    {
        bool finite(const std::vector<double>& values) noexcept
        {
            return std::all_of(values.begin(),
                               values.end(),
                               [](double value)
                               { return std::isfinite(value); });
        }

        TaskLinearization3DResult failure(TaskDiagnostic3D diagnostic,
                                          const TaskSettings3D& settings,
                                          std::string_view message) noexcept
        {
            std::fprintf(
                stderr,
                "[termin-robotics] task '%s' failed: %.*s (%.*s)\n",
                settings.diagnostic_name.c_str(),
                static_cast<int>(message.size()),
                message.data(),
                static_cast<int>(task_diagnostic_name(diagnostic).size()),
                task_diagnostic_name(diagnostic).data());
            return {{}, diagnostic};
        }

        TaskDiagnostic3D
        validate_context(const TaskLinearizationContext3D& context) noexcept
        {
            if (context.articulation == nullptr)
            {
                return TaskDiagnostic3D::InvalidContext;
            }
            if (context.articulation->diagnostic() !=
                Articulation3DDiagnostic::None)
            {
                return TaskDiagnostic3D::InvalidModel;
            }
            return TaskDiagnostic3D::None;
        }

        TaskLinearization3D
        make_linearization(const TaskLinearizationContext3D& context,
                           const TaskSettings3D& settings,
                           TaskRelation3D relation,
                           std::size_t rows)
        {
            TaskLinearization3D value;
            value.relation = relation;
            value.derivative_order = context.derivative_order;
            value.priority = settings.priority;
            value.active = settings.enabled && rows != 0;
            value.diagnostic_name = settings.diagnostic_name;
            value.variable_count = context.articulation->dof_count();
            value.matrix_storage.assign(rows * value.variable_count, 0.0);
            value.target_storage.assign(rows, 0.0);
            return value;
        }

        TaskDiagnostic3D apply_weight(TaskLinearization3D& value,
                                      const TaskSettings3D& settings)
        {
            if (value.relation != TaskRelation3D::Objective ||
                settings.diagonal_weight.empty())
            {
                return TaskDiagnostic3D::None;
            }
            const std::size_t rows = value.row_count();
            if (settings.diagonal_weight.size() != rows)
            {
                return TaskDiagnostic3D::DimensionMismatch;
            }
            if (!finite(settings.diagonal_weight) ||
                std::any_of(settings.diagonal_weight.begin(),
                            settings.diagonal_weight.end(),
                            [](double weight) { return weight < 0.0; }))
            {
                return TaskDiagnostic3D::InvalidWeight;
            }
            value.weight_storage.assign(rows * rows, 0.0);
            for (std::size_t index = 0; index < rows; ++index)
            {
                value.weight_storage[index * rows + index] =
                    settings.diagonal_weight[index];
            }
            return TaskDiagnostic3D::None;
        }

        TaskDiagnostic3D
        validate_joints(const Articulation3D& articulation,
                        const std::vector<std::size_t>& joint_indices) noexcept
        {
            for (std::size_t position = 0; position < joint_indices.size();
                 ++position)
            {
                if (joint_indices[position] >= articulation.link_count())
                {
                    return TaskDiagnostic3D::InvalidJoint;
                }
                if (std::find(joint_indices.begin(),
                              joint_indices.begin() +
                                  static_cast<std::ptrdiff_t>(position),
                              joint_indices[position]) !=
                    joint_indices.begin() +
                        static_cast<std::ptrdiff_t>(position))
                {
                    return TaskDiagnostic3D::DuplicateJoint;
                }
            }
            return TaskDiagnostic3D::None;
        }

        std::vector<std::size_t>
        resolve_joints(const Articulation3D& articulation,
                       const std::vector<std::size_t>& joint_indices)
        {
            if (!joint_indices.empty())
            {
                return joint_indices;
            }
            std::vector<std::size_t> resolved(articulation.link_count());
            for (std::size_t index = 0; index < resolved.size(); ++index)
            {
                resolved[index] = index;
            }
            return resolved;
        }

        std::size_t joint_offset(const Articulation3D& articulation) noexcept
        {
            return articulation.has_floating_base() ? 6 : 0;
        }

        TaskDiagnostic3D
        frame_diagnostic(Articulation3DDiagnostic diagnostic) noexcept
        {
            if (diagnostic == Articulation3DDiagnostic::InvalidLink)
            {
                return TaskDiagnostic3D::InvalidLink;
            }
            return diagnostic == Articulation3DDiagnostic::None
                       ? TaskDiagnostic3D::None
                       : TaskDiagnostic3D::InvalidModel;
        }

        void write_vec3(std::vector<double>& destination,
                        std::size_t offset,
                        termin::Vec3 value) noexcept
        {
            destination[offset] = value.x;
            destination[offset + 1] = value.y;
            destination[offset + 2] = value.z;
        }

    } // namespace

    std::string_view task_diagnostic_name(TaskDiagnostic3D value) noexcept
    {
        switch (value)
        {
        case TaskDiagnostic3D::None:
            return "none";
        case TaskDiagnostic3D::InvalidContext:
            return "invalid_context";
        case TaskDiagnostic3D::InvalidModel:
            return "invalid_model";
        case TaskDiagnostic3D::InvalidLink:
            return "invalid_link";
        case TaskDiagnostic3D::InvalidJoint:
            return "invalid_joint";
        case TaskDiagnostic3D::DuplicateJoint:
            return "duplicate_joint";
        case TaskDiagnostic3D::DimensionMismatch:
            return "dimension_mismatch";
        case TaskDiagnostic3D::NonFiniteInput:
            return "non_finite_input";
        case TaskDiagnostic3D::InvalidWeight:
            return "invalid_weight";
        case TaskDiagnostic3D::InvalidGain:
            return "invalid_gain";
        case TaskDiagnostic3D::InvalidTimeStep:
            return "invalid_time_step";
        case TaskDiagnostic3D::InvalidNormal:
            return "invalid_normal";
        case TaskDiagnostic3D::UnsupportedDerivativeOrder:
            return "unsupported_derivative_order";
        case TaskDiagnostic3D::InternalFailure:
            return "internal_failure";
        }
        return "unknown";
    }

    std::size_t TaskLinearization3D::row_count() const noexcept
    {
        return target_storage.size();
    }

    qopt::ConstDenseMatrixView TaskLinearization3D::matrix() const noexcept
    {
        if (row_count() == 0 || variable_count == 0 ||
            matrix_storage.size() != row_count() * variable_count)
        {
            return {};
        }
        return qopt::ConstDenseMatrixView::row_major(
            matrix_storage.data(), row_count(), variable_count);
    }

    qopt::ConstDenseVectorView TaskLinearization3D::target() const noexcept
    {
        return {target_storage.data(), target_storage.size(), 1};
    }

    qopt::ConstDenseMatrixView TaskLinearization3D::weight() const noexcept
    {
        const std::size_t rows = row_count();
        if (weight_storage.empty())
        {
            return {};
        }
        if (weight_storage.size() != rows * rows)
        {
            return {};
        }
        return qopt::ConstDenseMatrixView::row_major(
            weight_storage.data(), rows, rows);
    }

    bool TaskLinearization3DResult::ok() const noexcept
    {
        return diagnostic == TaskDiagnostic3D::None;
    }

    PointVelocityTask3D::PointVelocityTask3D(std::size_t link_index,
                                             termin::Vec3 point_local,
                                             termin::Vec3 target_velocity_world,
                                             TaskSettings3D settings)
        : link_index_(link_index), point_local_(point_local),
          target_velocity_world_(target_velocity_world),
          settings_(std::move(settings))
    {
    }

    TaskLinearization3DResult PointVelocityTask3D::linearize(
        const TaskLinearizationContext3D& context) const noexcept
    {
        const TaskDiagnostic3D context_diagnostic = validate_context(context);
        if (context_diagnostic != TaskDiagnostic3D::None)
        {
            return failure(context_diagnostic, settings_, "invalid context");
        }
        if (!settings_.enabled)
        {
            return {make_linearization(
                        context, settings_, TaskRelation3D::Objective, 0),
                    TaskDiagnostic3D::None};
        }
        if (context.derivative_order != TaskDerivativeOrder3D::Velocity)
        {
            return failure(TaskDiagnostic3D::UnsupportedDerivativeOrder,
                           settings_,
                           "point velocity requires velocity variables");
        }
        if (!point_local_.is_finite() || !target_velocity_world_.is_finite())
        {
            return failure(TaskDiagnostic3D::NonFiniteInput,
                           settings_,
                           "non-finite point velocity input");
        }

        try
        {
            const ArticulationPointKinematics3DResult point =
                context.articulation->point_kinematics(link_index_,
                                                       point_local_);
            if (!point.ok())
            {
                return failure(frame_diagnostic(point.diagnostic),
                               settings_,
                               "point kinematics unavailable");
            }
            TaskLinearization3D value = make_linearization(
                context, settings_, TaskRelation3D::Objective, 3);
            value.matrix_storage = point.value.linear_jacobian_world_storage;
            write_vec3(value.target_storage, 0, target_velocity_world_);
            const TaskDiagnostic3D weight = apply_weight(value, settings_);
            if (weight != TaskDiagnostic3D::None)
            {
                return failure(weight, settings_, "invalid objective weight");
            }
            return {std::move(value), TaskDiagnostic3D::None};
        }
        catch (const std::exception& error)
        {
            std::fprintf(stderr,
                         "[termin-robotics] point velocity task failed: %s\n",
                         error.what());
        }
        catch (...)
        {
            std::fprintf(stderr,
                         "[termin-robotics] point velocity task failed with "
                         "an unknown exception\n");
        }
        return failure(TaskDiagnostic3D::InternalFailure,
                       settings_,
                       "point velocity linearization failed");
    }

    PoseTrackingTask3D::PoseTrackingTask3D(std::size_t link_index,
                                           termin::Pose3 target_pose_world,
                                           termin::Screw3 target_velocity_world,
                                           double linear_gain,
                                           double angular_gain,
                                           TaskSettings3D settings)
        : link_index_(link_index), target_pose_world_(target_pose_world),
          target_velocity_world_(target_velocity_world),
          linear_gain_(linear_gain), angular_gain_(angular_gain),
          settings_(std::move(settings))
    {
    }

    TaskLinearization3DResult PoseTrackingTask3D::linearize(
        const TaskLinearizationContext3D& context) const noexcept
    {
        const TaskDiagnostic3D context_diagnostic = validate_context(context);
        if (context_diagnostic != TaskDiagnostic3D::None)
        {
            return failure(context_diagnostic, settings_, "invalid context");
        }
        if (!settings_.enabled)
        {
            return {make_linearization(
                        context, settings_, TaskRelation3D::Objective, 0),
                    TaskDiagnostic3D::None};
        }
        if (context.derivative_order != TaskDerivativeOrder3D::Velocity)
        {
            return failure(TaskDiagnostic3D::UnsupportedDerivativeOrder,
                           settings_,
                           "pose tracking requires velocity variables");
        }
        if (!target_pose_world_.is_finite() ||
            target_pose_world_.ang.norm() <= 1e-12 ||
            !target_velocity_world_.is_finite())
        {
            return failure(TaskDiagnostic3D::NonFiniteInput,
                           settings_,
                           "non-finite pose target");
        }
        if (!std::isfinite(linear_gain_) || linear_gain_ < 0.0 ||
            !std::isfinite(angular_gain_) || angular_gain_ < 0.0)
        {
            return failure(
                TaskDiagnostic3D::InvalidGain, settings_, "invalid pose gain");
        }

        try
        {
            const ArticulationFrameKinematics3DResult frame =
                context.articulation->frame_kinematics(link_index_);
            if (!frame.ok())
            {
                return failure(frame_diagnostic(frame.diagnostic),
                               settings_,
                               "frame kinematics unavailable");
            }
            const termin::Pose3 error_pose =
                frame.value.pose_world.inverse() * target_pose_world_;
            const termin::Screw3 error_world =
                termin::se3_log(error_pose)
                    .rotated_by(frame.value.pose_world.ang);
            const termin::Screw3 desired{
                target_velocity_world_.ang + error_world.ang * angular_gain_,
                target_velocity_world_.lin + error_world.lin * linear_gain_,
            };

            TaskLinearization3D value = make_linearization(
                context, settings_, TaskRelation3D::Objective, 6);
            value.matrix_storage = frame.value.spatial_jacobian_world_storage;
            write_vec3(value.target_storage, 0, desired.lin);
            write_vec3(value.target_storage, 3, desired.ang);
            const TaskDiagnostic3D weight = apply_weight(value, settings_);
            if (weight != TaskDiagnostic3D::None)
            {
                return failure(weight, settings_, "invalid objective weight");
            }
            return {std::move(value), TaskDiagnostic3D::None};
        }
        catch (const std::exception& error)
        {
            std::fprintf(stderr,
                         "[termin-robotics] pose task failed: %s\n",
                         error.what());
        }
        catch (...)
        {
            std::fprintf(stderr,
                         "[termin-robotics] pose task failed with an unknown "
                         "exception\n");
        }
        return failure(TaskDiagnostic3D::InternalFailure,
                       settings_,
                       "pose linearization failed");
    }

    JointPositionTask3D::JointPositionTask3D(
        std::vector<std::size_t> joint_indices,
        std::vector<double> target_positions,
        double gain,
        std::vector<double> feedforward_velocities,
        TaskSettings3D settings)
        : joint_indices_(std::move(joint_indices)),
          target_positions_(std::move(target_positions)), gain_(gain),
          feedforward_velocities_(std::move(feedforward_velocities)),
          settings_(std::move(settings))
    {
    }

    TaskLinearization3DResult JointPositionTask3D::linearize(
        const TaskLinearizationContext3D& context) const noexcept
    {
        const TaskDiagnostic3D context_diagnostic = validate_context(context);
        if (context_diagnostic != TaskDiagnostic3D::None)
        {
            return failure(context_diagnostic, settings_, "invalid context");
        }
        if (!settings_.enabled)
        {
            return {make_linearization(
                        context, settings_, TaskRelation3D::Objective, 0),
                    TaskDiagnostic3D::None};
        }
        if (context.derivative_order != TaskDerivativeOrder3D::Velocity)
        {
            return failure(TaskDiagnostic3D::UnsupportedDerivativeOrder,
                           settings_,
                           "joint position requires velocity variables");
        }
        if (!std::isfinite(gain_) || gain_ < 0.0)
        {
            return failure(TaskDiagnostic3D::InvalidGain,
                           settings_,
                           "invalid joint position gain");
        }
        if (!finite(target_positions_) || !finite(feedforward_velocities_))
        {
            return failure(TaskDiagnostic3D::NonFiniteInput,
                           settings_,
                           "non-finite joint position target");
        }

        try
        {
            const std::vector<std::size_t> joints =
                resolve_joints(*context.articulation, joint_indices_);
            const TaskDiagnostic3D joints_diagnostic =
                validate_joints(*context.articulation, joints);
            if (joints_diagnostic != TaskDiagnostic3D::None)
            {
                return failure(
                    joints_diagnostic, settings_, "invalid joint selection");
            }
            if (target_positions_.size() != joints.size() ||
                (!feedforward_velocities_.empty() &&
                 feedforward_velocities_.size() != joints.size()))
            {
                return failure(TaskDiagnostic3D::DimensionMismatch,
                               settings_,
                               "joint target size mismatch");
            }

            TaskLinearization3D value = make_linearization(
                context, settings_, TaskRelation3D::Objective, joints.size());
            const std::size_t offset = joint_offset(*context.articulation);
            for (std::size_t row = 0; row < joints.size(); ++row)
            {
                value.matrix_storage[row * value.variable_count + offset +
                                     joints[row]] = 1.0;
                const double feedforward = feedforward_velocities_.empty()
                                               ? 0.0
                                               : feedforward_velocities_[row];
                value.target_storage[row] =
                    feedforward + gain_ * (target_positions_[row] -
                                           context.articulation->state()
                                               .coordinates[joints[row]]);
            }
            const TaskDiagnostic3D weight = apply_weight(value, settings_);
            if (weight != TaskDiagnostic3D::None)
            {
                return failure(weight, settings_, "invalid objective weight");
            }
            return {std::move(value), TaskDiagnostic3D::None};
        }
        catch (const std::exception& error)
        {
            std::fprintf(stderr,
                         "[termin-robotics] joint position task failed: %s\n",
                         error.what());
        }
        catch (...)
        {
            std::fprintf(stderr,
                         "[termin-robotics] joint position task failed with "
                         "an unknown exception\n");
        }
        return failure(TaskDiagnostic3D::InternalFailure,
                       settings_,
                       "joint position linearization failed");
    }

    JointVelocityTask3D::JointVelocityTask3D(
        std::vector<std::size_t> joint_indices,
        std::vector<double> target_velocities,
        double acceleration_gain,
        TaskSettings3D settings)
        : joint_indices_(std::move(joint_indices)),
          target_velocities_(std::move(target_velocities)),
          acceleration_gain_(acceleration_gain), settings_(std::move(settings))
    {
    }

    TaskLinearization3DResult JointVelocityTask3D::linearize(
        const TaskLinearizationContext3D& context) const noexcept
    {
        const TaskDiagnostic3D context_diagnostic = validate_context(context);
        if (context_diagnostic != TaskDiagnostic3D::None)
        {
            return failure(context_diagnostic, settings_, "invalid context");
        }
        if (!settings_.enabled)
        {
            return {make_linearization(
                        context, settings_, TaskRelation3D::Objective, 0),
                    TaskDiagnostic3D::None};
        }
        if (!std::isfinite(acceleration_gain_) || acceleration_gain_ < 0.0)
        {
            return failure(TaskDiagnostic3D::InvalidGain,
                           settings_,
                           "invalid velocity tracking gain");
        }
        if (!finite(target_velocities_))
        {
            return failure(TaskDiagnostic3D::NonFiniteInput,
                           settings_,
                           "non-finite joint velocity target");
        }

        try
        {
            const std::vector<std::size_t> joints =
                resolve_joints(*context.articulation, joint_indices_);
            const TaskDiagnostic3D joints_diagnostic =
                validate_joints(*context.articulation, joints);
            if (joints_diagnostic != TaskDiagnostic3D::None)
            {
                return failure(
                    joints_diagnostic, settings_, "invalid joint selection");
            }
            if (target_velocities_.size() != joints.size())
            {
                return failure(TaskDiagnostic3D::DimensionMismatch,
                               settings_,
                               "joint target size mismatch");
            }

            TaskLinearization3D value = make_linearization(
                context, settings_, TaskRelation3D::Objective, joints.size());
            const std::size_t offset = joint_offset(*context.articulation);
            for (std::size_t row = 0; row < joints.size(); ++row)
            {
                value.matrix_storage[row * value.variable_count + offset +
                                     joints[row]] = 1.0;
                value.target_storage[row] =
                    context.derivative_order == TaskDerivativeOrder3D::Velocity
                        ? target_velocities_[row]
                        : acceleration_gain_ * (target_velocities_[row] -
                                                context.articulation->state()
                                                    .velocities[joints[row]]);
            }
            const TaskDiagnostic3D weight = apply_weight(value, settings_);
            if (weight != TaskDiagnostic3D::None)
            {
                return failure(weight, settings_, "invalid objective weight");
            }
            return {std::move(value), TaskDiagnostic3D::None};
        }
        catch (const std::exception& error)
        {
            std::fprintf(stderr,
                         "[termin-robotics] joint velocity task failed: %s\n",
                         error.what());
        }
        catch (...)
        {
            std::fprintf(stderr,
                         "[termin-robotics] joint velocity task failed with "
                         "an unknown exception\n");
        }
        return failure(TaskDiagnostic3D::InternalFailure,
                       settings_,
                       "joint velocity linearization failed");
    }

    JointLimitConstraint3D::JointLimitConstraint3D(TaskSettings3D settings)
        : settings_(std::move(settings))
    {
    }

    TaskLinearization3DResult JointLimitConstraint3D::linearize(
        const TaskLinearizationContext3D& context) const noexcept
    {
        const TaskDiagnostic3D context_diagnostic = validate_context(context);
        if (context_diagnostic != TaskDiagnostic3D::None)
        {
            return failure(context_diagnostic, settings_, "invalid context");
        }
        if (!settings_.enabled)
        {
            return {make_linearization(
                        context, settings_, TaskRelation3D::Inequality, 0),
                    TaskDiagnostic3D::None};
        }
        if (!std::isfinite(context.time_step) || context.time_step <= 0.0)
        {
            return failure(TaskDiagnostic3D::InvalidTimeStep,
                           settings_,
                           "joint limits require a positive time step");
        }

        try
        {
            std::size_t rows = 0;
            for (const ArticulationLink3D& link : context.articulation->links())
            {
                rows += link.limits.maximum.has_value() ? 1 : 0;
                rows += link.limits.minimum.has_value() ? 1 : 0;
            }
            TaskLinearization3D value = make_linearization(
                context, settings_, TaskRelation3D::Inequality, rows);
            const std::size_t offset = joint_offset(*context.articulation);
            std::size_t row = 0;
            for (std::size_t joint = 0;
                 joint < context.articulation->link_count();
                 ++joint)
            {
                const ArticulationJointLimits3D& limits =
                    context.articulation->links()[joint].limits;
                const double coordinate =
                    context.articulation->state().coordinates[joint];
                const double velocity =
                    context.articulation->state().velocities[joint];
                const bool acceleration = context.derivative_order ==
                                          TaskDerivativeOrder3D::Acceleration;
                const double coefficient =
                    acceleration ? 0.5 * context.time_step * context.time_step
                                 : context.time_step;
                const double drift =
                    acceleration ? context.time_step * velocity : 0.0;

                if (limits.maximum.has_value())
                {
                    value.matrix_storage[row * value.variable_count + offset +
                                         joint] = coefficient;
                    value.target_storage[row] =
                        *limits.maximum - coordinate - drift;
                    ++row;
                }
                if (limits.minimum.has_value())
                {
                    value.matrix_storage[row * value.variable_count + offset +
                                         joint] = -coefficient;
                    value.target_storage[row] =
                        coordinate - *limits.minimum + drift;
                    ++row;
                }
            }
            return {std::move(value), TaskDiagnostic3D::None};
        }
        catch (const std::exception& error)
        {
            std::fprintf(stderr,
                         "[termin-robotics] joint limit task failed: %s\n",
                         error.what());
        }
        catch (...)
        {
            std::fprintf(stderr,
                         "[termin-robotics] joint limit task failed with an "
                         "unknown exception\n");
        }
        return failure(TaskDiagnostic3D::InternalFailure,
                       settings_,
                       "joint limit linearization failed");
    }

    PointAvoidanceConstraint3D::PointAvoidanceConstraint3D(
        std::size_t link_index,
        termin::Vec3 point_local,
        termin::Vec3 normal_world,
        double signed_distance,
        double minimum_distance,
        double horizon,
        TaskSettings3D settings)
        : link_index_(link_index), point_local_(point_local),
          normal_world_(normal_world), signed_distance_(signed_distance),
          minimum_distance_(minimum_distance), horizon_(horizon),
          settings_(std::move(settings))
    {
    }

    TaskLinearization3DResult PointAvoidanceConstraint3D::linearize(
        const TaskLinearizationContext3D& context) const noexcept
    {
        const TaskDiagnostic3D context_diagnostic = validate_context(context);
        if (context_diagnostic != TaskDiagnostic3D::None)
        {
            return failure(context_diagnostic, settings_, "invalid context");
        }
        if (!settings_.enabled)
        {
            return {make_linearization(
                        context, settings_, TaskRelation3D::Inequality, 0),
                    TaskDiagnostic3D::None};
        }
        if (context.derivative_order != TaskDerivativeOrder3D::Velocity)
        {
            return failure(TaskDiagnostic3D::UnsupportedDerivativeOrder,
                           settings_,
                           "avoidance requires velocity variables");
        }
        if (!point_local_.is_finite() || !normal_world_.is_finite() ||
            !std::isfinite(signed_distance_) ||
            !std::isfinite(minimum_distance_) || !std::isfinite(horizon_) ||
            horizon_ <= 0.0)
        {
            return failure(TaskDiagnostic3D::NonFiniteInput,
                           settings_,
                           "invalid avoidance input");
        }
        const double normal_length = normal_world_.norm();
        if (!std::isfinite(normal_length) || normal_length <= 1e-12)
        {
            return failure(TaskDiagnostic3D::InvalidNormal,
                           settings_,
                           "avoidance normal has no direction");
        }

        try
        {
            const ArticulationPointKinematics3DResult point =
                context.articulation->point_kinematics(link_index_,
                                                       point_local_);
            if (!point.ok())
            {
                return failure(frame_diagnostic(point.diagnostic),
                               settings_,
                               "point kinematics unavailable");
            }
            const termin::Vec3 normal = normal_world_ / normal_length;
            const qopt::ConstDenseMatrixView jacobian =
                point.value.linear_jacobian_world();
            TaskLinearization3D value = make_linearization(
                context, settings_, TaskRelation3D::Inequality, 1);
            for (std::size_t column = 0; column < value.variable_count;
                 ++column)
            {
                value.matrix_storage[column] =
                    -(normal.x * jacobian(0, column) +
                      normal.y * jacobian(1, column) +
                      normal.z * jacobian(2, column));
            }
            value.target_storage[0] =
                (signed_distance_ - minimum_distance_) / horizon_;
            return {std::move(value), TaskDiagnostic3D::None};
        }
        catch (const std::exception& error)
        {
            std::fprintf(stderr,
                         "[termin-robotics] avoidance task failed: %s\n",
                         error.what());
        }
        catch (...)
        {
            std::fprintf(stderr,
                         "[termin-robotics] avoidance task failed with an "
                         "unknown exception\n");
        }
        return failure(TaskDiagnostic3D::InternalFailure,
                       settings_,
                       "avoidance linearization failed");
    }

} // namespace termin::robotics
