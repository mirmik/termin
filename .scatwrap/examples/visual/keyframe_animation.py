<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>examples/visual/keyframe_animation.py</title>
</head>
<body>
<!-- BEGIN SCAT CODE -->
&quot;&quot;&quot;Keyframed animation demo: translation + rotation + scale.&quot;&quot;&quot;<br>
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
)<br>
from termin.visualization.components import MeshRenderer<br>
from termin.visualization.shader import ShaderProgram<br>
from termin.visualization.skybox import SkyBoxEntity<br>
from termin.visualization.animation import (<br>
&#9;AnimationChannel,<br>
&#9;AnimationClip,<br>
&#9;AnimationPlayer,<br>
&#9;AnimationKeyframe,<br>
)<br>
<br>
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
<br>
void main() {<br>
&#9;v_normal = mat3(transpose(inverse(u_model))) * a_normal;<br>
&#9;gl_Position = u_projection * u_view * u_model * vec4(a_position, 1.0);<br>
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
def build_scene(world: VisualizationWorld):<br>
&#9;mesh = MeshDrawable(CubeMesh(size=1.0))<br>
&#9;shader = ShaderProgram(VERT, FRAG)<br>
&#9;material = Material(<br>
&#9;&#9;shader=shader,<br>
&#9;&#9;color=np.array([0.4, 0.9, 0.4, 1.0], dtype=np.float32),<br>
&#9;)<br>
<br>
&#9;cube = Entity(pose=Pose3.identity(), name=&quot;animated_cube&quot;)<br>
&#9;cube.add_component(MeshRenderer(mesh, material))<br>
<br>
&#9;# ============<br>
&#9;# Keyframes<br>
&#9;# ============<br>
<br>
&#9;# движение по &quot;квадрату&quot;<br>
&#9;trs_keys = [<br>
&#9;&#9;AnimationKeyframe(0.0, translation=np.array([1.5, 0.0, 0.0])),<br>
&#9;&#9;AnimationKeyframe(1.0, translation=np.array([0.0, 1.5, 0.0])),<br>
&#9;&#9;AnimationKeyframe(2.0, translation=np.array([-1.5, 0.0, 0.0])),<br>
&#9;&#9;AnimationKeyframe(3.0, translation=np.array([0.0, -1.5, 0.0])),<br>
&#9;&#9;AnimationKeyframe(4.0, translation=np.array([1.5, 0.0, 0.0])),<br>
&#9;]<br>
<br>
&#9;# полный оборот вокруг Y за 4 секунды<br>
&#9;rot_keys = [<br>
&#9;&#9;AnimationKeyframe(0.0, rotation=Pose3.rotateY(0.0).ang),<br>
&#9;&#9;AnimationKeyframe(1.0, rotation=Pose3.rotateY(np.pi/2).ang),<br>
&#9;&#9;AnimationKeyframe(2.0, rotation=Pose3.rotateY(np.pi).ang),<br>
&#9;&#9;AnimationKeyframe(3.0, rotation=Pose3.rotateY(1.5 * np.pi).ang),<br>
&#9;&#9;AnimationKeyframe(4.0, rotation=Pose3.rotateY(2.0 * np.pi).ang),<br>
&#9;]<br>
<br>
&#9;# пульсация масштаба<br>
&#9;scale_keys = [<br>
&#9;&#9;AnimationKeyframe(0.0, scale=1.0),<br>
&#9;&#9;AnimationKeyframe(1.0, scale=1.5),<br>
&#9;&#9;AnimationKeyframe(2.0, scale=1.0),<br>
&#9;&#9;AnimationKeyframe(3.0, scale=0.7),<br>
&#9;&#9;AnimationKeyframe(4.0, scale=1.0),<br>
&#9;]<br>
<br>
&#9;clip = AnimationClip(<br>
&#9;&#9;&quot;move_rotate_scale&quot;,<br>
&#9;&#9;tps = 1.0,  # тики в секунду<br>
&#9;&#9;channels={<br>
&#9;&#9;&#9;&quot;clip&quot; :AnimationChannel(translation_keys=trs_keys, rotation_keys=rot_keys, scale_keys=scale_keys)<br>
&#9;&#9;},<br>
&#9;&#9;loop=True,<br>
&#9;)<br>
<br>
&#9;player = cube.add_component(AnimationPlayer())<br>
&#9;player.add_clip(clip)<br>
&#9;player.play(&quot;move_rotate_scale&quot;)<br>
<br>
&#9;scene = Scene()<br>
&#9;scene.add(cube)<br>
&#9;scene.add(SkyBoxEntity())<br>
&#9;world.add_scene(scene)<br>
<br>
&#9;cam_entity = Entity(name=&quot;camera&quot;)<br>
&#9;cam = PerspectiveCameraComponent()<br>
&#9;cam_entity.add_component(cam)<br>
&#9;cam_entity.add_component(OrbitCameraController(radius=6.0, elevation=30.0))<br>
&#9;scene.add(cam_entity)<br>
<br>
&#9;return scene, cam<br>
<br>
<br>
def main():<br>
&#9;world = VisualizationWorld()<br>
&#9;scene, cam = build_scene(world)<br>
&#9;window = world.create_window(title=&quot;termin keyframed cube&quot;)<br>
&#9;window.add_viewport(scene, cam)<br>
&#9;world.run()<br>
<br>
<br>
if __name__ == &quot;__main__&quot;:<br>
&#9;main()<br>
<!-- END SCAT CODE -->
</body>
</html>
