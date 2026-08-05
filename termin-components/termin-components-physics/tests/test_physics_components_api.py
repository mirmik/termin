import pytest

from termin.bootstrap import bootstrap_player, shutdown_runtime
from termin.colliders.collider_component import ColliderComponent
from termin.geombase import GeneralPose3, Vec3
from termin.physics_components import PhysicsWorldComponent, RigidBodyComponent
from termin.scene import Component, TcScene


def test_physics_components_export_native_canonical_classes() -> None:
    world = PhysicsWorldComponent(gravity=Vec3(0.0, 0.0, -5.0), iterations=7)
    body = RigidBodyComponent(mass=2.0, is_static=True)

    assert isinstance(world, Component)
    assert isinstance(body, Component)
    assert world.type_name() == "PhysicsWorldComponent"
    assert body.type_name() == "RigidBodyComponent"
    assert world.gravity == Vec3(0.0, 0.0, -5.0)
    assert world.iterations == 7
    assert body.mass == pytest.approx(2.0)
    assert body.is_static


def test_physics_world_settings_are_serializable_native_fields() -> None:
    bootstrap_player()
    try:
        component = PhysicsWorldComponent(
            gravity=Vec3(1.0, 2.0, -3.0),
            iterations=14,
            restitution=0.4,
            friction=0.7,
        )
        data = component.serialize_data()
        assert data["gravity"] == [1.0, 2.0, -3.0]
        assert data["iterations"] == 14
        assert data["restitution"] == pytest.approx(0.4)
        assert data["friction"] == pytest.approx(0.7)
    finally:
        shutdown_runtime()


def test_rigid_body_component_uses_scaled_sphere_mass_properties() -> None:
    bootstrap_player()
    scene = TcScene.create("sphere-rigid-body-component")
    try:
        entity = scene.create_entity("Ball")
        entity.transform.relocate(GeneralPose3(scale=Vec3(2.0, 3.0, 4.0)))
        collider = ColliderComponent()
        collider.collider_type = "Sphere"
        entity.add_component(collider)
        rigid_body = RigidBodyComponent(mass=2.0)
        entity.add_component(rigid_body)

        world_entity = scene.create_entity("Physics World")
        world = PhysicsWorldComponent()
        world_entity.add_component(world)
        world.start()

        assert world.initialized
        assert rigid_body.initialized
        body = rigid_body.rigid_body
        assert body is not None
        assert body.inertia.x == pytest.approx(0.8)
        assert body.inertia.y == pytest.approx(0.8)
        assert body.inertia.z == pytest.approx(0.8)
    finally:
        scene.destroy()
        shutdown_runtime()


def test_scaled_box_mass_properties_work_before_rigid_body_start() -> None:
    bootstrap_player()
    scene = TcScene.create("rigid-body-registration-order")
    try:
        entity = scene.create_entity("ScaledBox")
        entity.transform.relocate(GeneralPose3(scale=Vec3(2.0, 3.0, 4.0)))
        collider = ColliderComponent()
        entity.add_component(collider)
        rigid_body = RigidBodyComponent(mass=2.0)
        entity.add_component(rigid_body)

        world_entity = scene.create_entity("Physics World")
        world = PhysicsWorldComponent()
        world_entity.add_component(world)
        world.start()
        body = rigid_body.rigid_body
        assert body is not None

        assert body.inertia.x == pytest.approx(25.0 / 6.0)
        assert body.inertia.y == pytest.approx(10.0 / 3.0)
        assert body.inertia.z == pytest.approx(13.0 / 6.0)
    finally:
        scene.destroy()
        shutdown_runtime()
