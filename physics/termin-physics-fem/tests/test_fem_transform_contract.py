def test_fem_revolute_joint_accepts_deserialized_list_offset() -> None:
    import numpy as np
    import termin.bootstrap
    from termin.geombase import Vec3
    from termin.physics_fem import ReferenceFEMRevoluteJointComponent
    from termin.scene import TcScene

    termin.bootstrap.bootstrap_player()
    scene = TcScene.create("fem-revolute-transform-contract")
    entity = scene.create_entity("body-a")
    entity.transform.set_global_position(Vec3(1.0, 2.0, 3.0))
    component = ReferenceFEMRevoluteJointComponent()
    component.joint_offset_in_body_a = [0.0, 0.0, -1.5]

    joint_point = component._compute_joint_point(entity)

    assert np.allclose(joint_point, [1.0, 2.0, 1.5])

    scene.destroy()
    termin.bootstrap.shutdown_player()
