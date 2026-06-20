from termin.physics_components import PhysicsWorldComponent, RigidBodyComponent


def test_physics_components_export_canonical_classes() -> None:
    assert PhysicsWorldComponent.__name__ == "PhysicsWorldComponent"
    assert RigidBodyComponent.__name__ == "RigidBodyComponent"
