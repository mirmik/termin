#include <termin/geom/se3.hpp>
#include <termin/robotics/articulation3d.hpp>

#include "test_check.hpp"

#include <cmath>
#include <vector>

using namespace termin;
using namespace termin::robotics;

namespace
{
    SpatialInertia3 unit_inertia()
    {
        return {1.0, {0.2, 0.3, 0.4}, Pose3::identity()};
    }

    std::vector<ArticulationUnit3D> units()
    {
        return {
            {
                .parent_unit = articulation_root_frame,
                .parent_to_unit_zero = Pose3::translation(1.0, 0.0, 0.0),
                .motion_twist_at_unit =
                    Screw3{Vec3::unit_z(), Vec3::zero()}.adjoint_inv(
                        Pose3::translation(1.0, 0.0, 0.0)),
                .inertia = unit_inertia(),
                .diagnostic_name = "root",
            },
            {
                .parent_unit = 0,
                .parent_to_unit_zero = Pose3::translation(1.0, 0.0, 0.0),
                .motion_twist_at_unit =
                    Screw3{Vec3::unit_y(), Vec3::zero()}.adjoint_inv(
                        Pose3::translation(0.5, 0.0, 0.0)),
                .inertia = unit_inertia(),
                .diagnostic_name = "child",
            },
        };
    }

    void test_validation()
    {
        Articulation3D empty({}, {}, "empty");
        TERMIN_ROBOTICS_CHECK(empty.diagnostic() ==
                              Articulation3DDiagnostic::EmptyModel);

        auto invalid_units = units();
        invalid_units[0].parent_unit = 0;
        Articulation3D invalid(std::move(invalid_units),
                               {{0.0, 0.0}, {0.0, 0.0}});
        TERMIN_ROBOTICS_CHECK(invalid.diagnostic() ==
                              Articulation3DDiagnostic::InvalidParent);
    }

    void test_kinematics_and_inertial_model()
    {
        const Articulation3DState state{{0.3, -0.4}, {0.7, -0.2}};
        Articulation3D model(units(), state, "two-unit");
        TERMIN_ROBOTICS_CHECK(model.diagnostic() ==
                              Articulation3DDiagnostic::None);
        TERMIN_ROBOTICS_CHECK(model.unit_poses_world().size() == 2);

        const auto point = model.point_kinematics(1, {0.2, -0.1, 0.3});
        TERMIN_ROBOTICS_CHECK(point.ok());
        const auto jacobian = point.value.linear_jacobian_world();
        TERMIN_ROBOTICS_CHECK(jacobian.rows == 3);
        TERMIN_ROBOTICS_CHECK(jacobian.columns == 2);

        Vec3 jacobian_velocity = Vec3::zero();
        for (std::size_t column = 0; column < state.velocities.size(); ++column)
        {
            jacobian_velocity.x +=
                jacobian(0, column) * state.velocities[column];
            jacobian_velocity.y +=
                jacobian(1, column) * state.velocities[column];
            jacobian_velocity.z +=
                jacobian(2, column) * state.velocities[column];
        }
        TERMIN_ROBOTICS_CHECK(
            (jacobian_velocity - point.value.velocity_world).norm() < 1e-12);

        std::vector<double> mass;
        TERMIN_ROBOTICS_CHECK(model.mass_matrix(mass));
        TERMIN_ROBOTICS_CHECK(mass.size() == 4);
        TERMIN_ROBOTICS_CHECK(std::abs(mass[1] - mass[2]) < 1e-12);
        TERMIN_ROBOTICS_CHECK(
            std::isfinite(model.total_energy({0.0, 0.0, -9.81})));
    }

    void check_vec_near(Vec3 actual, Vec3 expected, double tolerance)
    {
        TERMIN_ROBOTICS_CHECK((actual - expected).norm() < tolerance);
    }

    void test_unit_frame_collapse_equivalence()
    {
        const Pose3 parent_to_joint = Pose3::translation(0.2, -0.3, 0.4) *
                                      Pose3::rotation(Vec3::unit_x(), 0.35);
        const Pose3 joint_to_output = Pose3::translation(0.7, 0.1, -0.2) *
                                      Pose3::rotation(Vec3::unit_z(), -0.25);
        const Screw3 motion_at_joint{Vec3::unit_y(), Vec3::zero()};
        constexpr double coordinate = 0.6;
        constexpr double velocity = -0.8;

        Articulation3D model(
            {{.parent_unit = articulation_root_frame,
              .parent_to_unit_zero =
                  (parent_to_joint * joint_to_output).normalized(),
              .motion_twist_at_unit =
                  motion_at_joint.adjoint_inv(joint_to_output),
              .inertia = unit_inertia(),
              .diagnostic_name = "collapsed-unit"}},
            {{coordinate}, {velocity}},
            "unit-frame-collapse");
        TERMIN_ROBOTICS_CHECK(model.diagnostic() ==
                              Articulation3DDiagnostic::None);

        const Pose3 separated_oracle =
            (parent_to_joint * se3_exp(motion_at_joint * coordinate) *
             joint_to_output)
                .normalized();
        const Pose3& actual = model.unit_poses_world()[0];
        check_vec_near(actual.transform_point({0.3, -0.2, 0.5}),
                       separated_oracle.transform_point({0.3, -0.2, 0.5}),
                       1.0e-12);
        check_vec_near(actual.transform_vector({0.4, 0.5, -0.1}),
                       separated_oracle.transform_vector({0.4, 0.5, -0.1}),
                       1.0e-12);
        const Screw3 expected_velocity =
            motion_at_joint.adjoint_inv(joint_to_output) * velocity;
        check_vec_near(model.unit_velocities_local()[0].ang,
                       expected_velocity.ang,
                       1.0e-12);
        check_vec_near(model.unit_velocities_local()[0].lin,
                       expected_velocity.lin,
                       1.0e-12);
    }

    void test_bias_acceleration_against_finite_difference()
    {
        constexpr double step = 1.0e-7;
        const Vec3 point_local{0.2, -0.1, 0.3};
        const Articulation3DState initial{{0.3, -0.4}, {0.7, -0.2}};

        Articulation3D fixed(units(), initial, "fixed-bias");
        const auto fixed_point_before = fixed.point_kinematics(1, point_local);
        const auto fixed_frame_before = fixed.frame_kinematics(1);
        TERMIN_ROBOTICS_CHECK(fixed_point_before.ok());
        TERMIN_ROBOTICS_CHECK(fixed_frame_before.ok());
        Articulation3DState advanced = initial;
        for (std::size_t joint = 0; joint < advanced.coordinates.size();
             ++joint)
        {
            advanced.coordinates[joint] += advanced.velocities[joint] * step;
        }
        TERMIN_ROBOTICS_CHECK(fixed.set_state(advanced) ==
                              Articulation3DDiagnostic::None);
        const auto fixed_point_after = fixed.point_kinematics(1, point_local);
        const auto fixed_frame_after = fixed.frame_kinematics(1);
        check_vec_near((fixed_point_after.value.velocity_world -
                        fixed_point_before.value.velocity_world) /
                           step,
                       fixed_point_before.value.bias_acceleration_world,
                       2.0e-6);
        check_vec_near((fixed_frame_after.value.velocity_world.lin -
                        fixed_frame_before.value.velocity_world.lin) /
                           step,
                       fixed_frame_before.value.bias_acceleration_world.lin,
                       2.0e-6);
        check_vec_near((fixed_frame_after.value.velocity_world.ang -
                        fixed_frame_before.value.velocity_world.ang) /
                           step,
                       fixed_frame_before.value.bias_acceleration_world.ang,
                       2.0e-6);

        ArticulationFloatingBase3D base{
            .inertia = unit_inertia(),
            .pose_world = se3_exp({{0.2, -0.1, 0.3}, {0.4, -0.2, 0.1}}),
            .velocity_local = {{0.4, -0.3, 0.2}, {0.7, 0.1, -0.2}},
            .diagnostic_name = "base",
        };
        Articulation3D floating(base, units(), initial, "floating-bias");
        const auto floating_point_before =
            floating.point_kinematics(1, point_local);
        const auto floating_frame_before = floating.frame_kinematics(1);
        const auto base_point_before =
            floating.floating_base_point_kinematics(point_local);
        TERMIN_ROBOTICS_CHECK(floating_point_before.ok());
        TERMIN_ROBOTICS_CHECK(floating_frame_before.ok());
        TERMIN_ROBOTICS_CHECK(base_point_before.ok());
        TERMIN_ROBOTICS_CHECK(floating.set_state(advanced) ==
                              Articulation3DDiagnostic::None);
        TERMIN_ROBOTICS_CHECK(
            floating.set_floating_base_state(
                base.pose_world * se3_exp(base.velocity_local * step),
                base.velocity_local) == Articulation3DDiagnostic::None);
        const auto floating_point_after =
            floating.point_kinematics(1, point_local);
        const auto floating_frame_after = floating.frame_kinematics(1);
        const auto base_point_after =
            floating.floating_base_point_kinematics(point_local);
        check_vec_near((floating_point_after.value.velocity_world -
                        floating_point_before.value.velocity_world) /
                           step,
                       floating_point_before.value.bias_acceleration_world,
                       3.0e-6);
        check_vec_near((floating_frame_after.value.velocity_world.lin -
                        floating_frame_before.value.velocity_world.lin) /
                           step,
                       floating_frame_before.value.bias_acceleration_world.lin,
                       3.0e-6);
        check_vec_near((floating_frame_after.value.velocity_world.ang -
                        floating_frame_before.value.velocity_world.ang) /
                           step,
                       floating_frame_before.value.bias_acceleration_world.ang,
                       3.0e-6);
        check_vec_near((base_point_after.value.velocity_world -
                        base_point_before.value.velocity_world) /
                           step,
                       base_point_before.value.bias_acceleration_world,
                       2.0e-6);
    }
}

int main()
{
    test_validation();
    test_kinematics_and_inertial_model();
    test_unit_frame_collapse_equivalence();
    test_bias_acceleration_against_finite_difference();
    return 0;
}
