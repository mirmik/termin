<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>termin/mesh/mesh_viewer_miniapp.py</title>
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
from termin.visualization import (<br>
&#9;Entity,<br>
&#9;MeshDrawable,<br>
&#9;Scene,<br>
&#9;Material,<br>
&#9;VisualizationWorld,<br>
&#9;PerspectiveCameraComponent,<br>
&#9;OrbitCameraController,<br>
)<br>
from termin.visualization.components import MeshRenderer, LineRenderer  <br>
from termin.visualization.shader import ShaderProgram<br>
from termin.visualization.skybox import SkyBoxEntity<br>
<br>
vert = &quot;&quot;&quot;<br>
#version 330 core<br>
<br>
layout(location = 0) in vec3 a_position;<br>
layout(location = 1) in vec3 a_normal;<br>
<br>
uniform mat4 u_model;<br>
uniform mat4 u_view;<br>
uniform mat4 u_projection;<br>
<br>
out vec3 v_normal;     // нормаль в мировом пространстве<br>
out vec3 v_world_pos;  // позиция в мировом пространстве<br>
<br>
void main() {<br>
&#9;vec4 world = u_model * vec4(a_position, 1.0);<br>
&#9;v_world_pos = world.xyz;<br>
<br>
&#9;// нормальная матрица = mat3(transpose(inverse(u_model)))<br>
&#9;v_normal = mat3(transpose(inverse(u_model))) * a_normal;<br>
<br>
&#9;gl_Position = u_projection * u_view * world;<br>
}<br>
&quot;&quot;&quot;<br>
<br>
<br>
frag = &quot;&quot;&quot;<br>
#version 330 core<br>
<br>
in vec3 v_normal;<br>
in vec3 v_world_pos;<br>
<br>
uniform vec4 u_color;        // базовый цвет материала (RGBA)<br>
uniform vec3 u_light_dir;    // направление от источника к объекту (world space)<br>
uniform vec3 u_light_color;  // цвет света<br>
uniform vec3 u_view_pos;     // позиция камеры (world space)<br>
<br>
out vec4 FragColor;<br>
<br>
void main() {<br>
&#9;// Нормаль<br>
&#9;vec3 N = normalize(v_normal);<br>
<br>
&#9;// Направление на свет: если u_light_dir - направление *от* света, то на объект оно то же<br>
&#9;vec3 L = normalize(-u_light_dir); // если задаёшь уже &quot;к объекту&quot;, убери минус<br>
<br>
&#9;// Направление на камеру<br>
&#9;vec3 V = normalize(u_view_pos - v_world_pos);<br>
<br>
&#9;// Полуунитектор (half-vector) для Blinn–Phong<br>
&#9;vec3 H = normalize(L + V);<br>
<br>
&#9;// --- коэффициенты освещения ---<br>
&#9;const float ambientStrength  = 0.2;  // эмбиент<br>
&#9;const float diffuseStrength  = 0.8;  // диффуз<br>
&#9;const float specularStrength = 0.4;  // спекуляр<br>
&#9;const float shininess        = 32.0; // степень блеска<br>
<br>
&#9;// Эмбиент<br>
&#9;vec3 ambient = ambientStrength * u_color.rgb;<br>
<br>
&#9;// Диффуз (Ламберт)<br>
&#9;float ndotl = max(dot(N, L), 0.0);<br>
&#9;vec3 diffuse = diffuseStrength * ndotl * u_color.rgb;<br>
<br>
&#9;// Спекуляр (Blinn–Phong)<br>
&#9;float specFactor = 0.0;<br>
&#9;if (ndotl &gt; 0.0) {<br>
&#9;&#9;specFactor = pow(max(dot(N, H), 0.0), shininess);<br>
&#9;}<br>
&#9;vec3 specular = specularStrength * specFactor * u_light_color;<br>
<br>
&#9;// Итоговый цвет: модифицируем цвет материала цветом света<br>
&#9;vec3 color = (ambient + diffuse) * u_light_color + specular;<br>
<br>
&#9;// Можно слегка ограничить, чтобы не улетало в дикий перегиб<br>
&#9;color = clamp(color, 0.0, 1.0);<br>
<br>
&#9;FragColor = vec4(color, u_color.a);<br>
}<br>
&quot;&quot;&quot;<br>
<br>
def build_scene(world: VisualizationWorld, mesh: &quot;Mesh&quot;) -&gt; tuple[Scene, PerspectiveCameraComponent]:<br>
<br>
&#9;scene = Scene()<br>
&#9;<br>
&#9;drawable = MeshDrawable(mesh)<br>
&#9;shader_prog = ShaderProgram(vert, frag)<br>
&#9;material = Material(shader=shader_prog, color=np.array([0.8, 0.3, 0.3, 1.0], dtype=np.float32))<br>
&#9;entity = Entity(pose=Pose3.identity(), name=&quot;cube&quot;)<br>
&#9;entity.add_component(MeshRenderer(drawable, material))<br>
&#9;<br>
&#9;scene.add(entity)<br>
<br>
&#9;skybox = SkyBoxEntity()<br>
&#9;scene.add(skybox)<br>
&#9;world.add_scene(scene)<br>
<br>
&#9;T = 10000.0<br>
&#9;coord_lines = Entity(name=&quot;coord_lines&quot;)<br>
&#9;coord_lines.add_component(LineRenderer(points=[(0,0,-T), (0,0,T)], color=(1,0,0,1), width=2.0))  # Z - красная<br>
&#9;coord_lines.add_component(LineRenderer(points=[(0,-T,0), (0,T,0)], color=(0,1,0,1), width=2.0))  # Y - зелёная<br>
&#9;coord_lines.add_component(LineRenderer(points=[(-T,0,0), (T,0,0)], color=(0,0,1,1), width=2.0))  # X - синяя<br>
&#9;scene.add(coord_lines)<br>
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
def show_mesh_app(mesh: &quot;Mesh&quot;):<br>
&#9;world = VisualizationWorld()<br>
&#9;scene, camera = build_scene(world, mesh)<br>
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
