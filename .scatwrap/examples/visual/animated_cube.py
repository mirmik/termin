<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>examples/visual/animated_cube.py</title>
</head>
<body>
<!-- BEGIN SCAT CODE -->
&quot;&quot;&quot;Animated cube demo: simple rotation driven by a custom component.&quot;&quot;&quot;<br>
<br>
from __future__ import annotations<br>
<br>
import numpy as np<br>
<br>
from termin.geombase.pose3 import Pose3<br>
from termin.mesh.mesh import CubeMesh<br>
from termin.visualization import (<br>
&#9;Entity,<br>
&#9;MeshDrawable,<br>
&#9;Scene,<br>
&#9;Material,<br>
&#9;VisualizationWorld,<br>
&#9;PerspectiveCameraComponent,<br>
&#9;OrbitCameraController,<br>
&#9;Component,<br>
)<br>
from termin.visualization.components import MeshRenderer<br>
from termin.visualization.shader import ShaderProgram<br>
from termin.visualization.skybox import SkyBoxEntity<br>
from termin.visualization.camera import CameraController<br>
<br>
VERT = &quot;&quot;&quot;<br>
#version 330 core<br>
layout(location = 0) in vec3 a_position;<br>
layout(location = 1) in vec3 a_normal;<br>
<br>
uniform mat4 u_model;<br>
uniform mat4 u_view;<br>
uniform mat4 u_projection;<br>
<br>
out vec3 v_normal;<br>
out vec3 v_world_pos;<br>
<br>
void main() {<br>
&#9;vec4 world = u_model * vec4(a_position, 1.0);<br>
&#9;v_world_pos = world.xyz;<br>
&#9;v_normal = mat3(transpose(inverse(u_model))) * a_normal;<br>
&#9;gl_Position = u_projection * u_view * world;<br>
}<br>
&quot;&quot;&quot;<br>
<br>
FRAG = &quot;&quot;&quot;<br>
#version 330 core<br>
in vec3 v_normal;<br>
<br>
uniform vec4 u_color;<br>
uniform vec3 u_light_dir;<br>
<br>
out vec4 FragColor;<br>
<br>
void main() {<br>
&#9;vec3 N = normalize(v_normal);<br>
&#9;float ndotl = max(dot(N, -normalize(u_light_dir)), 0.0);<br>
&#9;vec3 color = u_color.rgb * (0.2 + 0.8 * ndotl);<br>
&#9;FragColor = vec4(color, u_color.a);<br>
}<br>
&quot;&quot;&quot;<br>
<br>
<br>
class RotateComponent(Component):<br>
&#9;&quot;&quot;&quot;Simple component that rotates its entity around a fixed axis.&quot;&quot;&quot;<br>
<br>
&#9;def __init__(self, axis: np.ndarray = np.array([0.0, 1.0, 0.0]), speed: float = 1.0):<br>
&#9;&#9;super().__init__(enabled=True)<br>
&#9;&#9;axis = np.asarray(axis, dtype=float)<br>
&#9;&#9;norm = np.linalg.norm(axis)<br>
&#9;&#9;self.axis = axis / norm if norm &gt; 0 else np.array([0.0, 1.0, 0.0])<br>
&#9;&#9;self.speed = speed<br>
&#9;&#9;self.angle = 0.0<br>
<br>
&#9;def update(self, dt: float):<br>
&#9;&#9;if self.entity is None:<br>
&#9;&#9;&#9;return<br>
&#9;&#9;self.angle += self.speed * dt<br>
&#9;&#9;rot_pose = Pose3.rotation(self.axis, self.angle)<br>
&#9;&#9;translation = self.entity.transform.global_pose().lin.copy()<br>
&#9;&#9;self.entity.transform.relocate(Pose3(ang=rot_pose.ang.copy(), lin=translation))<br>
<br>
<br>
def build_scene(world: VisualizationWorld) -&gt; tuple[Scene, PerspectiveCameraComponent]:<br>
&#9;mesh = MeshDrawable(CubeMesh(size=1.0))<br>
&#9;shader = ShaderProgram(VERT, FRAG)<br>
&#9;material = Material(shader=shader, color=np.array([0.3, 0.7, 0.9, 1.0], dtype=np.float32))<br>
<br>
&#9;cube = Entity(pose=Pose3.identity(), name=&quot;cube&quot;)<br>
&#9;cube.add_component(MeshRenderer(mesh, material))<br>
&#9;cube.add_component(RotateComponent(axis=np.array([0.2, 1.0, 0.3]), speed=1.5))<br>
<br>
&#9;scene = Scene()<br>
&#9;scene.add(cube)<br>
&#9;scene.add(SkyBoxEntity())<br>
&#9;world.add_scene(scene)<br>
<br>
&#9;camera_entity = Entity(name=&quot;camera&quot;)<br>
&#9;camera = PerspectiveCameraComponent()<br>
&#9;camera_entity.add_component(camera)<br>
&#9;camera_entity.add_component(OrbitCameraController(radius=5.0, elevation=30.0))<br>
&#9;scene.add(camera_entity)<br>
<br>
&#9;return scene, camera<br>
<br>
<br>
def main():<br>
&#9;world = VisualizationWorld()<br>
&#9;scene, camera = build_scene(world)<br>
&#9;window = world.create_window(title=&quot;termin animated cube&quot;)<br>
&#9;window.add_viewport(scene, camera)<br>
&#9;world.run()<br>
<br>
<br>
if __name__ == &quot;__main__&quot;:<br>
&#9;main()<br>
<!-- END SCAT CODE -->
</body>
</html>
