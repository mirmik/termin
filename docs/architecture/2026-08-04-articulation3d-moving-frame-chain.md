# Articulation3D as a chain of moving frames

Status: accepted and implemented as of 2026-08-04.

## Decision

`termin::robotics::Articulation3D` is a reduced-coordinate kinematic tree of
moving output frames. It is not an object model of alternating joints and
links.

Every `ArticulationUnit3D` simultaneously defines:

- one parent-relative moving output frame;
- one scalar generalized coordinate and its motion twist;
- the spatial inertia rigidly attached to that output frame;
- optional limits of the generalized coordinate.

Units are stored in topological order and refer directly to a parent unit or
to the articulation root frame:

```text
articulation root frame
└── unit 0: moving frame + coordinate + inertia
    └── unit 1: moving frame + coordinate + inertia
        └── unit 2: moving frame + coordinate + inertia
```

Branches use the same representation. “Chain” here means a sequence along
each root-to-leaf path, not a restriction to a single unbranched mechanism.

## Unit transform

For unit `i`, the parent-relative pose is

```text
parent_to_unit(q_i) = parent_to_unit_zero * exp(motion_twist_at_unit * q_i)
```

Both the twist and the spatial inertia are expressed in the unit output
frame. The unit frame is therefore the common coordinate system for forward
kinematics, spatial velocity, dynamics, point Jacobians and contact loads.

A conventional description

```text
A * exp(S * q) * B
```

does not require separate joint and link objects. Its fixed attachment `B`
is folded exactly into the unit representation:

```text
parent_to_unit_zero = A * B
motion_twist_at_unit = Ad(B^-1) * S
```

so that

```text
A * exp(S * q) * B
    = (A * B) * exp(Ad(B^-1) * S * q).
```

The inertia and local geometry are already expressed relative to the same
output frame. A physics backend may build private body records as solver
workspace, but those records are not articulation topology and must not leak
into the public model.

## Contacts and external consumers

An articulated contact endpoint is identified by

```text
articulation + unit_index + point_local
```

There is no body or link handle between the contact system and
`Articulation3D`. The physics adapter obtains the point pose, velocity,
Jacobian and generalized force mapping from the referenced unit frame.

Controllers follow the same boundary. They borrow or reference an
`Articulation3D` to calculate control commands; they do not own the
articulation, scene hierarchy or integrator. Likewise, `Articulation3D` owns
kinematic state and calculations but does not autonomously advance time.

## Consequences

- Do not introduce `Joint3D` and `Link3D` objects inside `Articulation3D`.
- Do not mirror the scene hierarchy as a second runtime object hierarchy.
- Keep mass, center of mass and inertia on the unit in its output frame.
- Use unit indices for kinematic queries, dynamics adapters and contacts.
- Treat joint/link scene formats such as URDF or the transitional FEM
  authoring hierarchy as compiler inputs, not as the native runtime model.
- Multi-DOF joints may be represented by multiple serial units or by a future
  explicit multi-coordinate unit; neither option requires link objects.

## Relation to scene authoring

The target scene hierarchy is

```text
ArticulationComponent (root)
└── KinematicUnit
    └── KinematicUnit
        └── ...
```

Scene components provide authored transforms, inertia and synchronization.
They compile into the unit tree above. `FEMArticulationComponent` may mark the
same tree as controlled by a physical solver, but it does not define an
alternative joint-link topology.

The current legacy FEM joint-to-body authoring grammar is documented in
[Hierarchical multibody authoring](hierarchical-multibody-authoring.md). Until
that scene migration is complete, its compiler must collapse authored
joint/body pairs into `ArticulationUnit3D`; the compatibility grammar must not
shape the `Articulation3D` API.
