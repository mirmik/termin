from types import SimpleNamespace


def test_fem_rigid_body_accepts_rigid_world_pose() -> None:
    import numpy as np
    import termin.bootstrap
    from termin.fem.dynamic_assembler import DynamicMatrixAssembler
    from termin.geombase import Quat, Vec3
    from termin.physics_fem import FEMRigidBodyComponent
    from termin.scene import TcScene, publish_python_component

    termin.bootstrap.bootstrap_player()
    publish_python_component(
        FEMRigidBodyComponent,
        owner="termin-physics-fem-test",
    )
    scene = TcScene.create("fem-rigid-transform-contract")
    entity = scene.create_entity("rigid-body")
    entity.transform.set_global_position(Vec3(1.0, 2.0, 3.0))
    entity.transform.set_global_orientation(Quat.identity())
    component = FEMRigidBodyComponent()
    entity.add_component(component)

    component._register_with_fem_world(
        SimpleNamespace(
            gravity=np.array([0.0, 0.0, -9.81], dtype=np.float64),
            assembler=DynamicMatrixAssembler(),
        )
    )

    assert component.fem_body is not None
    pose = component.fem_body.pose()
    assert np.allclose(np.asarray(pose.lin), [1.0, 2.0, 3.0])

    scene.destroy()
    termin.bootstrap.shutdown_player()


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


def test_fem_revolute_joint_accepts_deserialized_list_offset() -> None:
    import numpy as np
    import termin.bootstrap
    from termin.geombase import Vec3
    from termin.physics_fem import FEMRevoluteJointComponent
    from termin.scene import TcScene

    termin.bootstrap.bootstrap_player()
    scene = TcScene.create("fem-revolute-transform-contract")
    entity = scene.create_entity("body-a")
    entity.transform.set_global_position(Vec3(1.0, 2.0, 3.0))
    component = FEMRevoluteJointComponent()
    component.joint_offset_in_body_a = [0.0, 0.0, -1.5]

    joint_point = component._compute_joint_point(entity)

    assert np.allclose(joint_point, [1.0, 2.0, 1.5])

    scene.destroy()
    termin.bootstrap.shutdown_player()
