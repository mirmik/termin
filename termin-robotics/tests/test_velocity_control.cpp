#include <termin/robotics/velocity_control.hpp>

#include "test_check.hpp"

#include <array>
#include <cmath>
#include <vector>

using namespace termin;
using namespace termin::robotics;

namespace {
    constexpr double tolerance = 1e-8;

    SpatialInertia3 unit_inertia() {
        return {1.0, {0.2, 0.3, 0.4}, Pose3::identity()};
    }

    ArticulationUnit3D revolute_unit(std::size_t parent, std::string name) {
        return {
            .parent_unit = parent,
            .parent_to_unit_zero = Pose3::translation(1.0, 0.0, 0.0),
            .motion_twist_at_unit = Screw3{Vec3::unit_z(), Vec3::zero()}.adjoint_inv(Pose3::translation(1.0, 0.0, 0.0)),
            .inertia = unit_inertia(),
            .limits = {.minimum = -2.5, .maximum = 2.5},
            .diagnostic_name = std::move(name),
        };
    }

    Articulation3D two_unit_model() {
        std::vector<ArticulationUnit3D> units;
        units.push_back(revolute_unit(articulation_root_frame, "shoulder"));
        units.push_back(revolute_unit(0, "elbow"));
        return Articulation3D(std::move(units), {{0.35, -0.6}, {0.0, 0.0}}, "velocity-control-test");
    }

    std::span<const ArticulationTask3D* const> task_span(const std::vector<const ArticulationTask3D*>& tasks) {
        return {tasks.data(), tasks.size()};
    }

    void test_priority_and_primal_warm_start() {
        Articulation3D articulation = two_unit_model();
        VelocityHqpController3D controller(articulation);
        JointVelocityTask3D primary({0}, {0.7}, 1.0, {.priority = 0, .diagnostic_name = "primary"});
        JointVelocityTask3D posture({}, {0.0, 0.0}, 1.0, {.priority = 1, .diagnostic_name = "posture"});
        const std::vector<const ArticulationTask3D*> tasks{&primary, &posture};

        const VelocityControlResult3D first = controller.solve(task_span(tasks));
        TERMIN_ROBOTICS_CHECK(first.ok());
        TERMIN_ROBOTICS_CHECK(!first.primal_warm_start_used);
        TERMIN_ROBOTICS_CHECK(first.level_priorities == std::vector<int>({0, 1}));
        TERMIN_ROBOTICS_CHECK(std::abs(first.generalized_velocity[0] - 0.7) < tolerance);
        TERMIN_ROBOTICS_CHECK(std::abs(first.generalized_velocity[1]) < tolerance);

        const VelocityControlResult3D second = controller.solve(task_span(tasks));
        TERMIN_ROBOTICS_CHECK(second.ok());
        TERMIN_ROBOTICS_CHECK(second.primal_warm_start_used);
        controller.reset_primal_warm_start();
        const VelocityControlResult3D third = controller.solve(task_span(tasks));
        TERMIN_ROBOTICS_CHECK(third.ok());
        TERMIN_ROBOTICS_CHECK(!third.primal_warm_start_used);
    }

    void test_hard_velocity_and_position_limits() {
        Articulation3D articulation = two_unit_model();
        Articulation3DState near_limit = articulation.state();
        near_limit.coordinates[0] = 2.49;
        TERMIN_ROBOTICS_CHECK(articulation.set_state(std::move(near_limit)) == Articulation3DDiagnostic::None);

        VelocityHqpController3D controller(articulation);
        JointVelocityTask3D target({0}, {10.0}, 1.0, {.priority = 1, .diagnostic_name = "target"});
        JointVelocityLimitConstraint3D velocity_limit({0}, {-0.4}, {0.4}, {.priority = 0, .diagnostic_name = "speed"});
        JointLimitConstraint3D position_limit({.priority = 0, .diagnostic_name = "position"});
        const std::vector<const ArticulationTask3D*> tasks{&target, &velocity_limit, &position_limit};
        VelocityControlOptions3D options;
        options.time_step = 0.1;
        const VelocityControlResult3D result = controller.solve(task_span(tasks), options);
        TERMIN_ROBOTICS_CHECK(result.ok());
        TERMIN_ROBOTICS_CHECK(result.generalized_velocity[0] <= 0.10000001);
        TERMIN_ROBOTICS_CHECK(result.generalized_velocity[0] >= -0.40000001);
    }

    void test_fixed_and_floating_integration() {
        Articulation3D fixed = two_unit_model();
        const std::array<double, 2> fixed_velocity{0.2, -0.4};
        const VelocityIntegrationResult3D fixed_result =
            integrate_articulation_velocity(fixed, {fixed_velocity.data(), fixed_velocity.size()}, 0.5);
        TERMIN_ROBOTICS_CHECK(fixed_result.ok());
        TERMIN_ROBOTICS_CHECK(std::abs(fixed.state().coordinates[0] - 0.45) < tolerance);
        TERMIN_ROBOTICS_CHECK(std::abs(fixed.state().coordinates[1] + 0.8) < tolerance);
        TERMIN_ROBOTICS_CHECK(std::abs(fixed.state().velocities[0] - 0.2) < tolerance);

        ArticulationFloatingBase3D base{
            .inertia = unit_inertia(),
            .pose_world = Pose3::identity(),
            .velocity_local = Screw3::zero(),
            .diagnostic_name = "base",
        };
        Articulation3D floating(base, {revolute_unit(articulation_root_frame, "joint")}, {{0.0}, {0.0}}, "floating");
        VelocityHqpController3D controller(floating);
        JointVelocityTask3D joint_task({0}, {0.25}, 1.0, {.diagnostic_name = "joint"});
        const std::array<const ArticulationTask3D*, 1> tasks{&joint_task};
        const VelocityControlResult3D solved = controller.solve(tasks);
        TERMIN_ROBOTICS_CHECK(solved.ok());
        TERMIN_ROBOTICS_CHECK(solved.generalized_velocity.size() == 7);
        TERMIN_ROBOTICS_CHECK(std::abs(solved.generalized_velocity[6] - 0.25) < tolerance);

        const std::array<double, 7> floating_velocity{1.0, 0.0, 0.0, 0.0, 0.0, 0.5, 0.25};
        const VelocityIntegrationResult3D floating_result =
            integrate_articulation_velocity(floating, {floating_velocity.data(), floating_velocity.size()}, 0.2);
        TERMIN_ROBOTICS_CHECK(floating_result.ok());
        TERMIN_ROBOTICS_CHECK(std::abs(floating.state().coordinates[0] - 0.05) < tolerance);
        TERMIN_ROBOTICS_CHECK(std::abs(floating.floating_base()->velocity_local.lin.x - 1.0) < tolerance);
        TERMIN_ROBOTICS_CHECK(std::abs(floating.floating_base()->velocity_local.ang.z - 0.5) < tolerance);
        TERMIN_ROBOTICS_CHECK(floating.floating_base()->pose_world.lin.norm() > 0.19);
    }

    void test_active_avoidance_constraint() {
        Articulation3D articulation = two_unit_model();
        const ArticulationPointKinematics3DResult point = articulation.point_kinematics(1, Vec3::zero());
        TERMIN_ROBOTICS_CHECK(point.ok());
        const qopt::ConstDenseMatrixView jacobian = point.value.linear_jacobian_world();
        const Vec3 first_joint_direction{jacobian(0, 0), jacobian(1, 0), jacobian(2, 0)};
        const Vec3 normal = first_joint_direction.normalized();
        const double normal_jacobian =
            normal.x * jacobian(0, 0) + normal.y * jacobian(1, 0) + normal.z * jacobian(2, 0);

        PointAvoidanceConstraint3D avoidance(
            1, Vec3::zero(), normal, 0.0, 0.1, 0.5, {.priority = 0, .diagnostic_name = "active-avoidance"});
        JointVelocityTask3D conflicting_target(
            {0, 1}, {-1.0, 0.0}, 1.0, {.priority = 1, .diagnostic_name = "conflicting-target"});
        const std::vector<const ArticulationTask3D*> tasks{&avoidance, &conflicting_target};
        VelocityHqpController3D controller(articulation);
        const VelocityControlResult3D result = controller.solve(task_span(tasks));
        TERMIN_ROBOTICS_CHECK(result.ok());

        double separation_velocity = 0.0;
        for (std::size_t joint = 0; joint < 2; ++joint) {
            separation_velocity +=
                (normal.x * jacobian(0, joint) + normal.y * jacobian(1, joint) + normal.z * jacobian(2, joint)) *
                result.generalized_velocity[joint];
        }
        TERMIN_ROBOTICS_CHECK(normal_jacobian > 0.0);
        TERMIN_ROBOTICS_CHECK(separation_velocity >= 0.2 - tolerance);
    }

    void test_end_effector_tracking_and_avoidance() {
        Articulation3D articulation = two_unit_model();
        VelocityHqpController3D controller(articulation);
        const Vec3 target{1.3, 0.7, 0.0};
        const double initial_distance = (articulation.unit_poses_world()[1].lin - target).norm();
        double distance = initial_distance;

        for (std::size_t step = 0; step < 120; ++step) {
            const Vec3 point = articulation.unit_poses_world()[1].lin;
            const Vec3 tracking_velocity = (target - point) * 3.0;
            PointVelocityTask3D tracking(
                1, Vec3::zero(), tracking_velocity, {.priority = 1, .diagnostic_name = "end-effector"});
            JointVelocityTask3D posture(
                {}, {0.0, 0.0}, 1.0, {.priority = 2, .diagonal_weight = {0.01, 0.01}, .diagnostic_name = "posture"});
            JointVelocityLimitConstraint3D velocity_limits(
                {}, {-1.5, -1.5}, {1.5, 1.5}, {.priority = 0, .diagnostic_name = "velocity-limits"});
            JointLimitConstraint3D joint_limits({.priority = 0, .diagnostic_name = "joint-limits"});

            // Keep the endpoint on the positive-y side of a virtual plane.
            PointAvoidanceConstraint3D avoidance(1,
                                                 Vec3::zero(),
                                                 Vec3::unit_y(),
                                                 point.y,
                                                 0.05,
                                                 0.1,
                                                 {.priority = 0, .diagnostic_name = "virtual-plane"});
            const std::vector<const ArticulationTask3D*> tasks{
                &tracking,
                &posture,
                &velocity_limits,
                &joint_limits,
                &avoidance,
            };
            VelocityControlOptions3D options;
            options.time_step = 0.02;
            const VelocityControlResult3D solved = controller.solve(task_span(tasks), options);
            TERMIN_ROBOTICS_CHECK(solved.ok());
            TERMIN_ROBOTICS_CHECK(solved.generalized_velocity[0] <= 1.5 + tolerance);
            TERMIN_ROBOTICS_CHECK(solved.generalized_velocity[1] <= 1.5 + tolerance);
            const VelocityIntegrationResult3D integrated = integrate_articulation_velocity(
                articulation,
                {solved.generalized_velocity.data(), solved.generalized_velocity.size()},
                options.time_step);
            TERMIN_ROBOTICS_CHECK(integrated.ok());
        }

        distance = (articulation.unit_poses_world()[1].lin - target).norm();
        TERMIN_ROBOTICS_CHECK(distance < initial_distance * 0.15);
        TERMIN_ROBOTICS_CHECK(articulation.unit_poses_world()[1].lin.y > 0.05);
    }
} // namespace

int main() {
    test_priority_and_primal_warm_start();
    test_hard_velocity_and_position_limits();
    test_fixed_and_floating_integration();
    test_active_avoidance_constraint();
    test_end_effector_tracking_and_avoidance();
    return 0;
}
