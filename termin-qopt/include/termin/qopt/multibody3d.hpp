#pragma once

#include <cstddef>
#include <cstdint>
#include <limits>
#include <memory>
#include <string_view>

#include <termin/geom/pose3.hpp>
#include <termin/qopt/dynamics.hpp>
#include <termin/qopt/termin_qopt_api.hpp>

namespace termin::qopt {

enum class Multibody3DDiagnostic : std::uint8_t {
  None,
  ModelFinalized,
  ModelNotFinalized,
  InvalidBody,
  InvalidJoint,
  InvalidMass,
  InvalidInertia,
  NonFiniteInput,
  InvalidMatrixView,
  DuplicateBody,
  InvalidJointAxis,
  InvalidTimeStep,
  InvalidProjectionOptions,
  AssemblyFailure,
  DynamicsFailure,
  PositionProjectionFailure,
  VelocityProjectionFailure,
  InternalFailure,
};

[[nodiscard]] TERMIN_QOPT_API std::string_view
multibody3d_diagnostic_name(Multibody3DDiagnostic diagnostic) noexcept;

struct RigidBody3DHandle {
  std::uint64_t system_id = 0;
  std::size_t index = std::numeric_limits<std::size_t>::max();

  [[nodiscard]] constexpr bool valid() const noexcept {
    return system_id != 0
        && index != std::numeric_limits<std::size_t>::max();
  }
};

struct PointJoint3DHandle {
  std::uint64_t system_id = 0;
  std::size_t index = std::numeric_limits<std::size_t>::max();

  [[nodiscard]] constexpr bool valid() const noexcept {
    return system_id != 0
        && index != std::numeric_limits<std::size_t>::max();
  }
};

struct RevoluteJoint3DHandle {
  std::uint64_t system_id = 0;
  std::size_t index = std::numeric_limits<std::size_t>::max();

  [[nodiscard]] constexpr bool valid() const noexcept {
    return system_id != 0
        && index != std::numeric_limits<std::size_t>::max();
  }
};

template <typename Handle>
struct Multibody3DRegistrationResult {
  Handle handle;
  Multibody3DDiagnostic diagnostic = Multibody3DDiagnostic::None;

  [[nodiscard]] constexpr bool ok() const noexcept {
    return diagnostic == Multibody3DDiagnostic::None;
  }
};

// Principal moments and their frame are expressed in body-local coordinates.
// inertia_frame_local.lin is the center of mass; .ang orients principal axes.
struct SpatialInertia3D {
  double mass = 1.0;
  termin::Vec3 principal_moments = {1.0, 1.0, 1.0};
  termin::Pose3 inertia_frame_local = termin::Pose3::identity();
};

// Writes the 6x6 spatial inertia about the body origin in generalized ordering
// [linear_world(3), angular_world(3)].
[[nodiscard]] TERMIN_QOPT_API Multibody3DDiagnostic
write_spatial_inertia3d_matrix_world(
    const SpatialInertia3D& inertia,
    termin::Quat body_orientation_world,
    DenseMatrixView destination
) noexcept;

struct RigidBody3DState {
  termin::Pose3 pose = termin::Pose3::identity();
  termin::Vec3 linear_velocity_world = termin::Vec3::zero();
  termin::Vec3 angular_velocity_world = termin::Vec3::zero();
};

struct RigidBody3DAcceleration {
  termin::Vec3 linear_world = termin::Vec3::zero();
  termin::Vec3 angular_world = termin::Vec3::zero();
};

// Persistent external wrench about the body-frame origin, expressed in world
// coordinates. Gravity is supplied separately to step().
struct RigidBody3DWrench {
  termin::Vec3 force_world = termin::Vec3::zero();
  termin::Vec3 torque_about_origin_world = termin::Vec3::zero();
};

// Constraint wrench applied to body A (or to the body for a fixed joint).
// torque_world is perpendicular to the hinge axis by construction.
struct RevoluteJoint3DReaction {
  termin::Vec3 force_world = termin::Vec3::zero();
  termin::Vec3 torque_world = termin::Vec3::zero();
};

struct Multibody3DStepOptions {
  double time_step = 0.001;
  double position_tolerance = 1e-9;
  double velocity_tolerance = 1e-9;
  std::size_t max_position_iterations = 6;
  QpTolerance qp_tolerance;
};

struct Multibody3DStepResult {
  QpStatus status = QpStatus::InvalidInput;
  Multibody3DDiagnostic diagnostic = Multibody3DDiagnostic::None;
  QpSolveResult dynamics;
  double position_constraint_linf =
      std::numeric_limits<double>::infinity();
  double velocity_constraint_linf =
      std::numeric_limits<double>::infinity();
  std::size_t position_iterations = 0;
};

// Dense maximal-coordinate 3D model. Its generalized-vector ordering is
// [linear_world(3), angular_world(3)]. Point joints constrain translation at
// an anchor and deliberately leave all three relative rotational DOFs free.
class TERMIN_QOPT_API Multibody3DSystem {
public:
  Multibody3DSystem();
  ~Multibody3DSystem();

  Multibody3DSystem(Multibody3DSystem&&) noexcept;
  Multibody3DSystem& operator=(Multibody3DSystem&&) noexcept;

  Multibody3DSystem(const Multibody3DSystem&) = delete;
  Multibody3DSystem& operator=(const Multibody3DSystem&) = delete;

  [[nodiscard]] Multibody3DRegistrationResult<RigidBody3DHandle> add_body(
      SpatialInertia3D inertia,
      RigidBody3DState initial_state = {},
      std::string_view diagnostic_name = {}
  ) noexcept;

  [[nodiscard]] Multibody3DRegistrationResult<PointJoint3DHandle>
  add_fixed_point_joint(
      RigidBody3DHandle body,
      termin::Vec3 body_anchor_local,
      termin::Vec3 world_anchor,
      std::string_view diagnostic_name = {}
  ) noexcept;

  [[nodiscard]] Multibody3DRegistrationResult<PointJoint3DHandle>
  add_point_joint(
      RigidBody3DHandle body_a,
      termin::Vec3 body_a_anchor_local,
      RigidBody3DHandle body_b,
      termin::Vec3 body_b_anchor_local,
      std::string_view diagnostic_name = {}
  ) noexcept;

  [[nodiscard]] Multibody3DRegistrationResult<RevoluteJoint3DHandle>
  add_fixed_revolute_joint(
      RigidBody3DHandle body,
      termin::Vec3 body_anchor_local,
      termin::Vec3 body_axis_local,
      termin::Vec3 world_anchor,
      termin::Vec3 world_axis,
      std::string_view diagnostic_name = {}
  ) noexcept;

  [[nodiscard]] Multibody3DRegistrationResult<RevoluteJoint3DHandle>
  add_revolute_joint(
      RigidBody3DHandle body_a,
      termin::Vec3 body_a_anchor_local,
      termin::Vec3 body_a_axis_local,
      RigidBody3DHandle body_b,
      termin::Vec3 body_b_anchor_local,
      termin::Vec3 body_b_axis_local,
      std::string_view diagnostic_name = {}
  ) noexcept;

  [[nodiscard]] Multibody3DDiagnostic finalize() noexcept;
  [[nodiscard]] bool finalized() const noexcept;
  [[nodiscard]] std::size_t body_count() const noexcept;
  [[nodiscard]] std::size_t joint_count() const noexcept;

  [[nodiscard]] Multibody3DDiagnostic set_body_state(
      RigidBody3DHandle body, RigidBody3DState state
  ) noexcept;
  [[nodiscard]] Multibody3DDiagnostic set_body_wrench(
      RigidBody3DHandle body, RigidBody3DWrench wrench
  ) noexcept;
  [[nodiscard]] RigidBody3DState body_state(
      RigidBody3DHandle body
  ) const noexcept;
  [[nodiscard]] RigidBody3DAcceleration body_acceleration(
      RigidBody3DHandle body
  ) const noexcept;
  [[nodiscard]] termin::Vec3 joint_reaction(
      PointJoint3DHandle joint
  ) const noexcept;
  [[nodiscard]] RevoluteJoint3DReaction revolute_joint_reaction(
      RevoluteJoint3DHandle joint
  ) const noexcept;

  [[nodiscard]] Multibody3DStepResult step(
      termin::Vec3 gravity_world,
      Multibody3DStepOptions options = {}
  ) noexcept;

  [[nodiscard]] double max_position_constraint_error() const noexcept;
  [[nodiscard]] double max_velocity_constraint_error() const noexcept;
  [[nodiscard]] double total_energy(termin::Vec3 gravity_world) const noexcept;

private:
  struct Impl;
  std::unique_ptr<Impl> impl_;
};

} // namespace termin::qopt
