#include <termin/qopt/multibody2d.hpp>

#include "test_check.hpp"

#include <cmath>

using namespace termin;
using namespace termin::qopt;

int main() {
  Multibody2DSystem invalid;
  TERMIN_QOPT_CHECK(
      invalid.add_body({0.0, 1.0, {}}).diagnostic
      == Multibody2DDiagnostic::InvalidMass
  );

  Multibody2DSystem falling;
  const auto falling_body = falling.add_body(
      {2.0, 0.75, {0.2, -0.1}},
      {{0.25, {1.0, 2.0}}, {0.5, -0.25}, 0.0},
      "falling"
  );
  TERMIN_QOPT_CHECK(falling_body.ok());
  TERMIN_QOPT_CHECK(falling.finalize() == Multibody2DDiagnostic::None);
  const auto falling_step = falling.step(
      {0.0, -10.0},
      {
          .time_step = 0.01,
          .position_tolerance = 1e-9,
          .velocity_tolerance = 1e-9,
          .max_position_iterations = 4,
          .qp_tolerance = {},
      }
  );
  TERMIN_QOPT_CHECK(falling_step.status == QpStatus::Optimal);
  const RigidBody2DAcceleration falling_acceleration =
      falling.body_acceleration(falling_body.handle);
  TERMIN_QOPT_CHECK(
      std::abs(falling_acceleration.linear_world.x) < 1e-10
  );
  TERMIN_QOPT_CHECK(
      std::abs(falling_acceleration.linear_world.y + 10.0) < 1e-10
  );
  TERMIN_QOPT_CHECK(std::abs(falling_acceleration.angular) < 1e-10);

  Multibody2DSystem pendulum;
  const auto pendulum_body = pendulum.add_body(
      {1.5, 0.2, {}},
      {{0.0, {0.5, -0.8660254037844386}}, {}, 0.0},
      "pendulum"
  );
  TERMIN_QOPT_CHECK(pendulum_body.ok());
  const auto fixed = pendulum.add_fixed_point_joint(
      pendulum_body.handle,
      {-0.5, 0.8660254037844386},
      {0.0, 0.0},
      "anchor"
  );
  TERMIN_QOPT_CHECK(fixed.ok());
  TERMIN_QOPT_CHECK(pendulum.finalize() == Multibody2DDiagnostic::None);
  const double initial_energy = pendulum.total_energy({0.0, -10.0});
  for (std::size_t step = 0; step < 500; ++step) {
    const Multibody2DStepResult result = pendulum.step(
        {0.0, -10.0},
        {
            .time_step = 0.001,
            .position_tolerance = 1e-9,
            .velocity_tolerance = 1e-9,
            .max_position_iterations = 4,
            .qp_tolerance = {},
        }
    );
    TERMIN_QOPT_CHECK(result.status == QpStatus::Optimal);
  }
  TERMIN_QOPT_CHECK(
      pendulum.max_position_constraint_error() < 1e-9
  );
  TERMIN_QOPT_CHECK(
      pendulum.max_velocity_constraint_error() < 1e-9
  );
  const Vec2 fixed_reaction = pendulum.joint_reaction(fixed.handle);
  TERMIN_QOPT_CHECK(std::isfinite(fixed_reaction.x));
  TERMIN_QOPT_CHECK(std::isfinite(fixed_reaction.y));
  const double final_energy = pendulum.total_energy({0.0, -10.0});
  TERMIN_QOPT_CHECK(
      std::abs(final_energy - initial_energy)
          / std::max(1.0, std::abs(initial_energy))
      < 0.03
  );

  Multibody2DSystem pair;
  const auto first = pair.add_body(
      {1.0, 0.1, {}}, {{0.0, {0.0, 0.0}}, {}, 0.0}, "first"
  );
  const auto second = pair.add_body(
      {1.0, 0.1, {}}, {{0.0, {1.0, 0.0}}, {}, 0.0}, "second"
  );
  TERMIN_QOPT_CHECK(first.ok());
  TERMIN_QOPT_CHECK(second.ok());
  const auto revolute = pair.add_revolute_joint(
      first.handle, {0.5, 0.0}, second.handle, {-0.5, 0.0}, "revolute"
  );
  TERMIN_QOPT_CHECK(revolute.ok());
  TERMIN_QOPT_CHECK(pair.finalize() == Multibody2DDiagnostic::None);
  TERMIN_QOPT_CHECK(
      pair.step(
          {0.0, -10.0},
          {
              .time_step = 0.001,
              .position_tolerance = 1e-9,
              .velocity_tolerance = 1e-9,
              .max_position_iterations = 4,
              .qp_tolerance = {},
          }
      ).status
      == QpStatus::Optimal
  );
  TERMIN_QOPT_CHECK(pair.max_position_constraint_error() < 1e-9);
  TERMIN_QOPT_CHECK(pair.max_velocity_constraint_error() < 1e-9);

  return 0;
}
