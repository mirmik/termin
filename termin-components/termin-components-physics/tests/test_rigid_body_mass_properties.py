import math
import subprocess
import sys
import textwrap

import pytest

from termin.colliders.collider_component import ColliderComponent
from termin.geombase import GeneralPose3, Vec3
from termin.physics._physics_native import PhysicsWorld
from termin.physics_components import RigidBodyComponent
from termin.scene import TcScene


def test_capsule_component_uses_scaled_analytic_mass_properties() -> None:
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

        world = PhysicsWorld()
        rigid_body._register_with_world(world)
        body = world.get_body(rigid_body._body_index)

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
        attached_transform = collider.attached.world_transform()
        assert collider.collider.radius * min(
            attached_transform.scale.x,
            attached_transform.scale.y,
        ) == pytest.approx(radius)
        assert (
            collider.collider.half_height * attached_transform.scale.z
            == pytest.approx(half_height)
        )
    finally:
        scene.destroy()


def test_asymmetric_and_degenerate_hull_component_mass_properties() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            textwrap.dedent(
                """
                import numpy as np

                from termin.bootstrap import bootstrap_player, shutdown_runtime
                from termin.colliders.collider_component import ColliderComponent
                from termin.geombase import GeneralPose3, Quat, Vec3
                from termin.mesh import MeshComponent
                from termin.physics._physics_native import PhysicsWorld
                from termin.physics_components import RigidBodyComponent
                from termin.scene import TcScene
                from tmesh import Mesh3, TcMesh

                bootstrap_player()

                vertices = np.asarray([
                    [0.0, 0.0, 0.0],
                    [2.0, 0.0, 0.0],
                    [0.0, 1.0, 0.0],
                    [0.0, 0.0, 3.0],
                ], dtype=np.float32)
                triangles = np.asarray([
                    [0, 2, 1],
                    [0, 1, 3],
                    [0, 3, 2],
                    [1, 2, 3],
                ], dtype=np.uint32)

                scene = TcScene.create("asymmetric-hull-rigid-body")
                entity = scene.create_entity("AsymmetricHull")
                angle = 0.4
                entity.transform.relocate(GeneralPose3(
                    ang=Quat(0.0, 0.0, np.sin(angle / 2.0), np.cos(angle / 2.0)),
                    lin=Vec3(10.0, 20.0, 30.0),
                    scale=Vec3(2.0, 3.0, 0.5),
                ))
                mesh = MeshComponent()
                mesh.set_generated_mesh(TcMesh.from_mesh3(Mesh3(vertices, triangles)))
                entity.add_component(mesh)
                collider = ColliderComponent()
                collider.collider_type = "ConvexHull"
                collider.convex_hull_mesh_source = "MeshComponent"
                entity.add_component(collider)
                rigid_body = RigidBodyComponent(mass=4.0)
                entity.add_component(rigid_body)

                world = PhysicsWorld()
                rigid_body._register_with_world(world)
                assert rigid_body._body_index >= 0
                body = world.get_body(rigid_body._body_index)
                center_local = body.inertia_frame_local.lin
                np.testing.assert_allclose(
                    [center_local.x, center_local.y, center_local.z],
                    [1.0, 0.75, 0.375],
                    rtol=0.0,
                    atol=1.0e-10,
                )
                assert 0.0 < body.inertia.x < body.inertia.y < body.inertia.z
                shape_pose = body.shape_pose()
                np.testing.assert_allclose(
                    [shape_pose.lin.x, shape_pose.lin.y, shape_pose.lin.z],
                    [10.0, 20.0, 30.0],
                    rtol=0.0,
                    atol=1.0e-10,
                )

                coplanar_vertices = vertices.copy()
                coplanar_vertices[:, 2] = 0.0
                invalid_entity = scene.create_entity("DegenerateHull")
                invalid_mesh = MeshComponent()
                invalid_mesh.set_generated_mesh(
                    TcMesh.from_mesh3(Mesh3(coplanar_vertices, triangles))
                )
                invalid_entity.add_component(invalid_mesh)
                invalid_collider = ColliderComponent()
                invalid_collider.collider_type = "ConvexHull"
                invalid_collider.convex_hull_mesh_source = "MeshComponent"
                invalid_entity.add_component(invalid_collider)
                invalid_body = RigidBodyComponent(mass=1.0)
                invalid_entity.add_component(invalid_body)
                invalid_body._register_with_world(world)
                assert invalid_body._body_index == -1

                scene.destroy()
                shutdown_runtime()
                """
            ),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    output = result.stdout + result.stderr
    assert result.returncode == 0, output
    assert "rejected ConvexHull mass properties" in output
    assert "closed non-degenerate surface" in output or "zero" in output
