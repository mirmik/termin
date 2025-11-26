<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>examples/visual/ui_slider.py</title>
</head>
<body>
<!-- BEGIN SCAT CODE -->
&quot;&quot;&quot;UI slider demo: draggable slider controlling cube color.&quot;&quot;&quot;<br>
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
<br>
from termin.visualization.ui import Canvas, UIRectangle<br>
from termin.visualization.ui.font import FontTextureAtlas<br>
from termin.visualization.ui.elements import UISlider, UIText<br>
<br>
<br>
# ----- 3D SHADER ---------------------------------------------------<br>
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
uniform vec3 u_light_dir;<br>
out vec4 FragColor;<br>
<br>
void main(){<br>
&#9;vec3 N = normalize(v_normal);<br>
&#9;float ndotl = max(dot(N, -normalize(u_light_dir)), 0.0);<br>
&#9;vec3 color = u_color.rgb * (0.2 + 0.8 * ndotl);<br>
&#9;FragColor = vec4(color, u_color.a);<br>
}<br>
&quot;&quot;&quot;<br>
<br>
<br>
# ----- UI SHADER ---------------------------------------------------<br>
<br>
UI_VERTEX_SHADER = &quot;&quot;&quot;<br>
#version 330 core<br>
layout(location=0) in vec2 a_position;<br>
layout(location=1) in vec2 a_uv;<br>
<br>
out vec2 v_uv;<br>
<br>
void main(){<br>
&#9;v_uv = a_uv;<br>
&#9;gl_Position = vec4(a_position, 0, 1);<br>
}<br>
&quot;&quot;&quot;<br>
<br>
UI_FRAGMENT_SHADER = &quot;&quot;&quot;<br>
#version 330 core<br>
uniform sampler2D u_texture;<br>
uniform vec4 u_color;<br>
uniform bool u_use_texture;<br>
<br>
in vec2 v_uv;<br>
out vec4 FragColor;<br>
<br>
void main(){<br>
&#9;float alpha = u_color.a;<br>
&#9;if (u_use_texture) {<br>
&#9;&#9;alpha *= texture(u_texture, v_uv).r;<br>
&#9;}<br>
&#9;FragColor = vec4(u_color.rgb, alpha);<br>
}<br>
&quot;&quot;&quot;<br>
<br>
<br>
# ----- BUILD SCENE ---------------------------------------------------<br>
<br>
def build_scene(world: VisualizationWorld):<br>
&#9;# 3D cube<br>
&#9;shader = ShaderProgram(VERT, FRAG)<br>
&#9;cube_color = np.array([0.6, 0.8, 0.9, 1.0], dtype=np.float32)<br>
&#9;material = Material(shader=shader, color=cube_color)<br>
&#9;cube_mesh = MeshDrawable(CubeMesh(size=1.0))<br>
<br>
&#9;cube = Entity(name=&quot;cube&quot;, pose=Pose3.identity())<br>
&#9;cube.add_component(MeshRenderer(cube_mesh, material))<br>
<br>
&#9;scene = Scene()<br>
&#9;scene.add(cube)<br>
&#9;scene.add(SkyBoxEntity())<br>
&#9;world.add_scene(scene)<br>
<br>
&#9;# Camera + orbit controller<br>
&#9;cam_entity = Entity(name=&quot;camera&quot;)<br>
&#9;cam = PerspectiveCameraComponent()<br>
&#9;cam_entity.add_component(cam)<br>
&#9;cam_entity.add_component(OrbitCameraController(radius=5.0))<br>
&#9;scene.add(cam_entity)<br>
<br>
&#9;# ----- UI CANVAS -----<br>
&#9;canvas = Canvas()<br>
<br>
&#9;# UI materials<br>
&#9;ui_shader = ShaderProgram(UI_VERTEX_SHADER, UI_FRAGMENT_SHADER)<br>
&#9;ui_material_rect = Material(<br>
&#9;&#9;ui_shader,<br>
&#9;&#9;color=np.array([1, 1, 1, 1], dtype=np.float32),<br>
&#9;&#9;uniforms={&quot;u_use_texture&quot;: False}<br>
&#9;)<br>
&#9;ui_material_text = Material(<br>
&#9;&#9;ui_shader,<br>
&#9;&#9;color=np.array([1, 1, 1, 1], dtype=np.float32),<br>
&#9;&#9;uniforms={&quot;u_use_texture&quot;: True}<br>
&#9;)<br>
<br>
&#9;# Font for text and slider label<br>
&#9;canvas.font = FontTextureAtlas(&quot;examples/data/fonts/Roboto-Regular.ttf&quot;, size=32)<br>
<br>
&#9;# Background panel<br>
&#9;canvas.add(UIRectangle(<br>
&#9;&#9;position=(0.04, 0.04),<br>
&#9;&#9;size=(0.50, 0.20),<br>
&#9;&#9;color=(0, 0, 0, 0.4),<br>
&#9;&#9;material=ui_material_rect,<br>
&#9;))<br>
<br>
&#9;# Label above slider<br>
&#9;canvas.add(UIText(<br>
&#9;&#9;text=&quot;Cube color (blue component):&quot;,<br>
&#9;&#9;position=(0.05, 0.05),<br>
&#9;&#9;color=(1, 1, 1, 1),<br>
&#9;&#9;material=ui_material_text,<br>
&#9;&#9;scale=0.8,<br>
&#9;))<br>
<br>
&#9;# ----- SLIDER -----<br>
&#9;def on_slider(value: float):<br>
&#9;&#9;# value 0..1 → меняем кубовый цвет<br>
&#9;&#9;cube_color[2] = value  # blue channel<br>
&#9;&#9;material.update_color(cube_color)<br>
<br>
&#9;slider = UISlider(<br>
&#9;&#9;position=(0.05, 0.10),<br>
&#9;&#9;size=(0.40, 0.06),<br>
&#9;&#9;value=0.9,<br>
&#9;&#9;on_change=on_slider,<br>
&#9;&#9;material=ui_material_rect,        # track material<br>
&#9;&#9;handle_material=ui_material_rect  # handle material<br>
&#9;)<br>
&#9;canvas.add(slider)<br>
<br>
&#9;return scene, cam, canvas<br>
<br>
<br>
# ----- MAIN -----------------------------------------------------------<br>
<br>
def main():<br>
&#9;world = VisualizationWorld()<br>
&#9;scene, cam, canvas = build_scene(world)<br>
<br>
&#9;win = world.create_window(title=&quot;termin UI slider demo&quot;)<br>
&#9;win.add_viewport(scene, cam, canvas=canvas)<br>
<br>
&#9;world.run()<br>
<br>
<br>
if __name__ == &quot;__main__&quot;:<br>
&#9;main()<br>
<!-- END SCAT CODE -->
</body>
</html>
