<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>examples/visual/gizmo_self.py</title>
</head>
<body>
<pre><code>
&quot;&quot;&quot;Minimal demo that renders a cube and allows orbiting camera controls.&quot;&quot;&quot;

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
from termin.visualization.components import MeshRenderer
from termin.visualization.shader import ShaderProgram
from termin.visualization.skybox import SkyBoxEntity
from termin.visualization.gizmos import GizmoEntity, GizmoMoveController
from termin.visualization.scene import Scene

def build_scene(world: VisualizationWorld) -&gt; tuple[Scene, PerspectiveCameraComponent]:
    scene = Scene()

    gizmo = GizmoEntity(size=2.0)
    gizmo.add_component(GizmoMoveController(gizmo, scene))
    scene.add(gizmo)

    skybox = SkyBoxEntity()
    scene.add(skybox)
    world.add_scene(scene)

    camera_entity = Entity(name=&quot;camera&quot;)
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
    window = world.create_window(title=&quot;termin cube demo&quot;)
    window.add_viewport(scene, camera)
    world.run()


if __name__ == &quot;__main__&quot;:
    main()

</code></pre>
</body>
</html>
