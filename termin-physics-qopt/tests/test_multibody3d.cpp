#include <termin/physics_qopt/multibody3d.hpp>

#include "multibody_oracle_case.hpp"
#include "test_check.hpp"

#include <algorithm>
#include <array>
#include <cmath>
#include <memory>

using namespace termin;
using namespace termin::physics_qopt;

namespace
{

    Vec3 vec(OracleVec3 v)
    {
        return {v.x, v.y, v.z};
    }

    Quat quat(OracleQuat v)
    {
        return {v.x, v.y, v.z, v.w};
    }

    Pose3 pose(OraclePose3 v)
    {
        return {quat(v.quaternion), vec(v.translation)};
    }

    SpatialInertia3 inertia(OracleSpatialInertia3D v)
    {
        return {v.mass, vec(v.principal_moments), pose(v.inertia_frame_local)};
    }

    RigidBody3DState state(const OracleBody3D& v)
    {
        const Pose3 initial_pose = pose(v.initial_pose);
        return {
            initial_pose,
            Screw3{
                initial_pose.ang.inverse_rotate(
                    vec(v.initial_angular_velocity)),
                initial_pose.ang.inverse_rotate(vec(v.initial_linear_velocity)),
            },
        };
    }

    double distance(Vec3 a, Vec3 b)
    {
        return (a - b).norm();
    }

    double quaternion_norm(Quat q)
    {
        return std::sqrt(q.x * q.x + q.y * q.y + q.z * q.z + q.w * q.w);
    }

    template <typename Contribution>
    Contribution* add(Multibody3DSystem& system,
                      std::unique_ptr<Contribution> contribution)
    {
        Contribution* result = contribution.get();
        if (system.add_contribution(std::move(contribution)) !=
            DynamicsSystemDiagnostic::None)
        {
            return nullptr;
        }
        return result;
    }

    Multibody3DStepOptions
    options(double dt, double tolerance, std::size_t iterations = 8)
    {
        return {
            .time_step = dt,
            .position_tolerance = tolerance,
            .velocity_tolerance = tolerance,
            .max_position_iterations = iterations,
            .qp_tolerance = {},
        };
    }

} // namespace

int main()
{
    const auto& free_fall_oracle = kFreeFall3DOracle;
    const auto& anchored_oracle = kAnchoredPoint3DOracle;
    const auto& hinge_oracle = kFixedRevolute3DOracle;
    const auto& double_oracle = kDoubleRevolute3DOracle;

    const SpatialInertia3 offset_inertia =
        inertia(free_fall_oracle.body.inertia);
    const Mat66 matrix = offset_inertia.matrix_vw();
    for (std::size_t row = 0; row < 6; ++row)
    {
        for (std::size_t column = 0; column < 6; ++column)
        {
            TERMIN_QOPT_CHECK(
                std::abs(
                    matrix(static_cast<int>(column), static_cast<int>(row)) -
                    matrix(static_cast<int>(row), static_cast<int>(column))) <
                1e-12);
        }
    }
    TERMIN_QOPT_CHECK(
        RigidBody3DContribution({0.0, {1.0, 1.0, 1.0}, {}}).diagnostic() ==
        Multibody3DDiagnostic::InvalidMass);
    TERMIN_QOPT_CHECK(
        RigidBody3DContribution({1.0, {1.0, -1.0, 1.0}, {}}).diagnostic() ==
        Multibody3DDiagnostic::InvalidInertia);

    // The system sees only the base interface; the body owns its equations and
    // state.
    Multibody3DSystem free_fall;
    const Vec3 gravity = vec(free_fall_oracle.gravity);
    auto* falling = add(
        free_fall,
        std::make_unique<RigidBody3DContribution>(
            offset_inertia, state(free_fall_oracle.body), gravity, "falling"));
    TERMIN_QOPT_CHECK(falling != nullptr);
    TERMIN_QOPT_CHECK(free_fall.finalize() == DynamicsSystemDiagnostic::None);
    TERMIN_QOPT_CHECK(free_fall.topology().dof_count() == 6);
    TERMIN_QOPT_CHECK(free_fall.topology().constraint_count() == 0);
    TERMIN_QOPT_CHECK(
        free_fall.step(options(free_fall_oracle.time_step, 1e-9)).ok());
    TERMIN_QOPT_CHECK(distance(falling->twist_rate_at_body_origin_local().lin,
                               gravity) < free_fall_oracle.acceleration_linf);
    TERMIN_QOPT_CHECK(falling->twist_rate_at_body_origin_local().ang.norm() <
                      free_fall_oracle.acceleration_linf);

    Multibody3DSystem gyroscope;
    auto* spinning = add(gyroscope,
                         std::make_unique<RigidBody3DContribution>(
                             SpatialInertia3{1.0, {2.0, 3.0, 4.0}, {}},
                             RigidBody3DState{
                                 {},
                                 Screw3{{1.0, 2.0, 3.0}, {7.0, -3.0, 2.0}},
                             },
                             Vec3::zero(),
                             "gyroscope"));
    TERMIN_QOPT_CHECK(spinning != nullptr);
    TERMIN_QOPT_CHECK(gyroscope.finalize() == DynamicsSystemDiagnostic::None);
    TERMIN_QOPT_CHECK(gyroscope.step(options(1e-5, 1e-9)).ok());
    // Velocity Verlet exposes acceleration at q[n+1], not the first force
    // evaluation at q[n]. The exact initial gyroscopic load is covered by the
    // assembly test; over this tiny step the endpoint value stays nearby.
    TERMIN_QOPT_CHECK(distance(spinning->twist_rate_at_body_origin_local().ang,
                               {-3.0, 2.0, -0.5}) < 1e-3);

    // A fixed point is a separate three-row contribution.
    Multibody3DSystem anchored;
    auto* pendulum = add(anchored,
                         std::make_unique<RigidBody3DContribution>(
                             inertia(anchored_oracle.body.inertia),
                             state(anchored_oracle.body),
                             vec(anchored_oracle.gravity),
                             "anchored"));
    TERMIN_QOPT_CHECK(pendulum != nullptr);
    auto* fixed = add(anchored,
                      std::make_unique<FixedPointJoint3DContribution>(
                          *pendulum,
                          vec(anchored_oracle.body_anchor_local),
                          vec(anchored_oracle.world_anchor),
                          "world-point"));
    TERMIN_QOPT_CHECK(fixed != nullptr);
    TERMIN_QOPT_CHECK(anchored.finalize() == DynamicsSystemDiagnostic::None);
    TERMIN_QOPT_CHECK(anchored.topology().constraint_count() == 3);
    const double anchored_energy = pendulum->total_energy();
    for (std::size_t step = 0; step < anchored_oracle.steps; ++step)
    {
        TERMIN_QOPT_CHECK(anchored
                              .step(options(anchored_oracle.time_step,
                                            anchored_oracle.constraint_linf,
                                            6))
                              .ok());
    }
    TERMIN_QOPT_CHECK(distance(pendulum->state().pose.transform_point(
                                   vec(anchored_oracle.body_anchor_local)),
                               vec(anchored_oracle.world_anchor)) <
                      anchored_oracle.constraint_linf);
    TERMIN_QOPT_CHECK(anchored.max_velocity_constraint_error() <
                      anchored_oracle.constraint_linf);
    TERMIN_QOPT_CHECK(std::abs(quaternion_norm(pendulum->state().pose.ang) -
                               1.0) < anchored_oracle.quaternion_norm);
    TERMIN_QOPT_CHECK(std::abs(pendulum->total_energy() - anchored_energy) /
                          std::max(1.0, std::abs(anchored_energy)) <
                      anchored_oracle.relative_energy_drift);

    // Contributions may share body variables without the collector knowing
    // their type.
    Multibody3DSystem pair;
    const SpatialInertia3 unit_inertia{1.0, {0.25, 0.3, 0.35}, {}};
    auto* body_a = add(pair,
                       std::make_unique<RigidBody3DContribution>(
                           unit_inertia,
                           RigidBody3DState{
                               {Quat::identity(), {-0.5, 0.0, 0.0}},
                               Screw3{{0.3, 0.0, 0.0}, Vec3::zero()},
                           },
                           Vec3::zero(),
                           "a"));
    auto* body_b = add(pair,
                       std::make_unique<RigidBody3DContribution>(
                           unit_inertia,
                           RigidBody3DState{
                               {Quat::identity(), {0.5, 0.0, 0.0}},
                               Screw3{{-0.2, 0.1, 0.0}, Vec3::zero()},
                           },
                           Vec3::zero(),
                           "b"));
    auto* point =
        add(pair,
            std::make_unique<PointJoint3DContribution>(*body_a,
                                                       Vec3{0.5, 0.0, 0.0},
                                                       *body_b,
                                                       Vec3{-0.5, 0.0, 0.0},
                                                       "ball"));
    TERMIN_QOPT_CHECK(body_a && body_b && point);
    TERMIN_QOPT_CHECK(pair.finalize() == DynamicsSystemDiagnostic::None);
    const auto first_pair = pair.step(options(0.001, 1e-9, 6));
    TERMIN_QOPT_CHECK(first_pair.ok());
    TERMIN_QOPT_CHECK(first_pair.dynamics.constraint_rank == 3);
    for (std::size_t step = 1; step < 200; ++step)
        TERMIN_QOPT_CHECK(pair.step(options(0.001, 1e-9, 6)).ok());
    TERMIN_QOPT_CHECK(
        distance(body_a->state().pose.transform_point({0.5, 0.0, 0.0}),
                 body_b->state().pose.transform_point({-0.5, 0.0, 0.0})) <
        1e-9);
    TERMIN_QOPT_CHECK(distance(body_a->velocity_at_body_origin_world().ang,
                               body_b->velocity_at_body_origin_world().ang) >
                      1e-3);

    Multibody3DSystem hinge;
    auto* hinge_body = add(hinge,
                           std::make_unique<RigidBody3DContribution>(
                               inertia(hinge_oracle.body.inertia),
                               state(hinge_oracle.body),
                               vec(hinge_oracle.gravity),
                               "hinge-body"));
    auto invalid_hinge =
        std::make_unique<FixedRevoluteJoint3DContribution>(*hinge_body,
                                                           Vec3::zero(),
                                                           Vec3::zero(),
                                                           Vec3::zero(),
                                                           Vec3::unit_y(),
                                                           "invalid-axis");
    TERMIN_QOPT_CHECK(invalid_hinge->diagnostic() ==
                      Multibody3DDiagnostic::InvalidJointAxis);
    auto* world_hinge = add(hinge,
                            std::make_unique<FixedRevoluteJoint3DContribution>(
                                *hinge_body,
                                vec(hinge_oracle.body_anchor_local),
                                vec(hinge_oracle.body_axis_local),
                                vec(hinge_oracle.world_anchor),
                                vec(hinge_oracle.world_axis),
                                "world-hinge"));
    TERMIN_QOPT_CHECK(world_hinge != nullptr);
    TERMIN_QOPT_CHECK(hinge.finalize() == DynamicsSystemDiagnostic::None);
    const auto first_hinge = hinge.step(
        options(hinge_oracle.time_step, hinge_oracle.constraint_linf));
    TERMIN_QOPT_CHECK(first_hinge.ok());
    TERMIN_QOPT_CHECK(first_hinge.dynamics.constraint_rank ==
                      hinge_oracle.constraint_rows);
    for (std::size_t step = 1; step < hinge_oracle.steps; ++step)
    {
        TERMIN_QOPT_CHECK(hinge
                              .step(options(hinge_oracle.time_step,
                                            hinge_oracle.constraint_linf))
                              .ok());
    }
    const Vec3 hinge_axis =
        hinge_body->state().pose.ang.rotate(vec(hinge_oracle.body_axis_local));
    TERMIN_QOPT_CHECK(hinge_axis.cross(vec(hinge_oracle.world_axis)).norm() <
                      hinge_oracle.constraint_linf);

    Multibody3DSystem double_hinge;
    auto* upper = add(double_hinge,
                      std::make_unique<RigidBody3DContribution>(
                          inertia(double_oracle.bodies[0].inertia),
                          state(double_oracle.bodies[0]),
                          vec(double_oracle.gravity),
                          "upper"));
    auto* lower = add(double_hinge,
                      std::make_unique<RigidBody3DContribution>(
                          inertia(double_oracle.bodies[1].inertia),
                          state(double_oracle.bodies[1]),
                          vec(double_oracle.gravity),
                          "lower"));
    auto* upper_hinge = add(double_hinge,
                            std::make_unique<FixedRevoluteJoint3DContribution>(
                                *upper,
                                vec(double_oracle.body_fixed_anchor),
                                vec(double_oracle.body_fixed_axis),
                                vec(double_oracle.world_anchor),
                                vec(double_oracle.world_axis),
                                "upper-world"));
    auto* lower_hinge = add(double_hinge,
                            std::make_unique<RevoluteJoint3DContribution>(
                                *upper,
                                vec(double_oracle.body_a_anchor),
                                vec(double_oracle.body_a_axis),
                                *lower,
                                vec(double_oracle.body_b_anchor),
                                vec(double_oracle.body_b_axis),
                                "upper-lower"));
    TERMIN_QOPT_CHECK(upper && lower && upper_hinge && lower_hinge);
    TERMIN_QOPT_CHECK(double_hinge.finalize() ==
                      DynamicsSystemDiagnostic::None);
    TERMIN_QOPT_CHECK(double_hinge.contribution_count() == 4);
    const double initial_energy = upper->total_energy() + lower->total_energy();
    for (std::size_t step = 0; step < double_oracle.steps; ++step)
    {
        const auto result = double_hinge.step(
            options(double_oracle.time_step, double_oracle.constraint_linf));
        TERMIN_QOPT_CHECK(result.ok());
        if (step == 0)
            TERMIN_QOPT_CHECK(result.dynamics.constraint_rank ==
                              2 * double_oracle.constraint_rows);
    }
    const Vec3 upper_axis =
        upper->state().pose.ang.rotate(vec(double_oracle.body_a_axis));
    const Vec3 lower_axis =
        lower->state().pose.ang.rotate(vec(double_oracle.body_b_axis));
    TERMIN_QOPT_CHECK(upper_axis.cross(vec(double_oracle.world_axis)).norm() <
                      double_oracle.constraint_linf);
    TERMIN_QOPT_CHECK(upper_axis.cross(lower_axis).norm() <
                      double_oracle.constraint_linf);
    TERMIN_QOPT_CHECK(
        std::abs(upper_hinge->reaction_at_joint_anchor_world().ang.dot(
            upper_axis)) < double_oracle.reaction_axis_work);
    TERMIN_QOPT_CHECK(
        std::abs(lower_hinge->reaction_at_joint_anchor_world().ang.dot(
            upper_axis)) < double_oracle.reaction_axis_work);
    const double final_energy = upper->total_energy() + lower->total_energy();
    TERMIN_QOPT_CHECK(std::abs(final_energy - initial_energy) /
                          std::max(1.0, std::abs(initial_energy)) <
                      double_oracle.relative_energy_drift);

    return 0;
}
