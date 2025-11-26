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
    Entity,<br>
    MeshDrawable,<br>
    Scene,<br>
    Material,<br>
    VisualizationWorld,<br>
    PerspectiveCameraComponent,<br>
    OrbitCameraController,<br>
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
    vec4 world = u_model * vec4(a_position, 1.0);<br>
    v_world_pos = world.xyz;<br>
<br>
    // нормальная матрица = mat3(transpose(inverse(u_model)))<br>
    v_normal = mat3(transpose(inverse(u_model))) * a_normal;<br>
<br>
    gl_Position = u_projection * u_view * world;<br>
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
    // Нормаль<br>
    vec3 N = normalize(v_normal);<br>
<br>
    // Направление на свет: если u_light_dir - направление *от* света, то на объект оно то же<br>
    vec3 L = normalize(-u_light_dir); // если задаёшь уже &quot;к объекту&quot;, убери минус<br>
<br>
    // Направление на камеру<br>
    vec3 V = normalize(u_view_pos - v_world_pos);<br>
<br>
    // Полуунитектор (half-vector) для Blinn–Phong<br>
    vec3 H = normalize(L + V);<br>
<br>
    // --- коэффициенты освещения ---<br>
    const float ambientStrength  = 0.2;  // эмбиент<br>
    const float diffuseStrength  = 0.8;  // диффуз<br>
    const float specularStrength = 0.4;  // спекуляр<br>
    const float shininess        = 32.0; // степень блеска<br>
<br>
    // Эмбиент<br>
    vec3 ambient = ambientStrength * u_color.rgb;<br>
<br>
    // Диффуз (Ламберт)<br>
    float ndotl = max(dot(N, L), 0.0);<br>
    vec3 diffuse = diffuseStrength * ndotl * u_color.rgb;<br>
<br>
    // Спекуляр (Blinn–Phong)<br>
    float specFactor = 0.0;<br>
    if (ndotl &gt; 0.0) {<br>
        specFactor = pow(max(dot(N, H), 0.0), shininess);<br>
    }<br>
    vec3 specular = specularStrength * specFactor * u_light_color;<br>
<br>
    // Итоговый цвет: модифицируем цвет материала цветом света<br>
    vec3 color = (ambient + diffuse) * u_light_color + specular;<br>
<br>
    // Можно слегка ограничить, чтобы не улетало в дикий перегиб<br>
    color = clamp(color, 0.0, 1.0);<br>
<br>
    FragColor = vec4(color, u_color.a);<br>
}<br>
&quot;&quot;&quot;<br>
<br>
def build_scene(world: VisualizationWorld, mesh: &quot;Mesh&quot;) -&gt; tuple[Scene, PerspectiveCameraComponent]:<br>
<br>
    scene = Scene()<br>
    <br>
    drawable = MeshDrawable(mesh)<br>
    shader_prog = ShaderProgram(vert, frag)<br>
    material = Material(shader=shader_prog, color=np.array([0.8, 0.3, 0.3, 1.0], dtype=np.float32))<br>
    entity = Entity(pose=Pose3.identity(), name=&quot;cube&quot;)<br>
    entity.add_component(MeshRenderer(drawable, material))<br>
    <br>
    scene.add(entity)<br>
<br>
    skybox = SkyBoxEntity()<br>
    scene.add(skybox)<br>
    world.add_scene(scene)<br>
<br>
    T = 10000.0<br>
    coord_lines = Entity(name=&quot;coord_lines&quot;)<br>
    coord_lines.add_component(LineRenderer(points=[(0,0,-T), (0,0,T)], color=(1,0,0,1), width=2.0))  # Z - красная<br>
    coord_lines.add_component(LineRenderer(points=[(0,-T,0), (0,T,0)], color=(0,1,0,1), width=2.0))  # Y - зелёная<br>
    coord_lines.add_component(LineRenderer(points=[(-T,0,0), (T,0,0)], color=(0,0,1,1), width=2.0))  # X - синяя<br>
    scene.add(coord_lines)<br>
<br>
    camera_entity = Entity(name=&quot;camera&quot;)<br>
    camera = PerspectiveCameraComponent()<br>
    camera_entity.add_component(camera)<br>
    camera_entity.add_component(OrbitCameraController())<br>
    scene.add(camera_entity)<br>
<br>
    return scene, camera<br>
<br>
<br>
def show_mesh_app(mesh: &quot;Mesh&quot;):<br>
    world = VisualizationWorld()<br>
    scene, camera = build_scene(world, mesh)<br>
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
