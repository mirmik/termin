#include <termin/robotics/articulation3d.hpp>

#include <termin/geom/se3.hpp>

#include <algorithm>
#include <array>
#include <cmath>
#include <cstdio>
#include <exception>
#include <limits>
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

        qopt::ConstDenseMatrixView
        matrix_view(const std::vector<double>& values,
                    std::size_t size) noexcept
        {
            return qopt::ConstDenseMatrixView::row_major(
                values.data(), size, size);
        }

        qopt::ConstDenseVectorView
        vector_view(const std::vector<double>& values) noexcept
        {
            return {values.data(), values.size(), 1};
        }

        termin::Screw3 read_screw_vw(const std::vector<double>& values,
                                     std::size_t offset = 0) noexcept
        {
            return {
                {values[offset + 3], values[offset + 4], values[offset + 5]},
                {values[offset], values[offset + 1], values[offset + 2]},
            };
        }

        void write_screw_vw(termin::Screw3 value,
                            std::vector<double>& destination,
                            std::size_t offset = 0) noexcept
        {
            destination[offset] = value.lin.x;
            destination[offset + 1] = value.lin.y;
            destination[offset + 2] = value.lin.z;
            destination[offset + 3] = value.ang.x;
            destination[offset + 4] = value.ang.y;
            destination[offset + 5] = value.ang.z;
        }

        termin::Screw3 basis_screw_vw(std::size_t column) noexcept
        {
            switch (column)
            {
            case 0:
                return {termin::Vec3::zero(), termin::Vec3::unit_x()};
            case 1:
                return {termin::Vec3::zero(), termin::Vec3::unit_y()};
            case 2:
                return {termin::Vec3::zero(), termin::Vec3::unit_z()};
            case 3:
                return {termin::Vec3::unit_x(), termin::Vec3::zero()};
            case 4:
                return {termin::Vec3::unit_y(), termin::Vec3::zero()};
            default:
                return {termin::Vec3::unit_z(), termin::Vec3::zero()};
            }
        }

    } // namespace

    std::string_view
    articulation3d_diagnostic_name(Articulation3DDiagnostic value) noexcept
    {
        switch (value)
        {
        case Articulation3DDiagnostic::None:
            return "none";
        case Articulation3DDiagnostic::EmptyModel:
            return "empty_model";
        case Articulation3DDiagnostic::InvalidParent:
            return "invalid_parent";
        case Articulation3DDiagnostic::InvalidPose:
            return "invalid_pose";
        case Articulation3DDiagnostic::InvalidMotionTwist:
            return "invalid_motion_twist";
        case Articulation3DDiagnostic::InvalidInertia:
            return "invalid_inertia";
        case Articulation3DDiagnostic::InvalidState:
            return "invalid_state";
        case Articulation3DDiagnostic::InvalidUnitLimits:
            return "invalid_unit_limits";
        case Articulation3DDiagnostic::NonFiniteInput:
            return "non_finite_input";
        case Articulation3DDiagnostic::InvalidModel:
            return "invalid_model";
        case Articulation3DDiagnostic::InvalidUnit:
            return "invalid_unit";
        case Articulation3DDiagnostic::NonFinitePoint:
            return "non_finite_point";
        case Articulation3DDiagnostic::InternalFailure:
            return "internal_failure";
        }
        return "unknown";
    }

    std::size_t ArticulationPointKinematics3D::dof_count() const noexcept
    {
        return linear_jacobian_world_storage.size() / 3;
    }

    qopt::ConstDenseMatrixView
    ArticulationPointKinematics3D::linear_jacobian_world() const noexcept
    {
        const std::size_t columns = dof_count();
        if (columns == 0 || linear_jacobian_world_storage.size() != 3 * columns)
        {
            return {};
        }
        return qopt::ConstDenseMatrixView::row_major(
            linear_jacobian_world_storage.data(), 3, columns);
    }

    bool ArticulationPointKinematics3DResult::ok() const noexcept
    {
        return diagnostic == Articulation3DDiagnostic::None;
    }

    std::size_t ArticulationFrameKinematics3D::dof_count() const noexcept
    {
        return spatial_jacobian_world_storage.size() / 6;
    }

    qopt::ConstDenseMatrixView
    ArticulationFrameKinematics3D::spatial_jacobian_world() const noexcept
    {
        const std::size_t columns = dof_count();
        if (columns == 0 ||
            spatial_jacobian_world_storage.size() != 6 * columns)
        {
            return {};
        }
        return qopt::ConstDenseMatrixView::row_major(
            spatial_jacobian_world_storage.data(), 6, columns);
    }

    bool ArticulationFrameKinematics3DResult::ok() const noexcept
    {
        return diagnostic == Articulation3DDiagnostic::None;
    }

    Articulation3D::Articulation3D(std::vector<ArticulationUnit3D> units,
                                   Articulation3DState initial_state,
                                   std::string_view diagnostic_name)
        : units_(std::move(units)), state_(std::move(initial_state)),
          diagnostic_name_(diagnostic_name)
    {
        parent_to_unit_.resize(units_.size());
        unit_poses_world_.resize(units_.size());
        motion_twists_at_unit_.resize(units_.size());
        unit_velocities_local_.resize(units_.size());
        diagnostic_ = validate_model();
        if (diagnostic_ == Articulation3DDiagnostic::None &&
            !update_kinematics())
        {
            diagnostic_ = Articulation3DDiagnostic::NonFiniteInput;
        }
    }

    Articulation3D::Articulation3D(ArticulationFloatingBase3D floating_base,
                                   std::vector<ArticulationUnit3D> units,
                                   Articulation3DState initial_state,
                                   std::string_view diagnostic_name)
        : Articulation3D(
              std::move(units), std::move(initial_state), diagnostic_name)
    {
        floating_base_ = std::move(floating_base);
        diagnostic_ = validate_model();
        if (diagnostic_ == Articulation3DDiagnostic::None &&
            !update_kinematics())
        {
            diagnostic_ = Articulation3DDiagnostic::NonFiniteInput;
        }
    }

    Articulation3DDiagnostic Articulation3D::validate_model() const noexcept
    {
        if (units_.empty() && !floating_base_.has_value())
        {
            return Articulation3DDiagnostic::EmptyModel;
        }
        if (state_.coordinates.size() != units_.size() ||
            state_.velocities.size() != units_.size() ||
            !finite(state_.coordinates) || !finite(state_.velocities))
        {
            return Articulation3DDiagnostic::InvalidState;
        }
        if (floating_base_.has_value() &&
            (!floating_base_->inertia.is_valid() ||
             !floating_base_->pose_world.is_finite() ||
             floating_base_->pose_world.ang.norm() <= 1e-10 ||
             !floating_base_->velocity_local.is_finite()))
        {
            return !floating_base_->inertia.is_valid()
                       ? Articulation3DDiagnostic::InvalidInertia
                       : Articulation3DDiagnostic::InvalidState;
        }
        for (std::size_t index = 0; index < units_.size(); ++index)
        {
            const ArticulationUnit3D& unit = units_[index];
            if (unit.parent_unit != articulation_root_frame &&
                unit.parent_unit >= index)
            {
                return Articulation3DDiagnostic::InvalidParent;
            }
            if (!unit.parent_to_unit_zero.is_finite() ||
                unit.parent_to_unit_zero.ang.norm() <= 1e-10)
            {
                return Articulation3DDiagnostic::InvalidPose;
            }
            if (!unit.motion_twist_at_unit.is_finite() ||
                unit.motion_twist_at_unit.dot(unit.motion_twist_at_unit) <=
                    1e-20)
            {
                return Articulation3DDiagnostic::InvalidMotionTwist;
            }
            if (!unit.inertia.is_valid())
            {
                return Articulation3DDiagnostic::InvalidInertia;
            }
            if ((unit.limits.minimum.has_value() &&
                 !std::isfinite(*unit.limits.minimum)) ||
                (unit.limits.maximum.has_value() &&
                 !std::isfinite(*unit.limits.maximum)) ||
                (unit.limits.minimum.has_value() &&
                 unit.limits.maximum.has_value() &&
                 *unit.limits.minimum > *unit.limits.maximum))
            {
                return Articulation3DDiagnostic::InvalidUnitLimits;
            }
        }
        return Articulation3DDiagnostic::None;
    }

    Articulation3DDiagnostic Articulation3D::diagnostic() const noexcept
    {
        return diagnostic_;
    }

    std::string_view Articulation3D::diagnostic_name() const noexcept
    {
        return diagnostic_name_;
    }

    std::size_t Articulation3D::unit_count() const noexcept
    {
        return units_.size();
    }

    std::size_t Articulation3D::dof_count() const noexcept
    {
        return units_.size() + (floating_base_.has_value() ? 6 : 0);
    }

    const std::vector<ArticulationUnit3D>&
    Articulation3D::units() const noexcept
    {
        return units_;
    }

    const Articulation3DState& Articulation3D::state() const noexcept
    {
        return state_;
    }

    bool Articulation3D::has_floating_base() const noexcept
    {
        return floating_base_.has_value();
    }

    const std::optional<ArticulationFloatingBase3D>&
    Articulation3D::floating_base() const noexcept
    {
        return floating_base_;
    }

    const std::vector<termin::Pose3>&
    Articulation3D::unit_poses_world() const noexcept
    {
        return unit_poses_world_;
    }

    const std::vector<termin::Screw3>&
    Articulation3D::unit_velocities_local() const noexcept
    {
        return unit_velocities_local_;
    }

    ArticulationFrameKinematics3DResult
    Articulation3D::floating_base_frame_kinematics() const noexcept
    {
        if (diagnostic_ != Articulation3DDiagnostic::None ||
            !floating_base_.has_value())
        {
            std::fprintf(stderr,
                         "[termin-robotics] articulation '%s' has no valid "
                         "floating base frame\n",
                         diagnostic_name_.c_str());
            return {{}, Articulation3DDiagnostic::InvalidModel};
        }

        try
        {
            ArticulationFrameKinematics3D value;
            value.pose_world = floating_base_->pose_world;
            value.velocity_world = floating_base_->velocity_local.rotated_by(
                floating_base_->pose_world.ang);
            value.bias_acceleration_world = {
                termin::Vec3::zero(),
                floating_base_->pose_world.transform_vector(
                    floating_base_->velocity_local.ang.cross(
                        floating_base_->velocity_local.lin)),
            };
            const std::size_t generalized_count = dof_count();
            value.spatial_jacobian_world_storage.assign(6 * generalized_count,
                                                        0.0);
            for (std::size_t column = 0; column < 6; ++column)
            {
                std::vector<double> unit(6, 0.0);
                unit[column] = 1.0;
                const termin::Screw3 response = read_screw_vw(unit).rotated_by(
                    floating_base_->pose_world.ang);
                value.spatial_jacobian_world_storage[column] = response.lin.x;
                value.spatial_jacobian_world_storage[generalized_count +
                                                     column] = response.lin.y;
                value.spatial_jacobian_world_storage[2 * generalized_count +
                                                     column] = response.lin.z;
                value.spatial_jacobian_world_storage[3 * generalized_count +
                                                     column] = response.ang.x;
                value.spatial_jacobian_world_storage[4 * generalized_count +
                                                     column] = response.ang.y;
                value.spatial_jacobian_world_storage[5 * generalized_count +
                                                     column] = response.ang.z;
            }
            return {std::move(value), Articulation3DDiagnostic::None};
        }
        catch (const std::exception& error)
        {
            std::fprintf(stderr,
                         "[termin-robotics] floating-base frame kinematics "
                         "failed: %s\n",
                         error.what());
        }
        catch (...)
        {
            std::fprintf(stderr,
                         "[termin-robotics] floating-base frame kinematics "
                         "failed with an unknown exception\n");
        }
        return {{}, Articulation3DDiagnostic::InternalFailure};
    }

    ArticulationFrameKinematics3DResult
    Articulation3D::frame_kinematics(std::size_t unit_index) const noexcept
    {
        if (diagnostic_ != Articulation3DDiagnostic::None ||
            unit_poses_world_.size() != units_.size() ||
            parent_to_unit_.size() != units_.size() ||
            motion_twists_at_unit_.size() != units_.size() ||
            unit_velocities_local_.size() != units_.size())
        {
            std::fprintf(stderr,
                         "[termin-robotics] cannot query frame kinematics of "
                         "invalid articulation '%s'\n",
                         diagnostic_name_.c_str());
            return {{}, Articulation3DDiagnostic::InvalidModel};
        }
        if (unit_index >= units_.size())
        {
            std::fprintf(stderr,
                         "[termin-robotics] articulation frame references "
                         "invalid unit %zu\n",
                         unit_index);
            return {{}, Articulation3DDiagnostic::InvalidUnit};
        }

        try
        {
            ArticulationFrameKinematics3D value;
            value.pose_world = unit_poses_world_[unit_index];
            value.velocity_world =
                unit_velocities_local_[unit_index].rotated_by(
                    value.pose_world.ang);
            std::vector<termin::Screw3> bias_local;
            if (!bias_accelerations_local(bias_local))
            {
                return {{}, Articulation3DDiagnostic::InvalidModel};
            }
            const termin::Screw3& velocity_local =
                unit_velocities_local_[unit_index];
            const termin::Screw3& acceleration_local = bias_local[unit_index];
            value.bias_acceleration_world = {
                value.pose_world.transform_vector(acceleration_local.ang),
                value.pose_world.transform_vector(
                    acceleration_local.lin +
                    velocity_local.ang.cross(velocity_local.lin)),
            };
            const std::size_t generalized_count = dof_count();
            const std::size_t unit_offset = floating_base_.has_value() ? 6 : 0;
            value.spatial_jacobian_world_storage.assign(6 * generalized_count,
                                                        0.0);

            std::vector<termin::Screw3> unit_velocities(unit_index + 1);
            for (std::size_t column = 0; column < generalized_count; ++column)
            {
                termin::Screw3 base_velocity = termin::Screw3::zero();
                if (floating_base_.has_value() && column < 6)
                {
                    std::vector<double> unit_base(6, 0.0);
                    unit_base[column] = 1.0;
                    base_velocity = read_screw_vw(unit_base);
                }
                for (std::size_t index = 0; index <= unit_index; ++index)
                {
                    const std::size_t parent = units_[index].parent_unit;
                    const termin::Screw3 parent_velocity =
                        parent == articulation_root_frame
                            ? base_velocity
                            : unit_velocities[parent];
                    unit_velocities[index] =
                        parent_velocity.adjoint_inv(parent_to_unit_[index]);
                    if (column >= unit_offset && index == column - unit_offset)
                    {
                        unit_velocities[index] += motion_twists_at_unit_[index];
                    }
                }

                const termin::Screw3 response =
                    unit_velocities[unit_index].rotated_by(
                        value.pose_world.ang);
                value.spatial_jacobian_world_storage[column] = response.lin.x;
                value.spatial_jacobian_world_storage[generalized_count +
                                                     column] = response.lin.y;
                value.spatial_jacobian_world_storage[2 * generalized_count +
                                                     column] = response.lin.z;
                value.spatial_jacobian_world_storage[3 * generalized_count +
                                                     column] = response.ang.x;
                value.spatial_jacobian_world_storage[4 * generalized_count +
                                                     column] = response.ang.y;
                value.spatial_jacobian_world_storage[5 * generalized_count +
                                                     column] = response.ang.z;
            }
            return {std::move(value), Articulation3DDiagnostic::None};
        }
        catch (const std::exception& error)
        {
            std::fprintf(stderr,
                         "[termin-robotics] frame kinematics failed: %s\n",
                         error.what());
        }
        catch (...)
        {
            std::fprintf(stderr,
                         "[termin-robotics] frame kinematics failed with an "
                         "unknown exception\n");
        }
        return {{}, Articulation3DDiagnostic::InternalFailure};
    }

    ArticulationPointKinematics3DResult
    Articulation3D::floating_base_point_kinematics(
        termin::Vec3 point_local) const noexcept
    {
        if (diagnostic_ != Articulation3DDiagnostic::None ||
            !floating_base_.has_value())
        {
            std::fprintf(
                stderr,
                "[termin-robotics] articulation '%s' has no valid floating "
                "base point\n",
                diagnostic_name_.c_str());
            return {{}, Articulation3DDiagnostic::InvalidModel};
        }
        if (!point_local.is_finite())
        {
            std::fprintf(
                stderr,
                "[termin-robotics] rejected non-finite floating-base point\n");
            return {{}, Articulation3DDiagnostic::NonFinitePoint};
        }

        try
        {
            ArticulationPointKinematics3D value;
            value.position_world =
                floating_base_->pose_world.transform_point(point_local);
            value.velocity_world =
                floating_base_->velocity_local.velocity_at_offset(point_local)
                    .rotated_by(floating_base_->pose_world.ang)
                    .lin;
            const termin::Screw3 point_velocity_local =
                floating_base_->velocity_local.velocity_at_offset(point_local);
            value.bias_acceleration_world =
                floating_base_->pose_world.transform_vector(
                    floating_base_->velocity_local.ang.cross(
                        point_velocity_local.lin));
            const std::size_t generalized_count = dof_count();
            value.linear_jacobian_world_storage.assign(3 * generalized_count,
                                                       0.0);
            for (std::size_t column = 0; column < 6; ++column)
            {
                std::vector<double> unit(6, 0.0);
                unit[column] = 1.0;
                const termin::Vec3 response =
                    read_screw_vw(unit)
                        .velocity_at_offset(point_local)
                        .rotated_by(floating_base_->pose_world.ang)
                        .lin;
                value.linear_jacobian_world_storage[column] = response.x;
                value
                    .linear_jacobian_world_storage[generalized_count + column] =
                    response.y;
                value.linear_jacobian_world_storage[2 * generalized_count +
                                                    column] = response.z;
            }
            return {std::move(value), Articulation3DDiagnostic::None};
        }
        catch (const std::exception& error)
        {
            std::fprintf(
                stderr,
                "[termin-robotics] floating-base point kinematics failed: %s\n",
                error.what());
        }
        catch (...)
        {
            std::fprintf(
                stderr,
                "[termin-robotics] floating-base point kinematics failed "
                "with an unknown exception\n");
        }
        return {{}, Articulation3DDiagnostic::InternalFailure};
    }

    ArticulationPointKinematics3DResult
    Articulation3D::point_kinematics(std::size_t unit_index,
                                     termin::Vec3 point_local) const noexcept
    {
        if (diagnostic_ != Articulation3DDiagnostic::None ||
            unit_poses_world_.size() != units_.size() ||
            parent_to_unit_.size() != units_.size() ||
            motion_twists_at_unit_.size() != units_.size() ||
            unit_velocities_local_.size() != units_.size())
        {
            std::fprintf(
                stderr,
                "[termin-robotics] cannot query point kinematics of invalid "
                "articulation '%s'\n",
                diagnostic_name_.c_str());
            return {{}, Articulation3DDiagnostic::InvalidModel};
        }
        if (unit_index >= units_.size())
        {
            std::fprintf(
                stderr,
                "[termin-robotics] articulation point references invalid unit "
                "%zu\n",
                unit_index);
            return {{}, Articulation3DDiagnostic::InvalidUnit};
        }
        if (!point_local.is_finite())
        {
            std::fprintf(
                stderr,
                "[termin-robotics] rejected non-finite articulation point\n");
            return {{}, Articulation3DDiagnostic::NonFinitePoint};
        }

        try
        {
            ArticulationPointKinematics3D value;
            value.position_world =
                unit_poses_world_[unit_index].transform_point(point_local);
            value.velocity_world =
                unit_velocities_local_[unit_index]
                    .velocity_at_offset(point_local)
                    .rotated_by(unit_poses_world_[unit_index].ang)
                    .lin;
            std::vector<std::size_t> ancestry;
            for (std::size_t current = unit_index;;)
            {
                ancestry.push_back(current);
                const std::size_t parent = units_[current].parent_unit;
                if (parent == articulation_root_frame)
                {
                    break;
                }
                current = parent;
            }
            std::reverse(ancestry.begin(), ancestry.end());

            termin::Screw3 bias_local = termin::Screw3::zero();
            for (const std::size_t current : ancestry)
            {
                const termin::Screw3 unit_velocity =
                    motion_twists_at_unit_[current] *
                    state_.velocities[current];
                bias_local =
                    bias_local.adjoint_inv(parent_to_unit_[current]) +
                    unit_velocities_local_[current].cross_motion(unit_velocity);
            }
            const termin::Screw3 point_velocity_local =
                unit_velocities_local_[unit_index].velocity_at_offset(
                    point_local);
            const termin::Screw3 point_acceleration_local =
                bias_local.velocity_at_offset(point_local);
            value.bias_acceleration_world =
                unit_poses_world_[unit_index].transform_vector(
                    point_acceleration_local.lin +
                    unit_velocities_local_[unit_index].ang.cross(
                        point_velocity_local.lin));
            const std::size_t generalized_count = dof_count();
            const std::size_t unit_offset = floating_base_.has_value() ? 6 : 0;
            value.linear_jacobian_world_storage.assign(3 * generalized_count,
                                                       0.0);

            const auto write_response = [&](std::size_t column,
                                            termin::Screw3 response_twist)
            {
                const termin::Vec3 linear_response =
                    response_twist
                        .velocity_at_offset(point_local)
                        .rotated_by(unit_poses_world_[unit_index].ang)
                        .lin;
                value.linear_jacobian_world_storage[column] =
                    linear_response.x;
                value
                    .linear_jacobian_world_storage[generalized_count + column] =
                    linear_response.y;
                value.linear_jacobian_world_storage[2 * generalized_count +
                                                    column] = linear_response.z;
            };

            if (floating_base_.has_value())
            {
                for (std::size_t column = 0; column < 6; ++column)
                {
                    termin::Screw3 response = basis_screw_vw(column);
                    for (const std::size_t current : ancestry)
                    {
                        response = response.adjoint_inv(
                            parent_to_unit_[current]);
                    }
                    write_response(column, response);
                }
            }
            for (std::size_t ancestor = 0; ancestor < ancestry.size();
                 ++ancestor)
            {
                const std::size_t joint = ancestry[ancestor];
                termin::Screw3 response = motion_twists_at_unit_[joint];
                for (std::size_t descendant = ancestor + 1;
                     descendant < ancestry.size();
                     ++descendant)
                {
                    response = response.adjoint_inv(
                        parent_to_unit_[ancestry[descendant]]);
                }
                write_response(unit_offset + joint, response);
            }
            if (!value.position_world.is_finite() ||
                !value.velocity_world.is_finite())
            {
                return {{}, Articulation3DDiagnostic::InvalidModel};
            }
            return {std::move(value), Articulation3DDiagnostic::None};
        }
        catch (const std::exception& error)
        {
            std::fprintf(
                stderr,
                "[termin-robotics] articulation point kinematics failed: %s\n",
                error.what());
        }
        catch (...)
        {
            std::fprintf(
                stderr,
                "[termin-robotics] articulation point kinematics failed with "
                "an unknown exception\n");
        }
        return {{}, Articulation3DDiagnostic::InternalFailure};
    }

    Articulation3DDiagnostic
    Articulation3D::set_state(Articulation3DState value) noexcept
    {
        if (value.coordinates.size() != units_.size() ||
            value.velocities.size() != units_.size() ||
            !finite(value.coordinates) || !finite(value.velocities))
        {
            std::fprintf(
                stderr,
                "[termin-robotics] rejected invalid articulation state\n");
            return Articulation3DDiagnostic::InvalidState;
        }
        state_ = std::move(value);
        if (!update_kinematics())
        {
            return Articulation3DDiagnostic::NonFiniteInput;
        }
        return Articulation3DDiagnostic::None;
    }

    Articulation3DDiagnostic Articulation3D::set_floating_base_state(
        termin::Pose3 pose_world, termin::Screw3 velocity_local) noexcept
    {
        if (!floating_base_.has_value() || !pose_world.is_finite() ||
            pose_world.ang.norm() <= 1e-10 || !velocity_local.is_finite())
        {
            std::fprintf(
                stderr,
                "[termin-robotics] rejected invalid floating-base state\n");
            return Articulation3DDiagnostic::InvalidState;
        }
        floating_base_->pose_world = pose_world.normalized();
        floating_base_->velocity_local = velocity_local;
        return update_kinematics() ? Articulation3DDiagnostic::None
                                   : Articulation3DDiagnostic::NonFiniteInput;
    }

    bool Articulation3D::update_kinematics() noexcept
    {
        const std::size_t count = units_.size();
        if (parent_to_unit_.size() != count ||
            unit_poses_world_.size() != count ||
            motion_twists_at_unit_.size() != count ||
            unit_velocities_local_.size() != count)
        {
            return false;
        }

        for (std::size_t index = 0; index < count; ++index)
        {
            const ArticulationUnit3D& unit = units_[index];
            const termin::Pose3 unit_motion = termin::se3_exp(
                unit.motion_twist_at_unit * state_.coordinates[index]);
            parent_to_unit_[index] =
                (unit.parent_to_unit_zero * unit_motion).normalized();
            const termin::Pose3 parent_pose =
                unit.parent_unit == articulation_root_frame
                    ? (floating_base_.has_value() ? floating_base_->pose_world
                                                  : termin::Pose3::identity())
                    : unit_poses_world_[unit.parent_unit];
            unit_poses_world_[index] =
                (parent_pose * parent_to_unit_[index]).normalized();
            motion_twists_at_unit_[index] = unit.motion_twist_at_unit;

            const termin::Screw3 parent_velocity =
                unit.parent_unit == articulation_root_frame
                    ? (floating_base_.has_value()
                           ? floating_base_->velocity_local
                           : termin::Screw3::zero())
                    : unit_velocities_local_[unit.parent_unit];
            unit_velocities_local_[index] =
                parent_velocity.adjoint_inv(parent_to_unit_[index]) +
                motion_twists_at_unit_[index] * state_.velocities[index];

            if (!parent_to_unit_[index].is_finite() ||
                !unit_poses_world_[index].is_finite() ||
                !motion_twists_at_unit_[index].is_finite() ||
                !unit_velocities_local_[index].is_finite())
            {
                return false;
            }
        }
        return true;
    }

    bool Articulation3D::bias_accelerations_local(
        std::vector<termin::Screw3>& accelerations) const
    {
        if (parent_to_unit_.size() != units_.size() ||
            motion_twists_at_unit_.size() != units_.size() ||
            unit_velocities_local_.size() != units_.size())
        {
            return false;
        }
        accelerations.assign(units_.size(), termin::Screw3::zero());
        for (std::size_t index = 0; index < units_.size(); ++index)
        {
            const std::size_t parent = units_[index].parent_unit;
            const termin::Screw3 parent_acceleration =
                parent == articulation_root_frame ? termin::Screw3::zero()
                                                  : accelerations[parent];
            const termin::Screw3 unit_velocity =
                motion_twists_at_unit_[index] * state_.velocities[index];
            accelerations[index] =
                parent_acceleration.adjoint_inv(parent_to_unit_[index]) +
                unit_velocities_local_[index].cross_motion(unit_velocity);
            if (!accelerations[index].is_finite())
            {
                return false;
            }
        }
        return true;
    }

    bool
    Articulation3D::inverse_dynamics(const std::vector<double>& velocities,
                                     const std::vector<double>& accelerations,
                                     termin::Vec3 gravity_world,
                                     std::vector<double>& effort) const
    {
        const std::size_t unit_count = units_.size();
        const std::size_t count = dof_count();
        const std::size_t unit_offset = floating_base_.has_value() ? 6 : 0;
        if (velocities.size() != count || accelerations.size() != count ||
            !finite(velocities) || !finite(accelerations) ||
            !gravity_world.is_finite())
        {
            return false;
        }

        termin::Screw3 base_velocity = termin::Screw3::zero();
        termin::Screw3 base_acceleration{termin::Vec3::zero(), -gravity_world};
        termin::Screw3 base_force = termin::Screw3::zero();
        if (floating_base_.has_value())
        {
            base_velocity = read_screw_vw(velocities);
            base_acceleration =
                termin::Screw3{termin::Vec3::zero(), -gravity_world}
                    .adjoint_inv(floating_base_->pose_world) +
                read_screw_vw(accelerations);
            const termin::Screw3 momentum =
                floating_base_->inertia.momentum(base_velocity);
            base_force = floating_base_->inertia.momentum(base_acceleration) +
                         base_velocity.cross_force(momentum);
        }

        std::vector<termin::Screw3> velocities_local(unit_count);
        std::vector<termin::Screw3> accelerations_local(unit_count);
        std::vector<termin::Screw3> forces_local(unit_count);
        for (std::size_t index = 0; index < unit_count; ++index)
        {
            const ArticulationUnit3D& unit = units_[index];
            const termin::Screw3 parent_velocity =
                unit.parent_unit == articulation_root_frame
                    ? base_velocity
                    : velocities_local[unit.parent_unit];
            const termin::Screw3 parent_acceleration =
                unit.parent_unit == articulation_root_frame
                    ? base_acceleration
                    : accelerations_local[unit.parent_unit];
            const termin::Screw3 unit_velocity =
                motion_twists_at_unit_[index] * velocities[unit_offset + index];
            velocities_local[index] =
                parent_velocity.adjoint_inv(parent_to_unit_[index]) +
                unit_velocity;
            accelerations_local[index] =
                parent_acceleration.adjoint_inv(parent_to_unit_[index]) +
                motion_twists_at_unit_[index] *
                    accelerations[unit_offset + index] +
                velocities_local[index].cross_motion(unit_velocity);

            const termin::Screw3 momentum =
                unit.inertia.momentum(velocities_local[index]);
            forces_local[index] =
                unit.inertia.momentum(accelerations_local[index]) +
                velocities_local[index].cross_force(momentum);
        }

        effort.assign(count, 0.0);
        for (std::size_t reverse = unit_count; reverse-- > 0;)
        {
            effort[unit_offset + reverse] =
                motion_twists_at_unit_[reverse].dot(forces_local[reverse]);
            const std::size_t parent = units_[reverse].parent_unit;
            if (parent != articulation_root_frame)
            {
                forces_local[parent] +=
                    forces_local[reverse].coadjoint(parent_to_unit_[reverse]);
            }
            else if (floating_base_.has_value())
            {
                base_force +=
                    forces_local[reverse].coadjoint(parent_to_unit_[reverse]);
            }
        }
        if (floating_base_.has_value())
        {
            write_screw_vw(base_force, effort);
        }
        return finite(effort);
    }

    bool Articulation3D::mass_matrix(std::vector<double>& mass) const
    {
        const std::size_t count = dof_count();
        const std::vector<double> zero(count, 0.0);
        mass.assign(count * count, 0.0);
        std::vector<double> unit_acceleration(count, 0.0);
        std::vector<double> column;
        for (std::size_t column_index = 0; column_index < count; ++column_index)
        {
            unit_acceleration[column_index] = 1.0;
            if (!inverse_dynamics(
                    zero, unit_acceleration, termin::Vec3::zero(), column))
            {
                std::fprintf(
                    stderr,
                    "[termin-robotics] articulation '%s' inverse dynamics "
                    "failed for mass column %zu\n",
                    diagnostic_name_.c_str(),
                    column_index);
                return false;
            }
            for (std::size_t row = 0; row < count; ++row)
            {
                mass[row * count + column_index] = column[row];
            }
            unit_acceleration[column_index] = 0.0;
        }

        // RNEA columns are symmetric analytically. Average only the final
        // round-off so dense QP backends receive an exactly symmetric H.
        for (std::size_t row = 0; row < count; ++row)
        {
            for (std::size_t column_index = row + 1; column_index < count;
                 ++column_index)
            {
                const double value = 0.5 * (mass[row * count + column_index] +
                                            mass[column_index * count + row]);
                mass[row * count + column_index] = value;
                mass[column_index * count + row] = value;
            }
        }
        return finite(mass);
    }

    double
    Articulation3D::total_energy(termin::Vec3 gravity_world) const noexcept
    {
        if (diagnostic_ != Articulation3DDiagnostic::None ||
            !gravity_world.is_finite() ||
            unit_poses_world_.size() != units_.size() ||
            unit_velocities_local_.size() != units_.size())
        {
            return std::numeric_limits<double>::quiet_NaN();
        }
        double result = 0.0;
        if (floating_base_.has_value())
        {
            const termin::Vec3 center_world =
                floating_base_->pose_world.transform_point(
                    floating_base_->inertia.inertia_frame.lin);
            result += floating_base_->inertia.kinetic_energy(
                floating_base_->velocity_local);
            result -=
                floating_base_->inertia.mass * gravity_world.dot(center_world);
        }
        for (std::size_t index = 0; index < units_.size(); ++index)
        {
            const ArticulationUnit3D& unit = units_[index];
            const termin::Vec3 center_world =
                unit_poses_world_[index].transform_point(
                    unit.inertia.inertia_frame.lin);
            result +=
                unit.inertia.kinetic_energy(unit_velocities_local_[index]);
            result -= unit.inertia.mass * gravity_world.dot(center_world);
        }
        return result;
    }

} // namespace termin::robotics
