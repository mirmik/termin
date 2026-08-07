#include <termin/physics_qopt/articulation3d_dynamics.hpp>

#include <termin/geom/se3.hpp>
#include <termin/robotics/detail/articulation3d_access.hpp>

#include <algorithm>
#include <array>
#include <cmath>
#include <cstdio>
#include <utility>

namespace termin::physics_qopt {
    namespace {
        bool finite(const std::vector<double>& values) noexcept {
            return std::all_of(values.begin(), values.end(), [](double value) { return std::isfinite(value); });
        }

        ConstDenseMatrixView matrix_view(const std::vector<double>& values, std::size_t size) noexcept {
            return ConstDenseMatrixView::row_major(values.data(), size, size);
        }

        ConstDenseVectorView vector_view(const std::vector<double>& values) noexcept {
            return {values.data(), values.size(), 1};
        }

        PointKinematics3DDiagnostic point_diagnostic(robotics::Articulation3DDiagnostic diagnostic) noexcept {
            switch (diagnostic) {
            case robotics::Articulation3DDiagnostic::None:
                return PointKinematics3DDiagnostic::None;
            case robotics::Articulation3DDiagnostic::InvalidUnit:
                return PointKinematics3DDiagnostic::InvalidUnit;
            case robotics::Articulation3DDiagnostic::NonFinitePoint:
                return PointKinematics3DDiagnostic::NonFinitePoint;
            case robotics::Articulation3DDiagnostic::InternalFailure:
                return PointKinematics3DDiagnostic::InternalFailure;
            default:
                return PointKinematics3DDiagnostic::InvalidModel;
            }
        }

        termin::Screw3 read_screw_vw(ConstDenseVectorView values, std::size_t offset) noexcept {
            return {
                {values[offset + 3], values[offset + 4], values[offset + 5]},
                {values[offset], values[offset + 1], values[offset + 2]},
            };
        }

        void write_screw_vw(termin::Screw3 value, std::vector<double>& destination, std::size_t offset = 0) noexcept {
            destination[offset] = value.lin.x;
            destination[offset + 1] = value.lin.y;
            destination[offset + 2] = value.lin.z;
            destination[offset + 3] = value.ang.x;
            destination[offset + 4] = value.ang.y;
            destination[offset + 5] = value.ang.z;
        }

        void write_screw_vw(termin::Screw3 value, DenseVectorView destination, std::size_t offset) noexcept {
            destination[offset] = value.lin.x;
            destination[offset + 1] = value.lin.y;
            destination[offset + 2] = value.lin.z;
            destination[offset + 3] = value.ang.x;
            destination[offset + 4] = value.ang.y;
            destination[offset + 5] = value.ang.z;
        }
    } // namespace

    using robotics::Articulation3D;
    using robotics::Articulation3DDiagnostic;
    using robotics::Articulation3DState;
    using robotics::ArticulationFloatingBase3D;
    using robotics::ArticulationPointKinematics3DResult;
    using robotics::ArticulationUnit3D;
    using robotics::ArticulationUnitLimits3D;
    using ArticulationAccess = robotics::detail::Articulation3DMutableAccess;

    Articulation3DDynamicsContribution::Articulation3DDynamicsContribution(Articulation3D& articulation,
                                                                           termin::Vec3 gravity_world,
                                                                           std::string_view diagnostic_name)
        : articulation_(articulation),
          gravity_world_(gravity_world),
          diagnostic_name_(diagnostic_name.empty() ? std::string(articulation.diagnostic_name())
                                                   : std::string(diagnostic_name)) {
        diagnostic_ = articulation_.diagnostic();
        if (diagnostic_ == Articulation3DDiagnostic::None && !gravity_world_.is_finite()) {
            diagnostic_ = Articulation3DDiagnostic::NonFiniteInput;
        }
        accelerations_.assign(dof_count(), 0.0);
        unit_limit_rows_.resize(unit_count());
        unit_limit_states_.resize(unit_count());
        state_snapshot_.coordinates.assign(unit_count(), 0.0);
        state_snapshot_.velocities.assign(unit_count(), 0.0);
        acceleration_snapshot_.assign(dof_count(), 0.0);
        unit_limit_state_snapshot_.resize(unit_count());
        const std::size_t generalized_count = dof_count();
        mass_matrix_cache_.assign(generalized_count * generalized_count, 0.0);
        bias_work_.assign(generalized_count, 0.0);
        load_work_.assign(generalized_count, 0.0);
        generalized_velocity_work_.assign(generalized_count, 0.0);
        limit_row_work_.assign(generalized_count, 0.0);
        zero_acceleration_work_.assign(generalized_count, 0.0);
    }

    Articulation3D& Articulation3DDynamicsContribution::articulation() noexcept {
        invalidate_mass_matrix_cache();
        return articulation_;
    }

    const Articulation3D& Articulation3DDynamicsContribution::articulation() const noexcept {
        return articulation_;
    }

    Articulation3DDiagnostic Articulation3DDynamicsContribution::diagnostic() const noexcept {
        return diagnostic_;
    }

    std::size_t Articulation3DDynamicsContribution::unit_count() const noexcept {
        return articulation_.unit_count();
    }

    std::size_t Articulation3DDynamicsContribution::dof_count() const noexcept {
        return articulation_.dof_count();
    }

    const std::vector<ArticulationUnit3D>& Articulation3DDynamicsContribution::units() const noexcept {
        return articulation_.units();
    }

    const Articulation3DState& Articulation3DDynamicsContribution::state() const noexcept {
        return articulation_.state();
    }

    bool Articulation3DDynamicsContribution::has_floating_base() const noexcept {
        return articulation_.has_floating_base();
    }

    const std::optional<ArticulationFloatingBase3D>&
    Articulation3DDynamicsContribution::floating_base() const noexcept {
        return articulation_.floating_base();
    }

    const std::vector<double>& Articulation3DDynamicsContribution::accelerations() const noexcept {
        return accelerations_;
    }

    const std::vector<termin::Pose3>& Articulation3DDynamicsContribution::unit_poses_world() const noexcept {
        return articulation_.unit_poses_world();
    }

    const std::vector<termin::Screw3>& Articulation3DDynamicsContribution::unit_velocities_local() const noexcept {
        return articulation_.unit_velocities_local();
    }

    const std::vector<ArticulationUnitLimitState3D>&
    Articulation3DDynamicsContribution::unit_limit_states() const noexcept {
        return unit_limit_states_;
    }

    DynamicsDofHandle Articulation3DDynamicsContribution::dofs() const noexcept {
        return dofs_;
    }

    termin::Vec3 Articulation3DDynamicsContribution::gravity_world() const noexcept {
        return gravity_world_;
    }

    ArticulationDynamicsAssemblyCounters Articulation3DDynamicsContribution::assembly_counters() const noexcept {
        return assembly_counters_;
    }

    void Articulation3DDynamicsContribution::reset_assembly_counters() noexcept {
        assembly_counters_ = {};
    }

    PointKinematics3DResult
    Articulation3DDynamicsContribution::floating_base_point_kinematics(termin::Vec3 point_local) const noexcept {
        ArticulationPointKinematics3DResult source = articulation_.floating_base_point_kinematics(point_local);
        if (!source.ok()) {
            return {{}, point_diagnostic(source.diagnostic)};
        }
        PointKinematics3D value;
        value.position_world = source.value.position_world;
        value.velocity_world = source.value.velocity_world;
        value.dofs = dofs_;
        value.linear_jacobian_world_storage = std::move(source.value.linear_jacobian_world_storage);
        return {std::move(value), PointKinematics3DDiagnostic::None};
    }

    PointKinematics3DResult
    Articulation3DDynamicsContribution::point_kinematics(std::size_t unit_index,
                                                         termin::Vec3 point_local) const noexcept {
        ArticulationPointKinematics3DResult source = articulation_.point_kinematics(unit_index, point_local);
        if (!source.ok()) {
            return {{}, point_diagnostic(source.diagnostic)};
        }
        PointKinematics3D value;
        value.position_world = source.value.position_world;
        value.velocity_world = source.value.velocity_world;
        value.dofs = dofs_;
        value.linear_jacobian_world_storage = std::move(source.value.linear_jacobian_world_storage);
        return {std::move(value), PointKinematics3DDiagnostic::None};
    }

    Articulation3DDiagnostic Articulation3DDynamicsContribution::set_state(Articulation3DState value) noexcept {
        invalidate_mass_matrix_cache();
        return articulation_.set_state(std::move(value));
    }

    Articulation3DDiagnostic Articulation3DDynamicsContribution::set_gravity_world(termin::Vec3 value) noexcept {
        if (!value.is_finite()) {
            std::fprintf(stderr, "[termin-qopt] rejected non-finite articulation gravity\n");
            return Articulation3DDiagnostic::NonFiniteInput;
        }
        gravity_world_ = value;
        return Articulation3DDiagnostic::None;
    }

    Articulation3DDiagnostic
    Articulation3DDynamicsContribution::set_floating_base_state(termin::Pose3 pose_world,
                                                                termin::Screw3 velocity_local) noexcept {
        invalidate_mass_matrix_cache();
        return articulation_.set_floating_base_state(pose_world, velocity_local);
    }

    void Articulation3DDynamicsContribution::invalidate_mass_matrix_cache() noexcept {
        mass_matrix_cache_valid_ = false;
    }

    bool Articulation3DDynamicsContribution::prepare_mass_matrix() {
        if (!mass_matrix_cache_valid_) {
            if (!articulation_.mass_matrix(mass_matrix_cache_)) {
                return false;
            }
            mass_matrix_cache_valid_ = true;
            ++assembly_counters_.mass_matrix_evaluations;
        }
        return finite(mass_matrix_cache_);
    }

    bool Articulation3DDynamicsContribution::prepare_bias() {
        std::fill(generalized_velocity_work_.begin(), generalized_velocity_work_.end(), 0.0);
        const std::size_t unit_offset = articulation_.has_floating_base() ? 6 : 0;
        if (ArticulationAccess::floating_base(articulation_).has_value()) {
            write_screw_vw(ArticulationAccess::floating_base(articulation_)->velocity_local,
                           generalized_velocity_work_);
        }
        std::copy(ArticulationAccess::state(articulation_).velocities.begin(),
                  ArticulationAccess::state(articulation_).velocities.end(),
                  generalized_velocity_work_.begin() + unit_offset);
        if (!articulation_.inverse_dynamics(
                generalized_velocity_work_, zero_acceleration_work_, gravity_world_, bias_work_)) {
            std::fprintf(stderr,
                         "[termin-qopt] articulation '%s' inverse dynamics "
                         "failed for velocity/gravity bias\n",
                         diagnostic_name_.c_str());
            return false;
        }
        ++assembly_counters_.bias_evaluations;
        return finite(bias_work_);
    }

    double Articulation3DDynamicsContribution::total_energy() const noexcept {
        return articulation_.total_energy(gravity_world_);
    }

    AssemblyDiagnostic Articulation3DDynamicsContribution::register_topology(DynamicsTopology& topology) noexcept {
        if (diagnostic_ != Articulation3DDiagnostic::None) {
            std::fprintf(stderr,
                         "[termin-qopt] invalid articulation contribution '%s': %s\n",
                         diagnostic_name_.c_str(),
                         articulation3d_diagnostic_name(diagnostic_).data());
            return AssemblyDiagnostic::NonFiniteContribution;
        }
        const auto result = topology.register_dofs(dof_count(), diagnostic_name_);
        dofs_ = result.handle;
        return result.diagnostic;
    }

    AssemblyDiagnostic
    Articulation3DDynamicsContribution::register_unilateral_constraints(DynamicsUnilateralTopology& topology,
                                                                        double time_step) noexcept {
        if (diagnostic_ != Articulation3DDiagnostic::None || !std::isfinite(time_step) || time_step <= 0.0 ||
            unit_limit_rows_.size() != articulation_.units().size() ||
            unit_limit_states_.size() != articulation_.units().size()) {
            std::fprintf(stderr,
                         "[termin-qopt] articulation '%s' cannot register "
                         "joint limits\n",
                         diagnostic_name_.c_str());
            return AssemblyDiagnostic::NonFiniteContribution;
        }

        unilateral_time_step_ = time_step;
        std::fill(unit_limit_rows_.begin(), unit_limit_rows_.end(), UnitLimitRows{});
        std::fill(unit_limit_states_.begin(), unit_limit_states_.end(), ArticulationUnitLimitState3D{});
        try {
            const std::string prefix = diagnostic_name_.empty() ? "articulation" : diagnostic_name_;
            for (std::size_t index = 0; index < articulation_.units().size(); ++index) {
                const ArticulationUnitLimits3D& limits = articulation_.units()[index].limits;
                const double coordinate = ArticulationAccess::state(articulation_).coordinates[index];
                const double predicted_coordinate =
                    coordinate + time_step * ArticulationAccess::state(articulation_).velocities[index];
                if (limits.minimum.has_value() &&
                    (coordinate <= *limits.minimum || predicted_coordinate <= *limits.minimum)) {
                    const auto result =
                        topology.register_constraint(1, prefix + ".joint_limit.minimum." + std::to_string(index));
                    if (!result.ok()) {
                        return result.diagnostic;
                    }
                    unit_limit_rows_[index].minimum = result.handle;
                }
                if (limits.maximum.has_value() &&
                    (coordinate >= *limits.maximum || predicted_coordinate >= *limits.maximum)) {
                    const auto result =
                        topology.register_constraint(1, prefix + ".joint_limit.maximum." + std::to_string(index));
                    if (!result.ok()) {
                        return result.diagnostic;
                    }
                    unit_limit_rows_[index].maximum = result.handle;
                }
            }
            return AssemblyDiagnostic::None;
        } catch (const std::exception& error) {
            std::fprintf(stderr,
                         "[termin-qopt] articulation joint-limit topology "
                         "failed: %s\n",
                         error.what());
        } catch (...) {
            std::fprintf(stderr,
                         "[termin-qopt] articulation joint-limit topology "
                         "failed with an unknown exception\n");
        }
        return AssemblyDiagnostic::InternalFailure;
    }

    AssemblyDiagnostic Articulation3DDynamicsContribution::assemble(DynamicsAssembly& assembly,
                                                                    DynamicsAssemblyPhase phase) noexcept {
        try {
            if (!prepare_mass_matrix() || (phase == DynamicsAssemblyPhase::Acceleration && !prepare_bias())) {
                std::fprintf(stderr,
                             "[termin-qopt] articulation '%s' produced invalid "
                             "mass or bias during assembly\n",
                             diagnostic_name_.c_str());
                return AssemblyDiagnostic::NonFiniteContribution;
            }

            const std::size_t generalized_count = dof_count();
            const std::size_t unit_offset = ArticulationAccess::floating_base(articulation_).has_value() ? 6 : 0;
            std::fill(load_work_.begin(), load_work_.end(), 0.0);
            if (phase == DynamicsAssemblyPhase::Acceleration) {
                for (std::size_t index = 0; index < generalized_count; ++index) {
                    load_work_[index] = -bias_work_[index];
                }
            }
            if (phase == DynamicsAssemblyPhase::VelocityProjection) {
                std::fill(generalized_velocity_work_.begin(), generalized_velocity_work_.end(), 0.0);
                if (ArticulationAccess::floating_base(articulation_).has_value()) {
                    write_screw_vw(ArticulationAccess::floating_base(articulation_)->velocity_local,
                                   generalized_velocity_work_);
                }
                std::copy(ArticulationAccess::state(articulation_).velocities.begin(),
                          ArticulationAccess::state(articulation_).velocities.end(),
                          generalized_velocity_work_.begin() + unit_offset);
                for (std::size_t row = 0; row < generalized_count; ++row) {
                    for (std::size_t column = 0; column < generalized_count; ++column) {
                        load_work_[row] +=
                            mass_matrix_cache_[row * generalized_count + column] * generalized_velocity_work_[column];
                    }
                }
            }

            const AssemblyDiagnostic mass_result =
                assembly.add_mass(dofs_, dofs_, matrix_view(mass_matrix_cache_, generalized_count));
            const AssemblyDiagnostic load_result = assembly.add_load(dofs_, vector_view(load_work_));
            if (mass_result != AssemblyDiagnostic::None) {
                return mass_result;
            }
            if (load_result != AssemblyDiagnostic::None || phase != DynamicsAssemblyPhase::VelocityProjection) {
                return load_result;
            }
            if (!std::isfinite(unilateral_time_step_) || unilateral_time_step_ <= 0.0) {
                return AssemblyDiagnostic::NonFiniteContribution;
            }

            std::fill(limit_row_work_.begin(), limit_row_work_.end(), 0.0);
            for (std::size_t index = 0; index < articulation_.units().size(); ++index) {
                const ArticulationUnitLimits3D& limits = articulation_.units()[index].limits;
                limit_row_work_[unit_offset + index] = -1.0;
                if (unit_limit_rows_[index].minimum.valid()) {
                    const double coordinate = snapshot_ready_
                                                  ? state_snapshot_.coordinates[index]
                                                  : ArticulationAccess::state(articulation_).coordinates[index];
                    const double margin = std::max(0.0, coordinate - *limits.minimum);
                    const std::array<double, 1> limit{
                        margin / unilateral_time_step_,
                    };
                    AssemblyDiagnostic result = assembly.add_unilateral_jacobian(
                        unit_limit_rows_[index].minimum,
                        dofs_,
                        ConstDenseMatrixView::row_major(limit_row_work_.data(), 1, generalized_count));
                    if (result == AssemblyDiagnostic::None) {
                        result = assembly.add_unilateral_limit(unit_limit_rows_[index].minimum,
                                                               {limit.data(), limit.size(), 1});
                    }
                    if (result != AssemblyDiagnostic::None) {
                        return result;
                    }
                }
                limit_row_work_[unit_offset + index] = 1.0;
                if (unit_limit_rows_[index].maximum.valid()) {
                    const double coordinate = snapshot_ready_
                                                  ? state_snapshot_.coordinates[index]
                                                  : ArticulationAccess::state(articulation_).coordinates[index];
                    const double margin = std::max(0.0, *limits.maximum - coordinate);
                    const std::array<double, 1> limit{
                        margin / unilateral_time_step_,
                    };
                    AssemblyDiagnostic result = assembly.add_unilateral_jacobian(
                        unit_limit_rows_[index].maximum,
                        dofs_,
                        ConstDenseMatrixView::row_major(limit_row_work_.data(), 1, generalized_count));
                    if (result == AssemblyDiagnostic::None) {
                        result = assembly.add_unilateral_limit(unit_limit_rows_[index].maximum,
                                                               {limit.data(), limit.size(), 1});
                    }
                    if (result != AssemblyDiagnostic::None) {
                        return result;
                    }
                }
                limit_row_work_[unit_offset + index] = 0.0;
            }
            return AssemblyDiagnostic::None;
        } catch (const std::exception& error) {
            std::fprintf(stderr, "[termin-qopt] articulation assembly failed: %s\n", error.what());
        } catch (...) {
            std::fprintf(stderr,
                         "[termin-qopt] articulation assembly failed with "
                         "unknown exception\n");
        }
        return AssemblyDiagnostic::InternalFailure;
    }

    AssemblyDiagnostic Articulation3DDynamicsContribution::begin_step() noexcept {
        invalidate_mass_matrix_cache();
        std::copy(ArticulationAccess::state(articulation_).coordinates.begin(),
                  ArticulationAccess::state(articulation_).coordinates.end(),
                  state_snapshot_.coordinates.begin());
        std::copy(ArticulationAccess::state(articulation_).velocities.begin(),
                  ArticulationAccess::state(articulation_).velocities.end(),
                  state_snapshot_.velocities.begin());
        std::copy(accelerations_.begin(), accelerations_.end(), acceleration_snapshot_.begin());
        std::copy(unit_limit_states_.begin(), unit_limit_states_.end(), unit_limit_state_snapshot_.begin());
        floating_base_snapshot_ = ArticulationAccess::floating_base(articulation_);
        snapshot_ready_ = true;
        return AssemblyDiagnostic::None;
    }

    void Articulation3DDynamicsContribution::commit_step() noexcept {
        snapshot_ready_ = false;
    }

    void Articulation3DDynamicsContribution::rollback_step() noexcept {
        if (snapshot_ready_) {
            std::copy(state_snapshot_.coordinates.begin(),
                      state_snapshot_.coordinates.end(),
                      ArticulationAccess::state(articulation_).coordinates.begin());
            std::copy(state_snapshot_.velocities.begin(),
                      state_snapshot_.velocities.end(),
                      ArticulationAccess::state(articulation_).velocities.begin());
            std::copy(acceleration_snapshot_.begin(), acceleration_snapshot_.end(), accelerations_.begin());
            std::copy(unit_limit_state_snapshot_.begin(), unit_limit_state_snapshot_.end(), unit_limit_states_.begin());
            ArticulationAccess::floating_base(articulation_) = floating_base_snapshot_;
            (void)ArticulationAccess::update_kinematics(articulation_);
            invalidate_mass_matrix_cache();
            snapshot_ready_ = false;
        }
    }

    void
    Articulation3DDynamicsContribution::apply_unilateral_solution(const DynamicsTopology&,
                                                                  const DynamicsUnilateralTopology& unilateral_topology,
                                                                  ConstDenseVectorView reactions,
                                                                  ConstDenseVectorView tight_mask) noexcept {
        if (unit_limit_rows_.size() != articulation_.units().size() ||
            unit_limit_states_.size() != articulation_.units().size()) {
            return;
        }
        for (std::size_t index = 0; index < articulation_.units().size(); ++index) {
            ArticulationUnitLimitState3D& state = unit_limit_states_[index];
            const auto read = [&](DynamicsUnilateralConstraintHandle handle, double& reaction, bool& active) {
                if (!handle.valid()) {
                    return;
                }
                const DenseBlockInfo info = unilateral_topology.constraint_topology().block_info(handle.block);
                if (!info.ok() || info.size != 1 || info.offset >= reactions.size || info.offset >= tight_mask.size) {
                    return;
                }
                reaction = reactions[info.offset];
                active = tight_mask[info.offset] == 1.0;
            };
            read(unit_limit_rows_[index].minimum, state.minimum_reaction, state.minimum_active);
            read(unit_limit_rows_[index].maximum, state.maximum_reaction, state.maximum_active);
        }
    }

    void Articulation3DDynamicsContribution::apply_solution(DynamicsAssemblyPhase phase,
                                                            const DynamicsTopology& topology,
                                                            ConstDenseVectorView values,
                                                            ConstDenseVectorView) noexcept {
        const DenseBlockInfo info = topology.dof_topology().block_info(dofs_.block);
        const std::size_t generalized_count = dof_count();
        const std::size_t unit_offset = ArticulationAccess::floating_base(articulation_).has_value() ? 6 : 0;
        if (!info.ok() || info.size != generalized_count) {
            return;
        }
        if (phase == DynamicsAssemblyPhase::Acceleration) {
            for (std::size_t index = 0; index < generalized_count; ++index) {
                accelerations_[index] = values[info.offset + index];
            }
        } else if (phase == DynamicsAssemblyPhase::VelocityProjection) {
            if (ArticulationAccess::floating_base(articulation_).has_value()) {
                ArticulationAccess::floating_base(articulation_)->velocity_local = read_screw_vw(values, info.offset);
            }
            for (std::size_t index = 0; index < articulation_.units().size(); ++index) {
                ArticulationAccess::state(articulation_).velocities[index] = values[info.offset + unit_offset + index];
            }
            (void)ArticulationAccess::update_kinematics(articulation_);
        }
    }

    AssemblyDiagnostic Articulation3DDynamicsContribution::write_velocity(const DynamicsTopology& topology,
                                                                          DenseVectorView destination) const noexcept {
        const DenseBlockInfo info = topology.dof_topology().block_info(dofs_.block);
        const std::size_t unit_offset = ArticulationAccess::floating_base(articulation_).has_value() ? 6 : 0;
        if (!info.ok() || info.size != dof_count()) {
            return AssemblyDiagnostic::InvalidBlock;
        }
        if (ArticulationAccess::floating_base(articulation_).has_value()) {
            write_screw_vw(ArticulationAccess::floating_base(articulation_)->velocity_local, destination, info.offset);
        }
        for (std::size_t index = 0; index < articulation_.units().size(); ++index) {
            destination[info.offset + unit_offset + index] = ArticulationAccess::state(articulation_).velocities[index];
        }
        return AssemblyDiagnostic::None;
    }

    AssemblyDiagnostic Articulation3DDynamicsContribution::set_velocity(const DynamicsTopology& topology,
                                                                        ConstDenseVectorView source) noexcept {
        const DenseBlockInfo info = topology.dof_topology().block_info(dofs_.block);
        const std::size_t unit_offset = ArticulationAccess::floating_base(articulation_).has_value() ? 6 : 0;
        if (!info.ok() || info.size != dof_count()) {
            return AssemblyDiagnostic::InvalidBlock;
        }
        if (ArticulationAccess::floating_base(articulation_).has_value()) {
            ArticulationAccess::floating_base(articulation_)->velocity_local = read_screw_vw(source, info.offset);
        }
        for (std::size_t index = 0; index < articulation_.units().size(); ++index) {
            ArticulationAccess::state(articulation_).velocities[index] = source[info.offset + unit_offset + index];
        }
        return finite(ArticulationAccess::state(articulation_).velocities) &&
                       (!ArticulationAccess::floating_base(articulation_).has_value() ||
                        ArticulationAccess::floating_base(articulation_)->velocity_local.is_finite()) &&
                       ArticulationAccess::update_kinematics(articulation_)
                   ? AssemblyDiagnostic::None
                   : AssemblyDiagnostic::NonFiniteContribution;
    }

    AssemblyDiagnostic Articulation3DDynamicsContribution::set_trial_configuration(
        const DynamicsTopology& topology, ConstDenseVectorView midpoint_velocity, double time_step) noexcept {
        invalidate_mass_matrix_cache();
        if (!snapshot_ready_ || !std::isfinite(time_step) || time_step <= 0.0) {
            return AssemblyDiagnostic::NonFiniteContribution;
        }
        const DenseBlockInfo info = topology.dof_topology().block_info(dofs_.block);
        const std::size_t unit_offset = ArticulationAccess::floating_base(articulation_).has_value() ? 6 : 0;
        if (!info.ok() || info.size != dof_count()) {
            return AssemblyDiagnostic::InvalidBlock;
        }
        if (ArticulationAccess::floating_base(articulation_).has_value()) {
            const termin::Screw3 velocity = read_screw_vw(midpoint_velocity, info.offset);
            ArticulationAccess::floating_base(articulation_)->pose_world =
                (floating_base_snapshot_->pose_world * termin::se3_exp(velocity * time_step)).normalized();
            ArticulationAccess::floating_base(articulation_)->velocity_local = velocity;
        }
        for (std::size_t index = 0; index < articulation_.units().size(); ++index) {
            const double velocity = midpoint_velocity[info.offset + unit_offset + index];
            ArticulationAccess::state(articulation_).coordinates[index] =
                state_snapshot_.coordinates[index] + time_step * velocity;
            ArticulationAccess::state(articulation_).velocities[index] = velocity;
        }
        return finite(ArticulationAccess::state(articulation_).coordinates) &&
                       finite(ArticulationAccess::state(articulation_).velocities) &&
                       ArticulationAccess::update_kinematics(articulation_)
                   ? AssemblyDiagnostic::None
                   : AssemblyDiagnostic::NonFiniteContribution;
    }

    AssemblyDiagnostic
    Articulation3DDynamicsContribution::write_corrected_midpoint_velocity(const DynamicsTopology& topology,
                                                                          ConstDenseVectorView midpoint_velocity,
                                                                          ConstDenseVectorView correction,
                                                                          double time_step,
                                                                          DenseVectorView destination) const noexcept {
        if (!std::isfinite(time_step) || time_step <= 0.0) {
            return AssemblyDiagnostic::NonFiniteContribution;
        }
        const DenseBlockInfo info = topology.dof_topology().block_info(dofs_.block);
        const std::size_t unit_offset = ArticulationAccess::floating_base(articulation_).has_value() ? 6 : 0;
        if (!info.ok() || info.size != dof_count()) {
            return AssemblyDiagnostic::InvalidBlock;
        }
        if (ArticulationAccess::floating_base(articulation_).has_value()) {
            const termin::Pose3 current_increment =
                termin::se3_exp(read_screw_vw(midpoint_velocity, info.offset) * time_step);
            const termin::Pose3 tangent_increment = termin::se3_exp(read_screw_vw(correction, info.offset));
            write_screw_vw(
                termin::se3_log(current_increment * tangent_increment) / time_step, destination, info.offset);
        }
        for (std::size_t index = 0; index < articulation_.units().size(); ++index) {
            destination[info.offset + unit_offset + index] = midpoint_velocity[info.offset + unit_offset + index] +
                                                             correction[info.offset + unit_offset + index] / time_step;
        }
        return AssemblyDiagnostic::None;
    }

} // namespace termin::physics_qopt
