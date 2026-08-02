# Native FEM physics components

This module binds scene authoring to the native `termin-qopt` dynamics stack.
It owns no solver implementation: `FEMPhysicsWorldComponent` compiles enabled
body and joint components into a `Multibody3DSystem`, whose body and constraint
contributions are stepped by the common `DynamicsSystem` orchestrator.

The module registers the serialized names `FEMPhysicsWorldComponent`,
`FEMArticulationComponent`, `FEMRigidBodyComponent`,
`FEMArticulationMotorComponent`, `FEMJointServoComponent`,
`FEMFixedJointComponent`, and
`FEMRevoluteJointComponent` during core bootstrap. Projects using these types
do not need a Python module or NumPy at runtime.

The current native slice supports rigid transforms, diagonal body-local
inertia, fixed point joints, true axial revolute joints, damping wrenches,
fixed-step accumulation, constraint projection, and solver-to-scene pose
synchronization. It intentionally remains separate from the gameplay physics
world in `termin-physics`.

## Reduced articulation hierarchy

`FEMArticulationComponent` marks a fixed articulation root. Its subtree uses a
strict alternating hierarchy:

```text
articulation root
└── RotatorComponent or ActuatorComponent entity
    └── FEMRigidBodyComponent entity
        └── next joint entity
            └── next body entity
```

The joint entity is the explicit attachment frame. Its kinematic origin pose is
the fixed parent-to-joint transform. The axis is always a unit direction; the
separate `coordinate_scale` converts authored units to radians or metres before
the coordinate becomes reduced state. The body child's local rigid pose is the
fixed joint-to-link transform. Branching is represented by placing several
joint children under one body.

`compile_fem_articulation_scene()` exposes this translation as a separate,
testable pass. It produces public `ArticulationLink3D` values and bindings; the
world inserts the resulting `Articulation3DContribution` into the generic
system and copies solved SI coordinates back to the authored units. Scaled
joint/body frames, missing or ambiguous bodies, nested roots, and unsupported
damping are rejected instead of being approximated silently.

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
mechanical energy, motor effort, power, accumulated work, and saturation.
Motor work is a per-step diagnostic integral, not an additional conserved
state. Optional presentation belongs to the separate
`termin-components-physics-fem-ui` adapter module.

Body velocities and damping loads cross the model boundary as complete
`termin::Screw3` values reduced to each body's origin and expressed in world
axes. The API names this point explicitly. The component layer does not rotate
force/torque or linear/angular halves independently; frame and origin changes
belong to the multibody adjoint/coadjoint contract.
