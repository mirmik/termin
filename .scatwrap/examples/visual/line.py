<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>examples/visual/line.py</title>
</head>
<body>
<!-- BEGIN SCAT CODE -->
&quot;&quot;&quot;Line rendering demo with multiple viewports.&quot;&quot;&quot;<br>
<br>
from __future__ import annotations<br>
<br>
import numpy as np<br>
<br>
from termin.visualization import (<br>
&#9;Entity,<br>
&#9;Material,<br>
&#9;Scene,<br>
&#9;VisualizationWorld,<br>
&#9;PerspectiveCameraComponent,<br>
&#9;OrbitCameraController,<br>
)<br>
from termin.visualization.line import LineEntity<br>
from termin.visualization.shader import ShaderProgram<br>
<br>
<br>
VERT = &quot;&quot;&quot;<br>
#version 330 core<br>
layout(location = 0) in vec3 a_position;<br>
<br>
uniform mat4 u_model;<br>
uniform mat4 u_view;<br>
uniform mat4 u_projection;<br>
<br>
void main() {<br>
&#9;gl_Position = u_projection * u_view * u_model * vec4(a_position, 1.0);<br>
}<br>
&quot;&quot;&quot;<br>
<br>
<br>
FRAG = &quot;&quot;&quot;<br>
#version 330 core<br>
uniform vec4 u_color;<br>
out vec4 FragColor;<br>
<br>
void main() {<br>
&#9;FragColor = u_color;<br>
}<br>
&quot;&quot;&quot;<br>
<br>
<br>
def build_scene(world: VisualizationWorld) -&gt; tuple[Scene, PerspectiveCameraComponent]:<br>
&#9;shader_prog = ShaderProgram(VERT, FRAG)<br>
&#9;material = Material(shader=shader_prog, color=np.array([0.1, 0.8, 0.2, 1.0], dtype=np.float32))<br>
&#9;points = [<br>
&#9;&#9;np.array([0.0, 0.0, 0.0]),<br>
&#9;&#9;np.array([1.0, 0.0, 0.0]),<br>
&#9;&#9;np.array([1.0, 1.0, 0.0]),<br>
&#9;&#9;np.array([0.0, 1.0, 0.0]),<br>
&#9;&#9;np.array([0.0, 0.0, 0.0]),<br>
&#9;]<br>
&#9;line1 = LineEntity(points=points, material=material, name=&quot;line1&quot;)<br>
&#9;line2 = LineEntity(points=[p + np.array([0.0, 0.0, 1.0]) for p in points], material=material, name=&quot;line2&quot;)<br>
<br>
&#9;scene = Scene()<br>
&#9;scene.add(line1)<br>
&#9;scene.add(line2)<br>
&#9;world.add_scene(scene)<br>
<br>
&#9;camera_entity = Entity(name=&quot;camera&quot;)<br>
&#9;camera = PerspectiveCameraComponent()<br>
&#9;camera_entity.add_component(camera)<br>
&#9;camera_entity.add_component(OrbitCameraController(target=np.array([0.5, 0.5, 0.5])))<br>
&#9;scene.add(camera_entity)<br>
<br>
&#9;return scene, camera<br>
<br>
<br>
def main():<br>
&#9;world = VisualizationWorld()<br>
&#9;scene, camera = build_scene(world)<br>
&#9;window = world.create_window(title=&quot;termin line demo&quot;)<br>
&#9;# illustrate two viewports referencing same scene/camera<br>
&#9;window.add_viewport(scene, camera, rect=(0.0, 0.0, 0.5, 1.0))<br>
&#9;window.add_viewport(scene, camera, rect=(0.5, 0.0, 0.5, 1.0))<br>
&#9;world.run()<br>
<br>
<br>
if __name__ == &quot;__main__&quot;:<br>
&#9;main()<br>
<!-- END SCAT CODE -->
</body>
</html>
