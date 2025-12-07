"""
WebSocket стриминг демо.

Рендерит сцену с кубом и стримит в браузер через WebSocket.
Запуск: python examples/visual/webstream.py
Открыть: http://localhost:8080
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
from termin.visualization.render.components import MeshRenderer
from termin.visualization.render.skybox import SkyBoxEntity
from termin.visualization.streaming import WebStreamServer
from termin.visualization.render.shader import ShaderProgram

VERT = """
#version 330 core
layout(location = 0) in vec3 a_position;
layout(location = 1) in vec3 a_normal;

uniform mat4 u_model;
uniform mat4 u_view;
uniform mat4 u_projection;

out vec3 v_normal;

void main() {
    v_normal = mat3(transpose(inverse(u_model))) * a_normal;
    gl_Position = u_projection * u_view * u_model * vec4(a_position, 1.0);
}
"""

FRAG = """
#version 330 core
in vec3 v_normal;
uniform vec4 u_color;

out vec4 FragColor;

void main() {
    vec3 n = normalize(v_normal);
    float ndotl = max(dot(n, vec3(0.3, 0.7, 0.4)), 0.0);
    vec3 color = u_color.rgb * (0.2 + 0.8 * ndotl);
    FragColor = vec4(color, u_color.a);
}
"""

def build_scene(world: VisualizationWorld) -> tuple[Scene, PerspectiveCameraComponent]:
    """Создаёт сцену с кубом и камерой."""
    # Куб
    cube_mesh = CubeMesh()
    drawable = MeshDrawable(cube_mesh)
    shader = ShaderProgram(vertex_source=VERT, fragment_source=FRAG)
    material = Material(shader=shader)
    entity = Entity(pose=Pose3.identity(), name="cube")
    entity.add_component(MeshRenderer(drawable, material))

    scene = Scene()
    scene.add(entity)

    # Скайбокс
    skybox = SkyBoxEntity()
    scene.add(skybox)

    world.add_scene(scene)

    # Камера с орбитальным контроллером
    camera_entity = Entity(name="camera")
    camera = PerspectiveCameraComponent()
    camera_entity.add_component(camera)
    camera_entity.add_component(OrbitCameraController())
    scene.add(camera_entity)

    return scene, camera


def main():
    world = VisualizationWorld()
    scene, camera = build_scene(world)

    # Создаём стриминг сервер
    server = WebStreamServer(
        world=world,
        scene=scene,
        camera=camera,
        width=1280,
        height=720,
        fps=30,
        quality=85,
    )

    # Запускаем с HTTP сервером
    # WebSocket на порту 8765, HTTP на 8080
    server.run_with_http(host="0.0.0.0", ws_port=8765, http_port=8080)


if __name__ == "__main__":
    main()
