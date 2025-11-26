<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>examples/visual/wrap3d.py</title>
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
from termin.mesh.mesh import UVSphereMesh, Mesh, Mesh3<br>
from termin.visualization import (<br>
&#9;Entity,<br>
&#9;MeshDrawable,<br>
&#9;Scene,<br>
&#9;Material,<br>
&#9;VisualizationWorld,<br>
&#9;PerspectiveCameraComponent,<br>
&#9;OrbitCameraController,<br>
)<br>
from termin.visualization.components import MeshRenderer<br>
from termin.visualization.shader import ShaderProgram<br>
from termin.visualization.skybox import SkyBoxEntity<br>
from termin.visualization.materials.simple import ColorMaterial<br>
<br>
# import convex hull<br>
from scipy.spatial import ConvexHull<br>
<br>
def build_scene(world: VisualizationWorld) -&gt; tuple[Scene, PerspectiveCameraComponent]:<br>
&#9;<br>
&#9;mesh = ConvexHull([<br>
&#9;&#9;[1, 1, 1],<br>
&#9;&#9;[1, 1, -1],<br>
&#9;&#9;[1, -1, 1],<br>
&#9;&#9;[1, -1, -1],<br>
&#9;&#9;[-1, 1, 1],<br>
&#9;&#9;[-1, 1, -1],<br>
&#9;&#9;[-1, -1, 1],<br>
&#9;&#9;[-1, -1, -1],<br>
<br>
<br>
&#9;&#9;[-2, -2, -1],<br>
&#9;&#9;[2, -2, -1],<br>
&#9;&#9;[2, 2, -1],<br>
&#9;&#9;[-2, 2, -1],<br>
&#9;])<br>
&#9;mesh = Mesh3.from_convex_hull(mesh)<br>
<br>
&#9;drawable = MeshDrawable(mesh)<br>
<br>
&#9;material = ColorMaterial((0.8, 0.3, 0.3, 1.0))<br>
&#9;entity = Entity(pose=Pose3.identity(), name=&quot;cube&quot;)<br>
&#9;entity.add_component(MeshRenderer(drawable, material))<br>
&#9;scene = Scene()<br>
&#9;scene.add(entity)<br>
<br>
&#9;skybox = SkyBoxEntity()<br>
&#9;scene.add(skybox)<br>
&#9;world.add_scene(scene)<br>
<br>
&#9;camera_entity = Entity(name=&quot;camera&quot;)<br>
&#9;camera = PerspectiveCameraComponent()<br>
&#9;camera_entity.add_component(camera)<br>
&#9;camera_entity.add_component(OrbitCameraController())<br>
&#9;scene.add(camera_entity)<br>
<br>
&#9;return scene, camera<br>
<br>
<br>
def main():<br>
&#9;world = VisualizationWorld()<br>
&#9;scene, camera = build_scene(world)<br>
&#9;window = world.create_window(title=&quot;termin cube demo&quot;)<br>
&#9;window.add_viewport(scene, camera)<br>
&#9;world.run()<br>
<br>
<br>
if __name__ == &quot;__main__&quot;:<br>
&#9;main()<br>
<!-- END SCAT CODE -->
</body>
</html>
