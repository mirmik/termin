from termin.physics_fem import (
    FEMFixedJointComponent,
    FEMPhysicsWorldComponent,
    FEMRevoluteJointComponent,
    FEMRigidBodyComponent,
)


def test_physics_fem_exports_canonical_classes() -> None:
    assert FEMFixedJointComponent.__module__.startswith("termin.physics_fem.")
    assert FEMPhysicsWorldComponent.__module__.startswith("termin.physics_fem.")
    assert FEMRevoluteJointComponent.__module__.startswith("termin.physics_fem.")
    assert FEMRigidBodyComponent.__module__.startswith("termin.physics_fem.")
