from types import SimpleNamespace


def test_fem_rigid_body_rejects_scaled_world_before_registration() -> None:
    import termin.bootstrap
    from termin.geombase import Vec3
    from termin.physics_fem import FEMRigidBodyComponent
    from termin.scene import TcScene, publish_python_component

    termin.bootstrap.bootstrap_player()
    publish_python_component(
        FEMRigidBodyComponent,
        owner="termin-physics-fem-test",
    )
    scene = TcScene.create("fem-transform-contract")
    entity = scene.create_entity("scaled-body")
    entity.transform.set_local_scale(Vec3(2.0, 1.0, 1.0))
    component = FEMRigidBodyComponent()
    entity.add_component(component)

    component._register_with_fem_world(SimpleNamespace())

    assert component.fem_body is None
    assert component._fem_world is None

    scene.destroy()
    termin.bootstrap.shutdown_player()
