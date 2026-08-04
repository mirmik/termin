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
- material-point world positions, velocities and generalized Jacobians;
- recursive inverse dynamics;
- dense reduced mass matrix construction;
- mechanical energy evaluation.

The tree has no solver handles, contacts, motor commands, time-integration
policy or scene ownership. `termin-physics-qopt` borrows it through
`Articulation3DDynamicsContribution`.

## Planned control layers

```text
articulation
├── kinematics and Jacobians
└── inertial model

tasks
├── pose tracking
├── point velocity
├── joint posture and limits
└── collision avoidance

velocity_control
└── kinematic HQP formulation

inverse_dynamics
└── dynamic HQP formulation
```

Velocity and inverse-dynamics formulations will share semantic task objects
but produce different equations and decision-variable layouts. Neither
formulation will integrate the physical scene directly.

Closed chains are expected to be represented above `Articulation3D` as one or
more spanning trees plus explicit frame-to-frame closure constraints. The tree
itself intentionally remains acyclic so its recursive algorithms stay simple.
