import pytest

from termin.colliders.collider_component import ColliderComponent
from termin.geombase import GeneralPose3, Pose3, Vec3
from termin.physics._physics_native import PhysicsWorld
from termin.physics_components import PhysicsWorldComponent, RigidBodyComponent
from termin.scene import TcScene


def test_physics_components_export_canonical_classes() -> None:
    assert PhysicsWorldComponent.__name__ == "PhysicsWorldComponent"
    assert RigidBodyComponent.__name__ == "RigidBodyComponent"


def test_physics_world_settings_are_serializable_scene_fields() -> None:
    for field_name in (
        "gravity",
        "iterations",
        "restitution",
        "friction",
        "ground_enabled",
        "ground_height",
    ):
        assert PhysicsWorldComponent.inspect_fields[field_name].is_serializable


def test_rigid_body_component_creates_sphere_body_for_sphere_collider() -> None:
    scene = TcScene.create("sphere-rigid-body-component")
    try:
        entity = scene.create_entity("Ball")
        collider = ColliderComponent()
        collider.collider_type = "Sphere"
        collider.box_size = (1.0, 1.0, 1.0)
        entity.add_component(collider)
        rigid_body = RigidBodyComponent(mass=2.0)
        entity.add_component(rigid_body)

        rigid_body._half_extents = rigid_body._compute_half_extents()
        body = rigid_body._create_body(Pose3())

        assert body.inertia.x == pytest.approx(0.2)
        assert body.inertia.y == pytest.approx(0.2)
        assert body.inertia.z == pytest.approx(0.2)
    finally:
        scene.destroy()


def test_rigid_body_registration_computes_scaled_shape_before_component_start() -> None:
    scene = TcScene.create("rigid-body-registration-order")
    try:
        entity = scene.create_entity("ScaledBox")
        entity.transform.relocate(GeneralPose3(scale=Vec3(2.0, 3.0, 4.0)))
        collider = ColliderComponent()
        collider.collider_type = "Box"
        collider.box_size = (1.0, 1.0, 1.0)
        entity.add_component(collider)
        rigid_body = RigidBodyComponent(mass=2.0)
        entity.add_component(rigid_body)

        world = PhysicsWorld()
        rigid_body._register_with_world(world)
        body = world.get_body(rigid_body._body_index)

        # Box inertia for mass 2 and full extents 2x3x4.
        assert body.inertia.x == pytest.approx(25.0 / 6.0)
        assert body.inertia.y == pytest.approx(10.0 / 3.0)
        assert body.inertia.z == pytest.approx(13.0 / 6.0)
    finally:
        scene.destroy()
