"""Minimal demo that renders a cube and allows orbiting camera controls."""

from __future__ import annotations

import numpy as np

from termin.geombase import Pose3
from termin.mesh.mesh import CubeMesh
from termin.visualization import (
    Entity,
    MeshDrawable,
    Scene,
    Material,
    VisualizationWorld,
    PerspectiveCameraComponent,
    OrbitCameraController,
)
from termin.visualization.render.components import MeshRenderer, LightComponent


def build_scene(world: VisualizationWorld) -> tuple[Scene, PerspectiveCameraComponent]:
    cube_mesh = CubeMesh()
    drawable = MeshDrawable(cube_mesh)
    material = Material(color=np.array([0.8, 0.3, 0.3, 1.0], dtype=np.float32))
    entity = Entity(pose=Pose3.identity(), name="cube")
    entity.add_component(MeshRenderer(drawable, material))
    scene = Scene()
    scene.add(entity)

    world.add_scene(scene)

    # Light
    light_entity = Entity(
        pose=Pose3.from_euler(np.deg2rad(-45), np.deg2rad(-45), 0),
        name="light",
    )
    light_entity.add_component(LightComponent())
    scene.add(light_entity)

    # Camera
    camera_entity = Entity(name="camera")
    camera = PerspectiveCameraComponent()
    camera_entity.add_component(camera)
    camera_entity.add_component(OrbitCameraController())
    scene.add(camera_entity)

    return scene, camera


def main():
    world = VisualizationWorld()
    scene, camera = build_scene(world)
    window = world.create_window(title="termin cube demo")
    window.add_viewport(scene, camera)
    world.run()


if __name__ == "__main__":
    main()
