# termin-robotics

`termin-robotics` owns solver-neutral models and task semantics used by robot
control. The first implemented layer is `Articulation3D`: one fixed- or
floating-base tree of one-DOF kinematic units.

## Current articulation layer

`Articulation3D` owns topology, configuration, velocity and kinematic caches.
Each `ArticulationUnit3D` stores its parent unit, zero-coordinate transform,
one-DOF motion twist, limits and spatial inertia. Its moving output frame is
also the frame in which the twist and inertia are expressed; there is no
separate joint/link topology or constant joint-to-link transform. The floating
root is an explicit six-DOF base frame, not a fictitious unit.

The current API provides:

- forward kinematics for branching trees;
- unit-local output-frame velocities;
- unit-frame world twists and spatial generalized Jacobians in `vw` order;
- material-point world positions, velocities and linear generalized Jacobians;
- exact frame/point bias acceleration `Jdot(q,qdot) qdot` in world coordinates;
- recursive inverse dynamics;
- dense reduced mass matrix construction;
- mechanical energy evaluation.

The tree has no solver handles, contacts, motor commands, time-integration
policy or scene ownership. `termin-physics-qopt` borrows it through
`Articulation3DDynamicsContribution`.

## Task contracts

`TaskLinearization3D` is the common owned boundary between semantic robot
tasks and a control formulation. It contains a row-major matrix, right-hand
side, optional objective weight, priority, activation state and the derivative
order of its decision vector. It has no solver, physics-world or scene handles.

Relations have one canonical meaning:

- objective: minimize `||A x - b||²_W`;
- equality: `A x = b`;
- inequality: `A x <= b`.

`TaskLinearizationContext3D` selects generalized velocity or acceleration.
Tasks reject an unsupported order explicitly instead of silently applying a
velocity equation to accelerations. Joint velocity tracking and predictive
joint limits support both orders. `JointPostureTask3D` provides an explicit
acceleration-level joint PD law with optional acceleration feed-forward.
`PointAccelerationTask3D` and `PoseAccelerationTask3D` apply Cartesian PD plus
feed-forward acceleration and subtract the exact kinematic bias.
Signed-distance avoidance remains a velocity-level task.

The standard task layer currently provides:

- `PoseTrackingTask3D`, using an SE(3) logarithmic pose error expressed in the
  world frame;
- `PointVelocityTask3D`;
- `PointAccelerationTask3D`, with world position/velocity feedback and
  acceleration feed-forward;
- `PoseAccelerationTask3D`, with world-frame SE(3) feedback and spatial
  acceleration feed-forward;
- `JointPositionTask3D` with optional velocity feed-forward;
- `JointVelocityTask3D`;
- `JointPostureTask3D`, with position/velocity feedback and acceleration
  feed-forward;
- `JointLimitConstraint3D`, using one-step position prediction;
- `JointVelocityLimitConstraint3D`, usable as velocity bounds or as one-step
  acceleration bounds;
- `PointAvoidanceConstraint3D`, consuming a signed-distance sample and its
  outward world normal without depending on a collision world.

An empty joint selection means all reduced joints. Floating-base variables
remain the first six `vw` entries, followed by scalar joint variables. Task
weights are diagonal in the standard convenience classes; custom task types
may return any symmetric positive-semidefinite full weight through the common
linearization contract.

## Control layers

```text
articulation
├── kinematics and Jacobians
└── inertial model

tasks (implemented)
├── pose tracking
├── point velocity
├── joint posture and limits
└── collision avoidance

velocity_control (implemented)
├── kinematic HQP formulation
└── explicit articulation-state integration boundary

inverse_dynamics_control (implemented foundation)
├── acceleration-level HQP formulation
├── floating-base underactuation equations
├── actuator effort bounds and inverse-dynamics output
└── generic environmental-force decision blocks
```

Velocity and inverse-dynamics formulations share the task linearization
contract but produce different equations and decision-variable layouts.
Neither formulation integrates the physical scene directly.

`VelocityHqpController3D` relinearizes the supplied task list on every call,
groups active objectives and constraints by ascending integer priority, and
builds a `termin-qopt` hierarchical QP over generalized velocity. It supports
fixed and floating bases and exposes solver, task and per-level diagnostics.
The previous optimal generalized velocity is retained as an optional primal
warm start. The current `termin-qopt` HQP API does not retain an active set
between calls.

`InverseDynamicsHqpController3D` solves over generalized acceleration. It
constructs the reduced mass matrix and velocity/gravity bias from the
articulation, enforces zero required effort on unactuated DOFs, applies optional
per-actuator effort bounds inside the HQP, and returns both generalized
acceleration and the corresponding inverse-dynamics effort. By default every
scalar joint is actuated and the six floating-base DOFs are not. Known external
generalized loads may be supplied explicitly. Unknown environmental forces are
declared as solver-neutral `InverseDynamicsForceVariableBlock3D` objects with a
generalized-force basis and optional linear inequalities. The physics adapter
uses this contract for unilateral point-contact normal/tangent variables while
keeping contact ownership out of `termin-robotics`.

The controller does not mutate or integrate the plant. `termin-physics-qopt`
provides `inverse_dynamics_actuators_from_motor()` and
`apply_inverse_dynamics_motor_commands()` to preserve motor-channel DOF identity
and effort limits without introducing physical handles into this module.

Solving does not mutate the articulation. A caller that wants to advance the
model must explicitly call `integrate_articulation_velocity()`. Scalar joints
use explicit Euler integration. A floating root uses the right-trivialized
local base twist and a right SE(3) exponential update. The integrator does not
silently clamp coordinates; joint and velocity limits belong in the task set.

Closed chains are expected to be represented above `Articulation3D` as one or
more spanning trees plus explicit frame-to-frame closure constraints. The tree
itself intentionally remains acyclic so its recursive algorithms stay simple.

## Executable example

`examples/kinematic_point_control.cpp` is a complete public-API loop for a
two-unit arm. It relinearizes a point-velocity objective, solves bounded
kinematic HQP, and explicitly integrates the returned generalized velocity.
When native tests are enabled it is built and run as
`termin_robotics_kinematic_point_control_example`.
