"""Minimal demo that renders a cube and allows orbiting camera controls."""

from __future__ import annotations

import numpy as np

from termin.geombase.pose3 import Pose3
from termin.mesh.mesh import UVSphereMesh, Mesh, CubeMesh
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
from termin.visualization.render.shader import ShaderProgram
from termin.editor.gizmo import GizmoEntity, GizmoMoveController
from termin.visualization.core.scene import Scene

def build_scene(world: VisualizationWorld) -> tuple[Scene, PerspectiveCameraComponent]:
    scene = Scene()

    gizmo = GizmoEntity(size=2.0)
    gizmo.add_component(GizmoMoveController(gizmo, scene))
    scene.add(gizmo)

    world.add_scene(scene)

    camera_entity = Entity(name="camera")
    camera = PerspectiveCameraComponent()
    camera_entity.add_component(camera)
    controller = OrbitCameraController()
    controller.azimuth = 0
    controller.elevation = 0
    camera_entity.add_component(controller)
    
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
