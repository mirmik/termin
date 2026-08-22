#include <termin/physics_qopt/multibody3d.hpp>

#include <termin/geom/mat33.hpp>
#include <termin/geom/mat66.hpp>
#include <termin/geom/se3.hpp>
#include <termin/geom/vec6.hpp>

#include <algorithm>
#include <array>
#include <cmath>
#include <cstdio>
#include <exception>
#include <utility>

namespace termin::physics_qopt {
    namespace {

        using PointJacobian = std::array<double, 18>;
        using RevoluteJacobian = std::array<double, 30>;

        struct HingeFrame {
            termin::Vec3 axis_a;
            termin::Vec3 axis_b;
            termin::Vec3 tangent_1;
            termin::Vec3 tangent_2;
        };

        bool finite(double value) noexcept {
            return std::isfinite(value);
        }

        bool finite(termin::Vec3 value) noexcept {
            return value.is_finite();
        }

        bool finite(termin::Quat value) noexcept {
            return value.is_finite();
        }

        bool finite(termin::Pose3 value) noexcept {
            return value.is_finite();
        }

        bool finite(termin::Screw3 value) noexcept {
            return value.is_finite();
        }

        bool finite(const RigidBody3DState& value) noexcept {
            return finite(value.pose) && finite(value.velocity_local);
        }

        double linf(termin::Vec3 value) noexcept {
            return std::max({std::abs(value.x), std::abs(value.y), std::abs(value.z)});
        }

        PointJacobian point_jacobian(termin::Vec3 radius) noexcept {
            return {
                1.0,
                0.0,
                0.0,
                0.0,
                radius.z,
                -radius.y,
                0.0,
                1.0,
                0.0,
                -radius.z,
                0.0,
                radius.x,
                0.0,
                0.0,
                1.0,
                radius.y,
                -radius.x,
                0.0,
            };
        }

        PointJacobian point_jacobian_local(termin::Vec3 radius_local, termin::Quat body_orientation) noexcept {
            const PointJacobian local = point_jacobian(radius_local);
            const termin::Mat33 rotation = termin::Mat33::rotation(body_orientation.normalized());
            PointJacobian result{};
            for (std::size_t row = 0; row < 3; ++row) {
                for (std::size_t column = 0; column < 6; ++column) {
                    for (std::size_t inner = 0; inner < 3; ++inner) {
                        result[row * 6 + column] +=
                            rotation(static_cast<int>(inner), static_cast<int>(row)) * local[inner * 6 + column];
                    }
                }
            }
            return result;
        }

        ConstDenseMatrixView view(const termin::Mat66& value) noexcept {
            return ConstDenseMatrixView::column_major(value.ptr(), 6, 6);
        }

        ConstDenseMatrixView view(const PointJacobian& v) noexcept {
            return ConstDenseMatrixView::row_major(v.data(), 3, 6);
        }

        ConstDenseMatrixView view(const RevoluteJacobian& v) noexcept {
            return ConstDenseMatrixView::row_major(v.data(), 5, 6);
        }

        ConstDenseVectorView view(const termin::Vec6& value) noexcept {
            return {value.ptr(), value.size(), 1};
        }

        termin::Screw3 read_screw_vw(ConstDenseVectorView value, std::size_t offset) noexcept {
            return {
                {value[offset + 3], value[offset + 4], value[offset + 5]},
                {value[offset], value[offset + 1], value[offset + 2]},
            };
        }

        void write_vw(termin::Screw3 value, DenseVectorView destination, std::size_t offset) noexcept {
            destination[offset] = value.lin.x;
            destination[offset + 1] = value.lin.y;
            destination[offset + 2] = value.lin.z;
            destination[offset + 3] = value.ang.x;
            destination[offset + 4] = value.ang.y;
            destination[offset + 5] = value.ang.z;
        }

        template <std::size_t Size> ConstDenseVectorView view(const std::array<double, Size>& v) noexcept {
            return {v.data(), v.size(), 1};
        }

        AssemblyDiagnostic first(AssemblyDiagnostic a, AssemblyDiagnostic b) noexcept {
            return a == AssemblyDiagnostic::None ? b : a;
        }

        termin::Vec3 point_velocity(const RigidBody3DContribution& body, termin::Vec3 local) noexcept {
            return body.state().velocity_local.velocity_at_offset(local).rotated_by(body.state().pose.ang).lin;
        }

        HingeFrame hinge_frame(termin::Vec3 axis_a, termin::Vec3 axis_b) noexcept {
            axis_a = axis_a.normalized();
            axis_b = axis_b.normalized();
            const termin::Vec3 reference =
                std::abs(axis_a.x) <= std::abs(axis_a.y) && std::abs(axis_a.x) <= std::abs(axis_a.z)
                    ? termin::Vec3::unit_x()
                    : (std::abs(axis_a.y) <= std::abs(axis_a.z) ? termin::Vec3::unit_y() : termin::Vec3::unit_z());
            const termin::Vec3 tangent_1 = axis_a.cross(reference).normalized();
            return {axis_a, axis_b, tangent_1, axis_a.cross(tangent_1).normalized()};
        }

        termin::Vec3 angular_axis_column(termin::Vec3 basis, termin::Vec3 a, termin::Vec3 b, bool first_body) noexcept {
            return first_body ? basis.cross(a).cross(b) : a.cross(basis.cross(b));
        }

        void set_orientation_rows(RevoluteJacobian& block,
                                  termin::Quat body_orientation,
                                  const HingeFrame& frame,
                                  bool first_body) noexcept {
            const std::array<termin::Vec3, 3> basis{
                termin::Vec3::unit_x(), termin::Vec3::unit_y(), termin::Vec3::unit_z()};
            for (std::size_t column = 0; column < 3; ++column) {
                const termin::Vec3 response =
                    angular_axis_column(body_orientation.rotate(basis[column]), frame.axis_a, frame.axis_b, first_body);
                block[3 * 6 + column + 3] = frame.tangent_1.dot(response);
                block[4 * 6 + column + 3] = frame.tangent_2.dot(response);
            }
        }

        RevoluteJacobian revolute_jacobian_local(termin::Vec3 radius_local,
                                                 termin::Quat body_orientation,
                                                 const HingeFrame& frame,
                                                 bool first_body) noexcept {
            RevoluteJacobian result{};
            const PointJacobian point = point_jacobian_local(radius_local, body_orientation);
            const double sign = first_body ? 1.0 : -1.0;
            for (std::size_t value = 0; value < point.size(); ++value) {
                result[(value / 6) * 6 + value % 6] = sign * point[value];
            }
            set_orientation_rows(result, body_orientation, frame, first_body);
            return result;
        }

        std::array<double, 2>
        orientation_acceleration_rhs(const HingeFrame& frame, termin::Vec3 omega_a, termin::Vec3 omega_b) noexcept {
            const termin::Vec3 da = omega_a.cross(frame.axis_a);
            const termin::Vec3 db = omega_b.cross(frame.axis_b);
            const termin::Vec3 bias =
                omega_a.cross(da).cross(frame.axis_b) + da.cross(db) * 2.0 + frame.axis_a.cross(omega_b.cross(db));
            return {-frame.tangent_1.dot(bias), -frame.tangent_2.dot(bias)};
        }

        termin::Screw3 read_reaction(DynamicsConstraintHandle handle,
                                     const DynamicsTopology& topology,
                                     ConstDenseVectorView reactions,
                                     termin::Vec3 torque = termin::Vec3::zero()) noexcept {
            const DenseBlockInfo info = topology.constraint_topology().block_info(handle.block);
            return {
                torque,
                {reactions[info.offset], reactions[info.offset + 1], reactions[info.offset + 2]},
            };
        }

    } // namespace

    std::string_view multibody3d_diagnostic_name(Multibody3DDiagnostic value) noexcept {
        switch (value) {
        case Multibody3DDiagnostic::None:
            return "none";
        case Multibody3DDiagnostic::InvalidMass:
            return "invalid_mass";
        case Multibody3DDiagnostic::InvalidInertia:
            return "invalid_inertia";
        case Multibody3DDiagnostic::NonFiniteInput:
            return "non_finite_input";
        case Multibody3DDiagnostic::InvalidJointAxis:
            return "invalid_joint_axis";
        }
        return "unknown";
    }

    RigidBody3DContribution::RigidBody3DContribution(termin::SpatialInertia3 inertia,
                                                     RigidBody3DState state,
                                                     termin::Vec3 gravity,
                                                     std::string_view name)
        : inertia_(inertia),
          state_(state),
          gravity_world_(gravity),
          diagnostic_name_(name) {
        if (!finite(inertia.mass) || inertia.mass <= 0.0) {
            diagnostic_ = Multibody3DDiagnostic::InvalidMass;
        } else if (!inertia.is_valid()) {
            diagnostic_ = Multibody3DDiagnostic::InvalidInertia;
        } else if (!finite(state) || state.pose.ang.norm() <= 1e-10 || !finite(gravity)) {
            diagnostic_ = Multibody3DDiagnostic::NonFiniteInput;
        } else {
            inertia_.inertia_frame.ang = inertia_.inertia_frame.ang.normalized();
            state_.pose.ang = state_.pose.ang.normalized();
        }
    }

    Multibody3DDiagnostic RigidBody3DContribution::diagnostic() const noexcept {
        return diagnostic_;
    }

    const termin::SpatialInertia3& RigidBody3DContribution::inertia() const noexcept {
        return inertia_;
    }

    const RigidBody3DState& RigidBody3DContribution::state() const noexcept {
        return state_;
    }

    const termin::Screw3& RigidBody3DContribution::twist_rate_at_body_origin_local() const noexcept {
        return twist_rate_at_body_origin_local_;
    }

    termin::Screw3 RigidBody3DContribution::velocity_at_body_origin_world() const noexcept {
        return state_.velocity_local.rotated_by(state_.pose.ang);
    }

    DynamicsDofHandle RigidBody3DContribution::dofs() const noexcept {
        return dofs_;
    }

    termin::Vec3 RigidBody3DContribution::gravity_world() const noexcept {
        return gravity_world_;
    }

    PointKinematics3DResult RigidBody3DContribution::point_kinematics(termin::Vec3 point_local) const noexcept {
        if (diagnostic_ != Multibody3DDiagnostic::None) {
            std::fprintf(stderr,
                         "[termin-qopt] cannot query point kinematics of invalid "
                         "rigid body '%s'\n",
                         diagnostic_name_.c_str());
            return {{}, PointKinematics3DDiagnostic::InvalidModel};
        }
        if (!point_local.is_finite()) {
            std::fprintf(stderr, "[termin-qopt] rejected non-finite rigid-body point\n");
            return {{}, PointKinematics3DDiagnostic::NonFinitePoint};
        }

        try {
            PointKinematics3D value;
            value.position_world = state_.pose.transform_point(point_local);
            value.velocity_world =
                state_.velocity_local.velocity_at_offset(point_local).rotated_by(state_.pose.ang).lin;
            value.dofs = dofs_;
            value.linear_jacobian_world_storage.assign(18, 0.0);

            const std::array<termin::Screw3, 6> basis{
                termin::Screw3{{}, termin::Vec3::unit_x()},
                termin::Screw3{{}, termin::Vec3::unit_y()},
                termin::Screw3{{}, termin::Vec3::unit_z()},
                termin::Screw3{termin::Vec3::unit_x(), {}},
                termin::Screw3{termin::Vec3::unit_y(), {}},
                termin::Screw3{termin::Vec3::unit_z(), {}},
            };
            for (std::size_t column = 0; column < basis.size(); ++column) {
                const termin::Vec3 response =
                    basis[column].velocity_at_offset(point_local).rotated_by(state_.pose.ang).lin;
                value.linear_jacobian_world_storage[column] = response.x;
                value.linear_jacobian_world_storage[6 + column] = response.y;
                value.linear_jacobian_world_storage[12 + column] = response.z;
            }
            if (!value.position_world.is_finite() || !value.velocity_world.is_finite()) {
                return {{}, PointKinematics3DDiagnostic::InvalidModel};
            }
            return {std::move(value), PointKinematics3DDiagnostic::None};
        } catch (const std::exception& error) {
            std::fprintf(stderr, "[termin-qopt] rigid-body point kinematics failed: %s\n", error.what());
        } catch (...) {
            std::fprintf(stderr,
                         "[termin-qopt] rigid-body point kinematics failed with "
                         "an unknown exception\n");
        }
        return {{}, PointKinematics3DDiagnostic::InternalFailure};
    }

    Multibody3DDiagnostic RigidBody3DContribution::set_state(RigidBody3DState value) noexcept {
        if (!finite(value) || value.pose.ang.norm() <= 1e-10) {
            std::fprintf(stderr, "[termin-qopt] rejected non-finite 3D body state\n");
            return Multibody3DDiagnostic::NonFiniteInput;
        }
        value.pose.ang = value.pose.ang.normalized();
        state_ = value;
        return Multibody3DDiagnostic::None;
    }

    Multibody3DDiagnostic RigidBody3DContribution::set_gravity_world(termin::Vec3 value) noexcept {
        if (!finite(value)) {
            std::fprintf(stderr, "[termin-qopt] rejected non-finite 3D gravity\n");
            return Multibody3DDiagnostic::NonFiniteInput;
        }
        gravity_world_ = value;
        return Multibody3DDiagnostic::None;
    }

    double RigidBody3DContribution::total_energy() const noexcept {
        const termin::Vec3 center = state_.pose.lin + state_.pose.ang.rotate(inertia_.inertia_frame.lin);
        const double kinetic = inertia_.kinetic_energy(state_.velocity_local);
        return kinetic - inertia_.mass * gravity_world_.dot(center);
    }

    AssemblyDiagnostic RigidBody3DContribution::register_topology(DynamicsTopology& topology) noexcept {
        if (diagnostic_ != Multibody3DDiagnostic::None) {
            std::fprintf(stderr,
                         "[termin-qopt] invalid rigid-body contribution '%s': %s\n",
                         diagnostic_name_.c_str(),
                         multibody3d_diagnostic_name(diagnostic_).data());
            return AssemblyDiagnostic::NonFiniteContribution;
        }
        const auto result = topology.register_dofs(6, diagnostic_name_);
        dofs_ = result.handle;
        return result.diagnostic;
    }

    AssemblyDiagnostic RigidBody3DContribution::assemble(DynamicsAssembly& assembly,
                                                         DynamicsAssemblyPhase phase) noexcept {
        const termin::Mat66 mass = inertia_.matrix_vw();
        AssemblyDiagnostic result = assembly.add_mass(dofs_, dofs_, view(mass));
        termin::Vec6 load;
        if (phase == DynamicsAssemblyPhase::Acceleration) {
            const termin::Screw3 momentum = inertia_.momentum(state_.velocity_local);
            const termin::Screw3 gravity_at_com_world{
                termin::Vec3::zero(),
                gravity_world_ * inertia_.mass,
            };
            const termin::Screw3 gravity_local = gravity_at_com_world.inverse_rotated_by(state_.pose.ang)
                                                     .wrench_at_origin_from_offset(inertia_.inertia_frame.lin);
            const termin::Screw3 load_local = gravity_local - state_.velocity_local.cross_force(momentum);
            load = termin::screw3_to_vec6_vw(load_local);
        } else if (phase == DynamicsAssemblyPhase::VelocityProjection) {
            load = mass.transform(termin::screw3_to_vec6_vw(state_.velocity_local));
        }
        return first(result, assembly.add_load(dofs_, view(load)));
    }

    AssemblyDiagnostic RigidBody3DContribution::begin_step() noexcept {
        state_snapshot_ = state_;
        twist_rate_snapshot_ = twist_rate_at_body_origin_local_;
        snapshot_ready_ = true;
        return AssemblyDiagnostic::None;
    }

    void RigidBody3DContribution::commit_step() noexcept {
        snapshot_ready_ = false;
    }

    void RigidBody3DContribution::rollback_step() noexcept {
        if (snapshot_ready_) {
            state_ = state_snapshot_;
            twist_rate_at_body_origin_local_ = twist_rate_snapshot_;
            snapshot_ready_ = false;
        }
    }

    void RigidBody3DContribution::apply_solution(DynamicsAssemblyPhase phase,
                                                 const DynamicsTopology& topology,
                                                 ConstDenseVectorView values,
                                                 ConstDenseVectorView) noexcept {
        const DenseBlockInfo info = topology.dof_topology().block_info(dofs_.block);
        const termin::Screw3 value = read_screw_vw(values, info.offset);
        if (phase == DynamicsAssemblyPhase::Acceleration)
            twist_rate_at_body_origin_local_ = value;
        else if (phase == DynamicsAssemblyPhase::VelocityProjection) {
            state_.velocity_local = value;
        }
    }

    AssemblyDiagnostic RigidBody3DContribution::write_velocity(const DynamicsTopology& topology,
                                                               DenseVectorView destination) const noexcept {
        const DenseBlockInfo info = topology.dof_topology().block_info(dofs_.block);
        write_vw(state_.velocity_local, destination, info.offset);
        return AssemblyDiagnostic::None;
    }

    AssemblyDiagnostic RigidBody3DContribution::set_velocity(const DynamicsTopology& topology,
                                                             ConstDenseVectorView source) noexcept {
        const DenseBlockInfo info = topology.dof_topology().block_info(dofs_.block);
        const RigidBody3DState candidate{
            state_.pose,
            read_screw_vw(source, info.offset),
        };
        if (!finite(candidate))
            return AssemblyDiagnostic::NonFiniteContribution;
        state_.velocity_local = candidate.velocity_local;
        return AssemblyDiagnostic::None;
    }

    AssemblyDiagnostic RigidBody3DContribution::set_trial_configuration(const DynamicsTopology& topology,
                                                                        ConstDenseVectorView midpoint_velocity,
                                                                        double time_step) noexcept {
        if (!snapshot_ready_ || !finite(time_step) || time_step <= 0.0) {
            return AssemblyDiagnostic::NonFiniteContribution;
        }
        const DenseBlockInfo info = topology.dof_topology().block_info(dofs_.block);
        const termin::Screw3 velocity = read_screw_vw(midpoint_velocity, info.offset);
        if (!finite(velocity)) {
            return AssemblyDiagnostic::NonFiniteContribution;
        }
        state_.pose = state_snapshot_.pose * termin::se3_exp(velocity * time_step);
        state_.pose.ang = state_.pose.ang.normalized();
        state_.velocity_local = velocity;
        return AssemblyDiagnostic::None;
    }

    AssemblyDiagnostic
    RigidBody3DContribution::write_corrected_midpoint_velocity(const DynamicsTopology& topology,
                                                               ConstDenseVectorView midpoint_velocity,
                                                               ConstDenseVectorView correction,
                                                               double time_step,
                                                               DenseVectorView destination) const noexcept {
        if (!finite(time_step) || time_step <= 0.0) {
            return AssemblyDiagnostic::NonFiniteContribution;
        }
        const DenseBlockInfo info = topology.dof_topology().block_info(dofs_.block);
        const termin::Pose3 current_increment =
            termin::se3_exp(read_screw_vw(midpoint_velocity, info.offset) * time_step);
        const termin::Pose3 tangent_increment = termin::se3_exp(read_screw_vw(correction, info.offset));
        const termin::Screw3 correction_twist = termin::se3_log(current_increment * tangent_increment);
        const termin::Screw3 corrected = correction_twist / time_step;
        write_vw(corrected, destination, info.offset);
        return AssemblyDiagnostic::None;
    }

    ForceOnBody3DContribution::ForceOnBody3DContribution(RigidBody3DContribution& body,
                                                         termin::Screw3 wrench_at_body_origin_world) noexcept
        : body_(&body),
          wrench_at_body_origin_world_(wrench_at_body_origin_world) {}

    void ForceOnBody3DContribution::set_wrench_at_body_origin_world(termin::Screw3 value) noexcept {
        wrench_at_body_origin_world_ = value;
    }

    const termin::Screw3& ForceOnBody3DContribution::wrench_at_body_origin_world() const noexcept {
        return wrench_at_body_origin_world_;
    }

    AssemblyDiagnostic ForceOnBody3DContribution::register_topology(DynamicsTopology&) noexcept {
        return AssemblyDiagnostic::None;
    }

    AssemblyDiagnostic ForceOnBody3DContribution::assemble(DynamicsAssembly& assembly,
                                                           DynamicsAssemblyPhase phase) noexcept {
        if (phase != DynamicsAssemblyPhase::Acceleration)
            return AssemblyDiagnostic::None;
        if (!finite(wrench_at_body_origin_world_)) {
            std::fprintf(stderr,
                         "[termin-qopt] force contribution contains a "
                         "non-finite wrench\n");
            return AssemblyDiagnostic::NonFiniteContribution;
        }
        const termin::Vec6 load =
            termin::screw3_to_vec6_vw(wrench_at_body_origin_world_.inverse_rotated_by(body_->state().pose.ang));
        return assembly.add_load(body_->dofs(), view(load));
    }

    FixedPointJoint3DContribution::FixedPointJoint3DContribution(RigidBody3DContribution& body,
                                                                 termin::Vec3 local,
                                                                 termin::Vec3 world,
                                                                 std::string_view name)
        : body_(&body),
          body_anchor_local_(local),
          world_anchor_(world),
          diagnostic_name_(name) {}

    const termin::Screw3& FixedPointJoint3DContribution::reaction_at_joint_anchor_world() const noexcept {
        return reaction_at_joint_anchor_world_;
    }

    AssemblyDiagnostic FixedPointJoint3DContribution::register_topology(DynamicsTopology& topology) noexcept {
        if (!finite(body_anchor_local_) || !finite(world_anchor_))
            return AssemblyDiagnostic::NonFiniteContribution;
        const auto result = topology.register_constraint(3, diagnostic_name_);
        constraint_ = result.handle;
        return result.diagnostic;
    }

    AssemblyDiagnostic FixedPointJoint3DContribution::assemble(DynamicsAssembly& assembly,
                                                               DynamicsAssemblyPhase phase) noexcept {
        const PointJacobian jacobian = point_jacobian_local(body_anchor_local_, body_->state().pose.ang);
        AssemblyDiagnostic result = assembly.add_constraint_jacobian(constraint_, body_->dofs(), view(jacobian));
        std::array<double, 3> rhs{};
        if (phase == DynamicsAssemblyPhase::Acceleration) {
            const termin::Screw3 velocity = body_->state().velocity_local;
            const termin::Vec3 bias = body_->state().pose.ang.rotate(
                velocity.ang.cross(velocity.lin) + velocity.ang.cross(velocity.ang.cross(body_anchor_local_)));
            rhs = {-bias.x, -bias.y, -bias.z};
        } else if (phase == DynamicsAssemblyPhase::PositionProjection) {
            const termin::Vec3 error = body_->state().pose.transform_point(body_anchor_local_) - world_anchor_;
            rhs = {-error.x, -error.y, -error.z};
        }
        return first(result, assembly.add_constraint_rhs(constraint_, view(rhs)));
    }

    AssemblyDiagnostic FixedPointJoint3DContribution::begin_step() noexcept {
        reaction_snapshot_ = reaction_at_joint_anchor_world_;
        return AssemblyDiagnostic::None;
    }

    void FixedPointJoint3DContribution::commit_step() noexcept {}

    void FixedPointJoint3DContribution::rollback_step() noexcept {
        reaction_at_joint_anchor_world_ = reaction_snapshot_;
    }

    void FixedPointJoint3DContribution::apply_solution(DynamicsAssemblyPhase phase,
                                                       const DynamicsTopology& topology,
                                                       ConstDenseVectorView,
                                                       ConstDenseVectorView reactions) noexcept {
        if (phase == DynamicsAssemblyPhase::Acceleration)
            reaction_at_joint_anchor_world_ = read_reaction(constraint_, topology, reactions);
    }

    double FixedPointJoint3DContribution::position_error_linf() const noexcept {
        return linf(body_->state().pose.transform_point(body_anchor_local_) - world_anchor_);
    }

    double FixedPointJoint3DContribution::velocity_error_linf() const noexcept {
        return linf(point_velocity(*body_, body_anchor_local_));
    }

    PointJoint3DContribution::PointJoint3DContribution(RigidBody3DContribution& a,
                                                       termin::Vec3 local_a,
                                                       RigidBody3DContribution& b,
                                                       termin::Vec3 local_b,
                                                       std::string_view name)
        : body_a_(&a),
          body_b_(&b),
          body_a_anchor_local_(local_a),
          body_b_anchor_local_(local_b),
          diagnostic_name_(name) {}

    const termin::Screw3& PointJoint3DContribution::reaction_at_joint_anchor_world() const noexcept {
        return reaction_at_joint_anchor_world_;
    }

    AssemblyDiagnostic PointJoint3DContribution::register_topology(DynamicsTopology& topology) noexcept {
        if (body_a_ == body_b_ || !finite(body_a_anchor_local_) || !finite(body_b_anchor_local_))
            return AssemblyDiagnostic::NonFiniteContribution;
        const auto result = topology.register_constraint(3, diagnostic_name_);
        constraint_ = result.handle;
        return result.diagnostic;
    }

    AssemblyDiagnostic PointJoint3DContribution::assemble(DynamicsAssembly& assembly,
                                                          DynamicsAssemblyPhase phase) noexcept {
        const PointJacobian ja = point_jacobian_local(body_a_anchor_local_, body_a_->state().pose.ang);
        PointJacobian jb = point_jacobian_local(body_b_anchor_local_, body_b_->state().pose.ang);
        for (double& value : jb)
            value = -value;
        AssemblyDiagnostic result = assembly.add_constraint_jacobian(constraint_, body_a_->dofs(), view(ja));
        result = first(result, assembly.add_constraint_jacobian(constraint_, body_b_->dofs(), view(jb)));
        std::array<double, 3> rhs{};
        if (phase == DynamicsAssemblyPhase::Acceleration) {
            const termin::Screw3 va = body_a_->state().velocity_local;
            const termin::Screw3 vb = body_b_->state().velocity_local;
            const termin::Vec3 ba = body_a_->state().pose.ang.rotate(va.ang.cross(va.lin) +
                                                                     va.ang.cross(va.ang.cross(body_a_anchor_local_)));
            const termin::Vec3 bb = body_b_->state().pose.ang.rotate(vb.ang.cross(vb.lin) +
                                                                     vb.ang.cross(vb.ang.cross(body_b_anchor_local_)));
            const termin::Vec3 value = -ba + bb;
            rhs = {value.x, value.y, value.z};
        } else if (phase == DynamicsAssemblyPhase::PositionProjection) {
            const termin::Vec3 error = body_a_->state().pose.transform_point(body_a_anchor_local_) -
                                       body_b_->state().pose.transform_point(body_b_anchor_local_);
            rhs = {-error.x, -error.y, -error.z};
        }
        return first(result, assembly.add_constraint_rhs(constraint_, view(rhs)));
    }

    AssemblyDiagnostic PointJoint3DContribution::begin_step() noexcept {
        reaction_snapshot_ = reaction_at_joint_anchor_world_;
        return AssemblyDiagnostic::None;
    }

    void PointJoint3DContribution::commit_step() noexcept {}

    void PointJoint3DContribution::rollback_step() noexcept {
        reaction_at_joint_anchor_world_ = reaction_snapshot_;
    }

    void PointJoint3DContribution::apply_solution(DynamicsAssemblyPhase phase,
                                                  const DynamicsTopology& topology,
                                                  ConstDenseVectorView,
                                                  ConstDenseVectorView reactions) noexcept {
        if (phase == DynamicsAssemblyPhase::Acceleration)
            reaction_at_joint_anchor_world_ = read_reaction(constraint_, topology, reactions);
    }

    double PointJoint3DContribution::position_error_linf() const noexcept {
        return linf(body_a_->state().pose.transform_point(body_a_anchor_local_) -
                    body_b_->state().pose.transform_point(body_b_anchor_local_));
    }

    double PointJoint3DContribution::velocity_error_linf() const noexcept {
        return linf(point_velocity(*body_a_, body_a_anchor_local_) - point_velocity(*body_b_, body_b_anchor_local_));
    }

    FixedRevoluteJoint3DContribution::FixedRevoluteJoint3DContribution(RigidBody3DContribution& body,
                                                                       termin::Vec3 anchor,
                                                                       termin::Vec3 axis,
                                                                       termin::Vec3 world_anchor,
                                                                       termin::Vec3 world_axis,
                                                                       std::string_view name)
        : body_(&body),
          body_anchor_local_(anchor),
          body_axis_local_(axis),
          world_anchor_(world_anchor),
          world_axis_(world_axis),
          diagnostic_name_(name) {
        if (!finite(anchor) || !finite(axis) || !finite(world_anchor) || !finite(world_axis)) {
            diagnostic_ = Multibody3DDiagnostic::NonFiniteInput;
        } else if (axis.norm() <= 1e-10 || world_axis.norm() <= 1e-10) {
            diagnostic_ = Multibody3DDiagnostic::InvalidJointAxis;
        } else {
            body_axis_local_ = axis.normalized();
            world_axis_ = world_axis.normalized();
            if (body_->state().pose.ang.rotate(body_axis_local_).dot(world_axis_) < 0.0)
                world_axis_ = -world_axis_;
        }
    }

    Multibody3DDiagnostic FixedRevoluteJoint3DContribution::diagnostic() const noexcept {
        return diagnostic_;
    }

    const termin::Screw3& FixedRevoluteJoint3DContribution::reaction_at_joint_anchor_world() const noexcept {
        return reaction_at_joint_anchor_world_;
    }

    AssemblyDiagnostic FixedRevoluteJoint3DContribution::register_topology(DynamicsTopology& topology) noexcept {
        if (diagnostic_ != Multibody3DDiagnostic::None)
            return AssemblyDiagnostic::NonFiniteContribution;
        const auto result = topology.register_constraint(5, diagnostic_name_);
        constraint_ = result.handle;
        return result.diagnostic;
    }

    AssemblyDiagnostic FixedRevoluteJoint3DContribution::assemble(DynamicsAssembly& assembly,
                                                                  DynamicsAssemblyPhase phase) noexcept {
        const HingeFrame frame = hinge_frame(body_->state().pose.ang.rotate(body_axis_local_), world_axis_);
        const RevoluteJacobian jacobian =
            revolute_jacobian_local(body_anchor_local_, body_->state().pose.ang, frame, true);
        AssemblyDiagnostic result = assembly.add_constraint_jacobian(constraint_, body_->dofs(), view(jacobian));
        std::array<double, 5> rhs{};
        if (phase == DynamicsAssemblyPhase::Acceleration) {
            const termin::Screw3 velocity = body_->state().velocity_local;
            const termin::Vec3 point = body_->state().pose.ang.rotate(
                velocity.ang.cross(velocity.lin) + velocity.ang.cross(velocity.ang.cross(body_anchor_local_)));
            const auto angular =
                orientation_acceleration_rhs(frame, body_->velocity_at_body_origin_world().ang, termin::Vec3::zero());
            rhs = {-point.x, -point.y, -point.z, angular[0], angular[1]};
        } else if (phase == DynamicsAssemblyPhase::PositionProjection) {
            const termin::Vec3 point = body_->state().pose.transform_point(body_anchor_local_) - world_anchor_;
            const termin::Vec3 angular = frame.axis_a.cross(frame.axis_b);
            rhs = {-point.x, -point.y, -point.z, -frame.tangent_1.dot(angular), -frame.tangent_2.dot(angular)};
        }
        return first(result, assembly.add_constraint_rhs(constraint_, view(rhs)));
    }

    AssemblyDiagnostic FixedRevoluteJoint3DContribution::begin_step() noexcept {
        reaction_snapshot_ = reaction_at_joint_anchor_world_;
        return AssemblyDiagnostic::None;
    }

    void FixedRevoluteJoint3DContribution::commit_step() noexcept {}

    void FixedRevoluteJoint3DContribution::rollback_step() noexcept {
        reaction_at_joint_anchor_world_ = reaction_snapshot_;
    }

    void FixedRevoluteJoint3DContribution::apply_solution(DynamicsAssemblyPhase phase,
                                                          const DynamicsTopology& topology,
                                                          ConstDenseVectorView,
                                                          ConstDenseVectorView reactions) noexcept {
        if (phase != DynamicsAssemblyPhase::Acceleration)
            return;
        const DenseBlockInfo info = topology.constraint_topology().block_info(constraint_.block);
        const HingeFrame frame = hinge_frame(body_->state().pose.ang.rotate(body_axis_local_), world_axis_);
        reaction_at_joint_anchor_world_ =
            read_reaction(constraint_,
                          topology,
                          reactions,
                          frame.tangent_1 * reactions[info.offset + 3] + frame.tangent_2 * reactions[info.offset + 4]);
    }

    double FixedRevoluteJoint3DContribution::position_error_linf() const noexcept {
        const HingeFrame frame = hinge_frame(body_->state().pose.ang.rotate(body_axis_local_), world_axis_);
        const termin::Vec3 point = body_->state().pose.transform_point(body_anchor_local_) - world_anchor_;
        const termin::Vec3 angular = frame.axis_a.cross(frame.axis_b);
        return std::max(linf(point),
                        std::max(std::abs(frame.tangent_1.dot(angular)), std::abs(frame.tangent_2.dot(angular))));
    }

    double FixedRevoluteJoint3DContribution::velocity_error_linf() const noexcept {
        const HingeFrame frame = hinge_frame(body_->state().pose.ang.rotate(body_axis_local_), world_axis_);
        const termin::Vec3 angular = body_->velocity_at_body_origin_world().ang.cross(frame.axis_a).cross(frame.axis_b);
        return std::max(linf(point_velocity(*body_, body_anchor_local_)),
                        std::max(std::abs(frame.tangent_1.dot(angular)), std::abs(frame.tangent_2.dot(angular))));
    }

    RevoluteJoint3DContribution::RevoluteJoint3DContribution(RigidBody3DContribution& a,
                                                             termin::Vec3 anchor_a,
                                                             termin::Vec3 axis_a,
                                                             RigidBody3DContribution& b,
                                                             termin::Vec3 anchor_b,
                                                             termin::Vec3 axis_b,
                                                             std::string_view name)
        : body_a_(&a),
          body_b_(&b),
          body_a_anchor_local_(anchor_a),
          body_a_axis_local_(axis_a),
          body_b_anchor_local_(anchor_b),
          body_b_axis_local_(axis_b),
          diagnostic_name_(name) {
        if (body_a_ == body_b_ || !finite(anchor_a) || !finite(anchor_b) || !finite(axis_a) || !finite(axis_b)) {
            diagnostic_ = Multibody3DDiagnostic::NonFiniteInput;
        } else if (axis_a.norm() <= 1e-10 || axis_b.norm() <= 1e-10) {
            diagnostic_ = Multibody3DDiagnostic::InvalidJointAxis;
        } else {
            body_a_axis_local_ = axis_a.normalized();
            body_b_axis_local_ = axis_b.normalized();
            if (body_a_->state()
                    .pose.ang.rotate(body_a_axis_local_)
                    .dot(body_b_->state().pose.ang.rotate(body_b_axis_local_)) < 0.0)
                body_b_axis_local_ = -body_b_axis_local_;
        }
    }

    Multibody3DDiagnostic RevoluteJoint3DContribution::diagnostic() const noexcept {
        return diagnostic_;
    }

    const termin::Screw3& RevoluteJoint3DContribution::reaction_at_joint_anchor_world() const noexcept {
        return reaction_at_joint_anchor_world_;
    }

    AssemblyDiagnostic RevoluteJoint3DContribution::register_topology(DynamicsTopology& topology) noexcept {
        if (diagnostic_ != Multibody3DDiagnostic::None)
            return AssemblyDiagnostic::NonFiniteContribution;
        const auto result = topology.register_constraint(5, diagnostic_name_);
        constraint_ = result.handle;
        return result.diagnostic;
    }

    AssemblyDiagnostic RevoluteJoint3DContribution::assemble(DynamicsAssembly& assembly,
                                                             DynamicsAssemblyPhase phase) noexcept {
        const HingeFrame frame = hinge_frame(body_a_->state().pose.ang.rotate(body_a_axis_local_),
                                             body_b_->state().pose.ang.rotate(body_b_axis_local_));
        const RevoluteJacobian ja =
            revolute_jacobian_local(body_a_anchor_local_, body_a_->state().pose.ang, frame, true);
        const RevoluteJacobian jb =
            revolute_jacobian_local(body_b_anchor_local_, body_b_->state().pose.ang, frame, false);
        AssemblyDiagnostic result = assembly.add_constraint_jacobian(constraint_, body_a_->dofs(), view(ja));
        result = first(result, assembly.add_constraint_jacobian(constraint_, body_b_->dofs(), view(jb)));
        std::array<double, 5> rhs{};
        if (phase == DynamicsAssemblyPhase::Acceleration) {
            const termin::Screw3 va = body_a_->state().velocity_local;
            const termin::Screw3 vb = body_b_->state().velocity_local;
            const termin::Vec3 ba = body_a_->state().pose.ang.rotate(va.ang.cross(va.lin) +
                                                                     va.ang.cross(va.ang.cross(body_a_anchor_local_)));
            const termin::Vec3 bb = body_b_->state().pose.ang.rotate(vb.ang.cross(vb.lin) +
                                                                     vb.ang.cross(vb.ang.cross(body_b_anchor_local_)));
            const termin::Vec3 point = -ba + bb;
            const auto angular = orientation_acceleration_rhs(
                frame, body_a_->velocity_at_body_origin_world().ang, body_b_->velocity_at_body_origin_world().ang);
            rhs = {point.x, point.y, point.z, angular[0], angular[1]};
        } else if (phase == DynamicsAssemblyPhase::PositionProjection) {
            const termin::Vec3 point = body_a_->state().pose.transform_point(body_a_anchor_local_) -
                                       body_b_->state().pose.transform_point(body_b_anchor_local_);
            const termin::Vec3 angular = frame.axis_a.cross(frame.axis_b);
            rhs = {-point.x, -point.y, -point.z, -frame.tangent_1.dot(angular), -frame.tangent_2.dot(angular)};
        }
        return first(result, assembly.add_constraint_rhs(constraint_, view(rhs)));
    }

    AssemblyDiagnostic RevoluteJoint3DContribution::begin_step() noexcept {
        reaction_snapshot_ = reaction_at_joint_anchor_world_;
        return AssemblyDiagnostic::None;
    }

    void RevoluteJoint3DContribution::commit_step() noexcept {}

    void RevoluteJoint3DContribution::rollback_step() noexcept {
        reaction_at_joint_anchor_world_ = reaction_snapshot_;
    }

    void RevoluteJoint3DContribution::apply_solution(DynamicsAssemblyPhase phase,
                                                     const DynamicsTopology& topology,
                                                     ConstDenseVectorView,
                                                     ConstDenseVectorView reactions) noexcept {
        if (phase != DynamicsAssemblyPhase::Acceleration)
            return;
        const DenseBlockInfo info = topology.constraint_topology().block_info(constraint_.block);
        const HingeFrame frame = hinge_frame(body_a_->state().pose.ang.rotate(body_a_axis_local_),
                                             body_b_->state().pose.ang.rotate(body_b_axis_local_));
        reaction_at_joint_anchor_world_ =
            read_reaction(constraint_,
                          topology,
                          reactions,
                          frame.tangent_1 * reactions[info.offset + 3] + frame.tangent_2 * reactions[info.offset + 4]);
    }

    double RevoluteJoint3DContribution::position_error_linf() const noexcept {
        const HingeFrame frame = hinge_frame(body_a_->state().pose.ang.rotate(body_a_axis_local_),
                                             body_b_->state().pose.ang.rotate(body_b_axis_local_));
        const termin::Vec3 point = body_a_->state().pose.transform_point(body_a_anchor_local_) -
                                   body_b_->state().pose.transform_point(body_b_anchor_local_);
        const termin::Vec3 angular = frame.axis_a.cross(frame.axis_b);
        return std::max(linf(point),
                        std::max(std::abs(frame.tangent_1.dot(angular)), std::abs(frame.tangent_2.dot(angular))));
    }

    double RevoluteJoint3DContribution::velocity_error_linf() const noexcept {
        const HingeFrame frame = hinge_frame(body_a_->state().pose.ang.rotate(body_a_axis_local_),
                                             body_b_->state().pose.ang.rotate(body_b_axis_local_));
        const termin::Vec3 angular =
            body_a_->velocity_at_body_origin_world().ang.cross(frame.axis_a).cross(frame.axis_b) +
            frame.axis_a.cross(body_b_->velocity_at_body_origin_world().ang.cross(frame.axis_b));
        return std::max(
            linf(point_velocity(*body_a_, body_a_anchor_local_) - point_velocity(*body_b_, body_b_anchor_local_)),
            std::max(std::abs(frame.tangent_1.dot(angular)), std::abs(frame.tangent_2.dot(angular))));
    }

} // namespace termin::physics_qopt
