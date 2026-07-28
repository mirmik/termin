#pragma once

#include <cstddef>
#include <cstdint>
#include <limits>
#include <memory>
#include <string_view>

#include <termin/geom/pose2.hpp>
#include <termin/qopt/dynamics.hpp>
#include <termin/qopt/termin_qopt_api.hpp>

namespace termin::qopt {

enum class Multibody2DDiagnostic : std::uint8_t {
  None,
  ModelFinalized,
  ModelNotFinalized,
  InvalidBody,
  InvalidJoint,
  InvalidMass,
  InvalidInertia,
  NonFiniteInput,
  DuplicateBody,
  InvalidTimeStep,
  InvalidProjectionOptions,
  AssemblyFailure,
  DynamicsFailure,
  PositionProjectionFailure,
  VelocityProjectionFailure,
  InternalFailure,
};

[[nodiscard]] TERMIN_QOPT_API std::string_view
multibody2d_diagnostic_name(Multibody2DDiagnostic diagnostic) noexcept;

struct RigidBody2DHandle {
  std::uint64_t system_id = 0;
  std::size_t index = std::numeric_limits<std::size_t>::max();

  [[nodiscard]] constexpr bool valid() const noexcept {
    return system_id != 0
        && index != std::numeric_limits<std::size_t>::max();
  }
};

struct Joint2DHandle {
  std::uint64_t system_id = 0;
  std::size_t index = std::numeric_limits<std::size_t>::max();

  [[nodiscard]] constexpr bool valid() const noexcept {
    return system_id != 0
        && index != std::numeric_limits<std::size_t>::max();
  }
};

template <typename Handle>
struct Multibody2DRegistrationResult {
  Handle handle;
  Multibody2DDiagnostic diagnostic = Multibody2DDiagnostic::None;

  [[nodiscard]] constexpr bool ok() const noexcept {
    return diagnostic == Multibody2DDiagnostic::None;
  }
};

struct SpatialInertia2D {
  double mass = 1.0;
  double moment_at_center = 1.0;
  termin::Vec2 center_of_mass_local = termin::Vec2::zero();
};

struct RigidBody2DState {
  termin::Pose2 pose = termin::Pose2::identity();
  termin::Vec2 linear_velocity_world = termin::Vec2::zero();
  double angular_velocity = 0.0;
};

struct RigidBody2DAcceleration {
  termin::Vec2 linear_world = termin::Vec2::zero();
  double angular = 0.0;
};

// Persistent external generalized wrench about the body-frame origin,
// expressed in world coordinates. Gravity is supplied separately to step().
struct RigidBody2DWrench {
  termin::Vec2 force_world = termin::Vec2::zero();
  double torque_about_origin = 0.0;
};

struct Multibody2DStepOptions {
  double time_step = 0.001;
  double position_tolerance = 1e-9;
  double velocity_tolerance = 1e-9;
  std::size_t max_position_iterations = 4;
  QpTolerance qp_tolerance;
};

struct Multibody2DStepResult {
  QpStatus status = QpStatus::InvalidInput;
  Multibody2DDiagnostic diagnostic = Multibody2DDiagnostic::None;
  QpSolveResult dynamics;
  double position_constraint_linf =
      std::numeric_limits<double>::infinity();
  double velocity_constraint_linf =
      std::numeric_limits<double>::infinity();
  std::size_t position_iterations = 0;
};

// A small dense maximal-coordinate model. Model state, topology, numerical
// assembly and QP solving remain separate internally; this class orchestrates
// their lifetime for runtime consumers.
class TERMIN_QOPT_API Multibody2DSystem {
public:
  Multibody2DSystem();
  ~Multibody2DSystem();

  Multibody2DSystem(Multibody2DSystem&&) noexcept;
  Multibody2DSystem& operator=(Multibody2DSystem&&) noexcept;

  Multibody2DSystem(const Multibody2DSystem&) = delete;
  Multibody2DSystem& operator=(const Multibody2DSystem&) = delete;

  [[nodiscard]] Multibody2DRegistrationResult<RigidBody2DHandle> add_body(
      SpatialInertia2D inertia,
      RigidBody2DState initial_state = {},
      std::string_view diagnostic_name = {}
  ) noexcept;

  [[nodiscard]] Multibody2DRegistrationResult<Joint2DHandle>
  add_fixed_point_joint(
      RigidBody2DHandle body,
      termin::Vec2 body_anchor_local,
      termin::Vec2 world_anchor,
      std::string_view diagnostic_name = {}
  ) noexcept;

  [[nodiscard]] Multibody2DRegistrationResult<Joint2DHandle>
  add_revolute_joint(
      RigidBody2DHandle body_a,
      termin::Vec2 body_a_anchor_local,
      RigidBody2DHandle body_b,
      termin::Vec2 body_b_anchor_local,
      std::string_view diagnostic_name = {}
  ) noexcept;

  [[nodiscard]] Multibody2DDiagnostic finalize() noexcept;
  [[nodiscard]] bool finalized() const noexcept;
  [[nodiscard]] std::size_t body_count() const noexcept;
  [[nodiscard]] std::size_t joint_count() const noexcept;

  [[nodiscard]] Multibody2DDiagnostic set_body_state(
      RigidBody2DHandle body, RigidBody2DState state
  ) noexcept;
  [[nodiscard]] Multibody2DDiagnostic set_body_wrench(
      RigidBody2DHandle body, RigidBody2DWrench wrench
  ) noexcept;
  [[nodiscard]] RigidBody2DState body_state(
      RigidBody2DHandle body
  ) const noexcept;
  [[nodiscard]] RigidBody2DAcceleration body_acceleration(
      RigidBody2DHandle body
  ) const noexcept;
  [[nodiscard]] termin::Vec2 joint_reaction(
      Joint2DHandle joint
  ) const noexcept;

  [[nodiscard]] Multibody2DStepResult step(
      termin::Vec2 gravity_world,
      Multibody2DStepOptions options = {}
  ) noexcept;

  [[nodiscard]] double max_position_constraint_error() const noexcept;
  [[nodiscard]] double max_velocity_constraint_error() const noexcept;
  [[nodiscard]] double total_energy(termin::Vec2 gravity_world) const noexcept;

private:
  struct Impl;
  std::unique_ptr<Impl> impl_;
};

} // namespace termin::qopt
