# Hierarchical multibody authoring

Status: proposed architecture, 2026-08-01.

## Goal

Author an articulated mechanism as an ordinary scene hierarchy instead of
manually wiring body names and joint endpoints. A mechanism root owns the
simulation, inertial links are marked explicitly, and existing
`RotatorComponent` / `ActuatorComponent` nodes describe the one-degree-of-
freedom transform between adjacent links. The scene graph is compiled once as
a reduced-coordinate articulation inside the native
`termin::qopt::Multibody3DSystem` topology when play starts.

The authoring hierarchy is the source description, not the numerical model.
The compiled multibody graph owns runtime body state, joint handles, drive
state and solver workspace. An articulation contributes a floating-base block
of `6 + joint_count` generalized degrees of freedom instead of registering six
independent degrees of freedom and constraint rows for every link. This keeps
scene traversal, matrix assembly and time integration in separate layers.

`Multibody3DSystem` is the common contribution collector and stepping boundary,
not a synonym for maximal coordinates. Maximal bodies, forces, point joints
and revolute constraints are public contribution types outside the collector.
Reduced articulations are an additional contribution type in the same topology
and may coexist with maximal-coordinate bodies and external constraints.

This stack remains separate from the gameplay-oriented `termin-physics`
engine. Sharing scene conventions or collision geometry later does not imply
sharing world state or solver internals.

## Scene grammar

The initial supported form is a rooted tree:

```text
MechanismRoot (MultibodyMechanismComponent)
└── Base (MultibodyBodyComponent, optional for a fixed base)
    ├── visual/collider descendants belonging to Base
    └── HipJoint (RotatorComponent)
        └── UpperLeg (MultibodyBodyComponent)
            └── KneeJoint (RotatorComponent + optional MultibodyDriveComponent)
                └── LowerLeg (MultibodyBodyComponent)
```

Rules are deliberately strict:

- a floating mechanism has exactly one root body;
- a fixed mechanism uses the mechanism root as a world frame and does not
  create a dynamic root body;
- every non-root body has exactly one nearest ancestor body and exactly one
  enabled kinematic unit on the path between them;
- `RotatorComponent` compiles to a revolute joint;
- `ActuatorComponent` will compile to a prismatic joint once the native
  primitive exists;
- ordinary transform nodes between a joint and a body are fixed attachment
  frames and are folded into the compiled local anchors;
- branches are allowed, cycles, cross-mechanism references, multiple joint
  units on one body edge, massless implicit bodies and ambiguous ownership are
  rejected with entity-path diagnostics;
- a kinematic unit with no descendant body is not silently ignored.

The strict one-joint-per-body-edge rule is enough for common robot limbs and
keeps the mapping to maximal coordinates unambiguous. Multi-DOF compound
joints should later be an explicit primitive, not an accidental chain of
massless scene nodes.

## Components and ownership

### `MultibodyMechanismComponent`

Lives at the root and owns:

- compile/rebuild policy and diagnostics;
- the native `Multibody3DSystem` instance;
- the entity-to-contribution bindings;
- fixed-step accumulation, gravity and projection options;
- synchronization from solver body poses to scene transforms.

Topology is immutable after `Multibody3DSystem::finalize()`. Structural scene
changes require an explicit rebuild; scalar commands and external loads do
not. A failed rebuild leaves no partially usable runtime graph.

### `MultibodyBodyComponent`

Marks an inertial link and owns authored mass properties: mass, principal
moments and the local inertia/COM frame. Inside a hierarchical mechanism it
receives a typed articulated-link handle after successful compilation but
does not own the solver or step it. The existing independent-body handle and
registration path remain unchanged for maximal-coordinate models.

Geometry-derived inertia can be added later as an explicit authoring service.
It must not be guessed from arbitrary descendants during the first slice.

### `KinematicUnitComponent`

`RotatorComponent` and `ActuatorComponent` remain the canonical description of
the relative one-DOF transform:

- `base_position`, `base_rotation`, `base_scale` define the zero-coordinate
  attachment transform;
- axis direction defines the joint axis;
- axis length maps authored coordinate units to radians or metres;
- `coordinate` defines the authored/commanded coordinate;
- `min_coordinate` and `max_coordinate` define authored joint bounds.

Outside a dynamic mechanism, the current behavior is unchanged: changing
`coordinate` applies the kinematic transform. Inside a running mechanism the
compiled physics graph owns the actual body transforms. The component must
therefore expose read-only measured coordinate and velocity separately; it
must not overwrite `coordinate` with measured state.

The runtime ownership switch must be explicit. It is an error for both the
kinematic component and the physics synchronizer to write the same transform
during one simulation tick.

### `MultibodyDriveComponent`

Drive policy is optional and separate from joint geometry. It is attached to
the same entity as a `KinematicUnitComponent`. This avoids putting
QP-specific control fields into the reusable kinematic transform component.

The initial modes should be:

- `Passive`;
- `Effort`, with commanded force/torque and an effort limit;
- `PositionServo`, with target coordinate, target velocity, stiffness,
  damping, feed-forward effort and an effort limit.

The compiler automatically creates the native drive record and binds it to
the inferred joint. Missing drive means a passive joint. A drive without one
co-located kinematic unit is a compile error.

The first servo should contribute bounded equal-and-opposite internal wrench
to the adjacent bodies. An ideal acceleration constraint or HQP task can be a
later drive mode; it should not be disguised as the same physical actuator.

## Transform compilation

Compilation uses the authored world transforms before physics starts:

1. Traverse only the mechanism root subtree and assign every entity to its
   nearest marked body or to the fixed world root.
2. Register one articulation contribution and its inertial links, retaining
   typed articulation/link handles.
3. For each body edge, locate its single kinematic unit.
4. Use the joint entity world origin as the anchor and rotate the normalized
   authored axis into world space.
5. Transform the anchor and axis into both adjacent body-local frames.
6. Register an internal reduced-coordinate joint and its motion subspace;
   these tree joints do not add constraint rows.
7. Record the zero-coordinate relative orientation/translation needed to
   measure the joint coordinate continuously at runtime.
8. Register an optional drive and authored bounds, then finalize atomically.

Axis magnitude is never passed as physical geometry. It is only the unit
scale between component coordinate and the native joint coordinate.

During a step, body poses are written back in parent-before-child order using
global pose setters. Joint marker nodes remain attached to the parent body;
the child body local transform becomes the solver-owned residual relative to
that marker. The play-mode lifecycle must restore the authored scene state on
stop, as for other simulated components.

## Native model additions

The existing native 3D multibody slice supplies maximal-coordinate bodies,
point joints, true revolute constraints, reactions, equality-QP dynamics and
constraint projection. It remains intact, including the current pendulum
model. The common `Multibody3DSystem` needs an additional articulated-tree
contribution whose generalized state is a fixed/floating base plus one scalar
coordinate per revolute or prismatic joint.

The reduced contribution assembles its generalized mass matrix and bias/load
vector into the same `DynamicsTopology`. Its implementation may use standard
spatial articulated-body machinery (RNEA/CRBA and, where useful, ABA), while
the outer system retains the existing assembly, QP and step boundary.
Constraints which are not part of the tree—contacts, closed loops and links to
maximal-coordinate bodies—contribute Jacobian blocks with respect to the
articulation generalized coordinates. Thus reduced and maximal subsystems can
participate in one solve without pretending that every articulated link owns
six independent DOFs.

Controlled robot mechanisms additionally require explicit native contracts:

1. Articulation topology and generalized state: base pose/twist plus scalar
   joint coordinates and velocities.
2. Forward kinematics and link spatial Jacobians for synchronization and
   external constraints.
3. Generalized mass, bias/load and motor-effort assembly in the common world.
4. Prismatic joint state and effort for `ActuatorComponent`.
5. Joint bounds represented as unilateral constraints. Bounds must not be
   implemented by clamping transforms after integration.
6. Deterministic diagnostics for invalid topology, degenerate axes, duplicate
   body ownership, failed finalization and failed steps.

A visually convincing free-falling articulated dog needs only revolute joints
and drives. A dog that stands or walks needs a further contact slice: collision
queries, non-penetration, normal reactions and friction. The current native
multibody model has no contact contract, so locomotion is explicitly outside
the first vertical slice.

## Recommended delivery slices

### Slice 1: reduced articulation foundation

- add an articulation contribution to `Multibody3DSystem` beside the existing
  public body/joint contributions;
- fixed/floating base, inertial links and revolute joints;
- generalized state, forward kinematics and generalized dynamics assembly;
- native tests comparing a reduced pendulum fixture with the existing maximal
  pendulum on observable motion/energy invariants;
- keep the existing pendulum scene and model unchanged.

This validates coexistence of both formulations inside one system before scene
authoring or motor semantics are added.

### Slice 2: hierarchical scene authoring and drives

- native scene components for mechanism, body and drive;
- compiler for fixed/floating roots and `RotatorComponent` edges;
- bounded effort and position-servo drive;
- `MultibodyDriveComponent` and runtime command/state binding;
- a branching suspended quadruped scene with moving legs;
- energy, reaction and constraint-error tests.

### Slice 3: prismatic joints and bounds

- native prismatic joint;
- compile `ActuatorComponent`;
- proper unilateral min/max constraints for both joint types;
- limit activation/deactivation and invalid-range tests.

### Slice 4: contacts

- define the collision-query boundary without merging the two physics worlds;
- non-penetration and friction model;
- standing and locomotion acceptance scenes.

## Rejected shortcuts

- Generating name-based `FEM*JointComponent` records in the scene. This keeps
  the fragile references and merely hides them behind an importer.
- Treating the Python `RevoluteJoint3D` as the target backend. It is a
  three-row point/ball joint; the native five-row revolute joint is the
  correct primitive.
- Creating a second world/system API merely because articulation internals use
  reduced coordinates. Coordinate formulation is an implementation/model
  choice inside the common `Multibody3DSystem` boundary.
- Using `RotatorComponent.coordinate` simultaneously as command and measured
  state. Feedback would overwrite the next control target.
- Applying motor motion by writing transforms after the physics step. That
  bypasses reaction forces, inertia and the QP constraints.
- Silently accepting malformed hierarchies or fabricating massless bodies.
  During active development a clear compile failure is preferable to a model
  whose physics differs from the authored mechanism.
