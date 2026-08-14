# termin-physics-fem

`termin-physics-fem` retains the experimental Python FEM/reference package.
Runtime scene components with the same serialized type names now live in the
native `termin_components_physics_fem` module and are registered by the core
bootstrap.

The native components use the C++ `termin-qopt` contribution/dynamics stack;
they do not import NumPy or register a project Python module. The Python code
remains an algorithmic reference while the wider FEM element catalog is being
ported. Both stacks remain deliberately separate from the gameplay-oriented
`termin-physics` engine.

## Public API

Serialized scene component names:

Canonical component classes:

- `FEMPhysicsWorldComponent`
- `FEMRigidBodyComponent`
- `FEMFixedJointComponent`
- `FEMRevoluteJointComponent`

The Python package `termin.physics_fem` is reference-only for this scene API.

## Transform contract

FEM rigid bodies accept only scene transforms classified as `Rigid`. Their
mass and inertia are component-owned, so scaled or affine scene ancestry is
rejected rather than projected into a pose. Solver-to-scene synchronization
updates world position and logical orientation separately.

Joint anchors use exact world positions. `FEMRevoluteJointComponent` also
requires a non-zero body-A-local hinge axis; the native joint constrains anchor
translation and the two rotations perpendicular to that axis.
