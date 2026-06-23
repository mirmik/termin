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
