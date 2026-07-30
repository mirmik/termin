def test_rigid_body_accepts_decomposed_scale_and_rejects_affine_world(
    capfd,
) -> None:
    import math

    import termin.bootstrap
    from termin.geombase import Pose3, Quat, Vec3
    from termin.physics_components import RigidBodyComponent
    from termin.scene import TcScene, publish_python_component

    termin.bootstrap.bootstrap_player()
    publish_python_component(
        RigidBodyComponent,
        owner="termin-components-physics-test",
    )
    scene = TcScene.create("rigid-body-transform-contract")

    scaled = scene.create_entity("scaled")
    scaled.transform.set_local_scale(Vec3(2.0, 3.0, 4.0))
    scaled_component = RigidBodyComponent()
    scaled.add_component(scaled_component)
    pose_and_scale = scaled_component._physics_pose_and_scale()
    assert pose_and_scale is not None
    _, scale = pose_and_scale
    assert scale == Vec3(2.0, 3.0, 4.0)

    class FakeBody:
        pose = Pose3(
            ang=Quat(0.0, 0.0, 0.0, 1.0),
            lin=Vec3(7.0, 8.0, 9.0),
        )

    class FakeWorld:
        def get_body(self, index):
            assert index == 0
            return FakeBody()

    scaled_component._body_index = 0
    scaled_component._physics_world = FakeWorld()
    scaled_component._sync_from_physics()
    assert scaled.transform.local_scale() == Vec3(2.0, 3.0, 4.0)
    assert scaled.transform.global_position == Vec3(7.0, 8.0, 9.0)

    parent = scene.create_entity("parent")
    parent.transform.set_local_scale(Vec3(2.0, 1.0, 0.5))
    child = parent.create_child("child")
    half = math.pi * 0.25
    child.transform.set_local_rotation(
        Quat(0.0, 0.0, math.sin(half), math.cos(half))
    )
    affine_component = RigidBodyComponent()
    child.add_component(affine_component)
    assert affine_component._physics_pose_and_scale() is None
    affine_log = capfd.readouterr().err
    assert "rejects an affine world transform" in affine_log

    reflected = scene.create_entity("reflected")
    reflected.transform.set_local_scale(Vec3(-1.0, 1.0, 1.0))
    reflected_component = RigidBodyComponent()
    reflected.add_component(reflected_component)
    assert reflected_component._physics_pose_and_scale() is None
    reflected_log = capfd.readouterr().err
    assert "rejects non-positive or non-finite world scale" in reflected_log

    scene.destroy()
    termin.bootstrap.shutdown_player()
