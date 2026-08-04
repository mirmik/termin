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
        case Articulation3DDiagnostic::InvalidJointLimits:
            return "invalid_joint_limits";
        case Articulation3DDiagnostic::NonFiniteInput:
            return "non_finite_input";
        case Articulation3DDiagnostic::InvalidModel:
            return "invalid_model";
        case Articulation3DDiagnostic::InvalidLink:
            return "invalid_link";
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

    Articulation3D::Articulation3D(std::vector<ArticulationLink3D> links,
                                   Articulation3DState initial_state,
                                   std::string_view diagnostic_name)
        : links_(std::move(links)), state_(std::move(initial_state)),
          diagnostic_name_(diagnostic_name)
    {
        parent_to_link_.resize(links_.size());
        link_poses_world_.resize(links_.size());
        motion_twists_at_link_.resize(links_.size());
        link_velocities_local_.resize(links_.size());
        diagnostic_ = validate_model();
        if (diagnostic_ == Articulation3DDiagnostic::None &&
            !update_kinematics())
        {
            diagnostic_ = Articulation3DDiagnostic::NonFiniteInput;
        }
    }

    Articulation3D::Articulation3D(ArticulationFloatingBase3D floating_base,
                                   std::vector<ArticulationLink3D> links,
                                   Articulation3DState initial_state,
                                   std::string_view diagnostic_name)
        : Articulation3D(
              std::move(links), std::move(initial_state), diagnostic_name)
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
        if (links_.empty() && !floating_base_.has_value())
        {
            return Articulation3DDiagnostic::EmptyModel;
        }
        if (state_.coordinates.size() != links_.size() ||
            state_.velocities.size() != links_.size() ||
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
        for (std::size_t index = 0; index < links_.size(); ++index)
        {
            const ArticulationLink3D& link = links_[index];
            if (link.parent_link != articulation_world_link &&
                link.parent_link >= index)
            {
                return Articulation3DDiagnostic::InvalidParent;
            }
            if (!link.parent_to_joint_zero.is_finite() ||
                !link.joint_to_link.is_finite() ||
                link.parent_to_joint_zero.ang.norm() <= 1e-10 ||
                link.joint_to_link.ang.norm() <= 1e-10)
            {
                return Articulation3DDiagnostic::InvalidPose;
            }
            if (!link.motion_twist_at_joint.is_finite() ||
                link.motion_twist_at_joint.dot(link.motion_twist_at_joint) <=
                    1e-20)
            {
                return Articulation3DDiagnostic::InvalidMotionTwist;
            }
            if (!link.inertia.is_valid())
            {
                return Articulation3DDiagnostic::InvalidInertia;
            }
            if ((link.limits.minimum.has_value() &&
                 !std::isfinite(*link.limits.minimum)) ||
                (link.limits.maximum.has_value() &&
                 !std::isfinite(*link.limits.maximum)) ||
                (link.limits.minimum.has_value() &&
                 link.limits.maximum.has_value() &&
                 *link.limits.minimum > *link.limits.maximum))
            {
                return Articulation3DDiagnostic::InvalidJointLimits;
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

    std::size_t Articulation3D::link_count() const noexcept
    {
        return links_.size();
    }

    std::size_t Articulation3D::dof_count() const noexcept
    {
        return links_.size() + (floating_base_.has_value() ? 6 : 0);
    }

    const std::vector<ArticulationLink3D>&
    Articulation3D::links() const noexcept
    {
        return links_;
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
    Articulation3D::link_poses_world() const noexcept
    {
        return link_poses_world_;
    }

    const std::vector<termin::Screw3>&
    Articulation3D::link_velocities_local() const noexcept
    {
        return link_velocities_local_;
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
                "[termin-qopt] articulation '%s' has no valid floating "
                "base point\n",
                diagnostic_name_.c_str());
            return {{}, Articulation3DDiagnostic::InvalidModel};
        }
        if (!point_local.is_finite())
        {
            std::fprintf(
                stderr,
                "[termin-qopt] rejected non-finite floating-base point\n");
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
                "[termin-qopt] floating-base point kinematics failed: %s\n",
                error.what());
        }
        catch (...)
        {
            std::fprintf(stderr,
                         "[termin-qopt] floating-base point kinematics failed "
                         "with an unknown exception\n");
        }
        return {{}, Articulation3DDiagnostic::InternalFailure};
    }

    ArticulationPointKinematics3DResult
    Articulation3D::point_kinematics(std::size_t link_index,
                                     termin::Vec3 point_local) const noexcept
    {
        if (diagnostic_ != Articulation3DDiagnostic::None ||
            link_poses_world_.size() != links_.size() ||
            parent_to_link_.size() != links_.size() ||
            motion_twists_at_link_.size() != links_.size() ||
            link_velocities_local_.size() != links_.size())
        {
            std::fprintf(
                stderr,
                "[termin-qopt] cannot query point kinematics of invalid "
                "articulation '%s'\n",
                diagnostic_name_.c_str());
            return {{}, Articulation3DDiagnostic::InvalidModel};
        }
        if (link_index >= links_.size())
        {
            std::fprintf(
                stderr,
                "[termin-qopt] articulation point references invalid link "
                "%zu\n",
                link_index);
            return {{}, Articulation3DDiagnostic::InvalidLink};
        }
        if (!point_local.is_finite())
        {
            std::fprintf(
                stderr,
                "[termin-qopt] rejected non-finite articulation point\n");
            return {{}, Articulation3DDiagnostic::NonFinitePoint};
        }

        try
        {
            ArticulationPointKinematics3D value;
            value.position_world =
                link_poses_world_[link_index].transform_point(point_local);
            value.velocity_world =
                link_velocities_local_[link_index]
                    .velocity_at_offset(point_local)
                    .rotated_by(link_poses_world_[link_index].ang)
                    .lin;
            const std::size_t generalized_count = dof_count();
            const std::size_t joint_offset = floating_base_.has_value() ? 6 : 0;
            value.linear_jacobian_world_storage.assign(3 * generalized_count,
                                                       0.0);

            std::vector<termin::Screw3> unit_velocities(link_index + 1);
            for (std::size_t column = 0; column < generalized_count; ++column)
            {
                termin::Screw3 base_velocity = termin::Screw3::zero();
                if (floating_base_.has_value() && column < 6)
                {
                    std::vector<double> unit_base(6, 0.0);
                    unit_base[column] = 1.0;
                    base_velocity = read_screw_vw(unit_base);
                }
                for (std::size_t index = 0; index <= link_index; ++index)
                {
                    const std::size_t parent = links_[index].parent_link;
                    const termin::Screw3 parent_velocity =
                        parent == articulation_world_link
                            ? base_velocity
                            : unit_velocities[parent];
                    unit_velocities[index] =
                        parent_velocity.adjoint_inv(parent_to_link_[index]);
                    if (column >= joint_offset &&
                        index == column - joint_offset)
                    {
                        unit_velocities[index] += motion_twists_at_link_[index];
                    }
                }
                const termin::Vec3 response =
                    unit_velocities[link_index]
                        .velocity_at_offset(point_local)
                        .rotated_by(link_poses_world_[link_index].ang)
                        .lin;
                value.linear_jacobian_world_storage[column] = response.x;
                value
                    .linear_jacobian_world_storage[generalized_count + column] =
                    response.y;
                value.linear_jacobian_world_storage[2 * generalized_count +
                                                    column] = response.z;
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
                "[termin-qopt] articulation point kinematics failed: %s\n",
                error.what());
        }
        catch (...)
        {
            std::fprintf(
                stderr,
                "[termin-qopt] articulation point kinematics failed with "
                "an unknown exception\n");
        }
        return {{}, Articulation3DDiagnostic::InternalFailure};
    }

    Articulation3DDiagnostic
    Articulation3D::set_state(Articulation3DState value) noexcept
    {
        if (value.coordinates.size() != links_.size() ||
            value.velocities.size() != links_.size() ||
            !finite(value.coordinates) || !finite(value.velocities))
        {
            std::fprintf(stderr,
                         "[termin-qopt] rejected invalid articulation state\n");
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
                stderr, "[termin-qopt] rejected invalid floating-base state\n");
            return Articulation3DDiagnostic::InvalidState;
        }
        floating_base_->pose_world = pose_world.normalized();
        floating_base_->velocity_local = velocity_local;
        return update_kinematics() ? Articulation3DDiagnostic::None
                                   : Articulation3DDiagnostic::NonFiniteInput;
    }

    bool Articulation3D::update_kinematics() noexcept
    {
        const std::size_t count = links_.size();
        if (parent_to_link_.size() != count ||
            link_poses_world_.size() != count ||
            motion_twists_at_link_.size() != count ||
            link_velocities_local_.size() != count)
        {
            return false;
        }

        for (std::size_t index = 0; index < count; ++index)
        {
            const ArticulationLink3D& link = links_[index];
            const termin::Pose3 joint_motion = termin::se3_exp(
                link.motion_twist_at_joint * state_.coordinates[index]);
            parent_to_link_[index] =
                (link.parent_to_joint_zero * joint_motion * link.joint_to_link)
                    .normalized();
            const termin::Pose3 parent_pose =
                link.parent_link == articulation_world_link
                    ? (floating_base_.has_value() ? floating_base_->pose_world
                                                  : termin::Pose3::identity())
                    : link_poses_world_[link.parent_link];
            link_poses_world_[index] =
                (parent_pose * parent_to_link_[index]).normalized();
            motion_twists_at_link_[index] =
                link.motion_twist_at_joint.adjoint_inv(link.joint_to_link);

            const termin::Screw3 parent_velocity =
                link.parent_link == articulation_world_link
                    ? (floating_base_.has_value()
                           ? floating_base_->velocity_local
                           : termin::Screw3::zero())
                    : link_velocities_local_[link.parent_link];
            link_velocities_local_[index] =
                parent_velocity.adjoint_inv(parent_to_link_[index]) +
                motion_twists_at_link_[index] * state_.velocities[index];

            if (!parent_to_link_[index].is_finite() ||
                !link_poses_world_[index].is_finite() ||
                !motion_twists_at_link_[index].is_finite() ||
                !link_velocities_local_[index].is_finite())
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
        const std::size_t link_count = links_.size();
        const std::size_t count = dof_count();
        const std::size_t joint_offset = floating_base_.has_value() ? 6 : 0;
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

        std::vector<termin::Screw3> velocities_local(link_count);
        std::vector<termin::Screw3> accelerations_local(link_count);
        std::vector<termin::Screw3> forces_local(link_count);
        for (std::size_t index = 0; index < link_count; ++index)
        {
            const ArticulationLink3D& link = links_[index];
            const termin::Screw3 parent_velocity =
                link.parent_link == articulation_world_link
                    ? base_velocity
                    : velocities_local[link.parent_link];
            const termin::Screw3 parent_acceleration =
                link.parent_link == articulation_world_link
                    ? base_acceleration
                    : accelerations_local[link.parent_link];
            const termin::Screw3 joint_velocity =
                motion_twists_at_link_[index] *
                velocities[joint_offset + index];
            velocities_local[index] =
                parent_velocity.adjoint_inv(parent_to_link_[index]) +
                joint_velocity;
            accelerations_local[index] =
                parent_acceleration.adjoint_inv(parent_to_link_[index]) +
                motion_twists_at_link_[index] *
                    accelerations[joint_offset + index] +
                velocities_local[index].cross_motion(joint_velocity);

            const termin::Screw3 momentum =
                link.inertia.momentum(velocities_local[index]);
            forces_local[index] =
                link.inertia.momentum(accelerations_local[index]) +
                velocities_local[index].cross_force(momentum);
        }

        effort.assign(count, 0.0);
        for (std::size_t reverse = link_count; reverse-- > 0;)
        {
            effort[joint_offset + reverse] =
                motion_twists_at_link_[reverse].dot(forces_local[reverse]);
            const std::size_t parent = links_[reverse].parent_link;
            if (parent != articulation_world_link)
            {
                forces_local[parent] +=
                    forces_local[reverse].coadjoint(parent_to_link_[reverse]);
            }
            else if (floating_base_.has_value())
            {
                base_force +=
                    forces_local[reverse].coadjoint(parent_to_link_[reverse]);
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
                std::fprintf(stderr,
                             "[termin-qopt] articulation '%s' inverse dynamics "
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
            link_poses_world_.size() != links_.size() ||
            link_velocities_local_.size() != links_.size())
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
        for (std::size_t index = 0; index < links_.size(); ++index)
        {
            const ArticulationLink3D& link = links_[index];
            const termin::Vec3 center_world =
                link_poses_world_[index].transform_point(
                    link.inertia.inertia_frame.lin);
            result +=
                link.inertia.kinetic_energy(link_velocities_local_[index]);
            result -= link.inertia.mass * gravity_world.dot(center_world);
        }
        return result;
    }

} // namespace termin::robotics
