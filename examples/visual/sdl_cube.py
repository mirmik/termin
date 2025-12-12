"""Demo using SDL2 backend for window management instead of GLFW.

Shows how to use the SDL backend for rendering with the visualization system.
"""

from __future__ import annotations

import numpy as np

from termin.geombase.pose3 import Pose3
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
from termin.visualization.platform.backends.sdl import SDLWindowBackend


def build_scene(world: VisualizationWorld) -> tuple[Scene, PerspectiveCameraComponent]:
    cube_mesh = CubeMesh()
    drawable = MeshDrawable(cube_mesh)
    material = Material(color=np.array([0.3, 0.6, 0.8, 1.0], dtype=np.float32))
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
    # Use SDL backend instead of default GLFW
    sdl_backend = SDLWindowBackend()
    world = VisualizationWorld(window_backend=sdl_backend)

    scene, camera = build_scene(world)
    window = world.create_window(title="termin SDL demo")
    window.add_viewport(scene, camera)
    world.run()


if __name__ == "__main__":
    main()
