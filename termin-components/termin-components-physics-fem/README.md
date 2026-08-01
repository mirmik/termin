# Native FEM physics components

This module binds scene authoring to the native `termin-qopt` dynamics stack.
It owns no solver implementation: `FEMPhysicsWorldComponent` compiles enabled
body and joint components into a `Multibody3DSystem`, whose body and constraint
contributions are stepped by the common `DynamicsSystem` orchestrator.

The module registers the serialized names `FEMPhysicsWorldComponent`,
`FEMRigidBodyComponent`, `FEMFixedJointComponent`, and
`FEMRevoluteJointComponent` during core bootstrap. Projects using these types
do not need a Python module or NumPy at runtime.

The current native slice supports rigid transforms, diagonal body-local
inertia, fixed point joints, true axial revolute joints, damping wrenches,
fixed-step accumulation, constraint projection, and solver-to-scene pose
synchronization. It intentionally remains separate from the gameplay physics
world in `termin-physics`.

Body velocities and damping loads cross the model boundary as complete
`termin::Screw3` values reduced to each body's origin and expressed in world
axes. The API names this point explicitly. The component layer does not rotate
force/torque or linear/angular halves independently; frame and origin changes
belong to the multibody adjoint/coadjoint contract.
