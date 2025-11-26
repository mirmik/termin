<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>examples/visual/ui_overlay.py</title>
</head>
<body>
<!-- BEGIN SCAT CODE -->
&quot;&quot;&quot;Demonstrate 3D scene with a UI canvas overlay.&quot;&quot;&quot;<br>
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
from termin.visualization.ui import Canvas, UIRectangle<br>
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
    v_normal = mat3(transpose(inverse(u_model))) * a_normal;<br>
    gl_Position = u_projection * u_view * u_model * vec4(a_position, 1.0);<br>
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
    vec3 N = normalize(v_normal);<br>
    float ndotl = max(dot(N, -normalize(u_light_dir)), 0.0);<br>
    vec3 color = u_color.rgb * (0.2 + 0.8 * ndotl);<br>
    FragColor = vec4(color, u_color.a);<br>
}<br>
&quot;&quot;&quot;<br>
<br>
&quot;&quot;&quot;Standard UI shader sources (position + optional texturing).&quot;&quot;&quot;<br>
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
        // При включённой текстуре берём альфа-канал из красного канала атласа<br>
        alpha *= texture(u_texture, v_uv).r;<br>
    }<br>
    FragColor = vec4(u_color.rgb, alpha);<br>
}<br>
&quot;&quot;&quot;<br>
<br>
<br>
<br>
def build_scene(world: VisualizationWorld) -&gt; tuple[Scene, PerspectiveCameraComponent, Canvas]:<br>
    shader = ShaderProgram(VERT, FRAG)<br>
    material = Material(shader=shader, color=np.array([0.6, 0.8, 0.9, 1.0], dtype=np.float32))<br>
    mesh = MeshDrawable(CubeMesh(size=1.5))<br>
    cube = Entity(name=&quot;cube&quot;, pose=Pose3.identity())<br>
    cube.add_component(MeshRenderer(mesh, material))<br>
<br>
    scene = Scene()<br>
    scene.add(cube)<br>
    scene.add(SkyBoxEntity())<br>
    world.add_scene(scene)<br>
<br>
    cam_entity = Entity(name=&quot;camera&quot;)<br>
    camera = PerspectiveCameraComponent()<br>
    cam_entity.add_component(camera)<br>
    cam_entity.add_component(OrbitCameraController(radius=5.0))<br>
    scene.add(cam_entity)<br>
<br>
    canvas = Canvas()<br>
    ui_shader = ShaderProgram(UI_VERTEX_SHADER, UI_FRAGMENT_SHADER)<br>
    ui_material = Material(shader=ui_shader, color=np.array([1.0, 1.0, 1.0, 1.0], dtype=np.float32), uniforms={&quot;u_use_texture&quot;: False})<br>
    canvas.add(UIRectangle(position=(0.05, 0.05), size=(0.25, 0.1), color=(0.1, 0.1, 0.1, 0.7), material=ui_material))<br>
    canvas.add(UIRectangle(position=(0.07, 0.07), size=(0.21, 0.06), color=(0.9, 0.4, 0.2, 1.0), material=ui_material))<br>
<br>
    return scene, camera, canvas<br>
<br>
<br>
def main():<br>
    world = VisualizationWorld()<br>
    scene, camera, canvas = build_scene(world)<br>
    window = world.create_window(title=&quot;termin UI overlay&quot;)<br>
    window.add_viewport(scene, camera, canvas=canvas)<br>
    world.run()<br>
<br>
<br>
if __name__ == &quot;__main__&quot;:<br>
    main()<br>
<!-- END SCAT CODE -->
</body>
</html>
