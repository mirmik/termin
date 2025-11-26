<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>examples/visual/ui_button.py</title>
</head>
<body>
<!-- BEGIN SCAT CODE -->
&quot;&quot;&quot;UI button demo: clickable UI element overlay on 3D scene.&quot;&quot;&quot;<br>
<br>
from __future__ import annotations<br>
<br>
import numpy as np<br>
<br>
from termin.geombase.pose3 import Pose3<br>
from termin.mesh.mesh import CubeMesh<br>
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
<br>
from termin.visualization.ui import Canvas, UIRectangle<br>
from termin.visualization.ui.elements import UIButton   # ← наша новая кнопка<br>
from termin.visualization.ui.font import FontTextureAtlas<br>
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
    v_normal = mat3(transpose(inverse(u_model))) * a_normal;<br>
    gl_Position = u_projection * u_view * u_model * vec4(a_position, 1.0);<br>
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
    vec3 N = normalize(v_normal);<br>
    float ndotl = max(dot(N, -normalize(u_light_dir)), 0.0);<br>
    vec3 color = u_color.rgb * (0.2 + 0.8 * ndotl);<br>
    FragColor = vec4(color, u_color.a);<br>
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
    v_uv = a_uv;<br>
    gl_Position = vec4(a_position, 0, 1);<br>
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
    float alpha = u_color.a;<br>
    if (u_use_texture) {<br>
        alpha *= texture(u_texture, v_uv).r;<br>
    }<br>
    FragColor = vec4(u_color.rgb, alpha);<br>
}<br>
&quot;&quot;&quot;<br>
<br>
<br>
# ----- BUILD SCENE ---------------------------------------------------<br>
<br>
def build_scene(world: VisualizationWorld):<br>
    # 3D cube<br>
    shader = ShaderProgram(VERT, FRAG)<br>
    material = Material(shader=shader, color=np.array([0.6, 0.8, 0.9, 1.0], dtype=np.float32))<br>
    cube_mesh = MeshDrawable(CubeMesh(size=1.0))<br>
<br>
    cube = Entity(name=&quot;cube&quot;, pose=Pose3.identity())<br>
    cube.add_component(MeshRenderer(cube_mesh, material))<br>
<br>
    scene = Scene()<br>
    scene.add(cube)<br>
    scene.add(SkyBoxEntity())<br>
    world.add_scene(scene)<br>
<br>
    # Camera + orbit controller<br>
    cam_entity = Entity(name=&quot;camera&quot;)<br>
    cam = PerspectiveCameraComponent()<br>
    cam_entity.add_component(cam)<br>
    cam_entity.add_component(OrbitCameraController(radius=5.0))<br>
    scene.add(cam_entity)<br>
<br>
    # ----- UI CANVAS -----<br>
    canvas = Canvas()<br>
<br>
    # UI materials<br>
    ui_shader = ShaderProgram(UI_VERTEX_SHADER, UI_FRAGMENT_SHADER)<br>
    ui_material_rect = Material(ui_shader, color=np.array([1, 1, 1, 1], dtype=np.float32),<br>
                                uniforms={&quot;u_use_texture&quot;: False})<br>
    ui_material_text = Material(ui_shader, color=np.array([1, 1, 1, 1], dtype=np.float32),<br>
                                uniforms={&quot;u_use_texture&quot;: True})<br>
<br>
    # Font for the button label<br>
    canvas.font = FontTextureAtlas(&quot;examples/data/fonts/Roboto-Regular.ttf&quot;, size=32)<br>
<br>
    # Background rectangle for style (optional)<br>
    canvas.add(UIRectangle(<br>
        position=(0.04, 0.04),<br>
        size=(0.30, 0.12),<br>
        color=(0, 0, 0, 0.4),<br>
        material=ui_material_rect,<br>
    ))<br>
<br>
    # ----- BUTTON -----<br>
    button = UIButton(<br>
        position=(0.05, 0.05),<br>
        size=(0.28, 0.10),<br>
        text=&quot;Click me!&quot;,<br>
        material=ui_material_rect,       # фон<br>
        text_material=ui_material_text,  # ← это новое поле<br>
        on_click=lambda: print(&quot;&gt;&gt;&gt; BUTTON CLICKED!&quot;)<br>
    )<br>
    # Немного другой цвет фона — override в UIButton<br>
    button.background_color = (0.2, 0.4, 0.85, 1.0)<br>
    button.text_color = (1, 1, 1, 1)<br>
<br>
    canvas.add(button)<br>
<br>
    return scene, cam, canvas<br>
<br>
<br>
# ----- MAIN -----------------------------------------------------------<br>
<br>
def main():<br>
    world = VisualizationWorld()<br>
    scene, cam, canvas = build_scene(world)<br>
<br>
    win = world.create_window(title=&quot;termin UI button&quot;)<br>
    win.add_viewport(scene, cam, canvas=canvas)<br>
<br>
    world.run()<br>
<br>
<br>
if __name__ == &quot;__main__&quot;:<br>
    main()<br>
<!-- END SCAT CODE -->
</body>
</html>
