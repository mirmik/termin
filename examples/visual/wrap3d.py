"""Minimal demo that renders a cube and allows orbiting camera controls."""

from __future__ import annotations

import numpy as np

from termin.geombase import Pose3
from termin.mesh.mesh import UVSphereMesh, Mesh, Mesh3
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
from termin.visualization.render.shader import ShaderProgram
from termin.visualization.render.materials.simple import ColorMaterial

# import convex hull
from scipy.spatial import ConvexHull

def build_scene(world: VisualizationWorld) -> tuple[Scene, PerspectiveCameraComponent]:
    
    mesh = ConvexHull([
        [1, 1, 1],
        [1, 1, -1],
        [1, -1, 1],
        [1, -1, -1],
        [-1, 1, 1],
        [-1, 1, -1],
        [-1, -1, 1],
        [-1, -1, -1],


        [-2, -2, -1],
        [2, -2, -1],
        [2, 2, -1],
        [-2, 2, -1],
    ])
    mesh = Mesh3.from_convex_hull(mesh)

    drawable = MeshDrawable(mesh)

    material = ColorMaterial((0.8, 0.3, 0.3, 1.0))
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
