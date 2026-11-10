#include <termin/geom/se3.hpp>
#include <termin/robotics/articulation3d.hpp>

#include "test_check.hpp"

#include <algorithm>
#include <cmath>
#include <vector>

using namespace termin;
using namespace termin::robotics;

namespace {
    SpatialInertia3 unit_inertia() {
        return {1.0, {0.2, 0.3, 0.4}, Pose3::identity()};
    }

    std::vector<ArticulationUnit3D> units() {
        return {
            {
                .parent_unit = articulation_root_frame,
                .parent_to_unit_zero = Pose3::translation(1.0, 0.0, 0.0),
                .motion_twist_at_unit =
                    Screw3{Vec3::unit_z(), Vec3::zero()}.adjoint_inv(Pose3::translation(1.0, 0.0, 0.0)),
                .inertia = unit_inertia(),
                .diagnostic_name = "root",
            },
            {
                .parent_unit = 0,
                .parent_to_unit_zero = Pose3::translation(1.0, 0.0, 0.0),
                .motion_twist_at_unit =
                    Screw3{Vec3::unit_y(), Vec3::zero()}.adjoint_inv(Pose3::translation(0.5, 0.0, 0.0)),
                .inertia = unit_inertia(),
                .diagnostic_name = "child",
            },
        };
    }

    void test_validation() {
        Articulation3D empty({}, {}, "empty");
        TERMIN_ROBOTICS_CHECK(empty.diagnostic() == Articulation3DDiagnostic::EmptyModel);

        auto invalid_units = units();
        invalid_units[0].parent_unit = 0;
        Articulation3D invalid(std::move(invalid_units), {{0.0, 0.0}, {0.0, 0.0}});
        TERMIN_ROBOTICS_CHECK(invalid.diagnostic() == Articulation3DDiagnostic::InvalidParent);
        // An invalid topology must not enter the ancestor traversal (self-cycle).
        std::vector<double> mass{42.0};
        TERMIN_ROBOTICS_CHECK(!invalid.mass_matrix(mass));
        TERMIN_ROBOTICS_CHECK(mass == std::vector<double>{42.0});
        TERMIN_ROBOTICS_CHECK(!empty.mass_matrix(mass));
    }

    void test_kinematics_and_inertial_model() {
        const Articulation3DState state{{0.3, -0.4}, {0.7, -0.2}};
        Articulation3D model(units(), state, "two-unit");
        TERMIN_ROBOTICS_CHECK(model.diagnostic() == Articulation3DDiagnostic::None);
        TERMIN_ROBOTICS_CHECK(model.unit_poses_world().size() == 2);

        const auto point = model.point_kinematics(1, {0.2, -0.1, 0.3});
        TERMIN_ROBOTICS_CHECK(point.ok());
        const auto jacobian = point.value.linear_jacobian_world();
        TERMIN_ROBOTICS_CHECK(jacobian.rows == 3);
        TERMIN_ROBOTICS_CHECK(jacobian.columns == 2);

        Vec3 jacobian_velocity = Vec3::zero();
        for (std::size_t column = 0; column < state.velocities.size(); ++column) {
            jacobian_velocity.x += jacobian(0, column) * state.velocities[column];
            jacobian_velocity.y += jacobian(1, column) * state.velocities[column];
            jacobian_velocity.z += jacobian(2, column) * state.velocities[column];
        }
        TERMIN_ROBOTICS_CHECK((jacobian_velocity - point.value.velocity_world).norm() < 1e-12);

        std::vector<double> mass;
        TERMIN_ROBOTICS_CHECK(model.mass_matrix(mass));
        TERMIN_ROBOTICS_CHECK(mass.size() == 4);
        TERMIN_ROBOTICS_CHECK(std::abs(mass[1] - mass[2]) < 1e-12);
        TERMIN_ROBOTICS_CHECK(std::isfinite(model.total_energy({0.0, 0.0, -9.81})));
    }

    void check_vec_near(Vec3 actual, Vec3 expected, double tolerance) {
        TERMIN_ROBOTICS_CHECK((actual - expected).norm() < tolerance);
    }

    void test_unit_frame_collapse_equivalence() {
        const Pose3 parent_to_joint = Pose3::translation(0.2, -0.3, 0.4) * Pose3::rotation(Vec3::unit_x(), 0.35);
        const Pose3 joint_to_output = Pose3::translation(0.7, 0.1, -0.2) * Pose3::rotation(Vec3::unit_z(), -0.25);
        const Screw3 motion_at_joint{Vec3::unit_y(), Vec3::zero()};
        constexpr double coordinate = 0.6;
        constexpr double velocity = -0.8;

        Articulation3D model({{.parent_unit = articulation_root_frame,
                               .parent_to_unit_zero = (parent_to_joint * joint_to_output).normalized(),
                               .motion_twist_at_unit = motion_at_joint.adjoint_inv(joint_to_output),
                               .inertia = unit_inertia(),
                               .diagnostic_name = "collapsed-unit"}},
                             {{coordinate}, {velocity}},
                             "unit-frame-collapse");
        TERMIN_ROBOTICS_CHECK(model.diagnostic() == Articulation3DDiagnostic::None);

        const Pose3 separated_oracle =
            (parent_to_joint * se3_exp(motion_at_joint * coordinate) * joint_to_output).normalized();
        const Pose3& actual = model.unit_poses_world()[0];
        check_vec_near(
            actual.transform_point({0.3, -0.2, 0.5}), separated_oracle.transform_point({0.3, -0.2, 0.5}), 1.0e-12);
        check_vec_near(
            actual.transform_vector({0.4, 0.5, -0.1}), separated_oracle.transform_vector({0.4, 0.5, -0.1}), 1.0e-12);
        const Screw3 expected_velocity = motion_at_joint.adjoint_inv(joint_to_output) * velocity;
        check_vec_near(model.unit_velocities_local()[0].ang, expected_velocity.ang, 1.0e-12);
        check_vec_near(model.unit_velocities_local()[0].lin, expected_velocity.lin, 1.0e-12);
    }

    void test_bias_acceleration_against_finite_difference() {
        constexpr double step = 1.0e-7;
        const Vec3 point_local{0.2, -0.1, 0.3};
        const Articulation3DState initial{{0.3, -0.4}, {0.7, -0.2}};

        Articulation3D fixed(units(), initial, "fixed-bias");
        const auto fixed_point_before = fixed.point_kinematics(1, point_local);
        const auto fixed_frame_before = fixed.frame_kinematics(1);
        TERMIN_ROBOTICS_CHECK(fixed_point_before.ok());
        TERMIN_ROBOTICS_CHECK(fixed_frame_before.ok());
        Articulation3DState advanced = initial;
        for (std::size_t joint = 0; joint < advanced.coordinates.size(); ++joint) {
            advanced.coordinates[joint] += advanced.velocities[joint] * step;
        }
        TERMIN_ROBOTICS_CHECK(fixed.set_state(advanced) == Articulation3DDiagnostic::None);
        const auto fixed_point_after = fixed.point_kinematics(1, point_local);
        const auto fixed_frame_after = fixed.frame_kinematics(1);
        check_vec_near((fixed_point_after.value.velocity_world - fixed_point_before.value.velocity_world) / step,
                       fixed_point_before.value.bias_acceleration_world,
                       2.0e-6);
        check_vec_near((fixed_frame_after.value.velocity_world.lin - fixed_frame_before.value.velocity_world.lin) /
                           step,
                       fixed_frame_before.value.bias_acceleration_world.lin,
                       2.0e-6);
        check_vec_near((fixed_frame_after.value.velocity_world.ang - fixed_frame_before.value.velocity_world.ang) /
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
        const auto floating_point_before = floating.point_kinematics(1, point_local);
        const auto floating_frame_before = floating.frame_kinematics(1);
        const auto base_point_before = floating.floating_base_point_kinematics(point_local);
        TERMIN_ROBOTICS_CHECK(floating_point_before.ok());
        TERMIN_ROBOTICS_CHECK(floating_frame_before.ok());
        TERMIN_ROBOTICS_CHECK(base_point_before.ok());
        TERMIN_ROBOTICS_CHECK(floating.set_state(advanced) == Articulation3DDiagnostic::None);
        TERMIN_ROBOTICS_CHECK(floating.set_floating_base_state(base.pose_world * se3_exp(base.velocity_local * step),
                                                               base.velocity_local) == Articulation3DDiagnostic::None);
        const auto floating_point_after = floating.point_kinematics(1, point_local);
        const auto floating_frame_after = floating.frame_kinematics(1);
        const auto base_point_after = floating.floating_base_point_kinematics(point_local);
        check_vec_near((floating_point_after.value.velocity_world - floating_point_before.value.velocity_world) / step,
                       floating_point_before.value.bias_acceleration_world,
                       3.0e-6);
        check_vec_near(
            (floating_frame_after.value.velocity_world.lin - floating_frame_before.value.velocity_world.lin) / step,
            floating_frame_before.value.bias_acceleration_world.lin,
            3.0e-6);
        check_vec_near(
            (floating_frame_after.value.velocity_world.ang - floating_frame_before.value.velocity_world.ang) / step,
            floating_frame_before.value.bias_acceleration_world.ang,
            3.0e-6);
        check_vec_near((base_point_after.value.velocity_world - base_point_before.value.velocity_world) / step,
                       base_point_before.value.bias_acceleration_world,
                       2.0e-6);
    }

    void check_scalar_near(double actual, double expected) {
        const double scale = std::max(std::abs(actual), std::abs(expected));
        TERMIN_ROBOTICS_CHECK(std::abs(actual - expected) <= 2.0e-11 * (1.0 + scale));
    }

    std::vector<ArticulationUnit3D> branched_mass_units() {
        std::vector<ArticulationUnit3D> result;
        const std::size_t parents[] = {articulation_root_frame, 0, 0, 1, articulation_root_frame};
        for (std::size_t index = 0; index < 5; ++index) {
            const double scale = static_cast<double>(index + 1);
            // Include multiple roots, a branch and a grandchild, with mixed
            // revolute/prismatic units and displaced, rotated inertia frames.
            const Screw3 joint_twist =
                index % 2 == 0 ? Screw3{Vec3::unit_y(), Vec3::zero()} : Screw3{Vec3::zero(), Vec3::unit_z()};
            result.push_back({
                .parent_unit = parents[index],
                .parent_to_unit_zero =
                    Pose3::translation(0.17 * scale, -0.09, 0.13) * Pose3::rotation(Vec3::unit_z(), 0.19 * scale),
                .motion_twist_at_unit = joint_twist.adjoint_inv(Pose3::translation(0.08, -0.11, 0.06) *
                                                                Pose3::rotation(Vec3::unit_x(), 0.23)),
                .inertia = SpatialInertia3{0.7 + 0.2 * scale,
                                           {0.12 + 0.01 * scale, 0.16 + 0.02 * scale, 0.19 + 0.015 * scale},
                                           Pose3::translation(-0.05, 0.04 * scale, 0.07) *
                                               Pose3::rotation(Vec3::unit_x(), -0.21 * scale)},
                .diagnostic_name = "mass-oracle-unit",
            });
        }
        return result;
    }

    void check_mass_against_inverse_dynamics(const Articulation3D& model) {
        const std::size_t count = model.dof_count();
        std::vector<double> velocities(count);
        const std::size_t offset = model.has_floating_base() ? 6 : 0;
        if (model.has_floating_base()) {
            const Screw3 base_velocity = model.floating_base()->velocity_local;
            velocities = {base_velocity.lin.x,
                          base_velocity.lin.y,
                          base_velocity.lin.z,
                          base_velocity.ang.x,
                          base_velocity.ang.y,
                          base_velocity.ang.z};
            velocities.resize(count);
        }
        std::copy(model.state().velocities.begin(), model.state().velocities.end(), velocities.begin() + offset);

        std::vector<double> mass;
        TERMIN_ROBOTICS_CHECK(model.mass_matrix(mass));
        TERMIN_ROBOTICS_CHECK(mass.size() == count * count);
        const Vec3 gravity{0.7, -1.1, -9.81};
        const std::vector<double> zero(count, 0.0);
        std::vector<double> bias;
        TERMIN_ROBOTICS_CHECK(model.inverse_dynamics(velocities, zero, gravity, bias));
        for (std::size_t sample = 0; sample <= count; ++sample) {
            std::vector<double> acceleration(count, 0.0);
            if (sample < count) {
                acceleration[sample] = 1.0;
            } else {
                for (std::size_t index = 0; index < count; ++index) {
                    acceleration[index] = std::sin(0.7 * static_cast<double>(index + 1));
                }
            }
            std::vector<double> effort;
            TERMIN_ROBOTICS_CHECK(model.inverse_dynamics(velocities, acceleration, gravity, effort));
            for (std::size_t row = 0; row < count; ++row) {
                double mass_acceleration = 0.0;
                for (std::size_t column = 0; column < count; ++column) {
                    check_scalar_near(mass[row * count + column], mass[column * count + row]);
                    mass_acceleration += mass[row * count + column] * acceleration[column];
                }
                // The full velocity/gravity bias cancels, giving an oracle
                // independent of the algorithm used to construct M.
                check_scalar_near(mass_acceleration, effort[row] - bias[row]);
            }
        }

        double kinetic_energy = 0.0;
        for (std::size_t row = 0; row < count; ++row) {
            for (std::size_t column = 0; column < count; ++column) {
                kinetic_energy += 0.5 * velocities[row] * mass[row * count + column] * velocities[column];
            }
        }
        TERMIN_ROBOTICS_CHECK(kinetic_energy > 0.0);
        check_scalar_near(kinetic_energy, model.total_energy(Vec3::zero()));
    }

    void test_mass_matrix_oracles() {
        const Articulation3DState initial{std::vector<double>(5), std::vector<double>(5)};
        Articulation3D fixed(branched_mass_units(), initial, "fixed-mass-oracle");
        ArticulationFloatingBase3D base{
            .inertia = SpatialInertia3{2.1, {0.4, 0.5, 0.6}, Pose3::translation(0.12, -0.07, 0.19)},
            .diagnostic_name = "mass-oracle-base",
        };
        Articulation3D floating(base, branched_mass_units(), initial, "floating-mass-oracle");
        Articulation3D base_only(base, {}, {}, "base-only-mass-oracle");
        TERMIN_ROBOTICS_CHECK(fixed.diagnostic() == Articulation3DDiagnostic::None);
        TERMIN_ROBOTICS_CHECK(floating.diagnostic() == Articulation3DDiagnostic::None);
        TERMIN_ROBOTICS_CHECK(base_only.diagnostic() == Articulation3DDiagnostic::None);
        for (std::size_t sample = 0; sample < 4; ++sample) {
            const double phase = 0.37 * static_cast<double>(sample + 1);
            Articulation3DState state = initial;
            for (std::size_t index = 0; index < state.coordinates.size(); ++index) {
                const double scale = static_cast<double>(index + 1);
                state.coordinates[index] = 0.4 * std::sin(phase * scale);
                state.velocities[index] = 0.8 * std::cos(phase * scale);
            }
            TERMIN_ROBOTICS_CHECK(fixed.set_state(state) == Articulation3DDiagnostic::None);
            TERMIN_ROBOTICS_CHECK(floating.set_state(state) == Articulation3DDiagnostic::None);
            const Pose3 pose = se3_exp({{0.2 * phase, -0.3, 0.1}, {0.4, -0.2 * phase, 0.3}});
            const Screw3 velocity{{0.4, -0.3 * phase, 0.2}, {0.7 * phase, 0.1, -0.2}};
            TERMIN_ROBOTICS_CHECK(floating.set_floating_base_state(pose, velocity) == Articulation3DDiagnostic::None);
            TERMIN_ROBOTICS_CHECK(base_only.set_floating_base_state(pose, velocity) == Articulation3DDiagnostic::None);
            check_mass_against_inverse_dynamics(fixed);
            check_mass_against_inverse_dynamics(floating);
            check_mass_against_inverse_dynamics(base_only);
        }
    }
} // namespace

int main() {
    test_validation();
    test_kinematics_and_inertial_model();
    test_unit_frame_collapse_equivalence();
    test_bias_acceleration_against_finite_difference();
    test_mass_matrix_oracles();
    return 0;
}
