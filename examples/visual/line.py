"""Line rendering demo with multiple viewports."""

from __future__ import annotations

import numpy as np

from termin.geombase.pose3 import Pose3
from termin.visualization import (
    Entity,
    Material,
    Scene,
    VisualizationWorld,
    PerspectiveCameraComponent,
    OrbitCameraController,
)
from termin.visualization.core.line import LineEntity
from termin.visualization.render.components import LightComponent
from termin.visualization.render.shader import ShaderProgram


VERT = """
#version 330 core
layout(location = 0) in vec3 a_position;

uniform mat4 u_model;
uniform mat4 u_view;
uniform mat4 u_projection;

void main() {
    gl_Position = u_projection * u_view * u_model * vec4(a_position, 1.0);
}
"""


FRAG = """
#version 330 core
uniform vec4 u_color;
out vec4 FragColor;

void main() {
    FragColor = u_color;
}
"""


def build_scene(world: VisualizationWorld) -> tuple[Scene, PerspectiveCameraComponent]:
    shader_prog = ShaderProgram(VERT, FRAG)
    material = Material(shader=shader_prog, color=np.array([0.1, 0.8, 0.2, 1.0], dtype=np.float32))
    points = [
        np.array([0.0, 0.0, 0.0]),
        np.array([1.0, 0.0, 0.0]),
        np.array([1.0, 1.0, 0.0]),
        np.array([0.0, 1.0, 0.0]),
        np.array([0.0, 0.0, 0.0]),
    ]
    line1 = LineEntity(points=points, material=material, name="line1")
    line2 = LineEntity(points=[p + np.array([0.0, 0.0, 1.0]) for p in points], material=material, name="line2")

    scene = Scene()
    scene.add(line1)
    scene.add(line2)
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
    camera_entity.add_component(OrbitCameraController(target=np.array([0.5, 0.5, 0.5])))
    scene.add(camera_entity)

    return scene, camera


def main():
    world = VisualizationWorld()
    scene, camera = build_scene(world)
    window = world.create_window(title="termin line demo")
    # illustrate two viewports referencing same scene/camera
    window.add_viewport(scene, camera, rect=(0.0, 0.0, 0.5, 1.0))
    window.add_viewport(scene, camera, rect=(0.5, 0.0, 0.5, 1.0))
    world.run()


if __name__ == "__main__":
    main()
