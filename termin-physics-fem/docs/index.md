# termin-physics-fem

`termin-physics-fem` contains experimental Python FEM scene components.

The package depends on `termin-qopt` and therefore on the current Python
optimization stack. It is deliberately separate from `termin-physics`, whose
public Python API is the C++ rigid-body engine exposed through
`termin.physics`.

## Public API

Python package: `termin.physics_fem`.

Canonical component classes:

- `termin.physics_fem.FEMPhysicsWorldComponent`
- `termin.physics_fem.FEMRigidBodyComponent`
- `termin.physics_fem.FEMFixedJointComponent`
- `termin.physics_fem.FEMRevoluteJointComponent`

## Transform contract

FEM rigid bodies accept only scene transforms classified as `Rigid`. Their
mass and inertia are component-owned, so scaled or affine scene ancestry is
rejected rather than projected into a pose. Solver-to-scene synchronization
updates world position and logical orientation separately.

Joint anchors use exact world positions, and body-local joint offsets are
mapped with the exact scene affine transform.
