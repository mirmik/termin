#include <termin/physics_qopt/multibody2d.hpp>

#include <algorithm>
#include <array>
#include <atomic>
#include <cmath>
#include <cstdio>
#include <exception>
#include <limits>
#include <string>
#include <utility>
#include <variant>
#include <vector>

namespace termin::physics_qopt
{
    namespace
    {

        std::atomic<std::uint64_t> next_multibody_system_id{1};

        [[nodiscard]] bool finite(double value) noexcept
        {
            return std::isfinite(value);
        }

        [[nodiscard]] bool finite(termin::Vec2 value) noexcept
        {
            return finite(value.x) && finite(value.y);
        }

        [[nodiscard]] bool finite(RigidBody2DState state) noexcept
        {
            return finite(state.pose.ang) && finite(state.pose.lin) &&
                   finite(state.linear_velocity_world) &&
                   finite(state.angular_velocity);
        }

        [[nodiscard]] termin::Vec2 perpendicular(termin::Vec2 value) noexcept
        {
            return {-value.y, value.x};
        }

        [[nodiscard]] double cross(termin::Vec2 first,
                                   termin::Vec2 second) noexcept
        {
            return first.x * second.y - first.y * second.x;
        }

        [[nodiscard]] double linf(termin::Vec2 value) noexcept
        {
            return std::max(std::abs(value.x), std::abs(value.y));
        }

        [[nodiscard]] ConstDenseMatrixView
        matrix_view(const std::array<double, 9>& values) noexcept
        {
            return ConstDenseMatrixView::row_major(values.data(), 3, 3);
        }

        [[nodiscard]] ConstDenseMatrixView
        matrix_view(const std::array<double, 6>& values) noexcept
        {
            return ConstDenseMatrixView::row_major(values.data(), 2, 3);
        }

        [[nodiscard]] ConstDenseVectorView
        vector_view(const std::array<double, 3>& values) noexcept
        {
            return {values.data(), values.size(), 1};
        }

        [[nodiscard]] ConstDenseVectorView
        vector_view(const std::array<double, 2>& values) noexcept
        {
            return {values.data(), values.size(), 1};
        }

        [[nodiscard]] Multibody2DStepResult
        failure(QpStatus status,
                Multibody2DDiagnostic diagnostic,
                QpSolveResult dynamics = {}) noexcept
        {
            Multibody2DStepResult result;
            result.status = status;
            result.diagnostic = diagnostic;
            result.dynamics = dynamics;
            return result;
        }

    } // namespace

    struct Multibody2DSystem::Impl
    {
        struct Body
        {
            SpatialInertia2D inertia;
            RigidBody2DState state;
            RigidBody2DAcceleration acceleration;
            RigidBody2DWrench wrench;
            DynamicsDofHandle dofs;
            std::string name;
        };

        struct FixedPointJoint
        {
            std::size_t body = 0;
            termin::Vec2 body_anchor_local;
            termin::Vec2 world_anchor;
        };

        struct RevoluteJoint
        {
            std::size_t body_a = 0;
            std::size_t body_b = 0;
            termin::Vec2 body_a_anchor_local;
            termin::Vec2 body_b_anchor_local;
        };

        struct Joint
        {
            std::variant<FixedPointJoint, RevoluteJoint> model;
            DynamicsConstraintHandle constraint;
            termin::Vec2 reaction = termin::Vec2::zero();
            std::string name;
        };

        std::uint64_t id =
            next_multibody_system_id.fetch_add(1, std::memory_order_relaxed);
        DynamicsTopology topology;
        std::vector<Body> bodies;
        std::vector<Joint> joints;
        std::vector<double> mass;
        std::vector<double> load;
        std::vector<double> jacobian;
        std::vector<double> constraint_rhs;
        std::vector<double> acceleration;
        std::vector<double> reaction;
        bool finalized = false;

        [[nodiscard]] bool valid(RigidBody2DHandle handle) const noexcept
        {
            return handle.system_id == id && handle.index < bodies.size();
        }

        [[nodiscard]] bool valid(Joint2DHandle handle) const noexcept
        {
            return handle.system_id == id && handle.index < joints.size();
        }

        [[nodiscard]] std::array<double, 9>
        body_mass(const Body& body) const noexcept
        {
            const termin::Vec2 center = body.state.pose.rotate_vector(
                body.inertia.center_of_mass_local);
            const termin::Vec2 tangent = perpendicular(center);
            const double mass_value = body.inertia.mass;
            return {
                mass_value,
                0.0,
                mass_value * tangent.x,
                0.0,
                mass_value,
                mass_value * tangent.y,
                mass_value * tangent.x,
                mass_value * tangent.y,
                body.inertia.moment_at_center + mass_value * center.dot(center),
            };
        }

        [[nodiscard]] std::array<double, 3>
        body_load(const Body& body, termin::Vec2 gravity) const noexcept
        {
            const termin::Vec2 center = body.state.pose.rotate_vector(
                body.inertia.center_of_mass_local);
            const termin::Vec2 gravity_force = gravity * body.inertia.mass;
            const termin::Vec2 centrifugal =
                center * (body.inertia.mass * body.state.angular_velocity *
                          body.state.angular_velocity);
            const termin::Vec2 force =
                body.wrench.force_world + gravity_force + centrifugal;
            const double torque =
                body.wrench.torque_about_origin + cross(center, gravity_force);
            return {force.x, force.y, torque};
        }

        [[nodiscard]] std::array<double, 6>
        point_jacobian(const Body& body,
                       termin::Vec2 anchor_local) const noexcept
        {
            const termin::Vec2 radius =
                body.state.pose.rotate_vector(anchor_local);
            return {
                1.0,
                0.0,
                -radius.y,
                0.0,
                1.0,
                radius.x,
            };
        }

        [[nodiscard]] AssemblyDiagnostic assemble(DynamicsAssembly& assembly,
                                                  termin::Vec2 gravity) noexcept
        {
            AssemblyDiagnostic diagnostic = assembly.clear();
            if (diagnostic != AssemblyDiagnostic::None)
            {
                return diagnostic;
            }
            for (const Body& body : bodies)
            {
                const std::array<double, 9> mass_block = body_mass(body);
                diagnostic = assembly.add_mass(
                    body.dofs, body.dofs, matrix_view(mass_block));
                if (diagnostic != AssemblyDiagnostic::None)
                {
                    return diagnostic;
                }
                const std::array<double, 3> load_block =
                    body_load(body, gravity);
                diagnostic =
                    assembly.add_load(body.dofs, vector_view(load_block));
                if (diagnostic != AssemblyDiagnostic::None)
                {
                    return diagnostic;
                }
            }

            for (const Joint& joint : joints)
            {
                if (const auto* fixed =
                        std::get_if<FixedPointJoint>(&joint.model))
                {
                    const Body& body = bodies[fixed->body];
                    const std::array<double, 6> jacobian_block =
                        point_jacobian(body, fixed->body_anchor_local);
                    diagnostic = assembly.add_constraint_jacobian(
                        joint.constraint,
                        body.dofs,
                        matrix_view(jacobian_block));
                    if (diagnostic != AssemblyDiagnostic::None)
                    {
                        return diagnostic;
                    }
                    const termin::Vec2 radius =
                        body.state.pose.rotate_vector(fixed->body_anchor_local);
                    const double omega = body.state.angular_velocity;
                    const std::array<double, 2> rhs{
                        omega * omega * radius.x,
                        omega * omega * radius.y,
                    };
                    diagnostic = assembly.add_constraint_rhs(joint.constraint,
                                                             vector_view(rhs));
                }
                else
                {
                    const auto& revolute = std::get<RevoluteJoint>(joint.model);
                    const Body& body_a = bodies[revolute.body_a];
                    const Body& body_b = bodies[revolute.body_b];
                    const std::array<double, 6> jacobian_a =
                        point_jacobian(body_a, revolute.body_a_anchor_local);
                    std::array<double, 6> jacobian_b =
                        point_jacobian(body_b, revolute.body_b_anchor_local);
                    for (double& value : jacobian_b)
                    {
                        value = -value;
                    }
                    diagnostic = assembly.add_constraint_jacobian(
                        joint.constraint, body_a.dofs, matrix_view(jacobian_a));
                    if (diagnostic != AssemblyDiagnostic::None)
                    {
                        return diagnostic;
                    }
                    diagnostic = assembly.add_constraint_jacobian(
                        joint.constraint, body_b.dofs, matrix_view(jacobian_b));
                    if (diagnostic != AssemblyDiagnostic::None)
                    {
                        return diagnostic;
                    }
                    const termin::Vec2 radius_a =
                        body_a.state.pose.rotate_vector(
                            revolute.body_a_anchor_local);
                    const termin::Vec2 radius_b =
                        body_b.state.pose.rotate_vector(
                            revolute.body_b_anchor_local);
                    const double omega_a = body_a.state.angular_velocity;
                    const double omega_b = body_b.state.angular_velocity;
                    const termin::Vec2 rhs_value =
                        radius_a * (omega_a * omega_a) -
                        radius_b * (omega_b * omega_b);
                    const std::array<double, 2> rhs{rhs_value.x, rhs_value.y};
                    diagnostic = assembly.add_constraint_rhs(joint.constraint,
                                                             vector_view(rhs));
                }
                if (diagnostic != AssemblyDiagnostic::None)
                {
                    return diagnostic;
                }
            }
            return AssemblyDiagnostic::None;
        }

        [[nodiscard]] termin::Vec2
        position_error(const Joint& joint) const noexcept
        {
            if (const auto* fixed = std::get_if<FixedPointJoint>(&joint.model))
            {
                const Body& body = bodies[fixed->body];
                return body.state.pose.transform_point(
                           fixed->body_anchor_local) -
                       fixed->world_anchor;
            }
            const auto& revolute = std::get<RevoluteJoint>(joint.model);
            return bodies[revolute.body_a].state.pose.transform_point(
                       revolute.body_a_anchor_local) -
                   bodies[revolute.body_b].state.pose.transform_point(
                       revolute.body_b_anchor_local);
        }

        [[nodiscard]] termin::Vec2
        velocity_error(const Joint& joint) const noexcept
        {
            const auto point_velocity = [](const Body& body, termin::Vec2 local)
            {
                const termin::Vec2 radius =
                    body.state.pose.rotate_vector(local);
                return body.state.linear_velocity_world +
                       perpendicular(radius) * body.state.angular_velocity;
            };
            if (const auto* fixed = std::get_if<FixedPointJoint>(&joint.model))
            {
                return point_velocity(bodies[fixed->body],
                                      fixed->body_anchor_local);
            }
            const auto& revolute = std::get<RevoluteJoint>(joint.model);
            return point_velocity(bodies[revolute.body_a],
                                  revolute.body_a_anchor_local) -
                   point_velocity(bodies[revolute.body_b],
                                  revolute.body_b_anchor_local);
        }

        [[nodiscard]] double max_position_error() const noexcept
        {
            double result = 0.0;
            for (const Joint& joint : joints)
            {
                result = std::max(result, linf(position_error(joint)));
            }
            return result;
        }

        [[nodiscard]] double max_velocity_error() const noexcept
        {
            double result = 0.0;
            for (const Joint& joint : joints)
            {
                result = std::max(result, linf(velocity_error(joint)));
            }
            return result;
        }

        void apply_generalized_delta(ConstDenseVectorView delta,
                                     bool velocity) noexcept
        {
            for (std::size_t body_index = 0; body_index < bodies.size();
                 ++body_index)
            {
                Body& body = bodies[body_index];
                const DenseBlockInfo info =
                    topology.dof_topology().block_info(body.dofs.block);
                if (velocity)
                {
                    body.state.linear_velocity_world.x = delta[info.offset];
                    body.state.linear_velocity_world.y = delta[info.offset + 1];
                    body.state.angular_velocity = delta[info.offset + 2];
                }
                else
                {
                    body.state.pose.lin.x += delta[info.offset];
                    body.state.pose.lin.y += delta[info.offset + 1];
                    body.state.pose.ang += delta[info.offset + 2];
                    body.state.pose.normalize_angle();
                }
            }
        }

        [[nodiscard]] QpSolveResult
        project_positions(DynamicsAssembly& assembly,
                          QpTolerance tolerance) noexcept
        {
            std::vector<double> target(constraint_rhs.size());
            for (const Joint& joint : joints)
            {
                const DenseBlockInfo info =
                    topology.constraint_topology().block_info(
                        joint.constraint.block);
                const termin::Vec2 error = position_error(joint);
                target[info.offset] = -error.x;
                target[info.offset + 1] = -error.y;
            }
            std::vector<double> gradient(load.size(), 0.0);
            std::vector<double> delta(load.size());
            std::vector<double> dual(constraint_rhs.size());
            ConstDynamicsSystemView system = assembly.system();
            const QpSolveResult result = solve_equality_qp(
                {
                    system.mass,
                    {gradient.data(), gradient.size(), 1},
                    system.constraint_jacobian,
                    {target.data(), target.size(), 1},
                },
                {
                    {delta.data(), delta.size(), 1},
                    {dual.data(), dual.size(), 1},
                },
                tolerance);
            if (result.status == QpStatus::Optimal)
            {
                apply_generalized_delta({delta.data(), delta.size(), 1}, false);
            }
            return result;
        }

        [[nodiscard]] QpSolveResult
        project_velocities(DynamicsAssembly& assembly,
                           QpTolerance tolerance) noexcept
        {
            std::vector<double> current(load.size());
            for (const Body& body : bodies)
            {
                const DenseBlockInfo info =
                    topology.dof_topology().block_info(body.dofs.block);
                current[info.offset] = body.state.linear_velocity_world.x;
                current[info.offset + 1] = body.state.linear_velocity_world.y;
                current[info.offset + 2] = body.state.angular_velocity;
            }
            ConstDynamicsSystemView system = assembly.system();
            std::vector<double> target_load(load.size(), 0.0);
            for (std::size_t row = 0; row < system.mass.rows; ++row)
            {
                for (std::size_t column = 0; column < system.mass.columns;
                     ++column)
                {
                    target_load[row] +=
                        system.mass(row, column) * current[column];
                }
            }
            std::vector<double> projected(load.size());
            std::vector<double> projected_reaction(constraint_rhs.size());
            std::vector<double> zero_rhs(constraint_rhs.size(), 0.0);
            const QpSolveResult constrained = solve_constrained_dynamics(
                {
                    system.mass,
                    {target_load.data(), target_load.size(), 1},
                    system.constraint_jacobian,
                    {zero_rhs.data(), zero_rhs.size(), 1},
                },
                {
                    {projected.data(), projected.size(), 1},
                    {projected_reaction.data(), projected_reaction.size(), 1},
                },
                tolerance);
            if (constrained.status == QpStatus::Optimal)
            {
                apply_generalized_delta({projected.data(), projected.size(), 1},
                                        true);
            }
            return constrained;
        }
    };

    std::string_view
    multibody2d_diagnostic_name(Multibody2DDiagnostic diagnostic) noexcept
    {
        switch (diagnostic)
        {
        case Multibody2DDiagnostic::None:
            return "none";
        case Multibody2DDiagnostic::ModelFinalized:
            return "model_finalized";
        case Multibody2DDiagnostic::ModelNotFinalized:
            return "model_not_finalized";
        case Multibody2DDiagnostic::InvalidBody:
            return "invalid_body";
        case Multibody2DDiagnostic::InvalidJoint:
            return "invalid_joint";
        case Multibody2DDiagnostic::InvalidMass:
            return "invalid_mass";
        case Multibody2DDiagnostic::InvalidInertia:
            return "invalid_inertia";
        case Multibody2DDiagnostic::NonFiniteInput:
            return "non_finite_input";
        case Multibody2DDiagnostic::DuplicateBody:
            return "duplicate_body";
        case Multibody2DDiagnostic::InvalidTimeStep:
            return "invalid_time_step";
        case Multibody2DDiagnostic::InvalidProjectionOptions:
            return "invalid_projection_options";
        case Multibody2DDiagnostic::AssemblyFailure:
            return "assembly_failure";
        case Multibody2DDiagnostic::DynamicsFailure:
            return "dynamics_failure";
        case Multibody2DDiagnostic::PositionProjectionFailure:
            return "position_projection_failure";
        case Multibody2DDiagnostic::VelocityProjectionFailure:
            return "velocity_projection_failure";
        case Multibody2DDiagnostic::InternalFailure:
            return "internal_failure";
        }
        return "unknown";
    }

    Multibody2DSystem::Multibody2DSystem() : impl_(std::make_unique<Impl>()) {}

    Multibody2DSystem::~Multibody2DSystem() = default;
    Multibody2DSystem::Multibody2DSystem(Multibody2DSystem&&) noexcept =
        default;
    Multibody2DSystem&
    Multibody2DSystem::operator=(Multibody2DSystem&&) noexcept = default;

    Multibody2DRegistrationResult<RigidBody2DHandle>
    Multibody2DSystem::add_body(SpatialInertia2D inertia,
                                RigidBody2DState initial_state,
                                std::string_view diagnostic_name) noexcept
    {
        if (impl_ == nullptr)
        {
            return {{}, Multibody2DDiagnostic::InternalFailure};
        }
        if (impl_->finalized)
        {
            return {{}, Multibody2DDiagnostic::ModelFinalized};
        }
        if (!finite(inertia.mass) || inertia.mass <= 0.0)
        {
            return {{}, Multibody2DDiagnostic::InvalidMass};
        }
        if (!finite(inertia.moment_at_center) ||
            inertia.moment_at_center <= 0.0)
        {
            return {{}, Multibody2DDiagnostic::InvalidInertia};
        }
        if (!finite(inertia.center_of_mass_local) || !finite(initial_state))
        {
            return {{}, Multibody2DDiagnostic::NonFiniteInput};
        }

        const auto registration =
            impl_->topology.register_dofs(3, diagnostic_name);
        if (!registration.ok())
        {
            return {{}, Multibody2DDiagnostic::DuplicateBody};
        }
        try
        {
            const std::size_t index = impl_->bodies.size();
            impl_->bodies.push_back({
                inertia,
                initial_state,
                {},
                {},
                registration.handle,
                std::string(diagnostic_name),
            });
            return {{impl_->id, index}, Multibody2DDiagnostic::None};
        }
        catch (const std::exception& error)
        {
            std::fprintf(
                stderr, "[termin-qopt] add 2D body failed: %s\n", error.what());
        }
        catch (...)
        {
            std::fprintf(
                stderr,
                "[termin-qopt] add 2D body failed with an unknown exception\n");
        }
        return {{}, Multibody2DDiagnostic::InternalFailure};
    }

    Multibody2DRegistrationResult<Joint2DHandle>
    Multibody2DSystem::add_fixed_point_joint(
        RigidBody2DHandle body,
        termin::Vec2 body_anchor_local,
        termin::Vec2 world_anchor,
        std::string_view diagnostic_name) noexcept
    {
        if (impl_ == nullptr)
        {
            return {{}, Multibody2DDiagnostic::InternalFailure};
        }
        if (impl_->finalized)
        {
            return {{}, Multibody2DDiagnostic::ModelFinalized};
        }
        if (!impl_->valid(body))
        {
            return {{}, Multibody2DDiagnostic::InvalidBody};
        }
        if (!finite(body_anchor_local) || !finite(world_anchor))
        {
            return {{}, Multibody2DDiagnostic::NonFiniteInput};
        }
        const auto registration =
            impl_->topology.register_constraint(2, diagnostic_name);
        if (!registration.ok())
        {
            return {{}, Multibody2DDiagnostic::InvalidJoint};
        }
        try
        {
            const std::size_t index = impl_->joints.size();
            impl_->joints.push_back({
                Impl::FixedPointJoint{
                    body.index,
                    body_anchor_local,
                    world_anchor,
                },
                registration.handle,
                {},
                std::string(diagnostic_name),
            });
            return {{impl_->id, index}, Multibody2DDiagnostic::None};
        }
        catch (const std::exception& error)
        {
            std::fprintf(stderr,
                         "[termin-qopt] add fixed 2D joint failed: %s\n",
                         error.what());
        }
        catch (...)
        {
            std::fprintf(stderr,
                         "[termin-qopt] add fixed 2D joint failed with an "
                         "unknown exception\n");
        }
        return {{}, Multibody2DDiagnostic::InternalFailure};
    }

    Multibody2DRegistrationResult<Joint2DHandle>
    Multibody2DSystem::add_revolute_joint(
        RigidBody2DHandle body_a,
        termin::Vec2 body_a_anchor_local,
        RigidBody2DHandle body_b,
        termin::Vec2 body_b_anchor_local,
        std::string_view diagnostic_name) noexcept
    {
        if (impl_ == nullptr)
        {
            return {{}, Multibody2DDiagnostic::InternalFailure};
        }
        if (impl_->finalized)
        {
            return {{}, Multibody2DDiagnostic::ModelFinalized};
        }
        if (!impl_->valid(body_a) || !impl_->valid(body_b) ||
            body_a.index == body_b.index)
        {
            return {{}, Multibody2DDiagnostic::InvalidBody};
        }
        if (!finite(body_a_anchor_local) || !finite(body_b_anchor_local))
        {
            return {{}, Multibody2DDiagnostic::NonFiniteInput};
        }
        const auto registration =
            impl_->topology.register_constraint(2, diagnostic_name);
        if (!registration.ok())
        {
            return {{}, Multibody2DDiagnostic::InvalidJoint};
        }
        try
        {
            const std::size_t index = impl_->joints.size();
            impl_->joints.push_back({
                Impl::RevoluteJoint{
                    body_a.index,
                    body_b.index,
                    body_a_anchor_local,
                    body_b_anchor_local,
                },
                registration.handle,
                {},
                std::string(diagnostic_name),
            });
            return {{impl_->id, index}, Multibody2DDiagnostic::None};
        }
        catch (const std::exception& error)
        {
            std::fprintf(stderr,
                         "[termin-qopt] add revolute 2D joint failed: %s\n",
                         error.what());
        }
        catch (...)
        {
            std::fprintf(stderr,
                         "[termin-qopt] add revolute 2D joint failed with an "
                         "unknown exception\n");
        }
        return {{}, Multibody2DDiagnostic::InternalFailure};
    }

    Multibody2DDiagnostic Multibody2DSystem::finalize() noexcept
    {
        if (impl_ == nullptr)
        {
            return Multibody2DDiagnostic::InternalFailure;
        }
        if (impl_->finalized)
        {
            return Multibody2DDiagnostic::ModelFinalized;
        }
        if (impl_->bodies.empty())
        {
            return Multibody2DDiagnostic::InvalidBody;
        }
        try
        {
            const std::size_t dofs = impl_->topology.dof_count();
            const std::size_t constraints = impl_->topology.constraint_count();
            std::vector<double> mass(dofs * dofs, 0.0);
            std::vector<double> load(dofs, 0.0);
            std::vector<double> jacobian(constraints * dofs, 0.0);
            std::vector<double> constraint_rhs(constraints, 0.0);
            std::vector<double> acceleration(dofs, 0.0);
            std::vector<double> reaction(constraints, 0.0);
            if (impl_->topology.finalize() != AssemblyDiagnostic::None)
            {
                return Multibody2DDiagnostic::AssemblyFailure;
            }
            impl_->mass = std::move(mass);
            impl_->load = std::move(load);
            impl_->jacobian = std::move(jacobian);
            impl_->constraint_rhs = std::move(constraint_rhs);
            impl_->acceleration = std::move(acceleration);
            impl_->reaction = std::move(reaction);
            impl_->finalized = true;
            return Multibody2DDiagnostic::None;
        }
        catch (const std::exception& error)
        {
            std::fprintf(stderr,
                         "[termin-qopt] finalize 2D model failed: %s\n",
                         error.what());
        }
        catch (...)
        {
            std::fprintf(stderr,
                         "[termin-qopt] finalize 2D model failed with an "
                         "unknown exception\n");
        }
        return Multibody2DDiagnostic::InternalFailure;
    }

    bool Multibody2DSystem::finalized() const noexcept
    {
        return impl_ != nullptr && impl_->finalized;
    }

    std::size_t Multibody2DSystem::body_count() const noexcept
    {
        return impl_ == nullptr ? 0 : impl_->bodies.size();
    }

    std::size_t Multibody2DSystem::joint_count() const noexcept
    {
        return impl_ == nullptr ? 0 : impl_->joints.size();
    }

    Multibody2DDiagnostic
    Multibody2DSystem::set_body_state(RigidBody2DHandle body,
                                      RigidBody2DState state) noexcept
    {
        if (impl_ == nullptr || !impl_->valid(body))
        {
            return Multibody2DDiagnostic::InvalidBody;
        }
        if (!finite(state))
        {
            return Multibody2DDiagnostic::NonFiniteInput;
        }
        impl_->bodies[body.index].state = state;
        return Multibody2DDiagnostic::None;
    }

    Multibody2DDiagnostic
    Multibody2DSystem::set_body_wrench(RigidBody2DHandle body,
                                       RigidBody2DWrench wrench) noexcept
    {
        if (impl_ == nullptr || !impl_->valid(body))
        {
            return Multibody2DDiagnostic::InvalidBody;
        }
        if (!finite(wrench.force_world) || !finite(wrench.torque_about_origin))
        {
            return Multibody2DDiagnostic::NonFiniteInput;
        }
        impl_->bodies[body.index].wrench = wrench;
        return Multibody2DDiagnostic::None;
    }

    RigidBody2DState
    Multibody2DSystem::body_state(RigidBody2DHandle body) const noexcept
    {
        if (impl_ == nullptr || !impl_->valid(body))
        {
            return {};
        }
        return impl_->bodies[body.index].state;
    }

    RigidBody2DAcceleration
    Multibody2DSystem::body_acceleration(RigidBody2DHandle body) const noexcept
    {
        if (impl_ == nullptr || !impl_->valid(body))
        {
            return {};
        }
        return impl_->bodies[body.index].acceleration;
    }

    termin::Vec2
    Multibody2DSystem::joint_reaction(Joint2DHandle joint) const noexcept
    {
        if (impl_ == nullptr || !impl_->valid(joint))
        {
            return termin::Vec2::zero();
        }
        return impl_->joints[joint.index].reaction;
    }

    Multibody2DStepResult
    Multibody2DSystem::step(termin::Vec2 gravity_world,
                            Multibody2DStepOptions options) noexcept
    {
        if (impl_ == nullptr || !impl_->finalized)
        {
            return failure(QpStatus::InvalidInput,
                           Multibody2DDiagnostic::ModelNotFinalized);
        }
        if (!finite(gravity_world))
        {
            return failure(QpStatus::InvalidInput,
                           Multibody2DDiagnostic::NonFiniteInput);
        }
        if (!finite(options.time_step) || options.time_step <= 0.0)
        {
            return failure(QpStatus::InvalidInput,
                           Multibody2DDiagnostic::InvalidTimeStep);
        }
        if (!finite(options.position_tolerance) ||
            !finite(options.velocity_tolerance) ||
            options.position_tolerance < 0.0 ||
            options.velocity_tolerance < 0.0 ||
            (!impl_->joints.empty() && options.max_position_iterations == 0))
        {
            return failure(QpStatus::InvalidInput,
                           Multibody2DDiagnostic::InvalidProjectionOptions);
        }

        std::vector<Impl::Body> original_bodies;
        std::vector<Impl::Joint> original_joints;
        std::vector<double> original_acceleration;
        std::vector<double> original_reaction;
        bool snapshot_ready = false;
        const auto restore = [&]() noexcept
        {
            if (!snapshot_ready)
            {
                return;
            }
            impl_->bodies = std::move(original_bodies);
            impl_->joints = std::move(original_joints);
            impl_->acceleration = std::move(original_acceleration);
            impl_->reaction = std::move(original_reaction);
            snapshot_ready = false;
        };

        try
        {
            original_bodies = impl_->bodies;
            original_joints = impl_->joints;
            original_acceleration = impl_->acceleration;
            original_reaction = impl_->reaction;
            snapshot_ready = true;
            DynamicsAssembly assembly(
                impl_->topology,
                {
                    DenseMatrixView::row_major(impl_->mass.data(),
                                               impl_->topology.dof_count(),
                                               impl_->topology.dof_count()),
                    {impl_->load.data(), impl_->load.size(), 1},
                    DenseMatrixView::row_major(
                        impl_->jacobian.data(),
                        impl_->topology.constraint_count(),
                        impl_->topology.dof_count()),
                    {
                        impl_->constraint_rhs.data(),
                        impl_->constraint_rhs.size(),
                        1,
                    },
                });
            if (!assembly.valid() || impl_->assemble(assembly, gravity_world) !=
                                         AssemblyDiagnostic::None)
            {
                return failure(QpStatus::InvalidInput,
                               Multibody2DDiagnostic::AssemblyFailure);
            }

            const QpSolveResult dynamics = solve_constrained_dynamics(
                assembly.system(),
                {
                    {
                        impl_->acceleration.data(),
                        impl_->acceleration.size(),
                        1,
                    },
                    {impl_->reaction.data(), impl_->reaction.size(), 1},
                },
                options.qp_tolerance);
            if (dynamics.status != QpStatus::Optimal)
            {
                return failure(dynamics.status,
                               Multibody2DDiagnostic::DynamicsFailure,
                               dynamics);
            }

            for (Impl::Body& body : impl_->bodies)
            {
                const DenseBlockInfo info =
                    impl_->topology.dof_topology().block_info(body.dofs.block);
                body.acceleration.linear_world = {
                    impl_->acceleration[info.offset],
                    impl_->acceleration[info.offset + 1],
                };
                body.acceleration.angular =
                    impl_->acceleration[info.offset + 2];
                body.state.linear_velocity_world +=
                    body.acceleration.linear_world * options.time_step;
                body.state.angular_velocity +=
                    body.acceleration.angular * options.time_step;
                body.state.pose.lin +=
                    body.state.linear_velocity_world * options.time_step;
                body.state.pose.ang +=
                    body.state.angular_velocity * options.time_step;
                body.state.pose.normalize_angle();
            }
            for (Impl::Joint& joint : impl_->joints)
            {
                const DenseBlockInfo info =
                    impl_->topology.constraint_topology().block_info(
                        joint.constraint.block);
                joint.reaction = {
                    impl_->reaction[info.offset],
                    impl_->reaction[info.offset + 1],
                };
            }

            Multibody2DStepResult result;
            result.status = QpStatus::Optimal;
            result.diagnostic = Multibody2DDiagnostic::None;
            result.dynamics = dynamics;

            for (std::size_t iteration = 0;
                 iteration < options.max_position_iterations;
                 ++iteration)
            {
                result.position_constraint_linf = impl_->max_position_error();
                if (result.position_constraint_linf <=
                    options.position_tolerance)
                {
                    break;
                }
                if (impl_->assemble(assembly, gravity_world) !=
                    AssemblyDiagnostic::None)
                {
                    restore();
                    return failure(QpStatus::InvalidInput,
                                   Multibody2DDiagnostic::AssemblyFailure,
                                   dynamics);
                }
                const QpSolveResult projection =
                    impl_->project_positions(assembly, options.qp_tolerance);
                ++result.position_iterations;
                if (projection.status != QpStatus::Optimal)
                {
                    restore();
                    return failure(
                        projection.status,
                        Multibody2DDiagnostic::PositionProjectionFailure,
                        dynamics);
                }
            }
            result.position_constraint_linf = impl_->max_position_error();
            if (result.position_constraint_linf > options.position_tolerance)
            {
                restore();
                return failure(QpStatus::NumericalFailure,
                               Multibody2DDiagnostic::PositionProjectionFailure,
                               dynamics);
            }

            if (impl_->assemble(assembly, gravity_world) !=
                AssemblyDiagnostic::None)
            {
                restore();
                return failure(QpStatus::InvalidInput,
                               Multibody2DDiagnostic::AssemblyFailure,
                               dynamics);
            }
            const QpSolveResult velocity_projection =
                impl_->project_velocities(assembly, options.qp_tolerance);
            if (velocity_projection.status != QpStatus::Optimal)
            {
                restore();
                return failure(velocity_projection.status,
                               Multibody2DDiagnostic::VelocityProjectionFailure,
                               dynamics);
            }
            result.velocity_constraint_linf = impl_->max_velocity_error();
            if (result.velocity_constraint_linf > options.velocity_tolerance)
            {
                restore();
                return failure(QpStatus::NumericalFailure,
                               Multibody2DDiagnostic::VelocityProjectionFailure,
                               dynamics);
            }
            snapshot_ready = false;
            return result;
        }
        catch (const std::exception& error)
        {
            restore();
            std::fprintf(stderr,
                         "[termin-qopt] 2D multibody step failed: %s\n",
                         error.what());
        }
        catch (...)
        {
            restore();
            std::fprintf(stderr,
                         "[termin-qopt] 2D multibody step failed with an "
                         "unknown exception\n");
        }
        return failure(QpStatus::NumericalFailure,
                       Multibody2DDiagnostic::InternalFailure);
    }

    double Multibody2DSystem::max_position_constraint_error() const noexcept
    {
        return impl_ == nullptr ? std::numeric_limits<double>::infinity()
                                : impl_->max_position_error();
    }

    double Multibody2DSystem::max_velocity_constraint_error() const noexcept
    {
        return impl_ == nullptr ? std::numeric_limits<double>::infinity()
                                : impl_->max_velocity_error();
    }

    double
    Multibody2DSystem::total_energy(termin::Vec2 gravity_world) const noexcept
    {
        if (impl_ == nullptr || !finite(gravity_world))
        {
            return std::numeric_limits<double>::quiet_NaN();
        }
        double energy = 0.0;
        for (const Impl::Body& body : impl_->bodies)
        {
            const termin::Vec2 center = body.state.pose.rotate_vector(
                body.inertia.center_of_mass_local);
            const termin::Vec2 center_velocity =
                body.state.linear_velocity_world +
                perpendicular(center) * body.state.angular_velocity;
            const termin::Vec2 center_world = body.state.pose.lin + center;
            energy +=
                0.5 * body.inertia.mass * center_velocity.dot(center_velocity);
            energy += 0.5 * body.inertia.moment_at_center *
                      body.state.angular_velocity * body.state.angular_velocity;
            energy -= body.inertia.mass * gravity_world.dot(center_world);
        }
        return energy;
    }

} // namespace termin::physics_qopt
