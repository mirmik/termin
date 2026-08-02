# Native FEM physics components

This module binds scene authoring to the native `termin-qopt` dynamics stack.
It owns no solver implementation: `FEMPhysicsWorldComponent` compiles enabled
body and joint components into a `Multibody3DSystem`, whose body and constraint
contributions are stepped by the common `DynamicsSystem` orchestrator.

The module registers the serialized names `FEMPhysicsWorldComponent`,
`FEMArticulationComponent`, `FEMRigidBodyComponent`,
`FEMFixedJointComponent`, and `FEMRevoluteJointComponent` during core
bootstrap. Projects using these types do not need a Python module or NumPy at
runtime.

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
the fixed parent-to-joint transform, its axis is the reduced motion twist, and
its coordinate initializes the dynamic state. The body child's local rigid pose
is the fixed joint-to-link transform. Branching is represented by placing
several joint children under one body.

`compile_fem_articulation_scene()` exposes this translation as a separate,
testable pass. It produces public `ArticulationLink3D` values and bindings; the
world only inserts the resulting `Articulation3DContribution` into the generic
system and copies solved coordinates back to the joint components. Scaled
joint/body frames, missing or ambiguous bodies, nested roots, and unsupported
damping are rejected instead of being approximated silently.

The world also exposes a UI-neutral `FEMPhysicsTelemetry` snapshot containing
simulation time, successful step count, topology size, and initial/current
mechanical energy. Optional presentation belongs to the separate
`termin-components-physics-fem-ui` adapter module.

Body velocities and damping loads cross the model boundary as complete
`termin::Screw3` values reduced to each body's origin and expressed in world
axes. The API names this point explicitly. The component layer does not rotate
force/torque or linear/angular halves independently; frame and origin changes
belong to the multibody adjoint/coadjoint contract.
