<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>examples/visual/color_toggle.py</title>
</head>
<body>
<!-- BEGIN SCAT CODE -->
&quot;&quot;&quot;Example: change cube color when SPACE is pressed.&quot;&quot;&quot;<br>
<br>
from __future__ import annotations<br>
<br>
import numpy as np<br>
from termin.mesh.mesh import CubeMesh<br>
from termin.visualization import (<br>
&#9;Entity,<br>
&#9;MeshDrawable,<br>
&#9;Scene,<br>
&#9;Material,<br>
&#9;VisualizationWorld,<br>
&#9;PerspectiveCameraComponent,<br>
&#9;OrbitCameraController,<br>
&#9;InputComponent,<br>
)<br>
from termin.visualization.backends.base import Action, Key<br>
from termin.visualization.components import MeshRenderer<br>
from termin.visualization.shader import ShaderProgram<br>
from termin.visualization.skybox import SkyBoxEntity<br>
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
uniform vec4 u_color;<br>
<br>
out vec4 FragColor;<br>
<br>
void main() {<br>
&#9;vec3 n = normalize(v_normal);<br>
&#9;float ndotl = max(dot(n, vec3(0.3, 0.7, 0.4)), 0.0);<br>
&#9;vec3 color = u_color.rgb * (0.2 + 0.8 * ndotl);<br>
&#9;FragColor = vec4(color, u_color.a);<br>
}<br>
&quot;&quot;&quot;<br>
<br>
<br>
class ColorToggleComponent(InputComponent):<br>
&#9;&quot;&quot;&quot;Toggle material color when the user presses space.&quot;&quot;&quot;<br>
<br>
&#9;def __init__(self, material: Material, colors: list[np.ndarray]):<br>
&#9;&#9;super().__init__(enabled=True)<br>
&#9;&#9;self.material = material<br>
&#9;&#9;self.colors = colors<br>
&#9;&#9;self.index = 0<br>
<br>
&#9;def on_key(self, viewport, key: int, scancode: int, action: int, mods: int):<br>
&#9;&#9;if key == Key.SPACE and action == Action.PRESS:<br>
&#9;&#9;&#9;self.index = (self.index + 1) % len(self.colors)<br>
&#9;&#9;&#9;self.material.update_color(self.colors[self.index])<br>
<br>
<br>
def build_scene(world: VisualizationWorld) -&gt; tuple[Scene, PerspectiveCameraComponent]:<br>
&#9;shader = ShaderProgram(VERT, FRAG)<br>
&#9;material = Material(shader=shader, color=np.array([0.9, 0.2, 0.2, 1.0], dtype=np.float32))<br>
&#9;mesh = MeshDrawable(CubeMesh(size=1.5))<br>
&#9;cube = Entity(name=&quot;cube&quot;)<br>
&#9;cube.add_component(MeshRenderer(mesh, material))<br>
&#9;cube.add_component(<br>
&#9;&#9;ColorToggleComponent(<br>
&#9;&#9;&#9;material,<br>
&#9;&#9;&#9;[<br>
&#9;&#9;&#9;&#9;np.array([0.9, 0.2, 0.2, 1.0]),<br>
&#9;&#9;&#9;&#9;np.array([0.2, 0.9, 0.3, 1.0]),<br>
&#9;&#9;&#9;&#9;np.array([0.2, 0.4, 0.9, 1.0]),<br>
&#9;&#9;&#9;],<br>
&#9;&#9;)<br>
&#9;)<br>
<br>
&#9;scene = Scene()<br>
&#9;scene.add(cube)<br>
&#9;scene.add(SkyBoxEntity())<br>
&#9;world.add_scene(scene)<br>
<br>
&#9;cam_entity = Entity(name=&quot;camera&quot;)<br>
&#9;camera = PerspectiveCameraComponent()<br>
&#9;cam_entity.add_component(camera)<br>
&#9;cam_entity.add_component(OrbitCameraController(radius=4.0))<br>
&#9;scene.add(cam_entity)<br>
&#9;return scene, camera<br>
<br>
<br>
def main():<br>
&#9;world = VisualizationWorld()<br>
&#9;scene, camera = build_scene(world)<br>
&#9;window = world.create_window(title=&quot;termin color toggle&quot;)<br>
&#9;window.add_viewport(scene, camera)<br>
&#9;world.run()<br>
<br>
<br>
if __name__ == &quot;__main__&quot;:<br>
&#9;main()<br>
<!-- END SCAT CODE -->
</body>
</html>
