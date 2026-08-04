# termin-robotics

`termin-robotics` owns solver-neutral models and task semantics used by robot
control. The first implemented layer is `Articulation3D`: one fixed- or
floating-base kinematic tree with reduced joint coordinates.

## Current articulation layer

`Articulation3D` owns topology, configuration, velocity and kinematic caches.
Each link stores its parent joint transform, one-DOF motion twist, link frame,
limits and spatial inertia. The floating root is an explicit six-DOF body, not
a fictitious joint.

The current API provides:

- forward kinematics for branching trees;
- body-local link velocities;
- link-frame world twists and spatial generalized Jacobians in `vw` order;
- material-point world positions, velocities and linear generalized Jacobians;
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
joint limits support both orders. Pose tracking, point velocity and current
signed-distance avoidance are velocity-level tasks until their acceleration
bias (`Jdot qdot` and curvature terms) is represented explicitly.

The standard task layer currently provides:

- `PoseTrackingTask3D`, using an SE(3) logarithmic pose error expressed in the
  world frame;
- `PointVelocityTask3D`;
- `JointPositionTask3D` with optional velocity feed-forward;
- `JointVelocityTask3D`;
- `JointLimitConstraint3D`, using one-step position prediction;
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

velocity_control
└── kinematic HQP formulation

inverse_dynamics
└── dynamic HQP formulation
```

Velocity and inverse-dynamics formulations share the task linearization
contract but produce different equations and decision-variable layouts.
Neither formulation integrates the physical scene directly.

Closed chains are expected to be represented above `Articulation3D` as one or
more spanning trees plus explicit frame-to-frame closure constraints. The tree
itself intentionally remains acyclic so its recursive algorithms stay simple.
