#include <termin/geom/se3.hpp>
#include <termin/robotics/tasks.hpp>

#include "test_check.hpp"

#include <cmath>
#include <limits>
#include <vector>

using namespace termin;
using namespace termin::robotics;

namespace
{
    constexpr double tolerance = 1e-12;

    SpatialInertia3 link_inertia()
    {
        return {1.0, {0.2, 0.3, 0.4}, Pose3::identity()};
    }

    ArticulationLink3D link()
    {
        return {
            .parent_link = articulation_root_frame,
            .parent_to_joint_zero = Pose3::identity(),
            .motion_twist_at_joint = {Vec3::unit_z(), Vec3::zero()},
            .joint_to_link = Pose3::translation(1.0, 0.0, 0.0),
            .inertia = link_inertia(),
            .limits = {.minimum = -1.0, .maximum = 1.0},
            .diagnostic_name = "link",
        };
    }

    Articulation3D model()
    {
        return Articulation3D({link()}, {{0.25}, {0.1}}, "task-model");
    }

    void check_near(double actual, double expected)
    {
        TERMIN_ROBOTICS_CHECK(std::abs(actual - expected) < tolerance);
    }

    void test_frame_jacobian()
    {
        Articulation3D articulation = model();
        const ArticulationFrameKinematics3DResult frame =
            articulation.frame_kinematics(0);
        TERMIN_ROBOTICS_CHECK(frame.ok());
        const auto jacobian = frame.value.spatial_jacobian_world();
        TERMIN_ROBOTICS_CHECK(jacobian.rows == 6);
        TERMIN_ROBOTICS_CHECK(jacobian.columns == 1);

        check_near(jacobian(0, 0) * 0.1, frame.value.velocity_world.lin.x);
        check_near(jacobian(1, 0) * 0.1, frame.value.velocity_world.lin.y);
        check_near(jacobian(2, 0) * 0.1, frame.value.velocity_world.lin.z);
        check_near(jacobian(3, 0) * 0.1, frame.value.velocity_world.ang.x);
        check_near(jacobian(4, 0) * 0.1, frame.value.velocity_world.ang.y);
        check_near(jacobian(5, 0) * 0.1, frame.value.velocity_world.ang.z);
    }

    void test_point_and_pose_objectives()
    {
        Articulation3D articulation = model();
        const TaskLinearizationContext3D context{
            .articulation = &articulation,
            .derivative_order = TaskDerivativeOrder3D::Velocity,
        };

        PointVelocityTask3D point_task(0,
                                       Vec3::zero(),
                                       {1.0, 2.0, 3.0},
                                       {.priority = 2,
                                        .diagonal_weight = {2.0, 3.0, 4.0},
                                        .diagnostic_name = "point"});
        const TaskLinearization3DResult point = point_task.linearize(context);
        TERMIN_ROBOTICS_CHECK(point.ok());
        TERMIN_ROBOTICS_CHECK(point.value.relation ==
                              TaskRelation3D::Objective);
        TERMIN_ROBOTICS_CHECK(point.value.priority == 2);
        TERMIN_ROBOTICS_CHECK(point.value.matrix().rows == 3);
        TERMIN_ROBOTICS_CHECK(point.value.matrix().columns == 1);
        check_near(point.value.target()[0], 1.0);
        check_near(point.value.target()[1], 2.0);
        check_near(point.value.target()[2], 3.0);
        check_near(point.value.weight()(0, 0), 2.0);
        check_near(point.value.weight()(1, 1), 3.0);
        check_near(point.value.weight()(2, 2), 4.0);

        const Pose3 current = articulation.link_poses_world()[0];
        const Screw3 local_error{Vec3{0.0, 0.0, 0.2}, Vec3{0.1, -0.2, 0.3}};
        const Pose3 target = current * se3_exp(local_error);
        PoseTrackingTask3D pose_task(
            0, target, Screw3::zero(), 2.0, 3.0, {.diagnostic_name = "pose"});
        const TaskLinearization3DResult pose = pose_task.linearize(context);
        TERMIN_ROBOTICS_CHECK(pose.ok());
        TERMIN_ROBOTICS_CHECK(pose.value.matrix().rows == 6);
        const Screw3 error_world = local_error.rotated_by(current.ang);
        check_near(pose.value.target()[0], error_world.lin.x * 2.0);
        check_near(pose.value.target()[1], error_world.lin.y * 2.0);
        check_near(pose.value.target()[2], error_world.lin.z * 2.0);
        check_near(pose.value.target()[3], error_world.ang.x * 3.0);
        check_near(pose.value.target()[4], error_world.ang.y * 3.0);
        check_near(pose.value.target()[5], error_world.ang.z * 3.0);
    }

    void test_joint_objectives_and_floating_offset()
    {
        Articulation3D articulation = model();
        TaskLinearizationContext3D velocity_context{
            .articulation = &articulation,
            .derivative_order = TaskDerivativeOrder3D::Velocity,
        };
        JointPositionTask3D position(
            {}, {0.75}, 2.0, {0.1}, {.diagnostic_name = "position"});
        const TaskLinearization3DResult position_result =
            position.linearize(velocity_context);
        TERMIN_ROBOTICS_CHECK(position_result.ok());
        check_near(position_result.value.matrix()(0, 0), 1.0);
        check_near(position_result.value.target()[0], 1.1);

        JointVelocityTask3D velocity(
            {}, {0.5}, 4.0, {.diagnostic_name = "velocity"});
        const TaskLinearization3DResult velocity_result =
            velocity.linearize(velocity_context);
        TERMIN_ROBOTICS_CHECK(velocity_result.ok());
        check_near(velocity_result.value.target()[0], 0.5);

        velocity_context.derivative_order = TaskDerivativeOrder3D::Acceleration;
        const TaskLinearization3DResult acceleration_result =
            velocity.linearize(velocity_context);
        TERMIN_ROBOTICS_CHECK(acceleration_result.ok());
        check_near(acceleration_result.value.target()[0], 1.6);

        ArticulationFloatingBase3D base{
            .inertia = link_inertia(),
            .pose_world = Pose3::identity(),
            .velocity_local = Screw3::zero(),
            .diagnostic_name = "base",
        };
        Articulation3D floating(
            base, {link()}, {{0.0}, {0.0}}, "floating-task-model");
        const TaskLinearizationContext3D floating_context{
            .articulation = &floating,
            .derivative_order = TaskDerivativeOrder3D::Velocity,
        };
        JointVelocityTask3D floating_joint(
            {0}, {0.25}, 1.0, {.diagnostic_name = "floating-joint"});
        const TaskLinearization3DResult floating_result =
            floating_joint.linearize(floating_context);
        TERMIN_ROBOTICS_CHECK(floating_result.ok());
        TERMIN_ROBOTICS_CHECK(floating_result.value.variable_count == 7);
        for (std::size_t column = 0; column < 6; ++column)
        {
            check_near(floating_result.value.matrix()(0, column), 0.0);
        }
        check_near(floating_result.value.matrix()(0, 6), 1.0);
    }

    void test_joint_limit_inequality_signs()
    {
        Articulation3D articulation = model();
        JointLimitConstraint3D limits({.diagnostic_name = "limits"});
        TaskLinearizationContext3D context{
            .articulation = &articulation,
            .derivative_order = TaskDerivativeOrder3D::Velocity,
            .time_step = 0.2,
        };
        const TaskLinearization3DResult velocity = limits.linearize(context);
        TERMIN_ROBOTICS_CHECK(velocity.ok());
        TERMIN_ROBOTICS_CHECK(velocity.value.relation ==
                              TaskRelation3D::Inequality);
        check_near(velocity.value.matrix()(0, 0), 0.2);
        check_near(velocity.value.target()[0], 0.75);
        check_near(velocity.value.matrix()(1, 0), -0.2);
        check_near(velocity.value.target()[1], 1.25);

        context.derivative_order = TaskDerivativeOrder3D::Acceleration;
        const TaskLinearization3DResult acceleration =
            limits.linearize(context);
        TERMIN_ROBOTICS_CHECK(acceleration.ok());
        check_near(acceleration.value.matrix()(0, 0), 0.02);
        check_near(acceleration.value.target()[0], 0.73);
        check_near(acceleration.value.matrix()(1, 0), -0.02);
        check_near(acceleration.value.target()[1], 1.27);
    }

    void test_joint_velocity_limit_inequality_signs()
    {
        Articulation3D articulation = model();
        JointVelocityLimitConstraint3D limits(
            {0}, {-0.2}, {0.3}, {.diagnostic_name = "velocity-limits"});
        TaskLinearizationContext3D context{
            .articulation = &articulation,
            .derivative_order = TaskDerivativeOrder3D::Velocity,
            .time_step = 0.5,
        };
        const TaskLinearization3DResult velocity = limits.linearize(context);
        TERMIN_ROBOTICS_CHECK(velocity.ok());
        check_near(velocity.value.matrix()(0, 0), 1.0);
        check_near(velocity.value.target()[0], 0.3);
        check_near(velocity.value.matrix()(1, 0), -1.0);
        check_near(velocity.value.target()[1], 0.2);

        context.derivative_order = TaskDerivativeOrder3D::Acceleration;
        const TaskLinearization3DResult acceleration =
            limits.linearize(context);
        TERMIN_ROBOTICS_CHECK(acceleration.ok());
        check_near(acceleration.value.matrix()(0, 0), 0.5);
        check_near(acceleration.value.target()[0], 0.2);
        check_near(acceleration.value.matrix()(1, 0), -0.5);
        check_near(acceleration.value.target()[1], 0.3);
    }

    void test_avoidance_inequality_sign()
    {
        Articulation3D articulation = model();
        const ArticulationPointKinematics3DResult point =
            articulation.point_kinematics(0, Vec3::zero());
        TERMIN_ROBOTICS_CHECK(point.ok());
        const auto jacobian = point.value.linear_jacobian_world();
        const Vec3 normal =
            articulation.link_poses_world()[0].ang.rotate(Vec3::unit_y());
        const double normal_jacobian = normal.x * jacobian(0, 0) +
                                       normal.y * jacobian(1, 0) +
                                       normal.z * jacobian(2, 0);

        PointAvoidanceConstraint3D avoidance(0,
                                             Vec3::zero(),
                                             normal * 3.0,
                                             0.05,
                                             0.1,
                                             0.5,
                                             {.diagnostic_name = "avoidance"});
        const TaskLinearizationContext3D context{
            .articulation = &articulation,
            .derivative_order = TaskDerivativeOrder3D::Velocity,
        };
        const TaskLinearization3DResult result = avoidance.linearize(context);
        TERMIN_ROBOTICS_CHECK(result.ok());
        check_near(result.value.matrix()(0, 0), -normal_jacobian);
        check_near(result.value.target()[0], -0.1);
        // C*dq <= d therefore requires positive separation velocity here.
        TERMIN_ROBOTICS_CHECK(result.value.matrix()(0, 0) * 0.1 <=
                              result.value.target()[0] + tolerance);
        TERMIN_ROBOTICS_CHECK(result.value.matrix()(0, 0) * 0.0 >
                              result.value.target()[0]);
    }

    void test_activation_and_diagnostics()
    {
        Articulation3D articulation = model();
        const TaskLinearizationContext3D velocity_context{
            .articulation = &articulation,
            .derivative_order = TaskDerivativeOrder3D::Velocity,
        };
        PointVelocityTask3D disabled(
            std::numeric_limits<std::size_t>::max(),
            {std::numeric_limits<double>::quiet_NaN(), 0.0, 0.0},
            Vec3::zero(),
            {.enabled = false, .diagnostic_name = "disabled"});
        const TaskLinearization3DResult disabled_result =
            disabled.linearize(velocity_context);
        TERMIN_ROBOTICS_CHECK(disabled_result.ok());
        TERMIN_ROBOTICS_CHECK(!disabled_result.value.active);

        PointVelocityTask3D invalid_link(
            8, Vec3::zero(), Vec3::zero(), {.diagnostic_name = "bad-link"});
        TERMIN_ROBOTICS_CHECK(
            invalid_link.linearize(velocity_context).diagnostic ==
            TaskDiagnostic3D::InvalidLink);

        JointVelocityTask3D duplicate(
            {0, 0}, {0.0, 0.0}, 1.0, {.diagnostic_name = "duplicate"});
        TERMIN_ROBOTICS_CHECK(
            duplicate.linearize(velocity_context).diagnostic ==
            TaskDiagnostic3D::DuplicateJoint);

        PointVelocityTask3D bad_weight(
            0,
            Vec3::zero(),
            Vec3::zero(),
            {.diagonal_weight = {1.0, -1.0, 1.0}, .diagnostic_name = "weight"});
        TERMIN_ROBOTICS_CHECK(
            bad_weight.linearize(velocity_context).diagnostic ==
            TaskDiagnostic3D::InvalidWeight);

        PointAvoidanceConstraint3D bad_normal(0,
                                              Vec3::zero(),
                                              Vec3::zero(),
                                              0.0,
                                              0.1,
                                              1.0,
                                              {.diagnostic_name = "normal"});
        TERMIN_ROBOTICS_CHECK(
            bad_normal.linearize(velocity_context).diagnostic ==
            TaskDiagnostic3D::InvalidNormal);

        TaskLinearizationContext3D acceleration_context = velocity_context;
        acceleration_context.derivative_order =
            TaskDerivativeOrder3D::Acceleration;
        PoseTrackingTask3D pose(0, Pose3::identity(), Screw3::zero(), 1.0, 1.0);
        TERMIN_ROBOTICS_CHECK(pose.linearize(acceleration_context).diagnostic ==
                              TaskDiagnostic3D::UnsupportedDerivativeOrder);

        Articulation3D invalid_model({}, {}, "invalid-task-model");
        const TaskLinearizationContext3D invalid_context{
            .articulation = &invalid_model,
            .derivative_order = TaskDerivativeOrder3D::Velocity,
        };
        TERMIN_ROBOTICS_CHECK(
            invalid_link.linearize(invalid_context).diagnostic ==
            TaskDiagnostic3D::InvalidModel);
    }
}

int main()
{
    test_frame_jacobian();
    test_point_and_pose_objectives();
    test_joint_objectives_and_floating_offset();
    test_joint_limit_inequality_signs();
    test_joint_velocity_limit_inequality_signs();
    test_avoidance_inequality_sign();
    test_activation_and_diagnostics();
    return 0;
}
