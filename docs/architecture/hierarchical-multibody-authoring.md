# Hierarchical multibody authoring

Status: fixed- and floating-base robotics articulation core and scene authoring,
bounded servo, unilateral joint limits, solver-neutral point kinematics,
collision-world adaptation, persistent contact, and convex Coulomb-friction
slices and standing-robot acceptance implemented. Native velocity HQP and the
inverse-dynamics HQP, exact Cartesian acceleration bias tasks and explicit
contact-force control variables are implemented as of 2026-08-04; restitution
and material mixing remain future work.

> This document describes the current FEM scene-authoring grammar, including
> its transitional joint/body entities. The compiled `Articulation3D` runtime
> model does not preserve that split: it is a tree of moving output frames with
> inertia stored directly on each unit. See
> [Articulation3D as a chain of moving frames](2026-08-04-articulation3d-moving-frame-chain.md).

## Goal

Author an articulated mechanism as an ordinary scene hierarchy instead of
manually wiring body names and joint endpoints. A mechanism root owns the
simulation, inertial links are marked explicitly, and existing
`RotatorComponent` / `ActuatorComponent` nodes describe the one-degree-of-
freedom transform between adjacent links. The scene graph is compiled once as
a reduced-coordinate articulation inside the native
`termin::physics_qopt::Multibody3DSystem` topology when play starts.

The authoring hierarchy is the source description, not the numerical model.
The compiled multibody graph owns runtime body state, joint handles, motor
state and solver workspace. A fixed-base articulation contributes one
generalized degree of freedom per joint instead of registering six
independent degrees of freedom and constraint rows for every link. This keeps
scene traversal, matrix assembly and time integration in separate layers.

The native numerical model also supports an explicit floating root body. Its
generalized block is `[base local twist vw (6), joint velocities (N)]`; the root
pose is integrated on SE(3), while child joints retain ordinary scalar
coordinates. This is a property of the same contribution, not a second physics
world or a maximal-coordinate workaround. The scene compiler now authors both
forms through the same component and hierarchy.

`Multibody3DSystem` is the common contribution collector and stepping boundary,
not a synonym for maximal coordinates. Maximal bodies, forces, point joints
and revolute constraints are public contribution types outside the collector.
Reduced articulations are an additional contribution type in the same topology
and may coexist with maximal-coordinate bodies and external constraints.

This stack remains separate from the gameplay-oriented `termin-physics`
engine. Sharing scene conventions or collision geometry later does not imply
sharing world state or solver internals.

## Scene grammar

The supported form is a rooted tree. A fixed root is only a frame:

```text
Root (FEMArticulationComponent; fixed world frame)
└── HipJoint (RotatorComponent or ActuatorComponent)
    └── UpperLeg (FEMRigidBodyComponent)
        └── KneeJoint (RotatorComponent + optional motor/controller)
            └── LowerLeg (FEMRigidBodyComponent)
```

A floating root is itself the central body; no synthetic attachment entity is
inserted:

```text
Root (FEMArticulationComponent, Base Mode = Floating,
      FEMRigidBodyComponent)
├── LeftHip (RotatorComponent or ActuatorComponent)
│   └── LeftLeg (FEMRigidBodyComponent)
└── RightHip (RotatorComponent or ActuatorComponent)
    └── RightLeg (FEMRigidBodyComponent)
```

Rules are deliberately strict:

- `Base Mode = Fixed` rejects an enabled root body, while `Floating` requires
  the enabled `FEMRigidBodyComponent` co-located with the articulation;
- every non-root body has exactly one nearest ancestor body and exactly one
  enabled kinematic unit on the path between them;
- `RotatorComponent` compiles to a revolute joint;
- `ActuatorComponent` compiles to a prismatic reduced joint;
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

### `FEMArticulationComponent`

Lives at the root and owns:

- compile/rebuild policy and diagnostics;
- the entity-to-contribution bindings;
- synchronization from solver body poses to scene transforms.

`FEMPhysicsWorldComponent` owns the native `Multibody3DSystem`, fixed-step
accumulation, gravity, contacts and projection policy. The articulation owns
only its compiled contribution and scene bindings inside that world.

Topology is immutable after `Multibody3DSystem::finalize()`. Structural scene
changes require an explicit rebuild; scalar commands and external loads do
not. A failed rebuild leaves no partially usable runtime graph.

### `FEMRigidBodyComponent`

Marks an inertial body and owns authored mass and diagonal principal moments.
Inside a hierarchical mechanism it receives a typed floating-base or
articulated-link binding after successful compilation but does not own the
solver or step it. Its local velocity query works for maximal bodies, floating
bases and links; only maximal bodies and floating bases accept an independently
assigned velocity because a link velocity is determined by reduced state. The
existing independent-body registration path remains unchanged for
maximal-coordinate models. A separate inertia/COM frame is not yet authored.

Geometry-derived inertia can be added later as an explicit authoring service.
It must not be guessed from arbitrary descendants during the first slice.

### `KinematicUnitComponent`

`RotatorComponent` and `ActuatorComponent` remain the canonical description of
the relative one-DOF transform:

- `origin_position` and `origin_rotation` define the fixed parent-to-joint
  origin transform;
- `axis` is always a normalized joint direction;
- `coordinate_scale` maps authored coordinate units to radians or metres;
- `coordinate` defines authored state before play and measured state during
  simulation;
- `min_coordinate` and `max_coordinate` define authored joint bounds.

Outside a dynamic mechanism, the current behavior is unchanged: changing
`coordinate` applies the kinematic transform. Inside a running mechanism the
compiled physics graph owns the actual body transforms and writes the measured
reduced coordinate back to `coordinate` in authored units. Servo targets are
separate fields and are never overwritten by synchronization.

The runtime ownership switch must be explicit. It is an error for both the
kinematic component and the physics synchronizer to write the same transform
during one simulation tick.

### `FEMArticulationMotorComponent` and `FEMJointServoComponent`

The physical actuator and its control policy are separate and optional. Both
are attached to the same entity as a `KinematicUnitComponent`. This avoids
putting QP-specific effort fields or controller policy into the reusable
kinematic transform component.

`FEMArticulationMotorComponent` is a bounded generalized-effort channel. The
compiler creates one `ArticulationMotorContribution` per driven articulation
and binds each motor to the inferred reduced DOF. It can be commanded directly.
The motor contribution owns no state or topology block: it adds bounded
generalized effort to the articulation's load vector.

`FEMJointServoComponent` is a position/velocity PID policy with optional
feed-forward effort. `Position Control` governs the complete position-error
loop: disabling it removes both proportional and integral terms and resets the
integrator. Within that loop, the bounded integral term can be disabled
independently and uses conditional anti-windup against the physical motor
limit. Disabling the position loop produces a pure velocity regulator. It reads
joint state and writes the co-located motor's command. A missing motor means a
passive joint; a servo without a motor is an invalid model. Ideal acceleration
and HQP tasks remain separate future control policies and can target the same
physical actuator boundary.

## Transform compilation

Compilation uses the authored world transforms before physics starts:

1. Validate the explicit base mode. A fixed root defines an inertial frame; a
   floating root contributes its co-located rigid body and initial world pose.
2. Traverse only the mechanism root subtree and assign every joint/body edge
   to its nearest parent body or to the articulation root frame.
3. Register one articulation contribution and its inertial links, retaining
   typed articulation/link handles.
4. For each body edge, locate its single kinematic unit.
5. Keep top-level joint origins base-local for floating roots and fold the
   fixed root pose into them only for fixed roots.
6. Register an internal reduced-coordinate joint and its motion subspace;
   these tree joints do not add constraint rows.
7. Record the zero-coordinate relative orientation/translation needed to
   measure the joint coordinate continuously at runtime.
8. Register optional motor channels after the six base DOFs when floating,
   finalize all topology blocks, then bind cross-contribution references in a
   second pass.

Axis magnitude is never a unit scale or physical geometry. `set_axis()`
normalizes it, and `coordinate_scale` alone converts authored units to the
canonical reduced coordinate.

During a step, body poses are written back in parent-before-child order using
global pose setters. Joint marker nodes remain attached to the parent body;
the child body local transform becomes the solver-owned residual relative to
that marker. The play-mode lifecycle must restore the authored scene state on
stop, as for other simulated components.

## Native model additions

The `termin-physics-qopt` 3D multibody slice supplies maximal-coordinate bodies,
point joints, true revolute constraints, reactions, equality-QP dynamics and
constraint projection. It remains intact, including the current pendulum
model. The solver-neutral tree model lives in
`termin::robotics::Articulation3D`; the common
`termin::physics_qopt::Multibody3DSystem` contains its dynamics adapter
contribution, whose implemented state has one scalar coordinate per revolute or prismatic
joint plus, when floating, a world pose and six body-local base velocity
coordinates.

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

A standing or walking dog additionally needs collision queries,
non-penetration, normal reactions and friction. Those contracts now exist for
maximal bodies, floating bases and articulated links; the next acceptance slice
exercises their composition in a complete robot scene.

## Recommended delivery slices

### Slice 1: reduced articulation foundation (implemented)

- add an articulation contribution to `Multibody3DSystem` beside the existing
  public body/joint contributions;
- fixed base, inertial links, revolute and prismatic joints;
- generalized state, forward kinematics and generalized dynamics assembly;
- native tests comparing a reduced pendulum fixture with the existing maximal
  pendulum on observable motion/energy invariants;
- keep the existing pendulum scene and model unchanged.

This established coexistence of both formulations inside one system; the scene
compiler and motor contribution now build on that boundary.

### Slice 2: hierarchical scene authoring and drives (implemented)

- native scene components for fixed/floating articulations, bodies and servos;
- compiler for fixed/floating roots and revolute/prismatic kinematic edges;
- bounded physical effort and position-servo control;
- separate `FEMArticulationMotorComponent` and `FEMJointServoComponent`
  runtime bindings;
- passive double-pendulum acceptance scene and component-level servo tests;
- floating root/body synchronization, branching compilation, motor indexing,
  and base/link contact routing tests.

A standing branching quadruped fixture and broader reaction/error tests remain
as acceptance work built on this slice.

### Slice 3: joint bounds (implemented)

- optional unilateral min/max constraints for revolute and prismatic joints;
- predictive transient-row activation in the velocity projection;
- separate minimum/maximum reactions and active diagnostics;
- `FEMJointLimitComponent` authoring in kinematic coordinate units;
- activation, release, energy, invalid-range, and scene compilation tests.

### Slice 4: contacts

Contacts are a sequence of independently testable solver and integration
slices, not a scene-level special case:

#### Contact geometry ownership

`termin-collision` owns solver-neutral contact candidate generation and
deterministic geometric patch reduction. The same reduced patch is consumed by
the game-physics and FEM/qopt stacks. It contains points on both shapes, a
normal, signed gaps and geometric feature identifiers, but no rigid-body
pointers, generalized coordinates, accumulated impulses or active-set state.

Spatial reduction selects a bounded representative set from one instantaneous
geometric patch. Temporal matching, impulse persistence and warm start are
different operations and belong to each solver-side contact-set consumer. The
scene adapter only maps colliders to dynamics endpoints and converts conventions;
it does not implement either kind of reduction.

1. Add transient unilateral rows to `DynamicsSystem`. Permanent body, joint,
   DOF and equality topology remains finalized, while contributions register a
   different number of inequalities on every step.
2. Solve the velocity update as a mass-metric QP with permanent equalities and
   transient normal inequalities. With zero restitution, contact impulses must
   not add kinetic energy.

The native solver contract for this second step is

```text
minimize    0.5 v^T M v - load^T v
subject to  J v = b
            C v <= d
```

For projection around a trial velocity `v*`, a contribution assembles
`load = M v*`. A normal constraint `J_n v >= target` is therefore stored as
`C = -J_n`, `d = -target`. Its returned multiplier is non-negative and the
physical generalized impulse is `-C^T lambda = J_n^T lambda`. Equality and
unilateral rows are solved together; there is no post-solve velocity clamp.
The solver accepts a feasible primal plus optional active masks and returns a
tight-row mask, while temporal ownership and caching of that data remain in a
future persistent contact contribution rather than `DynamicsSystem`.
3. Use revolute and prismatic joint limits as the first, fixed-identity client
   of the unilateral machinery. Limits produce reactions and never clamp an
   already integrated transform.
4. Expose a solver-facing point-kinematics contract for maximal bodies,
   arbitrary articulation links and the static world. This is implemented as
   `PointKinematics3D`: it provides world position and velocity, the owning DOF
   block, a row-major `3 x n` generalized Jacobian, and `J^T` force mapping
   without a dependency on scene entities, colliders, or Eigen. Tests cover
   direct velocity, finite differences on a branching tree, virtual work,
   static zero-DOF points, and invalid inputs.
5. Implement a public `ContactSet3DContribution` which consumes endpoint pairs,
   normals, signed gaps and stable caller keys. This is implemented for static
   world points, maximal bodies, and arbitrary articulation links. It owns
   transient normal rows, impulse/reaction and tight-row state, and split
   penetration correction, but knows nothing about collision queries. Position
   projection changes only the trial configuration; the physical midpoint
   velocity remains separate until the unilateral velocity projection, so
   depenetration cannot create a rebound. Penetrating, impacting, resting,
   separating, removal, mixed-endpoint, matrix-sign, and invalid-input behavior
   is covered by native tests.
6. Adapt `CollisionWorld` manifolds in the FEM scene integration layer. This
   is implemented by the scene contact adapter in
   `termin-components-physics-fem`: before each substep it updates the one
   scene `CollisionWorld`, detects `ContactPatch` values, rebuilds an explicit
   collider-to-static/maximal-body/articulation-link map, and replaces the
   transient rows of one `ContactSet3DContribution`. A dynamic collider is
   owned by the enabled, co-located `FEMRigidBodyComponent`; a collider without
   such a body is static. Missing or ambiguous dynamic ownership is logged and
   rejected. The world collision-layer mask, component/entity enabled state,
   same-body pairs, and connected or adjacent-link pairs are explicit adapter
   policy. The adapter does not create another `PhysicsWorld` or reuse the
   maximal-body impulse solver from `termin-physics`.
7. Validate the frictionless vertical slice in a separate acceptance project:
   a maximal body and an articulation link contact static terrain, with gap,
   reaction, active-set and energy telemetry.
8. Deterministic persistent manifold matching and warm start are implemented
   in the contact contribution. Geometry remains stateless and solver-neutral:
   collision supplies stable pair/feature identities, while the contribution
   owns bounded temporal state, supporting-point selection and active-set hints.
9. Coulomb friction is implemented as a second global maximum-dissipation QP.
   A deterministic tangent basis and an inscribed regular 32-gon approximate
   each circular friction disk. The pass jointly corrects tangent impulses and
   redistributes normal impulses among tight contacts, preserves every normal
   velocity inequality, respects non-negative normal impulses, and includes
   bilateral-compatible inverse-mass response. This redistribution is required
   for moments generated by friction in a multi-point patch. Zero coefficient
   is an exact frictionless bypass. Sliding work is non-positive; finite polygon
   directional quantization and intentional physical dissipation are accepted
   approximation limits. Restitution remains separate future scope.

Floating-base dynamics and standing or locomotion demos follow this contact
foundation. They are not prerequisites for frictionless contact correctness.

## Rejected shortcuts

- Generating name-based `FEM*JointComponent` records in the scene. This keeps
  the fragile references and merely hides them behind an importer.
- Treating the Python `RevoluteJoint3D` as the target backend. It is a
  three-row point/ball joint; the native five-row revolute joint is the
  correct primitive.
- Creating a second world/system API merely because articulation internals use
  reduced coordinates. Coordinate formulation is an implementation/model
  choice inside the common `Multibody3DSystem` boundary.
- Using `RotatorComponent.coordinate` simultaneously as servo target and
  measured state. Runtime synchronization writes the measurement there, while
  `FEMJointServoComponent.target_coordinate` remains the command.
- Applying motor motion by writing transforms after the physics step. That
  bypasses reaction forces, inertia and the QP constraints.
- Silently accepting malformed hierarchies or fabricating massless bodies.
  During active development a clear compile failure is preferable to a model
  whose physics differs from the authored mechanism.
