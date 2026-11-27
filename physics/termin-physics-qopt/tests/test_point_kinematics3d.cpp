#include <termin/geom/se3.hpp>
#include <termin/physics_qopt/articulation3d_dynamics.hpp>
#include <termin/physics_qopt/contact3d.hpp>
#include <termin/physics_qopt/multibody3d.hpp>
#include <termin/physics_qopt/point_kinematics3d.hpp>

#include "test_check.hpp"

#include <array>
#include <cmath>
#include <limits>
#include <vector>

using namespace termin;
using namespace termin::physics_qopt;
using namespace termin::robotics;

namespace {

    constexpr double kTolerance = 1e-11;

    void check_near(double actual, double expected, double tolerance = kTolerance) {
        if (std::abs(actual - expected) > tolerance) {
            std::fprintf(stderr,
                         "actual=%.17g expected=%.17g error=%.17g tolerance=%.17g\n",
                         actual,
                         expected,
                         std::abs(actual - expected),
                         tolerance);
        }
        TERMIN_QOPT_CHECK(std::abs(actual - expected) <= tolerance);
    }

    void check_near(Vec3 actual, Vec3 expected, double tolerance = kTolerance) {
        check_near(actual.x, expected.x, tolerance);
        check_near(actual.y, expected.y, tolerance);
        check_near(actual.z, expected.z, tolerance);
    }

    Vec3 multiply(ConstDenseMatrixView matrix, const std::vector<double>& vector) {
        TERMIN_QOPT_CHECK(matrix.rows == 3);
        TERMIN_QOPT_CHECK(matrix.columns == vector.size());
        Vec3 result = Vec3::zero();
        double* values[3]{&result.x, &result.y, &result.z};
        for (std::size_t row = 0; row < 3; ++row) {
            for (std::size_t column = 0; column < vector.size(); ++column) {
                *values[row] += matrix(row, column) * vector[column];
            }
        }
        return result;
    }

    double dot(const std::vector<double>& a, const std::vector<double>& b) {
        TERMIN_QOPT_CHECK(a.size() == b.size());
        double result = 0.0;
        for (std::size_t index = 0; index < a.size(); ++index) {
            result += a[index] * b[index];
        }
        return result;
    }

    void bind(DynamicsContribution& contribution) {
        DynamicsTopology topology;
        TERMIN_QOPT_CHECK(contribution.register_topology(topology) == AssemblyDiagnostic::None);
        TERMIN_QOPT_CHECK(topology.finalize() == AssemblyDiagnostic::None);
    }

    SpatialInertia3 inertia() {
        return {1.0, {0.2, 0.3, 0.4}, Pose3::identity()};
    }

    std::vector<ArticulationUnit3D> branching_units() {
        return {
            {
                .parent_unit = articulation_root_frame,
                .parent_to_unit_zero = Pose3::translation(1.0, -0.1, 0.3),
                .motion_twist_at_unit =
                    Screw3{Vec3::unit_z(), Vec3::zero()}.adjoint_inv(Pose3::translation(0.8, 0.0, 0.0)),
                .inertia = inertia(),
                .diagnostic_name = "root-hinge",
            },
            {
                .parent_unit = 0,
                .parent_to_unit_zero = (Pose3::translation(0.5, 0.2, -0.1) * Pose3::rotation(Vec3::unit_x(), 0.2) *
                                        Pose3::translation(0.4, 0.1, 0.0))
                                           .normalized(),
                .motion_twist_at_unit =
                    Screw3{Vec3::unit_y(), Vec3::zero()}.adjoint_inv(Pose3::translation(0.4, 0.1, 0.0)),
                .inertia = inertia(),
                .diagnostic_name = "child-hinge",
            },
            {
                .parent_unit = 0,
                .parent_to_unit_zero = Pose3::translation(-0.2, 0.4, 0.3),
                .motion_twist_at_unit =
                    Screw3{Vec3::zero(), Vec3::unit_z()}.adjoint_inv(Pose3::translation(0.0, 0.0, 0.2)),
                .inertia = inertia(),
                .diagnostic_name = "sibling-slider",
            },
        };
    }

    void test_static_point() {
        const Vec3 position{1.0, -2.0, 3.0};
        const PointKinematics3DResult result = static_point_kinematics(position);
        TERMIN_QOPT_CHECK(result.ok());
        check_near(result.value.position_world, position);
        check_near(result.value.velocity_world, Vec3::zero());
        TERMIN_QOPT_CHECK(result.value.is_static());
        TERMIN_QOPT_CHECK(result.value.dof_count() == 0);
        TERMIN_QOPT_CHECK(!result.value.dofs.valid());
        const ConstDenseMatrixView jacobian = result.value.linear_jacobian_world();
        TERMIN_QOPT_CHECK(jacobian.rows == 3);
        TERMIN_QOPT_CHECK(jacobian.columns == 0);
        TERMIN_QOPT_CHECK(result.value.map_force_to_generalized_effort({1.0, 2.0, 3.0}, {}) ==
                          PointKinematics3DDiagnostic::None);
    }

    void test_rigid_body_point() {
        const RigidBody3DState state{
            Pose3::translation(0.4, -0.3, 1.2) * Pose3::rotation(Vec3{1.0, 2.0, -1.0}.normalized(), 0.7),
            {{0.3, -0.5, 0.8}, {1.2, -0.4, 0.6}},
        };
        RigidBody3DContribution body(inertia(), state, Vec3::zero(), "point-body");
        bind(body);

        const Vec3 point_local{0.2, -0.7, 0.5};
        const PointKinematics3DResult result = body.point_kinematics(point_local);
        TERMIN_QOPT_CHECK(result.ok());
        TERMIN_QOPT_CHECK(result.value.dof_count() == 6);
        TERMIN_QOPT_CHECK(!result.value.is_static());
        TERMIN_QOPT_CHECK(result.value.dofs.valid());
        check_near(result.value.position_world, state.pose.transform_point(point_local));

        const std::vector<double> velocity{
            state.velocity_local.lin.x,
            state.velocity_local.lin.y,
            state.velocity_local.lin.z,
            state.velocity_local.ang.x,
            state.velocity_local.ang.y,
            state.velocity_local.ang.z,
        };
        check_near(multiply(result.value.linear_jacobian_world(), velocity), result.value.velocity_world);

        const std::array<Screw3, 6> basis{
            Screw3{{}, Vec3::unit_x()},
            Screw3{{}, Vec3::unit_y()},
            Screw3{{}, Vec3::unit_z()},
            Screw3{Vec3::unit_x(), {}},
            Screw3{Vec3::unit_y(), {}},
            Screw3{Vec3::unit_z(), {}},
        };
        constexpr double epsilon = 1e-6;
        const ConstDenseMatrixView jacobian = result.value.linear_jacobian_world();
        for (std::size_t column = 0; column < basis.size(); ++column) {
            const Vec3 positive = (state.pose * se3_exp(basis[column] * epsilon)).transform_point(point_local);
            const Vec3 negative = (state.pose * se3_exp(basis[column] * -epsilon)).transform_point(point_local);
            const Vec3 derivative = (positive - negative) / (2.0 * epsilon);
            check_near(derivative, {jacobian(0, column), jacobian(1, column), jacobian(2, column)}, 2e-10);
        }

        const Vec3 force_world{-2.0, 0.7, 1.4};
        std::vector<double> effort(6);
        TERMIN_QOPT_CHECK(result.value.map_force_to_generalized_effort(
                              force_world, {effort.data(), effort.size(), 1}) == PointKinematics3DDiagnostic::None);
        check_near(dot(velocity, effort), result.value.velocity_world.dot(force_world));
    }

    void test_articulation_point() {
        const Articulation3DState state{
            {0.35, -0.42, 0.17},
            {0.8, -0.55, 1.1},
        };
        Articulation3D model(branching_units(), state, "branching-point-model");
        const ArticulationPointKinematics3DResult model_result = model.point_kinematics(1, {0.15, -0.25, 0.35});
        TERMIN_QOPT_CHECK(model_result.ok());
        TERMIN_QOPT_CHECK(model_result.value.dof_count() == 3);
        check_near(multiply(model_result.value.linear_jacobian_world(), state.velocities),
                   model_result.value.velocity_world);
        Articulation3DDynamicsContribution articulation(model, Vec3::zero());
        bind(articulation);

        constexpr std::size_t unit_index = 1;
        const Vec3 point_local{0.15, -0.25, 0.35};
        const PointKinematics3DResult result = articulation.point_kinematics(unit_index, point_local);
        TERMIN_QOPT_CHECK(result.ok());
        TERMIN_QOPT_CHECK(result.value.dof_count() == 3);
        TERMIN_QOPT_CHECK(result.value.dofs.valid());
        check_near(result.value.position_world,
                   articulation.unit_poses_world()[unit_index].transform_point(point_local));
        check_near(multiply(result.value.linear_jacobian_world(), state.velocities), result.value.velocity_world);

        const ConstDenseMatrixView jacobian = result.value.linear_jacobian_world();
        check_near(jacobian(0, 2), 0.0);
        check_near(jacobian(1, 2), 0.0);
        check_near(jacobian(2, 2), 0.0);

        constexpr double epsilon = 1e-6;
        for (std::size_t column = 0; column < state.coordinates.size(); ++column) {
            Articulation3DState positive = state;
            positive.coordinates[column] += epsilon;
            TERMIN_QOPT_CHECK(articulation.set_state(positive) == Articulation3DDiagnostic::None);
            const Vec3 positive_position = articulation.point_kinematics(unit_index, point_local).value.position_world;

            Articulation3DState negative = state;
            negative.coordinates[column] -= epsilon;
            TERMIN_QOPT_CHECK(articulation.set_state(negative) == Articulation3DDiagnostic::None);
            const Vec3 negative_position = articulation.point_kinematics(unit_index, point_local).value.position_world;

            const Vec3 derivative = (positive_position - negative_position) / (2.0 * epsilon);
            check_near(derivative, {jacobian(0, column), jacobian(1, column), jacobian(2, column)}, 2e-9);
        }
        TERMIN_QOPT_CHECK(articulation.set_state(state) == Articulation3DDiagnostic::None);

        const Vec3 force_world{1.3, -0.8, 2.1};
        std::vector<double> effort(3);
        TERMIN_QOPT_CHECK(result.value.map_force_to_generalized_effort(
                              force_world, {effort.data(), effort.size(), 1}) == PointKinematics3DDiagnostic::None);
        check_near(dot(state.velocities, effort), result.value.velocity_world.dot(force_world));
    }

    void test_endpoint_motion() {
        const Vec3 point{0.2, -0.7, 0.5};
        const Pose3 pose = Pose3::translation(1, 2, 3) * Pose3::rotation(Vec3::unit_y(), 0.45);
        const Screw3 velocity{{0.4, 0.7, -0.3}, {-1, 2, 0.5}};
        RigidBody3DContribution body(inertia(), {pose, velocity});
        Articulation3D model(
            {inertia(), pose, velocity, "base"}, branching_units(), {{0.1, 0.2, 0.3}, {0.2, -0.4, 0.6}});
        Articulation3DDynamicsContribution articulation(model);
        const auto rigid = ContactEndpoint3D::rigid_body(body, point);
        const auto ground = ContactEndpoint3D::static_world(point);
        const auto base = ContactEndpoint3D::articulation_base(articulation, point);
        const auto unit = ContactEndpoint3D::articulation_unit(articulation, 1, point);

        // A point can be queried before binding, but cannot register a dynamic contact row yet.
        ContactSet3DContribution contacts;
        TERMIN_QOPT_CHECK(
            contacts.set_contacts(
                {{.key = 1, .endpoint_a = ground, .endpoint_b = rigid, .normal_from_a_to_b_world = Vec3::unit_z()}}) ==
            Contact3DDiagnostic::None);
        DynamicsUnilateralTopology topology;
        TERMIN_QOPT_CHECK(contacts.register_unilateral_constraints(topology, 0.001) != AssemblyDiagnostic::None);
        TERMIN_QOPT_CHECK(contacts.diagnostic() == Contact3DDiagnostic::InvalidEndpoint);
        bind(body);
        bind(articulation);
        for (const auto& endpoint : {ground, rigid, base, unit}) {
            const auto motion = endpoint.point_motion();
            const auto full = endpoint.point_kinematics();
            TERMIN_QOPT_CHECK(motion.ok() && full.ok());
            TERMIN_QOPT_CHECK(motion.dofs.block == full.value.dofs.block);
            TERMIN_QOPT_CHECK(motion.dofs.valid() != endpoint.is_static());
            check_near(motion.value.position_world, full.value.position_world);
            check_near(motion.value.velocity_world, full.value.velocity_world);
        }
        const double largest = std::numeric_limits<double>::max();
        const auto overflowing = ContactEndpoint3D::articulation_base(articulation, {largest, 0.0, largest});
        TERMIN_QOPT_CHECK(overflowing.point_motion().diagnostic == PointKinematics3DDiagnostic::InvalidModel);
        const auto base_motion = base.point_motion();
        check_near(base_motion.value.position_world, pose.transform_point(point));
        check_near(base_motion.value.velocity_world, pose.transform_vector(velocity.lin + velocity.ang.cross(point)));
        const auto unit_motion = unit.point_motion();
        check_near(unit_motion.value.position_world, model.unit_poses_world()[1].transform_point(point));
        const auto& link_twist = model.unit_velocities_local()[1];
        check_near(unit_motion.value.velocity_world,
                   model.unit_poses_world()[1].transform_vector(link_twist.lin + link_twist.ang.cross(point)));

        const Vec3 bad{0, std::numeric_limits<double>::quiet_NaN(), 0};
        for (const auto& endpoint : {ContactEndpoint3D::static_world(bad),
                                     ContactEndpoint3D::rigid_body(body, bad),
                                     ContactEndpoint3D::articulation_base(articulation, bad),
                                     ContactEndpoint3D::articulation_unit(articulation, 1, bad)}) {
            TERMIN_QOPT_CHECK(endpoint.point_motion().diagnostic == PointKinematics3DDiagnostic::NonFinitePoint);
        }
        TERMIN_QOPT_CHECK(ContactEndpoint3D{}.point_motion().diagnostic == PointKinematics3DDiagnostic::InvalidModel);
        TERMIN_QOPT_CHECK(ContactEndpoint3D::articulation_unit(articulation, 3, point).point_motion().diagnostic ==
                          PointKinematics3DDiagnostic::InvalidUnit);
    }

    void test_diagnostics() {
        const double nan = std::numeric_limits<double>::quiet_NaN();
        TERMIN_QOPT_CHECK(static_point_kinematics({nan, 0.0, 0.0}).diagnostic ==
                          PointKinematics3DDiagnostic::NonFinitePoint);

        RigidBody3DContribution invalid_body({0.0, {1.0, 1.0, 1.0}, Pose3::identity()});
        TERMIN_QOPT_CHECK(invalid_body.point_kinematics(Vec3::zero()).diagnostic ==
                          PointKinematics3DDiagnostic::InvalidModel);

        RigidBody3DContribution body(inertia());
        TERMIN_QOPT_CHECK(body.point_kinematics({0.0, nan, 0.0}).diagnostic ==
                          PointKinematics3DDiagnostic::NonFinitePoint);

        Articulation3D model(branching_units(), {{0.0, 0.0, 0.0}, {0.0, 0.0, 0.0}});
        Articulation3DDynamicsContribution articulation(model);
        TERMIN_QOPT_CHECK(articulation.floating_base_point_motion(Vec3::zero()).diagnostic ==
                          PointKinematics3DDiagnostic::InvalidModel);
        TERMIN_QOPT_CHECK(articulation.point_kinematics(3, Vec3::zero()).diagnostic ==
                          PointKinematics3DDiagnostic::InvalidUnit);
        TERMIN_QOPT_CHECK(articulation.point_kinematics(0, {0.0, 0.0, nan}).diagnostic ==
                          PointKinematics3DDiagnostic::NonFinitePoint);

        const PointKinematics3DResult result = body.point_kinematics(Vec3::zero());
        TERMIN_QOPT_CHECK(result.ok());
        std::vector<double> effort(6);
        TERMIN_QOPT_CHECK(
            result.value.map_force_to_generalized_effort({nan, 0.0, 0.0}, {effort.data(), effort.size(), 1}) ==
            PointKinematics3DDiagnostic::NonFiniteForce);
        TERMIN_QOPT_CHECK(
            result.value.map_force_to_generalized_effort(Vec3::zero(), {effort.data(), effort.size() - 1, 1}) ==
            PointKinematics3DDiagnostic::InvalidOutput);
    }

} // namespace

int main() {
    test_static_point();
    test_rigid_body_point();
    test_articulation_point();
    test_endpoint_motion();
    test_diagnostics();
    return 0;
}
