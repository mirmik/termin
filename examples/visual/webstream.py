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
    Scene,
    VisualizationWorld,
    PerspectiveCameraComponent,
    OrbitCameraController,
)
from termin.visualization.render.components import MeshRenderer
from termin.visualization.render.materials.simple import ColorMaterial
from termin.visualization.streaming import WebStreamServer


def build_scene(world: VisualizationWorld) -> tuple[Scene, PerspectiveCameraComponent]:
    """Создаёт сцену с кубом и камерой."""
    scene = Scene()

    # Камера с орбитальным контроллером
    camera_entity = Entity(name="camera")
    camera = PerspectiveCameraComponent()
    camera_entity.add_component(camera)
    camera_entity.add_component(OrbitCameraController())
    camera_entity.transform.relocate(Pose3.looking_at(
        eye=np.array([3.0, 3.0, 3.0]),
        target=np.array([0.0, 0.0, 0.0]),
        up=np.array([0.0, 0.0, 1.0]),
    ))
    scene.add(camera_entity)

    # Красный куб
    cube = Entity(name="cube")
    material = ColorMaterial(color=(1.0, 0.3, 0.3, 1.0))
    cube.add_component(MeshRenderer(CubeMesh(), material=material))
    scene.add(cube)

    world.add_scene(scene)

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
try:
    server.run_with_http(host="0.0.0.0", ws_port=8765, http_port=8080)
except:
    server.run_with_http(host="0.0.0.0", ws_port=8745, http_port=8060)

if __name__ == "__main__":
    main()
