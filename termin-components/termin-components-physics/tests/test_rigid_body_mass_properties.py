import math

import pytest

from termin.bootstrap import bootstrap_player, shutdown_runtime
from termin.colliders.collider_component import ColliderComponent
from termin.geombase import GeneralPose3, Vec3
from termin.physics_components import PhysicsWorldComponent, RigidBodyComponent
from termin.scene import TcScene


def test_capsule_component_uses_scaled_analytic_mass_properties() -> None:
    bootstrap_player()
    scene = TcScene.create("capsule-rigid-body-mass")
    try:
        entity = scene.create_entity("Capsule")
        entity.transform.relocate(GeneralPose3(scale=Vec3(3.0, 2.0, 0.5)))
        collider = ColliderComponent()
        collider.collider_type = "Capsule"
        collider.box_size = (2.0, 4.0, 6.0)
        entity.add_component(collider)
        rigid_body = RigidBodyComponent(mass=5.0)
        entity.add_component(rigid_body)

        world_entity = scene.create_entity("Physics World")
        world = PhysicsWorldComponent()
        world_entity.add_component(world)
        world.start()
        body = rigid_body.rigid_body
        assert body is not None

        radius = 2.0
        half_height = 1.5
        cylinder_volume = 2.0 * math.pi * radius**2 * half_height
        sphere_volume = 4.0 * math.pi * radius**3 / 3.0
        cylinder_mass = 5.0 * cylinder_volume / (cylinder_volume + sphere_volume)
        sphere_mass = 5.0 - cylinder_mass
        expected_axial = radius**2 * (
            0.5 * cylinder_mass + 0.4 * sphere_mass
        )
        expected_transverse = (
            cylinder_mass * (3.0 * radius**2 + 4.0 * half_height**2) / 12.0
            + sphere_mass
            * (0.4 * radius**2 + 0.75 * half_height * radius + half_height**2)
        )

        assert body.inertia.x == pytest.approx(expected_transverse)
        assert body.inertia.y == pytest.approx(expected_transverse)
        assert body.inertia.z == pytest.approx(expected_axial)
    finally:
        scene.destroy()
        shutdown_runtime()
