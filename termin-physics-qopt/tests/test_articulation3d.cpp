#include <termin/physics_qopt/articulation3d_dynamics.hpp>
#include <termin/physics_qopt/contact3d.hpp>
#include <termin/physics_qopt/multibody3d.hpp>

#include "test_check.hpp"

#include <algorithm>
#include <array>
#include <cmath>
#include <memory>
#include <numbers>
#include <vector>

using namespace termin;
using namespace termin::physics_qopt;
using namespace termin::robotics;

namespace
{
    constexpr double kMass = 1.0;
    constexpr double kLength = 1.0;
    constexpr double kHalfLength = 0.5;
    constexpr double kGravity = 9.81;

    SpatialInertia3 rod_inertia()
    {
        return {
            kMass,
            {0.01,
             kMass * kLength * kLength / 12.0,
             kMass * kLength * kLength / 12.0},
            Pose3::identity(),
        };
    }

    std::vector<ArticulationUnit3D> double_pendulum_units()
    {
        return {
            {
                .parent_unit = articulation_root_frame,
                .parent_to_unit_zero =
                    Pose3::translation(kHalfLength, 0.0, 0.0),
                .motion_twist_at_unit =
                    Screw3{Vec3::unit_y(), Vec3::zero()}.adjoint_inv(
                        Pose3::translation(kHalfLength, 0.0, 0.0)),
                .inertia = rod_inertia(),
                .diagnostic_name = "upper",
            },
            {
                .parent_unit = 0,
                .parent_to_unit_zero = Pose3::translation(kLength, 0.0, 0.0),
                .motion_twist_at_unit =
                    Screw3{Vec3::unit_y(), Vec3::zero()}.adjoint_inv(
                        Pose3::translation(kHalfLength, 0.0, 0.0)),
                .inertia = rod_inertia(),
                .diagnostic_name = "lower",
            },
        };
    }

    struct AssembledSystem
    {
        std::vector<double> mass;
        std::vector<double> load;
    };

    AssembledSystem assemble(DynamicsContribution& contribution)
    {
        DynamicsTopology topology;
        TERMIN_QOPT_CHECK(contribution.register_topology(topology) ==
                          AssemblyDiagnostic::None);
        TERMIN_QOPT_CHECK(topology.finalize() == AssemblyDiagnostic::None);
        const std::size_t dofs = topology.dof_count();
        AssembledSystem result;
        result.mass.assign(dofs * dofs, 0.0);
        result.load.assign(dofs, 0.0);
        std::vector<double> jacobian;
        std::vector<double> rhs;
        DynamicsAssembly assembly(
            topology,
            {
                DenseMatrixView::row_major(result.mass.data(), dofs, dofs),
                {result.load.data(), result.load.size(), 1},
                DenseMatrixView::row_major(nullptr, 0, dofs),
                {nullptr, 0, 1},
            });
        TERMIN_QOPT_CHECK(assembly.valid());
        TERMIN_QOPT_CHECK(assembly.clear() == AssemblyDiagnostic::None);
        const AssemblyDiagnostic diagnostic = contribution.assemble(
            assembly, DynamicsAssemblyPhase::Acceleration);
        if (diagnostic != AssemblyDiagnostic::None)
        {
            std::fprintf(stderr,
                         "articulation assembly diagnostic=%s dofs=%zu\n",
                         assembly_diagnostic_name(diagnostic).data(),
                         dofs);
        }
        TERMIN_QOPT_CHECK(diagnostic == AssemblyDiagnostic::None);
        return result;
    }

    void check_near(double actual, double expected, double tolerance)
    {
        if (std::abs(actual - expected) > tolerance)
        {
            std::fprintf(
                stderr,
                "actual=%.17g expected=%.17g error=%.17g tolerance=%.17g\n",
                actual,
                expected,
                std::abs(actual - expected),
                tolerance);
        }
        TERMIN_QOPT_CHECK(std::abs(actual - expected) <= tolerance);
    }

    template <typename Contribution>
    Contribution* add(Multibody3DSystem& system,
                      std::unique_ptr<Contribution> contribution)
    {
        Contribution* result = contribution.get();
        TERMIN_QOPT_CHECK(system.add_contribution(std::move(contribution)) ==
                          DynamicsSystemDiagnostic::None);
        return result;
    }

    DynamicsSystemStepOptions options(double time_step)
    {
        return {
            .time_step = time_step,
            .position_tolerance = 1e-10,
            .velocity_tolerance = 1e-10,
            .max_position_iterations = 10,
            .qp_tolerance = {},
        };
    }

    double rotation_error(Quat a, Quat b)
    {
        return std::max({
            (a.rotate(Vec3::unit_x()) - b.rotate(Vec3::unit_x())).norm(),
            (a.rotate(Vec3::unit_y()) - b.rotate(Vec3::unit_y())).norm(),
            (a.rotate(Vec3::unit_z()) - b.rotate(Vec3::unit_z())).norm(),
        });
    }

    void test_model_validation()
    {
        Articulation3D empty({}, {}, "empty");
        TERMIN_QOPT_CHECK(empty.diagnostic() ==
                          Articulation3DDiagnostic::EmptyModel);

        auto units = double_pendulum_units();
        units[0].parent_unit = 0;
        Articulation3D invalid_parent(std::move(units),
                                      {{0.0, 0.0}, {0.0, 0.0}});
        TERMIN_QOPT_CHECK(invalid_parent.diagnostic() ==
                          Articulation3DDiagnostic::InvalidParent);

        units = double_pendulum_units();
        units[0].limits = {.minimum = 1.0, .maximum = -1.0};
        Articulation3D invalid_limits(std::move(units),
                                      {{0.0, 0.0}, {0.0, 0.0}});
        TERMIN_QOPT_CHECK(invalid_limits.diagnostic() ==
                          Articulation3DDiagnostic::InvalidUnitLimits);

        units = double_pendulum_units();
        units[0].limits.minimum = std::numeric_limits<double>::quiet_NaN();
        Articulation3D non_finite_limits(std::move(units),
                                         {{0.0, 0.0}, {0.0, 0.0}});
        TERMIN_QOPT_CHECK(non_finite_limits.diagnostic() ==
                          Articulation3DDiagnostic::InvalidUnitLimits);
    }

    void test_floating_base_matches_rigid_body()
    {
        const SpatialInertia3 inertia{
            2.0,
            {0.7, 0.9, 1.1},
            Pose3::translation(0.1, -0.2, 0.05),
        };
        const Pose3 pose{
            Quat::from_axis_angle(Vec3{1.0, 2.0, -1.0}.normalized(), 0.4),
            {0.3, -0.5, 1.7},
        };
        const Screw3 velocity{{0.2, -0.1, 0.3}, {0.4, 0.25, -0.15}};
        const Vec3 gravity{0.0, 0.0, -kGravity};

        Articulation3D floating_model(
            ArticulationFloatingBase3D{inertia, pose, velocity, "base"},
            {},
            {{}, {}},
            "floating-only");
        Articulation3DDynamicsContribution floating(
            floating_model, gravity, "floating-only-dynamics");
        RigidBody3DContribution rigid(
            inertia, RigidBody3DState{pose, velocity}, gravity, "rigid-oracle");
        TERMIN_QOPT_CHECK(floating.diagnostic() ==
                          Articulation3DDiagnostic::None);
        TERMIN_QOPT_CHECK(floating.has_floating_base());
        TERMIN_QOPT_CHECK(floating.unit_count() == 0);
        TERMIN_QOPT_CHECK(floating.dof_count() == 6);

        const AssembledSystem floating_system = assemble(floating);
        const AssembledSystem rigid_system = assemble(rigid);
        TERMIN_QOPT_CHECK(floating_system.mass.size() ==
                          rigid_system.mass.size());
        for (std::size_t index = 0; index < floating_system.mass.size();
             ++index)
        {
            check_near(
                floating_system.mass[index], rigid_system.mass[index], 1e-12);
        }
        for (std::size_t index = 0; index < floating_system.load.size();
             ++index)
        {
            check_near(
                floating_system.load[index], rigid_system.load[index], 1e-12);
        }
        check_near(floating.total_energy(), rigid.total_energy(), 1e-12);

        const Vec3 point_local{0.2, -0.3, 0.4};
        const PointKinematics3DResult floating_point =
            floating.floating_base_point_kinematics(point_local);
        const PointKinematics3DResult rigid_point =
            rigid.point_kinematics(point_local);
        TERMIN_QOPT_CHECK(floating_point.ok());
        TERMIN_QOPT_CHECK(rigid_point.ok());
        check_near((floating_point.value.position_world -
                    rigid_point.value.position_world)
                       .norm(),
                   0.0,
                   1e-12);
        check_near((floating_point.value.velocity_world -
                    rigid_point.value.velocity_world)
                       .norm(),
                   0.0,
                   1e-12);
        for (std::size_t index = 0;
             index < floating_point.value.linear_jacobian_world_storage.size();
             ++index)
        {
            check_near(
                floating_point.value.linear_jacobian_world_storage[index],
                rigid_point.value.linear_jacobian_world_storage[index],
                1e-12);
        }
        const ContactEndpoint3D base_endpoint =
            ContactEndpoint3D::articulation_base(floating, point_local);
        TERMIN_QOPT_CHECK(base_endpoint.valid());
        const PointKinematics3DResult endpoint_point =
            base_endpoint.point_kinematics();
        TERMIN_QOPT_CHECK(endpoint_point.ok());
        check_near((endpoint_point.value.velocity_world -
                    floating_point.value.velocity_world)
                       .norm(),
                   0.0,
                   1e-12);

        DynamicsTopology rollback_topology;
        TERMIN_QOPT_CHECK(floating.register_topology(rollback_topology) ==
                          AssemblyDiagnostic::None);
        TERMIN_QOPT_CHECK(rollback_topology.finalize() ==
                          AssemblyDiagnostic::None);
        TERMIN_QOPT_CHECK(floating.begin_step() == AssemblyDiagnostic::None);
        const std::array<double, 6> trial_velocity{
            0.8, -0.4, 0.2, 0.1, 0.3, -0.2};
        TERMIN_QOPT_CHECK(floating.set_trial_configuration(
                              rollback_topology,
                              {trial_velocity.data(), trial_velocity.size(), 1},
                              0.01) == AssemblyDiagnostic::None);
        TERMIN_QOPT_CHECK(
            (floating.floating_base()->pose_world.lin - pose.lin).norm() >
            1e-5);
        floating.rollback_step();
        check_near((floating.floating_base()->pose_world.lin - pose.lin).norm(),
                   0.0,
                   1e-12);
        check_near(
            rotation_error(floating.floating_base()->pose_world.ang, pose.ang),
            0.0,
            1e-12);

        Multibody3DSystem floating_dynamics;
        Articulation3D floating_step_model(
            ArticulationFloatingBase3D{inertia, pose, velocity, "base"},
            {},
            {{}, {}},
            "floating-step");
        auto* floating_state =
            add(floating_dynamics,
                std::make_unique<Articulation3DDynamicsContribution>(
                    floating_step_model, gravity, "floating-step"));
        Multibody3DSystem rigid_dynamics;
        auto* rigid_state = add(rigid_dynamics,
                                std::make_unique<RigidBody3DContribution>(
                                    inertia,
                                    RigidBody3DState{pose, velocity},
                                    gravity,
                                    "rigid-step"));
        TERMIN_QOPT_CHECK(floating_dynamics.finalize() ==
                          DynamicsSystemDiagnostic::None);
        TERMIN_QOPT_CHECK(rigid_dynamics.finalize() ==
                          DynamicsSystemDiagnostic::None);
        constexpr double time_step = 0.001;
        for (std::size_t step = 0; step < 10; ++step)
        {
            TERMIN_QOPT_CHECK(floating_dynamics.step(options(time_step)).ok());
            TERMIN_QOPT_CHECK(rigid_dynamics.step(options(time_step)).ok());
        }
        const ArticulationFloatingBase3D& result =
            *floating_state->floating_base();
        check_near(
            (result.pose_world.lin - rigid_state->state().pose.lin).norm(),
            0.0,
            1e-11);
        check_near(rotation_error(result.pose_world.ang,
                                  rigid_state->state().pose.ang),
                   0.0,
                   1e-11);
        check_near((result.velocity_local.ang -
                    rigid_state->state().velocity_local.ang)
                       .norm(),
                   0.0,
                   1e-11);
        check_near((result.velocity_local.lin -
                    rigid_state->state().velocity_local.lin)
                       .norm(),
                   0.0,
                   1e-11);
    }

    void test_floating_base_joint_coupling_and_point_jacobian()
    {
        const Screw3 base_velocity{{0.1, -0.2, 0.3}, {0.4, -0.1, 0.2}};
        Articulation3D articulation_model(
            ArticulationFloatingBase3D{
                SpatialInertia3{3.0, {1.0, 1.2, 1.4}, Pose3::identity()},
                {Quat::from_axis_angle(Vec3::unit_x(), 0.2), {0.3, 0.4, 1.0}},
                base_velocity,
                "base",
            },
            {
                {
                    .parent_unit = articulation_root_frame,
                    .parent_to_unit_zero = Pose3::translation(0.9, 0.0, 0.0),
                    .motion_twist_at_unit =
                        Screw3{Vec3::unit_y(), Vec3::zero()}.adjoint_inv(
                            Pose3::translation(0.5, 0.0, 0.0)),
                    .inertia = rod_inertia(),
                    .diagnostic_name = "arm",
                },
            },
            {{0.35}, {-0.6}},
            "floating-arm");
        Articulation3DDynamicsContribution articulation(
            articulation_model, {0.0, 0.0, -kGravity}, "floating-arm-dynamics");
        TERMIN_QOPT_CHECK(articulation.diagnostic() ==
                          Articulation3DDiagnostic::None);
        TERMIN_QOPT_CHECK(articulation.dof_count() == 7);
        const AssembledSystem system = assemble(articulation);
        TERMIN_QOPT_CHECK(system.mass.size() == 49);
        bool coupled = false;
        for (std::size_t row = 0; row < 7; ++row)
        {
            for (std::size_t column = 0; column < 7; ++column)
            {
                const double value = system.mass[row * 7 + column];
                TERMIN_QOPT_CHECK(std::isfinite(value));
                check_near(value, system.mass[column * 7 + row], 1e-12);
                if (column == 6 && row < 6 && std::abs(value) > 1e-8)
                {
                    coupled = true;
                }
            }
        }
        TERMIN_QOPT_CHECK(coupled);

        const PointKinematics3DResult point =
            articulation.point_kinematics(0, {0.2, -0.1, 0.3});
        TERMIN_QOPT_CHECK(point.ok());
        TERMIN_QOPT_CHECK(point.value.dof_count() == 7);
        const std::array<double, 7> generalized_velocity{
            base_velocity.lin.x,
            base_velocity.lin.y,
            base_velocity.lin.z,
            base_velocity.ang.x,
            base_velocity.ang.y,
            base_velocity.ang.z,
            -0.6,
        };
        Vec3 jacobian_velocity = Vec3::zero();
        for (std::size_t column = 0; column < 7; ++column)
        {
            jacobian_velocity.x +=
                point.value.linear_jacobian_world_storage[column] *
                generalized_velocity[column];
            jacobian_velocity.y +=
                point.value.linear_jacobian_world_storage[7 + column] *
                generalized_velocity[column];
            jacobian_velocity.z +=
                point.value.linear_jacobian_world_storage[14 + column] *
                generalized_velocity[column];
        }
        check_near((jacobian_velocity - point.value.velocity_world).norm(),
                   0.0,
                   1e-12);
    }

    void test_double_pendulum_equations()
    {
        constexpr double upper_angle = 0.4;
        constexpr double relative_angle = -0.3;
        Articulation3D model(double_pendulum_units(),
                             {{upper_angle, relative_angle}, {0.0, 0.0}},
                             "reduced-double-pendulum");
        Articulation3DDynamicsContribution contribution(model,
                                                        {0.0, 0.0, -kGravity});
        TERMIN_QOPT_CHECK(contribution.diagnostic() ==
                          Articulation3DDiagnostic::None);
        const AssembledSystem system = assemble(contribution);
        std::vector<double> model_mass;
        TERMIN_QOPT_CHECK(model.mass_matrix(model_mass));
        TERMIN_QOPT_CHECK(model_mass == system.mass);

        const double relative_cosine = std::cos(relative_angle);
        const double expected_m00 = 5.0 / 3.0 + relative_cosine;
        const double expected_m01 = 1.0 / 3.0 + 0.5 * relative_cosine;
        const double expected_m11 = 1.0 / 3.0;
        check_near(system.mass[0], expected_m00, 1e-12);
        check_near(system.mass[1], expected_m01, 1e-12);
        check_near(system.mass[2], expected_m01, 1e-12);
        check_near(system.mass[3], expected_m11, 1e-12);

        const double expected_load_0 =
            kGravity * (1.5 * std::cos(upper_angle) +
                        0.5 * std::cos(upper_angle + relative_angle));
        const double expected_load_1 =
            kGravity * 0.5 * std::cos(upper_angle + relative_angle);
        check_near(system.load[0], expected_load_0, 1e-11);
        check_near(system.load[1], expected_load_1, 1e-11);
    }

    void test_velocity_bias()
    {
        constexpr double upper_angle = 0.4;
        constexpr double relative_angle = -0.3;
        constexpr double upper_velocity = 1.2;
        constexpr double relative_velocity = -0.7;
        Articulation3D model(double_pendulum_units(),
                             {{upper_angle, relative_angle},
                              {upper_velocity, relative_velocity}},
                             "reduced-double-pendulum");
        Articulation3DDynamicsContribution contribution(model,
                                                        {0.0, 0.0, -kGravity});
        const AssembledSystem system = assemble(contribution);

        const double coupling = 0.5 * std::sin(relative_angle);
        const double coriolis_0 =
            -coupling * (2.0 * upper_velocity * relative_velocity +
                         relative_velocity * relative_velocity);
        const double coriolis_1 = coupling * upper_velocity * upper_velocity;
        const double gravity_load_0 =
            kGravity * (1.5 * std::cos(upper_angle) +
                        0.5 * std::cos(upper_angle + relative_angle));
        const double gravity_load_1 =
            kGravity * 0.5 * std::cos(upper_angle + relative_angle);
        check_near(system.load[0], gravity_load_0 - coriolis_0, 1e-11);
        check_near(system.load[1], gravity_load_1 - coriolis_1, 1e-11);
    }

    void test_mass_matrix_cache_tracks_configuration()
    {
        Articulation3D model(double_pendulum_units(),
                             {{0.4, -0.3}, {1.2, -0.7}},
                             "mass-cache");
        Articulation3DDynamicsContribution contribution(model,
                                                        {0.0, 0.0, -kGravity});
        contribution.reset_assembly_counters();

        const AssembledSystem first = assemble(contribution);
        const AssembledSystem repeated = assemble(contribution);
        TERMIN_QOPT_CHECK(first.mass == repeated.mass);
        ArticulationDynamicsAssemblyCounters counters =
            contribution.assembly_counters();
        TERMIN_QOPT_CHECK(counters.mass_matrix_evaluations == 1);
        TERMIN_QOPT_CHECK(counters.bias_evaluations == 2);

        Articulation3DState changed_state = contribution.state();
        changed_state.coordinates[1] += 0.2;
        TERMIN_QOPT_CHECK(contribution.set_state(std::move(changed_state)) ==
                          Articulation3DDiagnostic::None);
        const AssembledSystem changed = assemble(contribution);
        TERMIN_QOPT_CHECK(changed.mass != repeated.mass);
        counters = contribution.assembly_counters();
        TERMIN_QOPT_CHECK(counters.mass_matrix_evaluations == 2);
        TERMIN_QOPT_CHECK(counters.bias_evaluations == 3);
    }

    void test_endpoint_iterations_reuse_mass_matrix()
    {
        Articulation3D model(double_pendulum_units(),
                             {{0.4, -0.3}, {1.2, -0.7}},
                             "endpoint-mass-cache");
        Multibody3DSystem system;
        auto contribution =
            std::make_unique<Articulation3DDynamicsContribution>(
                model, Vec3{0.0, 0.0, -kGravity}, "endpoint-mass-cache");
        Articulation3DDynamicsContribution* state = contribution.get();
        TERMIN_QOPT_CHECK(system.add_contribution(std::move(contribution)) ==
                          DynamicsSystemDiagnostic::None);
        TERMIN_QOPT_CHECK(system.finalize() == DynamicsSystemDiagnostic::None);
        state->reset_assembly_counters();

        TERMIN_QOPT_CHECK(system.step(options(0.002)).ok());
        const ArticulationDynamicsAssemblyCounters counters =
            state->assembly_counters();
        TERMIN_QOPT_CHECK(counters.mass_matrix_evaluations == 2);
        TERMIN_QOPT_CHECK(counters.bias_evaluations >
                          counters.mass_matrix_evaluations);
    }

    void test_prismatic_joint_equations()
    {
        Articulation3D model(
            {
                {
                    .parent_unit = articulation_root_frame,
                    .parent_to_unit_zero = Pose3::identity(),
                    .motion_twist_at_unit = {Vec3::zero(), Vec3::unit_z()},
                    .inertia = rod_inertia(),
                    .diagnostic_name = "slider",
                },
            },
            {{0.7}, {0.0}},
            "prismatic-articulation");
        Articulation3DDynamicsContribution contribution(model,
                                                        {0.0, 0.0, -kGravity});
        const AssembledSystem system = assemble(contribution);
        check_near(system.mass[0], kMass, 1e-12);
        check_near(system.load[0], -kMass * kGravity, 1e-12);
        check_near(contribution.unit_poses_world()[0].lin.z, 0.7, 1e-12);
    }

    std::vector<ArticulationUnit3D> limited_unit(bool prismatic)
    {
        return {
            {
                .parent_unit = articulation_root_frame,
                .parent_to_unit_zero = Pose3::identity(),
                .motion_twist_at_unit =
                    prismatic ? Screw3{Vec3::zero(), Vec3::unit_z()}
                              : Screw3{Vec3::unit_y(), Vec3::zero()},
                .inertia = rod_inertia(),
                .limits = {.minimum = 0.0, .maximum = 1.0},
                .diagnostic_name =
                    prismatic ? "limited-slider" : "limited-hinge",
            },
        };
    }

    void test_joint_limits()
    {
        Articulation3D model(
            limited_unit(false), {{0.0}, {-2.0}}, "limited-revolute");
        Multibody3DSystem system;
        auto contribution =
            std::make_unique<Articulation3DDynamicsContribution>(
                model, Vec3::zero(), "limited-revolute");
        Articulation3DDynamicsContribution* state = contribution.get();
        TERMIN_QOPT_CHECK(system.add_contribution(std::move(contribution)) ==
                          DynamicsSystemDiagnostic::None);
        TERMIN_QOPT_CHECK(system.finalize() == DynamicsSystemDiagnostic::None);

        const double energy_before = state->total_energy();
        const DynamicsSystemStepResult lower_hit = system.step(options(0.01));
        TERMIN_QOPT_CHECK(lower_hit.ok());
        TERMIN_QOPT_CHECK(lower_hit.unilateral_constraint_count == 1);
        TERMIN_QOPT_CHECK(std::abs(state->state().velocities[0]) < 1e-10);
        TERMIN_QOPT_CHECK(state->unit_limit_states()[0].minimum_reaction > 0.0);
        TERMIN_QOPT_CHECK(state->unit_limit_states()[0].minimum_active);
        TERMIN_QOPT_CHECK(
            std::abs(state->unit_limit_states()[0].maximum_reaction) < 1e-12);
        TERMIN_QOPT_CHECK(state->unit_limit_states()[0].signed_effort() > 0.0);
        TERMIN_QOPT_CHECK(state->total_energy() <= energy_before + 1e-12);

        TERMIN_QOPT_CHECK(state->set_state({{0.0}, {1.0}}) ==
                          Articulation3DDiagnostic::None);
        const DynamicsSystemStepResult lower_release =
            system.step(options(0.01));
        TERMIN_QOPT_CHECK(lower_release.ok());
        TERMIN_QOPT_CHECK(lower_release.unilateral_constraint_count == 1);
        TERMIN_QOPT_CHECK(state->state().velocities[0] > 0.9);
        TERMIN_QOPT_CHECK(
            std::abs(state->unit_limit_states()[0].minimum_reaction) < 1e-12);
        TERMIN_QOPT_CHECK(!state->unit_limit_states()[0].minimum_active);

        TERMIN_QOPT_CHECK(state->set_state({{1.0}, {2.0}}) ==
                          Articulation3DDiagnostic::None);
        const double upper_energy_before = state->total_energy();
        const DynamicsSystemStepResult upper_hit = system.step(options(0.01));
        TERMIN_QOPT_CHECK(upper_hit.ok());
        TERMIN_QOPT_CHECK(upper_hit.unilateral_constraint_count == 1);
        TERMIN_QOPT_CHECK(std::abs(state->state().velocities[0]) < 1e-10);
        TERMIN_QOPT_CHECK(state->unit_limit_states()[0].maximum_reaction > 0.0);
        TERMIN_QOPT_CHECK(state->unit_limit_states()[0].maximum_active);
        TERMIN_QOPT_CHECK(state->unit_limit_states()[0].signed_effort() < 0.0);
        TERMIN_QOPT_CHECK(state->total_energy() <= upper_energy_before + 1e-12);

        TERMIN_QOPT_CHECK(state->set_state({{0.5}, {0.1}}) ==
                          Articulation3DDiagnostic::None);
        const DynamicsSystemStepResult inactive = system.step(options(0.01));
        TERMIN_QOPT_CHECK(inactive.ok());
        TERMIN_QOPT_CHECK(inactive.unilateral_constraint_count == 0);
        TERMIN_QOPT_CHECK(!state->unit_limit_states()[0].minimum_active);
        TERMIN_QOPT_CHECK(!state->unit_limit_states()[0].maximum_active);

        TERMIN_QOPT_CHECK(state->set_state({{0.05}, {-10.0}}) ==
                          Articulation3DDiagnostic::None);
        const DynamicsSystemStepResult predicted_hit =
            system.step(options(0.01));
        TERMIN_QOPT_CHECK(predicted_hit.ok());
        TERMIN_QOPT_CHECK(predicted_hit.unilateral_constraint_count == 1);
        check_near(state->state().velocities[0], -5.0, 1e-10);
        TERMIN_QOPT_CHECK(state->unit_limit_states()[0].minimum_reaction > 0.0);

        Articulation3D prismatic_model(
            limited_unit(true), {{1.0}, {1.5}}, "limited-prismatic");
        Multibody3DSystem prismatic_system;
        auto prismatic = std::make_unique<Articulation3DDynamicsContribution>(
            prismatic_model, Vec3::zero(), "limited-prismatic");
        Articulation3DDynamicsContribution* prismatic_state = prismatic.get();
        TERMIN_QOPT_CHECK(prismatic_system.add_contribution(std::move(
                              prismatic)) == DynamicsSystemDiagnostic::None);
        TERMIN_QOPT_CHECK(prismatic_system.finalize() ==
                          DynamicsSystemDiagnostic::None);
        TERMIN_QOPT_CHECK(prismatic_system.step(options(0.01)).ok());
        TERMIN_QOPT_CHECK(std::abs(prismatic_state->state().velocities[0]) <
                          1e-10);
        TERMIN_QOPT_CHECK(
            prismatic_state->unit_limit_states()[0].maximum_reaction > 0.0);

        auto no_limits = limited_unit(false);
        no_limits[0].limits = {};
        Articulation3D unlimited_model(
            std::move(no_limits), {{0.0}, {-2.0}}, "unlimited");
        Multibody3DSystem unlimited_system;
        auto unlimited = std::make_unique<Articulation3DDynamicsContribution>(
            unlimited_model, Vec3::zero(), "unlimited");
        TERMIN_QOPT_CHECK(unlimited_system.add_contribution(std::move(
                              unlimited)) == DynamicsSystemDiagnostic::None);
        TERMIN_QOPT_CHECK(unlimited_system.finalize() ==
                          DynamicsSystemDiagnostic::None);
        const DynamicsSystemStepResult unlimited_step =
            unlimited_system.step(options(0.01));
        TERMIN_QOPT_CHECK(unlimited_step.ok());
        TERMIN_QOPT_CHECK(unlimited_step.unilateral_constraint_count == 0);
    }

    void test_floating_base_free_motion_conserves_energy_and_momentum()
    {
        constexpr double mass = 2.0;
        const SpatialInertia3 inertia{
            mass,
            {1.0, 1.0, 1.0},
            Pose3::identity(),
        };
        const Screw3 velocity{{0.0, 0.0, 0.3}, {0.5, -0.2, 0.1}};
        Articulation3D model(
            ArticulationFloatingBase3D{
                inertia, Pose3::identity(), velocity, "free-base"},
            {},
            {{}, {}},
            "free-floating");
        Multibody3DSystem dynamics;
        auto* state = add(dynamics,
                          std::make_unique<Articulation3DDynamicsContribution>(
                              model, Vec3::zero(), "free-floating"));
        TERMIN_QOPT_CHECK(dynamics.finalize() ==
                          DynamicsSystemDiagnostic::None);
        const double initial_energy = state->total_energy();
        const Vec3 initial_linear_momentum = velocity.lin * mass;
        constexpr double time_step = 0.001;
        for (std::size_t step = 0; step < 1000; ++step)
        {
            TERMIN_QOPT_CHECK(dynamics.step(options(time_step)).ok());
        }
        const ArticulationFloatingBase3D& result = *state->floating_base();
        const Vec3 final_linear_momentum =
            result.pose_world.ang.rotate(result.velocity_local.lin) * mass;
        check_near(state->total_energy(), initial_energy, 1e-10);
        check_near((final_linear_momentum - initial_linear_momentum).norm(),
                   0.0,
                   1e-8);
    }

    void test_branching_forward_kinematics()
    {
        std::vector<ArticulationUnit3D> units = double_pendulum_units();
        units.push_back({
            .parent_unit = 0,
            .parent_to_unit_zero =
                Pose3::translation(kHalfLength, kHalfLength, 0.0),
            .motion_twist_at_unit =
                Screw3{Vec3::unit_z(), Vec3::zero()}.adjoint_inv(
                    Pose3::translation(0.0, kHalfLength, 0.0)),
            .inertia = rod_inertia(),
            .diagnostic_name = "branch",
        });
        Articulation3D model(std::move(units),
                             {{0.2, -0.1, 0.3}, {0.4, -0.2, 0.1}},
                             "branched-articulation");
        Articulation3DDynamicsContribution contribution(model,
                                                        {0.0, 0.0, -kGravity});
        TERMIN_QOPT_CHECK(contribution.diagnostic() ==
                          Articulation3DDiagnostic::None);
        TERMIN_QOPT_CHECK(contribution.unit_count() == 3);
        const std::vector<Pose3>& poses = contribution.unit_poses_world();
        TERMIN_QOPT_CHECK(poses.size() == 3);
        const Vec3 common_joint =
            poses[0].transform_point({kHalfLength, 0.0, 0.0});
        check_near(
            (poses[1].transform_point({-kHalfLength, 0.0, 0.0}) - common_joint)
                .norm(),
            0.0,
            1e-12);
        check_near(
            (poses[2].transform_point({0.0, -kHalfLength, 0.0}) - common_joint)
                .norm(),
            0.0,
            1e-12);

        const AssembledSystem system = assemble(contribution);
        for (std::size_t row = 0; row < 3; ++row)
        {
            TERMIN_QOPT_CHECK(system.mass[row * 3 + row] > 0.0);
            for (std::size_t column = 0; column < 3; ++column)
            {
                check_near(system.mass[row * 3 + column],
                           system.mass[column * 3 + row],
                           1e-12);
            }
        }
    }

    void test_reduced_matches_maximal_double_pendulum()
    {
        constexpr double upper_angle = 0.65;
        constexpr double relative_angle = -0.35;
        const Articulation3DState initial_state{
            {upper_angle, relative_angle},
            {0.0, 0.0},
        };

        Articulation3D reduced_model(
            double_pendulum_units(), initial_state, "reduced-double-pendulum");
        Multibody3DSystem reduced_system;
        auto reduced = std::make_unique<Articulation3DDynamicsContribution>(
            reduced_model,
            Vec3{0.0, 0.0, -kGravity},
            "reduced-double-pendulum");
        Articulation3DDynamicsContribution* reduced_state = reduced.get();
        TERMIN_QOPT_CHECK(reduced_system.add_contribution(std::move(reduced)) ==
                          DynamicsSystemDiagnostic::None);
        TERMIN_QOPT_CHECK(reduced_system.finalize() ==
                          DynamicsSystemDiagnostic::None);

        const std::vector<Pose3> initial_poses =
            reduced_state->unit_poses_world();
        Multibody3DSystem maximal_system;
        auto* upper =
            add(maximal_system,
                std::make_unique<RigidBody3DContribution>(
                    rod_inertia(),
                    RigidBody3DState{initial_poses[0], Screw3::zero()},
                    Vec3{0.0, 0.0, -kGravity},
                    "maximal-upper"));
        auto* lower =
            add(maximal_system,
                std::make_unique<RigidBody3DContribution>(
                    rod_inertia(),
                    RigidBody3DState{initial_poses[1], Screw3::zero()},
                    Vec3{0.0, 0.0, -kGravity},
                    "maximal-lower"));
        add(maximal_system,
            std::make_unique<FixedRevoluteJoint3DContribution>(
                *upper,
                Vec3{-kHalfLength, 0.0, 0.0},
                Vec3::unit_y(),
                Vec3::zero(),
                Vec3::unit_y(),
                "maximal-world-hinge"));
        add(maximal_system,
            std::make_unique<RevoluteJoint3DContribution>(
                *upper,
                Vec3{kHalfLength, 0.0, 0.0},
                Vec3::unit_y(),
                *lower,
                Vec3{-kHalfLength, 0.0, 0.0},
                Vec3::unit_y(),
                "maximal-middle-hinge"));
        TERMIN_QOPT_CHECK(maximal_system.finalize() ==
                          DynamicsSystemDiagnostic::None);

        constexpr double time_step = 0.001;
        constexpr std::size_t steps = 500;
        const double reduced_initial_energy = reduced_state->total_energy();
        const double maximal_initial_energy =
            upper->total_energy() + lower->total_energy();
        check_near(reduced_initial_energy, maximal_initial_energy, 1e-12);

        for (std::size_t step = 0; step < steps; ++step)
        {
            TERMIN_QOPT_CHECK(reduced_system.step(options(time_step)).ok());
            TERMIN_QOPT_CHECK(maximal_system.step(options(time_step)).ok());
        }

        const std::vector<Pose3>& reduced_poses =
            reduced_state->unit_poses_world();
        check_near(
            (reduced_poses[0].lin - upper->state().pose.lin).norm(), 0.0, 2e-5);
        check_near(
            (reduced_poses[1].lin - lower->state().pose.lin).norm(), 0.0, 3e-5);
        check_near(
            rotation_error(reduced_poses[0].ang, upper->state().pose.ang),
            0.0,
            3e-5);
        check_near(
            rotation_error(reduced_poses[1].ang, lower->state().pose.ang),
            0.0,
            4e-5);

        const double reduced_drift =
            std::abs(reduced_state->total_energy() - reduced_initial_energy) /
            std::max(1.0, std::abs(reduced_initial_energy));
        const double maximal_drift =
            std::abs(upper->total_energy() + lower->total_energy() -
                     maximal_initial_energy) /
            std::max(1.0, std::abs(maximal_initial_energy));
        TERMIN_QOPT_CHECK(reduced_drift < 2e-5);
        TERMIN_QOPT_CHECK(maximal_drift < 2e-5);
    }

} // namespace

int main()
{
    test_model_validation();
    test_floating_base_matches_rigid_body();
    test_floating_base_joint_coupling_and_point_jacobian();
    test_floating_base_free_motion_conserves_energy_and_momentum();
    test_double_pendulum_equations();
    test_velocity_bias();
    test_mass_matrix_cache_tracks_configuration();
    test_endpoint_iterations_reuse_mass_matrix();
    test_prismatic_joint_equations();
    test_joint_limits();
    test_branching_forward_kinematics();
    test_reduced_matches_maximal_double_pendulum();
    return 0;
}
