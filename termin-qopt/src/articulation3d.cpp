#include <termin/qopt/articulation3d.hpp>

#include <termin/geom/se3.hpp>

#include <algorithm>
#include <array>
#include <cmath>
#include <cstdio>
#include <exception>
#include <limits>
#include <utility>

namespace termin::qopt
{
    namespace
    {
        bool finite(const std::vector<double>& values) noexcept
        {
            return std::all_of(values.begin(),
                               values.end(),
                               [](double value) { return std::isfinite(value); });
        }

        ConstDenseMatrixView matrix_view(const std::vector<double>& values,
                                         std::size_t size) noexcept
        {
            return ConstDenseMatrixView::row_major(values.data(), size, size);
        }

        ConstDenseVectorView vector_view(const std::vector<double>& values) noexcept
        {
            return {values.data(), values.size(), 1};
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
        }
        return "unknown";
    }

    Articulation3DContribution::Articulation3DContribution(
        std::vector<ArticulationLink3D> links,
        Articulation3DState initial_state,
        termin::Vec3 gravity_world,
        std::string_view diagnostic_name)
        : links_(std::move(links)), state_(std::move(initial_state)),
          gravity_world_(gravity_world), diagnostic_name_(diagnostic_name)
    {
        parent_to_link_.resize(links_.size());
        link_poses_world_.resize(links_.size());
        motion_twists_at_link_.resize(links_.size());
        link_velocities_local_.resize(links_.size());
        joint_limit_rows_.resize(links_.size());
        joint_limit_states_.resize(links_.size());
        diagnostic_ = validate_model();
        if (diagnostic_ == Articulation3DDiagnostic::None &&
            (!gravity_world_.is_finite() || !update_kinematics()))
        {
            diagnostic_ = Articulation3DDiagnostic::NonFiniteInput;
        }
        accelerations_.assign(links_.size(), 0.0);
        state_snapshot_.coordinates.assign(links_.size(), 0.0);
        state_snapshot_.velocities.assign(links_.size(), 0.0);
        acceleration_snapshot_.assign(links_.size(), 0.0);
        joint_limit_state_snapshot_.resize(links_.size());
    }

    Articulation3DDiagnostic Articulation3DContribution::validate_model() const noexcept
    {
        if (links_.empty())
        {
            return Articulation3DDiagnostic::EmptyModel;
        }
        if (state_.coordinates.size() != links_.size() ||
            state_.velocities.size() != links_.size() || !finite(state_.coordinates) ||
            !finite(state_.velocities))
        {
            return Articulation3DDiagnostic::InvalidState;
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
                link.motion_twist_at_joint.dot(link.motion_twist_at_joint) <= 1e-20)
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
                (link.limits.minimum.has_value() && link.limits.maximum.has_value() &&
                 *link.limits.minimum > *link.limits.maximum))
            {
                return Articulation3DDiagnostic::InvalidJointLimits;
            }
        }
        return Articulation3DDiagnostic::None;
    }

    Articulation3DDiagnostic Articulation3DContribution::diagnostic() const noexcept
    {
        return diagnostic_;
    }

    std::size_t Articulation3DContribution::link_count() const noexcept
    {
        return links_.size();
    }

    std::size_t Articulation3DContribution::dof_count() const noexcept
    {
        return links_.size();
    }

    const std::vector<ArticulationLink3D>&
    Articulation3DContribution::links() const noexcept
    {
        return links_;
    }

    const Articulation3DState& Articulation3DContribution::state() const noexcept
    {
        return state_;
    }

    const std::vector<double>&
    Articulation3DContribution::accelerations() const noexcept
    {
        return accelerations_;
    }

    const std::vector<termin::Pose3>&
    Articulation3DContribution::link_poses_world() const noexcept
    {
        return link_poses_world_;
    }

    const std::vector<termin::Screw3>&
    Articulation3DContribution::link_velocities_local() const noexcept
    {
        return link_velocities_local_;
    }

    const std::vector<ArticulationJointLimitState3D>&
    Articulation3DContribution::joint_limit_states() const noexcept
    {
        return joint_limit_states_;
    }

    DynamicsDofHandle Articulation3DContribution::dofs() const noexcept
    {
        return dofs_;
    }

    termin::Vec3 Articulation3DContribution::gravity_world() const noexcept
    {
        return gravity_world_;
    }

    Articulation3DDiagnostic
    Articulation3DContribution::set_state(Articulation3DState value) noexcept
    {
        if (value.coordinates.size() != links_.size() ||
            value.velocities.size() != links_.size() || !finite(value.coordinates) ||
            !finite(value.velocities))
        {
            std::fprintf(stderr, "[termin-qopt] rejected invalid articulation state\n");
            return Articulation3DDiagnostic::InvalidState;
        }
        state_ = std::move(value);
        if (!update_kinematics())
        {
            return Articulation3DDiagnostic::NonFiniteInput;
        }
        return Articulation3DDiagnostic::None;
    }

    Articulation3DDiagnostic
    Articulation3DContribution::set_gravity_world(termin::Vec3 value) noexcept
    {
        if (!value.is_finite())
        {
            std::fprintf(stderr,
                         "[termin-qopt] rejected non-finite articulation gravity\n");
            return Articulation3DDiagnostic::NonFiniteInput;
        }
        gravity_world_ = value;
        return Articulation3DDiagnostic::None;
    }

    bool Articulation3DContribution::update_kinematics() noexcept
    {
        const std::size_t count = links_.size();
        if (parent_to_link_.size() != count || link_poses_world_.size() != count ||
            motion_twists_at_link_.size() != count ||
            link_velocities_local_.size() != count)
        {
            return false;
        }

        for (std::size_t index = 0; index < count; ++index)
        {
            const ArticulationLink3D& link = links_[index];
            const termin::Pose3 joint_motion =
                termin::se3_exp(link.motion_twist_at_joint * state_.coordinates[index]);
            parent_to_link_[index] =
                (link.parent_to_joint_zero * joint_motion * link.joint_to_link)
                    .normalized();
            const termin::Pose3 parent_pose =
                link.parent_link == articulation_world_link
                    ? termin::Pose3::identity()
                    : link_poses_world_[link.parent_link];
            link_poses_world_[index] =
                (parent_pose * parent_to_link_[index]).normalized();
            motion_twists_at_link_[index] =
                link.motion_twist_at_joint.adjoint_inv(link.joint_to_link);

            const termin::Screw3 parent_velocity =
                link.parent_link == articulation_world_link
                    ? termin::Screw3::zero()
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

    bool Articulation3DContribution::inverse_dynamics(
        const std::vector<double>& velocities,
        const std::vector<double>& accelerations,
        termin::Vec3 gravity_world,
        std::vector<double>& effort) const
    {
        const std::size_t count = links_.size();
        if (velocities.size() != count || accelerations.size() != count ||
            !finite(velocities) || !finite(accelerations) || !gravity_world.is_finite())
        {
            return false;
        }

        std::vector<termin::Screw3> velocities_local(count);
        std::vector<termin::Screw3> accelerations_local(count);
        std::vector<termin::Screw3> forces_local(count);
        for (std::size_t index = 0; index < count; ++index)
        {
            const ArticulationLink3D& link = links_[index];
            const termin::Screw3 parent_velocity =
                link.parent_link == articulation_world_link
                    ? termin::Screw3::zero()
                    : velocities_local[link.parent_link];
            const termin::Screw3 parent_acceleration =
                link.parent_link == articulation_world_link
                    ? termin::Screw3{termin::Vec3::zero(), -gravity_world}
                    : accelerations_local[link.parent_link];
            const termin::Screw3 joint_velocity =
                motion_twists_at_link_[index] * velocities[index];
            velocities_local[index] =
                parent_velocity.adjoint_inv(parent_to_link_[index]) + joint_velocity;
            accelerations_local[index] =
                parent_acceleration.adjoint_inv(parent_to_link_[index]) +
                motion_twists_at_link_[index] * accelerations[index] +
                velocities_local[index].cross_motion(joint_velocity);

            const termin::Screw3 momentum =
                link.inertia.momentum(velocities_local[index]);
            forces_local[index] = link.inertia.momentum(accelerations_local[index]) +
                                  velocities_local[index].cross_force(momentum);
        }

        effort.assign(count, 0.0);
        for (std::size_t reverse = count; reverse-- > 0;)
        {
            effort[reverse] =
                motion_twists_at_link_[reverse].dot(forces_local[reverse]);
            const std::size_t parent = links_[reverse].parent_link;
            if (parent != articulation_world_link)
            {
                forces_local[parent] +=
                    forces_local[reverse].coadjoint(parent_to_link_[reverse]);
            }
        }
        return finite(effort);
    }

    bool
    Articulation3DContribution::assemble_mass_and_bias(std::vector<double>& mass,
                                                       std::vector<double>& bias) const
    {
        const std::size_t count = links_.size();
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
                return false;
            }
            for (std::size_t row = 0; row < count; ++row)
            {
                mass[row * count + column_index] = column[row];
            }
            unit_acceleration[column_index] = 0.0;
        }

        // RNEA columns are symmetric analytically. Average only the final
        // round-off so the dense QP backend receives an exactly symmetric H.
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
        return inverse_dynamics(state_.velocities, zero, gravity_world_, bias) &&
               finite(mass);
    }

    double Articulation3DContribution::total_energy() const noexcept
    {
        if (diagnostic_ != Articulation3DDiagnostic::None ||
            link_poses_world_.size() != links_.size() ||
            link_velocities_local_.size() != links_.size())
        {
            return std::numeric_limits<double>::quiet_NaN();
        }
        double result = 0.0;
        for (std::size_t index = 0; index < links_.size(); ++index)
        {
            const ArticulationLink3D& link = links_[index];
            const termin::Vec3 center_world = link_poses_world_[index].transform_point(
                link.inertia.inertia_frame.lin);
            result += link.inertia.kinetic_energy(link_velocities_local_[index]);
            result -= link.inertia.mass * gravity_world_.dot(center_world);
        }
        return result;
    }

    AssemblyDiagnostic
    Articulation3DContribution::register_topology(DynamicsTopology& topology) noexcept
    {
        if (diagnostic_ != Articulation3DDiagnostic::None)
        {
            std::fprintf(stderr,
                         "[termin-qopt] invalid articulation contribution '%s': %s\n",
                         diagnostic_name_.c_str(),
                         articulation3d_diagnostic_name(diagnostic_).data());
            return AssemblyDiagnostic::NonFiniteContribution;
        }
        const auto result = topology.register_dofs(links_.size(), diagnostic_name_);
        dofs_ = result.handle;
        return result.diagnostic;
    }

    AssemblyDiagnostic Articulation3DContribution::register_unilateral_constraints(
        DynamicsUnilateralTopology& topology, double time_step) noexcept
    {
        if (diagnostic_ != Articulation3DDiagnostic::None ||
            !std::isfinite(time_step) || time_step <= 0.0 ||
            joint_limit_rows_.size() != links_.size() ||
            joint_limit_states_.size() != links_.size())
        {
            std::fprintf(stderr,
                         "[termin-qopt] articulation '%s' cannot register "
                         "joint limits\n",
                         diagnostic_name_.c_str());
            return AssemblyDiagnostic::NonFiniteContribution;
        }

        unilateral_time_step_ = time_step;
        std::fill(joint_limit_rows_.begin(), joint_limit_rows_.end(), JointLimitRows{});
        std::fill(joint_limit_states_.begin(),
                  joint_limit_states_.end(),
                  ArticulationJointLimitState3D{});
        try
        {
            const std::string prefix =
                diagnostic_name_.empty() ? "articulation" : diagnostic_name_;
            for (std::size_t index = 0; index < links_.size(); ++index)
            {
                const ArticulationJointLimits3D& limits = links_[index].limits;
                const double coordinate = state_.coordinates[index];
                const double predicted_coordinate =
                    coordinate + time_step * state_.velocities[index];
                if (limits.minimum.has_value() &&
                    (coordinate <= *limits.minimum ||
                     predicted_coordinate <= *limits.minimum))
                {
                    const auto result = topology.register_constraint(
                        1, prefix + ".joint_limit.minimum." + std::to_string(index));
                    if (!result.ok())
                    {
                        return result.diagnostic;
                    }
                    joint_limit_rows_[index].minimum = result.handle;
                }
                if (limits.maximum.has_value() &&
                    (coordinate >= *limits.maximum ||
                     predicted_coordinate >= *limits.maximum))
                {
                    const auto result = topology.register_constraint(
                        1, prefix + ".joint_limit.maximum." + std::to_string(index));
                    if (!result.ok())
                    {
                        return result.diagnostic;
                    }
                    joint_limit_rows_[index].maximum = result.handle;
                }
            }
            return AssemblyDiagnostic::None;
        }
        catch (const std::exception& error)
        {
            std::fprintf(stderr,
                         "[termin-qopt] articulation joint-limit topology "
                         "failed: %s\n",
                         error.what());
        }
        catch (...)
        {
            std::fprintf(stderr,
                         "[termin-qopt] articulation joint-limit topology "
                         "failed with an unknown exception\n");
        }
        return AssemblyDiagnostic::InternalFailure;
    }

    AssemblyDiagnostic
    Articulation3DContribution::assemble(DynamicsAssembly& assembly,
                                         DynamicsAssemblyPhase phase) noexcept
    {
        try
        {
            std::vector<double> mass;
            std::vector<double> bias;
            if (!update_kinematics() || !assemble_mass_and_bias(mass, bias))
            {
                return AssemblyDiagnostic::NonFiniteContribution;
            }

            std::vector<double> load(links_.size(), 0.0);
            if (phase == DynamicsAssemblyPhase::Acceleration)
            {
                for (std::size_t index = 0; index < links_.size(); ++index)
                {
                    load[index] = -bias[index];
                }
            }
            else if (phase == DynamicsAssemblyPhase::VelocityProjection)
            {
                for (std::size_t row = 0; row < links_.size(); ++row)
                {
                    for (std::size_t column = 0; column < links_.size(); ++column)
                    {
                        load[row] += mass[row * links_.size() + column] *
                                     state_.velocities[column];
                    }
                }
            }

            const AssemblyDiagnostic mass_result =
                assembly.add_mass(dofs_, dofs_, matrix_view(mass, links_.size()));
            const AssemblyDiagnostic load_result =
                assembly.add_load(dofs_, vector_view(load));
            if (mass_result != AssemblyDiagnostic::None)
            {
                return mass_result;
            }
            if (load_result != AssemblyDiagnostic::None ||
                phase != DynamicsAssemblyPhase::VelocityProjection)
            {
                return load_result;
            }
            if (!std::isfinite(unilateral_time_step_) || unilateral_time_step_ <= 0.0)
            {
                return AssemblyDiagnostic::NonFiniteContribution;
            }

            std::vector<double> row(links_.size(), 0.0);
            for (std::size_t index = 0; index < links_.size(); ++index)
            {
                const ArticulationJointLimits3D& limits = links_[index].limits;
                row[index] = -1.0;
                if (joint_limit_rows_[index].minimum.valid())
                {
                    const double coordinate = snapshot_ready_
                                                  ? state_snapshot_.coordinates[index]
                                                  : state_.coordinates[index];
                    const double margin = std::max(0.0, coordinate - *limits.minimum);
                    const std::array<double, 1> limit{
                        margin / unilateral_time_step_,
                    };
                    AssemblyDiagnostic result = assembly.add_unilateral_jacobian(
                        joint_limit_rows_[index].minimum,
                        dofs_,
                        ConstDenseMatrixView::row_major(row.data(), 1, links_.size()));
                    if (result == AssemblyDiagnostic::None)
                    {
                        result = assembly.add_unilateral_limit(
                            joint_limit_rows_[index].minimum,
                            {limit.data(), limit.size(), 1});
                    }
                    if (result != AssemblyDiagnostic::None)
                    {
                        return result;
                    }
                }
                row[index] = 1.0;
                if (joint_limit_rows_[index].maximum.valid())
                {
                    const double coordinate = snapshot_ready_
                                                  ? state_snapshot_.coordinates[index]
                                                  : state_.coordinates[index];
                    const double margin = std::max(0.0, *limits.maximum - coordinate);
                    const std::array<double, 1> limit{
                        margin / unilateral_time_step_,
                    };
                    AssemblyDiagnostic result = assembly.add_unilateral_jacobian(
                        joint_limit_rows_[index].maximum,
                        dofs_,
                        ConstDenseMatrixView::row_major(row.data(), 1, links_.size()));
                    if (result == AssemblyDiagnostic::None)
                    {
                        result = assembly.add_unilateral_limit(
                            joint_limit_rows_[index].maximum,
                            {limit.data(), limit.size(), 1});
                    }
                    if (result != AssemblyDiagnostic::None)
                    {
                        return result;
                    }
                }
                row[index] = 0.0;
            }
            return AssemblyDiagnostic::None;
        }
        catch (const std::exception& error)
        {
            std::fprintf(stderr,
                         "[termin-qopt] articulation assembly failed: %s\n",
                         error.what());
        }
        catch (...)
        {
            std::fprintf(stderr,
                         "[termin-qopt] articulation assembly failed with "
                         "unknown exception\n");
        }
        return AssemblyDiagnostic::InternalFailure;
    }

    AssemblyDiagnostic Articulation3DContribution::begin_step() noexcept
    {
        std::copy(state_.coordinates.begin(),
                  state_.coordinates.end(),
                  state_snapshot_.coordinates.begin());
        std::copy(state_.velocities.begin(),
                  state_.velocities.end(),
                  state_snapshot_.velocities.begin());
        std::copy(accelerations_.begin(),
                  accelerations_.end(),
                  acceleration_snapshot_.begin());
        std::copy(joint_limit_states_.begin(),
                  joint_limit_states_.end(),
                  joint_limit_state_snapshot_.begin());
        snapshot_ready_ = true;
        return AssemblyDiagnostic::None;
    }

    void Articulation3DContribution::commit_step() noexcept
    {
        snapshot_ready_ = false;
    }

    void Articulation3DContribution::rollback_step() noexcept
    {
        if (snapshot_ready_)
        {
            std::copy(state_snapshot_.coordinates.begin(),
                      state_snapshot_.coordinates.end(),
                      state_.coordinates.begin());
            std::copy(state_snapshot_.velocities.begin(),
                      state_snapshot_.velocities.end(),
                      state_.velocities.begin());
            std::copy(acceleration_snapshot_.begin(),
                      acceleration_snapshot_.end(),
                      accelerations_.begin());
            std::copy(joint_limit_state_snapshot_.begin(),
                      joint_limit_state_snapshot_.end(),
                      joint_limit_states_.begin());
            (void)update_kinematics();
            snapshot_ready_ = false;
        }
    }

    void Articulation3DContribution::apply_unilateral_solution(
        const DynamicsTopology&,
        const DynamicsUnilateralTopology& unilateral_topology,
        ConstDenseVectorView reactions,
        ConstDenseVectorView tight_mask) noexcept
    {
        if (joint_limit_rows_.size() != links_.size() ||
            joint_limit_states_.size() != links_.size())
        {
            return;
        }
        for (std::size_t index = 0; index < links_.size(); ++index)
        {
            ArticulationJointLimitState3D& state = joint_limit_states_[index];
            const auto read = [&](DynamicsUnilateralConstraintHandle handle,
                                  double& reaction,
                                  bool& active)
            {
                if (!handle.valid())
                {
                    return;
                }
                const DenseBlockInfo info =
                    unilateral_topology.constraint_topology().block_info(handle.block);
                if (!info.ok() || info.size != 1 || info.offset >= reactions.size ||
                    info.offset >= tight_mask.size)
                {
                    return;
                }
                reaction = reactions[info.offset];
                active = tight_mask[info.offset] == 1.0;
            };
            read(joint_limit_rows_[index].minimum,
                 state.minimum_reaction,
                 state.minimum_active);
            read(joint_limit_rows_[index].maximum,
                 state.maximum_reaction,
                 state.maximum_active);
        }
    }

    void Articulation3DContribution::apply_solution(DynamicsAssemblyPhase phase,
                                                    const DynamicsTopology& topology,
                                                    ConstDenseVectorView values,
                                                    ConstDenseVectorView) noexcept
    {
        const DenseBlockInfo info = topology.dof_topology().block_info(dofs_.block);
        if (!info.ok() || info.size != links_.size())
        {
            return;
        }
        if (phase == DynamicsAssemblyPhase::Acceleration)
        {
            for (std::size_t index = 0; index < links_.size(); ++index)
            {
                accelerations_[index] = values[info.offset + index];
            }
        }
        else if (phase == DynamicsAssemblyPhase::VelocityProjection)
        {
            for (std::size_t index = 0; index < links_.size(); ++index)
            {
                state_.velocities[index] = values[info.offset + index];
            }
            (void)update_kinematics();
        }
    }

    AssemblyDiagnostic Articulation3DContribution::write_velocity(
        const DynamicsTopology& topology, DenseVectorView destination) const noexcept
    {
        const DenseBlockInfo info = topology.dof_topology().block_info(dofs_.block);
        if (!info.ok() || info.size != links_.size())
        {
            return AssemblyDiagnostic::InvalidBlock;
        }
        for (std::size_t index = 0; index < links_.size(); ++index)
        {
            destination[info.offset + index] = state_.velocities[index];
        }
        return AssemblyDiagnostic::None;
    }

    AssemblyDiagnostic
    Articulation3DContribution::set_velocity(const DynamicsTopology& topology,
                                             ConstDenseVectorView source) noexcept
    {
        const DenseBlockInfo info = topology.dof_topology().block_info(dofs_.block);
        if (!info.ok() || info.size != links_.size())
        {
            return AssemblyDiagnostic::InvalidBlock;
        }
        for (std::size_t index = 0; index < links_.size(); ++index)
        {
            state_.velocities[index] = source[info.offset + index];
        }
        return finite(state_.velocities) && update_kinematics()
                   ? AssemblyDiagnostic::None
                   : AssemblyDiagnostic::NonFiniteContribution;
    }

    AssemblyDiagnostic Articulation3DContribution::set_trial_configuration(
        const DynamicsTopology& topology,
        ConstDenseVectorView midpoint_velocity,
        double time_step) noexcept
    {
        if (!snapshot_ready_ || !std::isfinite(time_step) || time_step <= 0.0)
        {
            return AssemblyDiagnostic::NonFiniteContribution;
        }
        const DenseBlockInfo info = topology.dof_topology().block_info(dofs_.block);
        if (!info.ok() || info.size != links_.size())
        {
            return AssemblyDiagnostic::InvalidBlock;
        }
        for (std::size_t index = 0; index < links_.size(); ++index)
        {
            const double velocity = midpoint_velocity[info.offset + index];
            state_.coordinates[index] =
                state_snapshot_.coordinates[index] + time_step * velocity;
            state_.velocities[index] = velocity;
        }
        return finite(state_.coordinates) && finite(state_.velocities) &&
                       update_kinematics()
                   ? AssemblyDiagnostic::None
                   : AssemblyDiagnostic::NonFiniteContribution;
    }

    AssemblyDiagnostic Articulation3DContribution::write_corrected_midpoint_velocity(
        const DynamicsTopology& topology,
        ConstDenseVectorView midpoint_velocity,
        ConstDenseVectorView correction,
        double time_step,
        DenseVectorView destination) const noexcept
    {
        if (!std::isfinite(time_step) || time_step <= 0.0)
        {
            return AssemblyDiagnostic::NonFiniteContribution;
        }
        const DenseBlockInfo info = topology.dof_topology().block_info(dofs_.block);
        if (!info.ok() || info.size != links_.size())
        {
            return AssemblyDiagnostic::InvalidBlock;
        }
        for (std::size_t index = 0; index < links_.size(); ++index)
        {
            destination[info.offset + index] =
                midpoint_velocity[info.offset + index] +
                correction[info.offset + index] / time_step;
        }
        return AssemblyDiagnostic::None;
    }

} // namespace termin::qopt
