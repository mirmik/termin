import math

import pytest

from termin.bootstrap import bootstrap_player, shutdown_runtime
from termin.colliders.collider_component import ColliderComponent
from termin.geombase import Pose3, Quat, Vec3
from termin.physics_components import PhysicsWorldComponent, RigidBodyComponent
from termin.scene import TcScene


def test_native_rigid_body_preserves_scale_and_accepts_external_teleport() -> None:
    bootstrap_player()
    scene = TcScene.create("rigid-body-transform-contract")
    try:
        entity = scene.create_entity("scaled")
        entity.transform.set_local_position(Vec3(0.0, 0.0, 2.0))
        entity.transform.set_local_scale(Vec3(2.0, 3.0, 4.0))
        entity.add_component(ColliderComponent())
        body = RigidBodyComponent()
        entity.add_component(body)

        world_entity = scene.create_entity("Physics World")
        world = PhysicsWorldComponent()
        world_entity.add_component(world)
        world.start()
        assert body.initialized

        entity.transform.set_global_pose(
            Pose3(ang=Quat.identity(), lin=Vec3(7.0, 8.0, 9.0))
        )
        world.fixed_update(1.0 / 120.0)

        assert entity.transform.local_scale() == Vec3(2.0, 3.0, 4.0)
        assert entity.transform.global_position.x == pytest.approx(7.0)
        assert entity.transform.global_position.y == pytest.approx(8.0)
        assert entity.transform.global_position.z == pytest.approx(9.0, abs=0.002)
        assert body.rigid_body.linear_velocity.z < 0.0
    finally:
        scene.destroy()
        shutdown_runtime()


def test_native_rigid_body_rejects_affine_world_transform(capfd) -> None:
    bootstrap_player()
    scene = TcScene.create("rigid-body-affine-rejection")
    try:
        parent = scene.create_entity("parent")
        parent.transform.set_local_scale(Vec3(2.0, 1.0, 0.5))
        child = parent.create_child("child")
        half = math.pi * 0.25
        child.transform.set_local_rotation(
            Quat(0.0, 0.0, math.sin(half), math.cos(half))
        )
        child.add_component(ColliderComponent())
        body = RigidBodyComponent()
        child.add_component(body)

        world_entity = scene.create_entity("Physics World")
        world = PhysicsWorldComponent()
        world_entity.add_component(world)
        world.start()

        assert not world.initialized
        assert not body.initialized
        assert "rejects an affine world transform" in capfd.readouterr().err
    finally:
        scene.destroy()
        shutdown_runtime()
