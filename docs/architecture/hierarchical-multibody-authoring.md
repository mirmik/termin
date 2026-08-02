# Hierarchical multibody authoring

Status: fixed-base articulation and bounded servo slice implemented,
2026-08-02. Floating bases, joint limits, contacts, and HQP control remain
future work.

## Goal

Author an articulated mechanism as an ordinary scene hierarchy instead of
manually wiring body names and joint endpoints. A mechanism root owns the
simulation, inertial links are marked explicitly, and existing
`RotatorComponent` / `ActuatorComponent` nodes describe the one-degree-of-
freedom transform between adjacent links. The scene graph is compiled once as
a reduced-coordinate articulation inside the native
`termin::qopt::Multibody3DSystem` topology when play starts.

The authoring hierarchy is the source description, not the numerical model.
The compiled multibody graph owns runtime body state, joint handles, motor
state and solver workspace. The implemented fixed-base articulation contributes
one generalized degree of freedom per joint instead of registering six
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
Root (FEMArticulationComponent; fixed world frame)
└── HipJoint (RotatorComponent or ActuatorComponent)
    └── UpperLeg (FEMRigidBodyComponent)
        └── KneeJoint (RotatorComponent + optional motor/controller)
            └── LowerLeg (FEMRigidBodyComponent)
```

Rules are deliberately strict:

- the implemented mechanism root is a fixed world frame and does not create a
  dynamic root body;
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
- the native `Multibody3DSystem` instance;
- the entity-to-contribution bindings;
- fixed-step accumulation, gravity and projection options;
- synchronization from solver body poses to scene transforms.

Topology is immutable after `Multibody3DSystem::finalize()`. Structural scene
changes require an explicit rebuild; scalar commands and external loads do
not. A failed rebuild leaves no partially usable runtime graph.

### `FEMRigidBodyComponent`

Marks an inertial link and owns authored mass and diagonal principal moments.
Inside a hierarchical mechanism it receives a typed articulated-link handle
after successful compilation but does not own the solver or step it. The
existing independent-body handle and registration path remain unchanged for
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
8. Register optional motor channels, finalize all topology blocks, then bind
   cross-contribution references in a second pass.

Axis magnitude is never a unit scale or physical geometry. `set_axis()`
normalizes it, and `coordinate_scale` alone converts authored units to the
canonical reduced coordinate.

During a step, body poses are written back in parent-before-child order using
global pose setters. Joint marker nodes remain attached to the parent body;
the child body local transform becomes the solver-owned residual relative to
that marker. The play-mode lifecycle must restore the authored scene state on
stop, as for other simulated components.

## Native model additions

The existing native 3D multibody slice supplies maximal-coordinate bodies,
point joints, true revolute constraints, reactions, equality-QP dynamics and
constraint projection. It remains intact, including the current pendulum
model. The common `Multibody3DSystem` contains an articulated-tree contribution
whose implemented state has one scalar coordinate per revolute or prismatic
joint and a fixed base.

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

### Slice 2: hierarchical scene authoring and drives (partially implemented)

- native scene components for fixed articulations, bodies and servos;
- compiler for fixed roots and revolute/prismatic kinematic edges;
- bounded physical effort and position-servo control;
- separate `FEMArticulationMotorComponent` and `FEMJointServoComponent`
  runtime bindings;
- passive double-pendulum acceptance scene and component-level servo tests.

Floating roots, direct-effort authoring, a branching quadruped fixture, and
broader reaction/error tests remain in this slice.

### Slice 3: joint bounds

- proper unilateral min/max constraints for both joint types;
- limit activation/deactivation and invalid-range tests.

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
3. Use revolute and prismatic joint limits as the first, fixed-identity client
   of the unilateral machinery. Limits produce reactions and never clamp an
   already integrated transform.
4. Expose a solver-facing point-kinematics contract for maximal bodies,
   arbitrary articulation links and the static world. It provides point
   velocity, generalized Jacobian and the transpose force mapping without a
   dependency on scene entities or colliders.
5. Implement a public `ContactSet3DContribution` which consumes endpoint pairs,
   normals, signed gaps and stable caller keys. It owns normal rows, reactions
   and split penetration correction, but knows nothing about collision queries.
6. Adapt `CollisionWorld` manifolds in the FEM scene integration layer. The
   adapter owns collider-to-endpoint mapping, filtering and sign conversion;
   it does not create another `PhysicsWorld` or reuse the maximal-body impulse
   solver from `termin-physics`.
7. Validate the frictionless vertical slice in a separate acceptance project:
   a maximal body and an articulation link contact static terrain, with gap,
   reaction, active-set and energy telemetry.
8. Add deterministic persistent manifold matching and warm start in the contact
   contribution, then add a documented convex Coulomb-friction approximation.

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
