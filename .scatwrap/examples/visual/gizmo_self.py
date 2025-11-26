<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>examples/visual/gizmo_self.py</title>
</head>
<body>
<!-- BEGIN SCAT CODE -->
&quot;&quot;&quot;Minimal demo that renders a cube and allows orbiting camera controls.&quot;&quot;&quot;<br>
<br>
from __future__ import annotations<br>
<br>
import numpy as np<br>
<br>
from termin.geombase.pose3 import Pose3<br>
from termin.mesh.mesh import UVSphereMesh, Mesh, CubeMesh<br>
from termin.visualization import (<br>
    Entity,<br>
    MeshDrawable,<br>
    Scene,<br>
    Material,<br>
    VisualizationWorld,<br>
    PerspectiveCameraComponent,<br>
    OrbitCameraController,<br>
)<br>
from termin.visualization.components import MeshRenderer<br>
from termin.visualization.shader import ShaderProgram<br>
from termin.visualization.skybox import SkyBoxEntity<br>
from termin.visualization.gizmos import GizmoEntity, GizmoMoveController<br>
from termin.visualization.scene import Scene<br>
<br>
def build_scene(world: VisualizationWorld) -&gt; tuple[Scene, PerspectiveCameraComponent]:<br>
    scene = Scene()<br>
<br>
    gizmo = GizmoEntity(size=2.0)<br>
    gizmo.add_component(GizmoMoveController(gizmo, scene))<br>
    scene.add(gizmo)<br>
<br>
    skybox = SkyBoxEntity()<br>
    scene.add(skybox)<br>
    world.add_scene(scene)<br>
<br>
    camera_entity = Entity(name=&quot;camera&quot;)<br>
    camera = PerspectiveCameraComponent()<br>
    camera_entity.add_component(camera)<br>
    controller = OrbitCameraController()<br>
    controller.azimuth = 0<br>
    controller.elevation = 0<br>
    camera_entity.add_component(controller)<br>
    <br>
    scene.add(camera_entity)<br>
<br>
    return scene, camera<br>
<br>
<br>
def main():<br>
    world = VisualizationWorld()<br>
    scene, camera = build_scene(world)<br>
    window = world.create_window(title=&quot;termin cube demo&quot;)<br>
    window.add_viewport(scene, camera)<br>
    world.run()<br>
<br>
<br>
if __name__ == &quot;__main__&quot;:<br>
    main()<br>
<!-- END SCAT CODE -->
</body>
</html>
