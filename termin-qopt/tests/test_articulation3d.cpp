#include <termin/qopt/articulation3d.hpp>
#include <termin/qopt/multibody3d.hpp>

#include "test_check.hpp"

#include <algorithm>
#include <cmath>
#include <memory>
#include <numbers>
#include <vector>

using namespace termin;
using namespace termin::qopt;

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
            {0.01, kMass * kLength * kLength / 12.0, kMass * kLength * kLength / 12.0},
            Pose3::identity(),
        };
    }

    std::vector<ArticulationLink3D> double_pendulum_links()
    {
        return {
            {
                .parent_link = articulation_world_link,
                .parent_to_joint_zero = Pose3::identity(),
                .motion_twist_at_joint = {Vec3::unit_y(), Vec3::zero()},
                .joint_to_link = Pose3::translation(kHalfLength, 0.0, 0.0),
                .inertia = rod_inertia(),
                .diagnostic_name = "upper",
            },
            {
                .parent_link = 0,
                .parent_to_joint_zero = Pose3::translation(kHalfLength, 0.0, 0.0),
                .motion_twist_at_joint = {Vec3::unit_y(), Vec3::zero()},
                .joint_to_link = Pose3::translation(kHalfLength, 0.0, 0.0),
                .inertia = rod_inertia(),
                .diagnostic_name = "lower",
            },
        };
    }

    Articulation3DContribution articulation(Articulation3DState state)
    {
        return Articulation3DContribution(double_pendulum_links(),
                                          std::move(state),
                                          {0.0, 0.0, -kGravity},
                                          "reduced-double-pendulum");
    }

    struct AssembledSystem
    {
        std::vector<double> mass;
        std::vector<double> load;
    };

    AssembledSystem assemble(Articulation3DContribution& contribution)
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
        TERMIN_QOPT_CHECK(
            contribution.assemble(assembly, DynamicsAssemblyPhase::Acceleration) ==
            AssemblyDiagnostic::None);
        return result;
    }

    void check_near(double actual, double expected, double tolerance)
    {
        if (std::abs(actual - expected) > tolerance)
        {
            std::fprintf(stderr,
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
        Articulation3DContribution empty({}, {}, Vec3::zero(), "empty");
        TERMIN_QOPT_CHECK(empty.diagnostic() == Articulation3DDiagnostic::EmptyModel);

        auto links = double_pendulum_links();
        links[0].parent_link = 0;
        Articulation3DContribution invalid_parent(std::move(links),
                                                  {{0.0, 0.0}, {0.0, 0.0}});
        TERMIN_QOPT_CHECK(invalid_parent.diagnostic() ==
                          Articulation3DDiagnostic::InvalidParent);
    }

    void test_double_pendulum_equations()
    {
        constexpr double upper_angle = 0.4;
        constexpr double relative_angle = -0.3;
        auto contribution = articulation({{upper_angle, relative_angle}, {0.0, 0.0}});
        TERMIN_QOPT_CHECK(contribution.diagnostic() == Articulation3DDiagnostic::None);
        const AssembledSystem system = assemble(contribution);

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
        auto contribution = articulation({
            {upper_angle, relative_angle},
            {upper_velocity, relative_velocity},
        });
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

    void test_prismatic_joint_equations()
    {
        Articulation3DContribution contribution(
            {
                {
                    .parent_link = articulation_world_link,
                    .parent_to_joint_zero = Pose3::identity(),
                    .motion_twist_at_joint = {Vec3::zero(), Vec3::unit_z()},
                    .joint_to_link = Pose3::identity(),
                    .inertia = rod_inertia(),
                    .diagnostic_name = "slider",
                },
            },
            {{0.7}, {0.0}},
            {0.0, 0.0, -kGravity},
            "prismatic-articulation");
        const AssembledSystem system = assemble(contribution);
        check_near(system.mass[0], kMass, 1e-12);
        check_near(system.load[0], -kMass * kGravity, 1e-12);
        check_near(contribution.link_poses_world()[0].lin.z, 0.7, 1e-12);
    }

    void test_branching_forward_kinematics()
    {
        std::vector<ArticulationLink3D> links = double_pendulum_links();
        links.push_back({
            .parent_link = 0,
            .parent_to_joint_zero = Pose3::translation(kHalfLength, 0.0, 0.0),
            .motion_twist_at_joint = {Vec3::unit_z(), Vec3::zero()},
            .joint_to_link = Pose3::translation(0.0, kHalfLength, 0.0),
            .inertia = rod_inertia(),
            .diagnostic_name = "branch",
        });
        Articulation3DContribution contribution(std::move(links),
                                                {{0.2, -0.1, 0.3}, {0.4, -0.2, 0.1}},
                                                {0.0, 0.0, -kGravity},
                                                "branched-articulation");
        TERMIN_QOPT_CHECK(contribution.diagnostic() == Articulation3DDiagnostic::None);
        TERMIN_QOPT_CHECK(contribution.link_count() == 3);
        const std::vector<Pose3>& poses = contribution.link_poses_world();
        TERMIN_QOPT_CHECK(poses.size() == 3);
        const Vec3 common_joint = poses[0].transform_point({kHalfLength, 0.0, 0.0});
        check_near(
            (poses[1].transform_point({-kHalfLength, 0.0, 0.0}) - common_joint).norm(),
            0.0,
            1e-12);
        check_near(
            (poses[2].transform_point({0.0, -kHalfLength, 0.0}) - common_joint).norm(),
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

        Multibody3DSystem reduced_system;
        auto reduced =
            std::make_unique<Articulation3DContribution>(double_pendulum_links(),
                                                         initial_state,
                                                         Vec3{0.0, 0.0, -kGravity},
                                                         "reduced-double-pendulum");
        Articulation3DContribution* reduced_state = reduced.get();
        TERMIN_QOPT_CHECK(reduced_system.add_contribution(std::move(reduced)) ==
                          DynamicsSystemDiagnostic::None);
        TERMIN_QOPT_CHECK(reduced_system.finalize() == DynamicsSystemDiagnostic::None);

        const std::vector<Pose3> initial_poses = reduced_state->link_poses_world();
        Multibody3DSystem maximal_system;
        auto* upper = add(maximal_system,
                          std::make_unique<RigidBody3DContribution>(
                              rod_inertia(),
                              RigidBody3DState{initial_poses[0], Screw3::zero()},
                              Vec3{0.0, 0.0, -kGravity},
                              "maximal-upper"));
        auto* lower = add(maximal_system,
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
            std::make_unique<RevoluteJoint3DContribution>(*upper,
                                                          Vec3{kHalfLength, 0.0, 0.0},
                                                          Vec3::unit_y(),
                                                          *lower,
                                                          Vec3{-kHalfLength, 0.0, 0.0},
                                                          Vec3::unit_y(),
                                                          "maximal-middle-hinge"));
        TERMIN_QOPT_CHECK(maximal_system.finalize() == DynamicsSystemDiagnostic::None);

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

        const std::vector<Pose3>& reduced_poses = reduced_state->link_poses_world();
        check_near((reduced_poses[0].lin - upper->state().pose.lin).norm(), 0.0, 2e-5);
        check_near((reduced_poses[1].lin - lower->state().pose.lin).norm(), 0.0, 3e-5);
        check_near(
            rotation_error(reduced_poses[0].ang, upper->state().pose.ang), 0.0, 3e-5);
        check_near(
            rotation_error(reduced_poses[1].ang, lower->state().pose.ang), 0.0, 4e-5);

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
    test_double_pendulum_equations();
    test_velocity_bias();
    test_prismatic_joint_equations();
    test_branching_forward_kinematics();
    test_reduced_matches_maximal_double_pendulum();
    return 0;
}
