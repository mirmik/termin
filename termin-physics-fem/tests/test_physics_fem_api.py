import termin.physics_fem as physics_fem


def test_python_package_exports_native_articulation_control_bridge() -> None:
    assert hasattr(physics_fem, "FEMArticulationComponent")
    assert hasattr(physics_fem, "FEMArticulationMotorComponent")
    assert hasattr(physics_fem, "ReferenceFEMRigidBodyComponent")
    assert hasattr(physics_fem, "ReferenceFEMFixedJointComponent")
    assert hasattr(physics_fem, "ReferenceFEMRevoluteJointComponent")
    assert hasattr(physics_fem, "ReferenceFEMPhysicsWorldComponent")
    assert not hasattr(physics_fem, "FEMRigidBodyComponent")
