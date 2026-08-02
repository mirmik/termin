# Native FEM physics components

This module binds scene authoring to the native `termin-qopt` dynamics stack.
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
fixed-step accumulation, constraint projection, and solver-to-scene pose
synchronization. It intentionally remains separate from the gameplay physics
world in `termin-physics`.

## Reduced articulation hierarchy

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
the coordinate becomes reduced state. The body child's local rigid pose is the
fixed joint-to-link transform. Branching is represented by placing several
joint children under the root or one body.

An optional `FEMJointLimitComponent` on a joint entity gives that reduced DOF
a minimum, a maximum, or both. Bounds use the neighboring kinematic
component's authored units and pass through the same `coordinate_scale` as its
coordinate. The articulation activates transient velocity inequalities only
when a bound is reached or the current velocity predicts a crossing. It
reports separate non-negative minimum/maximum reactions and active flags; the
signed generalized effort is `minimum_reaction - maximum_reaction`. Limits do
not clamp the authored transform after integration.

`compile_fem_articulation_scene()` exposes this translation as a separate,
testable pass. It produces public `ArticulationLink3D` values and bindings; the
world inserts the resulting `Articulation3DContribution` into the generic
system, copies solved SI coordinates back to the authored units, and writes a
floating base pose back to the root entity. Floating generalized coordinates
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
Motor work is a per-step diagnostic integral, not an additional conserved
state. Optional presentation belongs to the separate
`termin-components-physics-fem-ui` adapter module.

## Scene contacts

The FEM scene adapter consumes solver-neutral `ContactPatch` values from the
scene's single `CollisionWorld`; it never creates a gameplay `PhysicsWorld`.
At every native substep it refreshes broad-phase poses and maps each enabled
co-located `ColliderComponent` to either a maximal body, a floating
articulation base, an articulation link, or the static world. Collider rebuild,
disable, removal, and scene teardown are therefore observed before a patch is
converted to `ContactEndpoint3D` values, without retaining collider pointers in
`termin-qopt` across substeps.

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
mixing rule are deliberately future scene-policy work; the qopt contact model
already accepts a coefficient per contact.

`collision_layer_mask` selects entity layers accepted by the FEM world.
Same-body contacts are always discarded. Contacts between directly connected
maximal bodies and adjacent links of one articulation are discarded by
default; `adjacent_link_collision_enabled` opts those pairs back in. A dynamic
collider whose enabled `FEMRigidBodyComponent` is not registered by this FEM
world is an error rather than an implicit static obstacle.

Body velocities cross the model boundary as complete `termin::Screw3` values
expressed in each body-local frame at that body's origin. The API names both
the frame and point explicitly. The component layer does not rotate
linear/angular halves independently; frame and origin changes belong to the
multibody adjoint/coadjoint contract.
