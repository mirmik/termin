# Native FEM physics components

This module binds scene authoring to the native `termin-physics-qopt` dynamics
stack and the solver-neutral articulation model from `termin-robotics`.
It owns no solver implementation: `FEMPhysicsWorldComponent` compiles enabled
body and joint components into a `Multibody3DSystem`, whose body and constraint
contributions are stepped by the common `DynamicsSystem` orchestrator.

The module registers the serialized names `FEMPhysicsWorldComponent`,
`FEMArticulationComponent`, `FEMRigidBodyComponent`,
`FEMArticulationMotorComponent`, `FEMJointLimitComponent`,
`FEMJointServoComponent`,
`FEMFixedJointComponent`, and
`FEMRevoluteJointComponent` during core bootstrap. Projects using these types
do not need a Python module or NumPy at runtime.

The current native slice supports rigid transforms, diagonal body-local
inertia, fixed point joints, true axial revolute joints, damping wrenches,
fixed-step scheduling, constraint projection, and solver-to-scene pose
synchronization. It intentionally remains separate from the gameplay physics
world in `termin-physics`.

## Fixed-step scheduling

`FEMPhysicsWorldComponent` participates in the scene's `fixed_update` scheduler
at `FIXED_UPDATE_PRIORITY_PHYSICS`. The serialized scene `fixed_timestep`
defines the control period; the scene owns the only elapsed-time accumulator.

```text
controller fixed_update (EARLY)
    -> FEM fixed_update (DEFAULT)
        -> system.step(fixed_dt)
```

The FEM world neither discovers nor invokes a controller and does not configure
the scene scheduler.

## Reduced articulation hierarchy

The native path places `ArticulationComponent` and
`FEMArticulationComponent` on the same root. `ArticulationComponent` owns the
solver-neutral `Articulation3D`; the FEM marker borrows that exact model and
contributes dynamics and bounded motor channels:

```text
root (ArticulationComponent, FEMArticulationComponent)
└── KinematicUnit + optional FEMArticulationMotorComponent
    └── KinematicUnit + optional FEMArticulationMotorComponent
        └── ...
```

Mass, centre of mass and inertia are authored on each unit. Visual children
are presentation and do not become runtime links. The alternating hierarchy
below remains a transitional compiler input for existing FEM scenes; new
scenes should use the shared model path.

The shared-model compiler currently supports a fixed base. Floating-base
authoring remains available only through the transitional body hierarchy until
its ownership contract is migrated too.

`FEMArticulationComponent` marks an articulation root and exposes an explicit
`Base Mode` choice. In `Fixed` mode the root entity is only an inertial-world
frame. In `Floating` mode that same entity must also own one enabled
`FEMRigidBodyComponent`; it becomes the physical six-DOF base body. No extra
attachment entity is required. Both modes use the same strict hierarchy below
the root:

```text
articulation root (plus FEMRigidBodyComponent in Floating mode)
└── RotatorComponent or ActuatorComponent entity
    └── FEMRigidBodyComponent entity
        └── next joint entity
            └── next body entity
```

The joint entity is the explicit attachment frame. Its kinematic origin pose is
the fixed parent-to-joint transform. For a fixed root, the root world pose is
folded into each top-level joint transform; for a floating root, top-level
joint transforms remain base-local. The axis is always a unit direction; the
separate `coordinate_scale` converts authored units to radians or metres before
the coordinate becomes reduced state. The compiler folds the body child's
local rigid pose into the same articulation unit: it composes the offset into
`parent_to_unit_zero` and transports the motion twist to the unit output frame.
Branching is represented by placing several joint children under the root or
one authored body.

An optional `FEMJointLimitComponent` on a joint entity gives that reduced DOF
a minimum, a maximum, or both. Bounds use the neighboring kinematic
component's authored units and pass through the same `coordinate_scale` as its
coordinate. The articulation activates transient velocity inequalities only
when a bound is reached or the current velocity predicts a crossing. It
reports separate non-negative minimum/maximum reactions and active flags; the
signed generalized effort is `minimum_reaction - maximum_reaction`. Limits do
not clamp the authored transform after integration.

`compile_fem_articulation_scene()` exposes this translation as a separate,
testable pass. It produces public `ArticulationUnit3D` values and bindings.
For transitional scenes `FEMArticulationComponent` retains the resulting
model. On the shared native path it borrows the model owned by
`ArticulationComponent`. The physics world inserts a borrowing
`Articulation3DDynamicsContribution` into
the generic system, copies solved SI coordinates back to the authored units,
and writes a floating base pose back to the root entity. Floating generalized coordinates
are ordered as `[base local twist vw (6), joints (N)]`; joint motor channels
are offset past the base block. Scaled joint/body frames, missing,
contradictory or ambiguous bodies, nested roots, and unsupported damping are
rejected instead of being approximated silently.

An optional `FEMArticulationMotorComponent` may be placed beside the kinematic
unit on the joint entity. Scene compilation binds its bounded physical effort
channel to the inferred reduced DOF. A separate, co-located
`FEMJointServoComponent` computes

```text
effort = kp (target_position - position)
       + ki integral(target_position - position) dt
       + kd (target_velocity - velocity)
       + feed_forward_effort
```

The `position_control_enabled` switch controls the complete position loop:
disabling it removes both the proportional and integral terms and resets the
accumulated integral effort. Within the enabled position loop, the integral
term can be disabled independently. It accumulates the same SI position error,
is bounded by `maximum_integral_effort`, and uses conditional integration
against the physical motor limit to prevent further windup during saturation.
Disable the position loop to operate as a pure velocity regulator with optional
direct effort feed-forward.

and writes the result to the motor's `commanded_effort` field.
`ArticulationMotorContribution` adds that command, clamped by the motor's
`maximum_effort`, to the articulation load vector. Targets use the kinematic
component's authored coordinate unit; gains and effort limits are physical SI
quantities. Motors own no DOFs and are bound to the articulation block in the
topology-binding pass after every contribution has registered its blocks. A
motor without a servo can be commanded directly; a servo without a motor is a
model error.

The world also exposes a UI-neutral `FEMPhysicsTelemetry` snapshot containing
simulation time, successful step count, topology size, initial/current
mechanical energy, motor effort, power, accumulated work, saturation, contact
count, cached and warm-started contact count, active normal rows, minimum gap,
normal impulse sum, normal reaction sum, and maximum normal reaction.
With contact friction enabled it also reports sliding-contact count, tangent
speed, tangent impulse, available friction capacity, and friction work.
The global friction QP uses the configured QP tolerance, relaxed only up to one
hundredth of the physical velocity tolerance. This avoids rejecting a
physically negligible friction residual while keeping it well below the
step-level acceptance threshold.

`test-projects/fem-standing-robot` combines the floating-base scene compiler,
eight reduced servo/motor channels, four frictional feet, and native HUD
telemetry into a vertical robot acceptance. Its headless counterpart verifies
a bounded five-second stance, a fifty-second asymmetric high landing, and
collapse after runtime servo disable.
Motor work is a per-step diagnostic integral, not an additional conserved
state. Optional presentation belongs to the separate
`termin-components-physics-fem-ui` adapter module.

## Dynamic controller bridge

`FEMArticulationComponent` exposes ordered actuator DOF indices, physical
effort limits, solver gravity and a validated
`apply_inverse_dynamics_control()` command sink. The same surface is available
to Python together with `InverseDynamicsHqpController3D`, explicit
solver-neutral acceleration tasks, priorities and hard constraints.

The controller calculates and submits efforts at the fixed control priority;
the FEM world applies them and integrates once at the later physics priority.
`test-projects/dynamic-hqp-point-tracking` demonstrates this boundary with a
three-dimensional azimuth/shoulder/elbow manipulator and a two-level Cartesian
task hierarchy assembled visibly in Python.

## Scene contacts

The FEM scene adapter consumes solver-neutral `ContactPatch` values from the
scene's single `CollisionWorld`; it never creates a gameplay `PhysicsWorld`.
At every fixed step it refreshes broad-phase poses and maps each enabled
`ColliderComponent` to the nearest `FEMRigidBodyComponent` on its own entity or
an ancestor. This lets end-effector entities own their collision geometry while
the parent link owns mass and inertia. A collider without such an owner belongs
to the static world. The resolved body becomes either a maximal body, a floating
articulation base, or an articulation unit. Collider rebuild, disable, removal,
and scene teardown are therefore observed before a patch is converted to
`ContactEndpoint3D` values, without retaining collider pointers in
`termin-physics-qopt` across fixed steps.

The adapter derives deterministic contact keys from the canonical collider
pair and collision feature IDs. It supplies all currently live collider-pair
group keys even when narrow phase returns no penetrating patch. This lets the
solver-side `ContactSet3DContribution` retain only positive-impulse support
points across the exact-surface query gap, while collider removal, disable, or
filter changes still expire the group immediately. A fresh patch for a pair
replaces its old feature set. Persistence distance, cached impulses, and
active-set hints remain solver policy; collision owns only geometry and stable
feature identity.

`contact_friction_coefficient` assigns one already-combined Coulomb coefficient
to contacts generated by this FEM world. Its default is zero, preserving the
frictionless scene path exactly. Material-specific collider coefficients and a
mixing rule are deliberately future scene-policy work; the physics-qopt contact
model
already accepts a coefficient per contact.

`collision_layer_mask` selects entity layers accepted by the FEM world.
Same-body contacts are always discarded. Contacts between directly connected
maximal bodies and adjacent links of one articulation are discarded by
default; `adjacent_unit_collision_enabled` opts those pairs back in. A dynamic
collider whose enabled `FEMRigidBodyComponent` is not registered by this FEM
world is an error rather than an implicit static obstacle.

Body velocities cross the model boundary as complete `termin::Screw3` values
expressed in each body-local frame at that body's origin. The API names both
the frame and point explicitly. The component layer does not rotate
linear/angular halves independently; frame and origin changes belong to the
multibody adjoint/coadjoint contract.
