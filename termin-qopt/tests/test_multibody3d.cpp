#include <termin/qopt/multibody3d.hpp>

#include "multibody_oracle_case.hpp"
#include "test_check.hpp"

#include <algorithm>
#include <array>
#include <cmath>
#include <cstdio>

using namespace termin;
using namespace termin::qopt;

namespace {

[[nodiscard]] Vec3 vec(OracleVec3 value) {
  return {value.x, value.y, value.z};
}

[[nodiscard]] Quat quat(OracleQuat value) {
  return {value.x, value.y, value.z, value.w};
}

[[nodiscard]] Pose3 pose(OraclePose3 value) {
  return {quat(value.quaternion), vec(value.translation)};
}

[[nodiscard]] SpatialInertia3D inertia(
    OracleSpatialInertia3D value
) {
  return {
      value.mass,
      vec(value.principal_moments),
      pose(value.inertia_frame_local),
  };
}

[[nodiscard]] RigidBody3DState state(const OracleBody3D& value) {
  return {
      pose(value.initial_pose),
      vec(value.initial_linear_velocity),
      vec(value.initial_angular_velocity),
  };
}

[[nodiscard]] double distance(Vec3 first, Vec3 second) {
  return (first - second).norm();
}

[[nodiscard]] double quaternion_norm(Quat value) {
  return std::sqrt(
      value.x * value.x
      + value.y * value.y
      + value.z * value.z
      + value.w * value.w
  );
}

} // namespace

int main() {
  const auto& free_fall_oracle = kFreeFall3DOracle;
  const auto& anchored_oracle = kAnchoredPoint3DOracle;
  const auto& hinge_oracle = kFixedRevolute3DOracle;
  const auto& double_hinge_oracle = kDoubleRevolute3DOracle;

  // Spatial inertia is symmetric and includes the COM parallel-axis coupling.
  const SpatialInertia3D offset_inertia =
      inertia(free_fall_oracle.body.inertia);
  std::array<double, 36> matrix{};
  TERMIN_QOPT_CHECK(
      write_spatial_inertia3d_matrix_world(
          offset_inertia,
          Quat::identity(),
          DenseMatrixView::row_major(matrix.data(), 6, 6)
      ) == Multibody3DDiagnostic::None
  );
  for (std::size_t row = 0; row < 6; ++row) {
    for (std::size_t column = 0; column < 6; ++column) {
      TERMIN_QOPT_CHECK(
          std::abs(matrix[row * 6 + column]
                   - matrix[column * 6 + row])
          < 1e-12
      );
    }
  }
  for (std::size_t index = 0; index < 6; ++index) {
    TERMIN_QOPT_CHECK(
        std::abs(
            matrix[index * 6 + index]
            - free_fall_oracle.expected_spatial_inertia_diagonal[index]
        ) < 1e-12
    );
  }
  TERMIN_QOPT_CHECK(std::abs(matrix[11] - 2.0) < 1e-12);
  TERMIN_QOPT_CHECK(std::abs(matrix[31] - 2.0) < 1e-12);
  TERMIN_QOPT_CHECK(
      write_spatial_inertia3d_matrix_world(
          offset_inertia,
          Quat::identity(),
          {matrix.data(), 6, 6, 0, 1}
      ) == Multibody3DDiagnostic::InvalidMatrixView
  );

  std::array<double, 36> rotated_matrix{};
  TERMIN_QOPT_CHECK(
      write_spatial_inertia3d_matrix_world(
          offset_inertia,
          Quat::from_axis_angle(Vec3::unit_z(), 0.5 * std::acos(-1.0)),
          DenseMatrixView::row_major(rotated_matrix.data(), 6, 6)
      ) == Multibody3DDiagnostic::None
  );
  TERMIN_QOPT_CHECK(std::abs(rotated_matrix[21] - 6.0) < 1e-10);
  TERMIN_QOPT_CHECK(std::abs(rotated_matrix[28] - 3.0) < 1e-10);
  TERMIN_QOPT_CHECK(std::abs(rotated_matrix[35] - 7.0) < 1e-10);

  Multibody3DSystem invalid;
  TERMIN_QOPT_CHECK(
      invalid.add_body({0.0, {1.0, 1.0, 1.0}, {}}).diagnostic
      == Multibody3DDiagnostic::InvalidMass
  );
  TERMIN_QOPT_CHECK(
      invalid.add_body({1.0, {1.0, -1.0, 1.0}, {}}).diagnostic
      == Multibody3DDiagnostic::InvalidInertia
  );

  // A COM-offset free body must still accelerate rigidly under uniform gravity.
  Multibody3DSystem free_fall;
  const auto falling = free_fall.add_body(
      offset_inertia,
      state(free_fall_oracle.body),
      "falling"
  );
  TERMIN_QOPT_CHECK(falling.ok());
  TERMIN_QOPT_CHECK(
      free_fall.finalize() == Multibody3DDiagnostic::None
  );
  const Vec3 gravity = vec(free_fall_oracle.gravity);
  const auto falling_step = free_fall.step(
      gravity,
      {
          .time_step = free_fall_oracle.time_step,
          .position_tolerance = 1e-9,
          .velocity_tolerance = 1e-9,
          .max_position_iterations = 6,
          .qp_tolerance = {},
      }
  );
  TERMIN_QOPT_CHECK(falling_step.status == QpStatus::Optimal);
  const RigidBody3DAcceleration falling_acceleration =
      free_fall.body_acceleration(falling.handle);
  TERMIN_QOPT_CHECK(
      distance(falling_acceleration.linear_world, gravity)
      < free_fall_oracle.acceleration_linf
  );
  TERMIN_QOPT_CHECK(
      falling_acceleration.angular_world.norm()
      < free_fall_oracle.acceleration_linf
  );
  TERMIN_QOPT_CHECK(
      std::abs(
          free_fall.body_state(falling.handle).pose.lin.z
          - (
              free_fall_oracle.body.initial_pose.translation.z
              + gravity.z
                  * free_fall_oracle.time_step
                  * free_fall_oracle.time_step
          )
      ) < 1e-10
  );

  // World-frame Euler bias is omega x (I omega), with no origin-velocity term.
  Multibody3DSystem gyroscope;
  const auto spinning = gyroscope.add_body(
      {
          1.0,
          {2.0, 3.0, 4.0},
          {},
      },
      {
          {},
          {7.0, -3.0, 2.0},
          {1.0, 2.0, 3.0},
      },
      "gyroscope"
  );
  TERMIN_QOPT_CHECK(spinning.ok());
  TERMIN_QOPT_CHECK(gyroscope.finalize() == Multibody3DDiagnostic::None);
  TERMIN_QOPT_CHECK(
      gyroscope.step(
          {},
          {
              .time_step = 1e-5,
              .position_tolerance = 1e-9,
              .velocity_tolerance = 1e-9,
              .max_position_iterations = 6,
              .qp_tolerance = {},
          }
      ).status == QpStatus::Optimal
  );
  const RigidBody3DAcceleration gyroscopic_acceleration =
      gyroscope.body_acceleration(spinning.handle);
  TERMIN_QOPT_CHECK(gyroscopic_acceleration.linear_world.norm() < 1e-12);
  TERMIN_QOPT_CHECK(
      distance(gyroscopic_acceleration.angular_world, {-3.0, 2.0, -0.5})
      < 1e-10
  );

  // A fixed point leaves all rotations free while projection holds its anchor.
  Multibody3DSystem anchored;
  const Vec3 local_anchor = vec(anchored_oracle.body_anchor_local);
  const Vec3 world_anchor = vec(anchored_oracle.world_anchor);
  const auto pendulum = anchored.add_body(
      inertia(anchored_oracle.body.inertia),
      state(anchored_oracle.body),
      "anchored"
  );
  TERMIN_QOPT_CHECK(pendulum.ok());
  const auto fixed = anchored.add_fixed_point_joint(
      pendulum.handle, local_anchor, world_anchor, "world-point"
  );
  TERMIN_QOPT_CHECK(fixed.ok());
  TERMIN_QOPT_CHECK(anchored.finalize() == Multibody3DDiagnostic::None);
  TERMIN_QOPT_CHECK(anchored_oracle.relative_rotational_dofs == 3);
  const Vec3 anchored_gravity = vec(anchored_oracle.gravity);
  const double anchored_energy = anchored.total_energy(anchored_gravity);
  for (std::size_t step = 0; step < anchored_oracle.steps; ++step) {
    const auto result = anchored.step(
        anchored_gravity,
        {
            .time_step = anchored_oracle.time_step,
            .position_tolerance = anchored_oracle.constraint_linf,
            .velocity_tolerance = anchored_oracle.constraint_linf,
            .max_position_iterations = 6,
            .qp_tolerance = {},
        }
    );
    TERMIN_QOPT_CHECK(result.status == QpStatus::Optimal);
  }
  const RigidBody3DState anchored_state =
      anchored.body_state(pendulum.handle);
  TERMIN_QOPT_CHECK(
      distance(
          anchored_state.pose.transform_point(local_anchor),
          world_anchor
      ) < anchored_oracle.constraint_linf
  );
  TERMIN_QOPT_CHECK(
      anchored.max_velocity_constraint_error()
      < anchored_oracle.constraint_linf
  );
  TERMIN_QOPT_CHECK(
      std::abs(quaternion_norm(anchored_state.pose.ang) - 1.0)
      < anchored_oracle.quaternion_norm
  );
  const double anchored_energy_drift =
      std::abs(
          anchored.total_energy(anchored_gravity) - anchored_energy
      )
      / std::max(1.0, std::abs(anchored_energy));
  if (anchored_energy_drift >= anchored_oracle.relative_energy_drift) {
    std::fprintf(
        stderr,
        "anchored 3D energy drift: %.17g initial=%.17g final=%.17g "
        "position=%.17g velocity=%.17g omega=(%.17g,%.17g,%.17g)\n",
        anchored_energy_drift,
        anchored_energy,
        anchored.total_energy(anchored_gravity),
        anchored.max_position_constraint_error(),
        anchored.max_velocity_constraint_error(),
        anchored_state.angular_velocity_world.x,
        anchored_state.angular_velocity_world.y,
        anchored_state.angular_velocity_world.z
    );
  }
  TERMIN_QOPT_CHECK(
      anchored_energy_drift < anchored_oracle.relative_energy_drift
  );

  // A two-body point joint constrains only anchor translation.
  Multibody3DSystem pair;
  const SpatialInertia3D unit_inertia{
      1.0,
      {0.25, 0.3, 0.35},
      {},
  };
  const auto body_a = pair.add_body(
      unit_inertia,
      {{Quat::identity(), {-0.5, 0.0, 0.0}}, {}, {0.3, 0.0, 0.0}},
      "a"
  );
  const auto body_b = pair.add_body(
      unit_inertia,
      {{Quat::identity(), {0.5, 0.0, 0.0}}, {}, {-0.2, 0.1, 0.0}},
      "b"
  );
  TERMIN_QOPT_CHECK(body_a.ok());
  TERMIN_QOPT_CHECK(body_b.ok());
  const auto point = pair.add_point_joint(
      body_a.handle,
      {0.5, 0.0, 0.0},
      body_b.handle,
      {-0.5, 0.0, 0.0},
      "ball"
  );
  TERMIN_QOPT_CHECK(point.ok());
  TERMIN_QOPT_CHECK(pair.finalize() == Multibody3DDiagnostic::None);
  const auto first_pair_step = pair.step(
      {},
      {
          .time_step = 0.001,
          .position_tolerance = 1e-9,
          .velocity_tolerance = 1e-9,
          .max_position_iterations = 6,
          .qp_tolerance = {},
      }
  );
  TERMIN_QOPT_CHECK(first_pair_step.status == QpStatus::Optimal);
  TERMIN_QOPT_CHECK(first_pair_step.dynamics.constraint_rank == 3);
  for (std::size_t step = 1; step < 200; ++step) {
    TERMIN_QOPT_CHECK(
        pair.step(
            {},
            {
                .time_step = 0.001,
                .position_tolerance = 1e-9,
                .velocity_tolerance = 1e-9,
                .max_position_iterations = 6,
                .qp_tolerance = {},
            }
        ).status == QpStatus::Optimal
    );
  }
  const RigidBody3DState state_a = pair.body_state(body_a.handle);
  const RigidBody3DState state_b = pair.body_state(body_b.handle);
  TERMIN_QOPT_CHECK(
      distance(
          state_a.pose.transform_point({0.5, 0.0, 0.0}),
          state_b.pose.transform_point({-0.5, 0.0, 0.0})
      ) < 1e-9
  );
  TERMIN_QOPT_CHECK(
      distance(state_a.angular_velocity_world, state_b.angular_velocity_world)
      > 1e-3
  );
  TERMIN_QOPT_CHECK(pair.joint_reaction(point.handle).norm() < 10.0);

  // A true fixed revolute joint has five independent rows: three at the
  // anchor and two for axis alignment. Twist about the hinge remains free.
  Multibody3DSystem hinge;
  const auto hinge_body = hinge.add_body(
      inertia(hinge_oracle.body.inertia),
      state(hinge_oracle.body),
      "hinge-body"
  );
  TERMIN_QOPT_CHECK(hinge_body.ok());
  TERMIN_QOPT_CHECK(
      hinge.add_fixed_revolute_joint(
          hinge_body.handle,
          vec(hinge_oracle.body_anchor_local),
          vec(hinge_oracle.body_axis_local),
          vec(hinge_oracle.world_anchor),
          vec(hinge_oracle.world_axis),
          "world-hinge"
      ).ok()
  );
  TERMIN_QOPT_CHECK(
      hinge.add_fixed_revolute_joint(
          hinge_body.handle,
          Vec3::zero(),
          Vec3::zero(),
          Vec3::zero(),
          Vec3::unit_y(),
          "invalid-axis"
      ).diagnostic == Multibody3DDiagnostic::InvalidJointAxis
  );
  TERMIN_QOPT_CHECK(hinge.finalize() == Multibody3DDiagnostic::None);
  const auto first_hinge_step = hinge.step(
      vec(hinge_oracle.gravity),
      {
          .time_step = hinge_oracle.time_step,
          .position_tolerance = hinge_oracle.constraint_linf,
          .velocity_tolerance = hinge_oracle.constraint_linf,
          .max_position_iterations = 8,
          .qp_tolerance = {},
      }
  );
  TERMIN_QOPT_CHECK(first_hinge_step.status == QpStatus::Optimal);
  TERMIN_QOPT_CHECK(
      first_hinge_step.dynamics.constraint_rank
      == hinge_oracle.constraint_rows
  );
  TERMIN_QOPT_CHECK(hinge_oracle.relative_rotational_dofs == 1);
  for (std::size_t step = 1; step < hinge_oracle.steps; ++step) {
    TERMIN_QOPT_CHECK(
        hinge.step(
            vec(hinge_oracle.gravity),
            {
                .time_step = hinge_oracle.time_step,
                .position_tolerance = hinge_oracle.constraint_linf,
                .velocity_tolerance = hinge_oracle.constraint_linf,
                .max_position_iterations = 8,
                .qp_tolerance = {},
            }
        ).status == QpStatus::Optimal
    );
  }
  const RigidBody3DState hinge_state =
      hinge.body_state(hinge_body.handle);
  TERMIN_QOPT_CHECK(
      distance(
          hinge_state.pose.transform_point(
              vec(hinge_oracle.body_anchor_local)
          ),
          vec(hinge_oracle.world_anchor)
      ) < hinge_oracle.constraint_linf
  );
  const Vec3 hinge_axis =
      hinge_state.pose.ang.rotate(vec(hinge_oracle.body_axis_local));
  const Vec3 world_hinge_axis = vec(hinge_oracle.world_axis);
  TERMIN_QOPT_CHECK(
      hinge_axis.cross(world_hinge_axis).norm()
      < hinge_oracle.constraint_linf
  );
  TERMIN_QOPT_CHECK(
      (
          hinge_state.angular_velocity_world
          - world_hinge_axis
              * hinge_state.angular_velocity_world.dot(world_hinge_axis)
      ).norm() < hinge_oracle.constraint_linf
  );

  // A two-link spatial pendulum uses one world hinge and one body-body hinge.
  Multibody3DSystem double_hinge;
  const auto upper = double_hinge.add_body(
      inertia(double_hinge_oracle.bodies[0].inertia),
      state(double_hinge_oracle.bodies[0]),
      "upper"
  );
  const auto lower = double_hinge.add_body(
      inertia(double_hinge_oracle.bodies[1].inertia),
      state(double_hinge_oracle.bodies[1]),
      "lower"
  );
  TERMIN_QOPT_CHECK(upper.ok());
  TERMIN_QOPT_CHECK(lower.ok());
  const auto upper_hinge = double_hinge.add_fixed_revolute_joint(
      upper.handle,
      vec(double_hinge_oracle.body_fixed_anchor),
      vec(double_hinge_oracle.body_fixed_axis),
      vec(double_hinge_oracle.world_anchor),
      vec(double_hinge_oracle.world_axis),
      "upper-world"
  );
  const auto lower_hinge = double_hinge.add_revolute_joint(
      upper.handle,
      vec(double_hinge_oracle.body_a_anchor),
      vec(double_hinge_oracle.body_a_axis),
      lower.handle,
      vec(double_hinge_oracle.body_b_anchor),
      vec(double_hinge_oracle.body_b_axis),
      "upper-lower"
  );
  TERMIN_QOPT_CHECK(upper_hinge.ok());
  TERMIN_QOPT_CHECK(lower_hinge.ok());
  TERMIN_QOPT_CHECK(
      double_hinge.finalize() == Multibody3DDiagnostic::None
  );
  const Vec3 double_gravity = vec(double_hinge_oracle.gravity);
  const double double_energy = double_hinge.total_energy(double_gravity);
  for (std::size_t step = 0; step < double_hinge_oracle.steps; ++step) {
    const auto result = double_hinge.step(
        double_gravity,
        {
            .time_step = double_hinge_oracle.time_step,
            .position_tolerance = double_hinge_oracle.constraint_linf,
            .velocity_tolerance = double_hinge_oracle.constraint_linf,
            .max_position_iterations = 8,
            .qp_tolerance = {},
        }
    );
    TERMIN_QOPT_CHECK(result.status == QpStatus::Optimal);
    if (step == 0) {
      TERMIN_QOPT_CHECK(
          result.dynamics.constraint_rank
          == 2 * double_hinge_oracle.constraint_rows
      );
    }
  }
  const RigidBody3DState upper_state =
      double_hinge.body_state(upper.handle);
  const RigidBody3DState lower_state =
      double_hinge.body_state(lower.handle);
  TERMIN_QOPT_CHECK(
      distance(
          upper_state.pose.transform_point(
              vec(double_hinge_oracle.body_fixed_anchor)
          ),
          vec(double_hinge_oracle.world_anchor)
      ) < double_hinge_oracle.constraint_linf
  );
  TERMIN_QOPT_CHECK(
      distance(
          upper_state.pose.transform_point(
              vec(double_hinge_oracle.body_a_anchor)
          ),
          lower_state.pose.transform_point(
              vec(double_hinge_oracle.body_b_anchor)
          )
      ) < double_hinge_oracle.constraint_linf
  );
  const Vec3 upper_axis =
      upper_state.pose.ang.rotate(vec(double_hinge_oracle.body_a_axis));
  const Vec3 lower_axis =
      lower_state.pose.ang.rotate(vec(double_hinge_oracle.body_b_axis));
  TERMIN_QOPT_CHECK(
      upper_axis.cross(vec(double_hinge_oracle.world_axis)).norm()
      < double_hinge_oracle.constraint_linf
  );
  TERMIN_QOPT_CHECK(
      upper_axis.cross(lower_axis).norm()
      < double_hinge_oracle.constraint_linf
  );
  const RevoluteJoint3DReaction upper_reaction =
      double_hinge.revolute_joint_reaction(upper_hinge.handle);
  const RevoluteJoint3DReaction lower_reaction =
      double_hinge.revolute_joint_reaction(lower_hinge.handle);
  TERMIN_QOPT_CHECK(
      std::abs(upper_reaction.torque_world.dot(upper_axis))
      < double_hinge_oracle.reaction_axis_work
  );
  TERMIN_QOPT_CHECK(
      std::abs(lower_reaction.torque_world.dot(upper_axis))
      < double_hinge_oracle.reaction_axis_work
  );
  const double double_energy_drift =
      std::abs(
          double_hinge.total_energy(double_gravity) - double_energy
      )
      / std::max(1.0, std::abs(double_energy));
  TERMIN_QOPT_CHECK(
      double_energy_drift < double_hinge_oracle.relative_energy_drift
  );

  return 0;
}
