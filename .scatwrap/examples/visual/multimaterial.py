<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>examples/visual/multimaterial.py</title>
</head>
<body>
<!-- BEGIN SCAT CODE -->
&quot;&quot;&quot;<br>
demo_wire_cube.py<br>
<br>
Куб, рисуемый в два прохода:<br>
1) обычный solid-шейдер<br>
2) поверх него — wireframe через геометрический шейдер<br>
<br>
Толщина линий передаётся в шейдер как uniform u_line_width.<br>
(Чтобы она реально влияла на визуал, нужно дописать более хитрый GS;<br>
сейчас это просто пример того, как параметр уходит в материал/шейдер.)<br>
&quot;&quot;&quot;<br>
<br>
from __future__ import annotations<br>
<br>
import numpy as np<br>
<br>
from termin.geombase.pose3 import Pose3<br>
from termin.mesh.mesh import CubeMesh<br>
<br>
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
from termin.visualization.renderpass import RenderPass, RenderState<br>
<br>
<br>
# ----------------------------------------------------------------------<br>
# SOLID SHADER (почти твой исходный)<br>
# ----------------------------------------------------------------------<br>
<br>
SOLID_VERT = &quot;&quot;&quot;<br>
#version 330 core<br>
<br>
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
    vec4 world = u_model * vec4(a_position, 1.0);<br>
    v_world_pos = world.xyz;<br>
<br>
    v_normal = mat3(transpose(inverse(u_model))) * a_normal;<br>
<br>
    gl_Position = u_projection * u_view * world;<br>
}<br>
&quot;&quot;&quot;<br>
<br>
SOLID_FRAG = &quot;&quot;&quot;<br>
#version 330 core<br>
<br>
in vec3 v_normal;<br>
in vec3 v_world_pos;<br>
<br>
uniform vec4 u_color;<br>
uniform vec3 u_light_dir;<br>
uniform vec3 u_light_color;<br>
uniform vec3 u_view_pos;<br>
<br>
out vec4 FragColor;<br>
<br>
void main() {<br>
    vec3 N = normalize(v_normal);<br>
    vec3 L = normalize(-u_light_dir);<br>
    vec3 V = normalize(u_view_pos - v_world_pos);<br>
    vec3 H = normalize(L + V);<br>
<br>
    const float ambientStrength  = 0.2;<br>
    const float diffuseStrength  = 0.8;<br>
    const float specularStrength = 0.4;<br>
    const float shininess        = 32.0;<br>
<br>
    vec3 ambient = ambientStrength * u_color.rgb;<br>
<br>
    float ndotl = max(dot(N, L), 0.0);<br>
    vec3 diffuse = diffuseStrength * ndotl * u_color.rgb;<br>
<br>
    float specFactor = 0.0;<br>
    if (ndotl &gt; 0.0) {<br>
        specFactor = pow(max(dot(N, H), 0.0), shininess);<br>
    }<br>
    vec3 specular = specularStrength * specFactor * u_light_color;<br>
<br>
    vec3 color = (ambient + diffuse) * u_light_color + specular;<br>
    color = clamp(color, 0.0, 1.0);<br>
<br>
    FragColor = vec4(color, u_color.a);<br>
}<br>
&quot;&quot;&quot;<br>
<br>
<br>
# ----------------------------------------------------------------------<br>
# WIREFRAME SHADERS<br>
# ----------------------------------------------------------------------<br>
<br>
# Вершинник — просто выдаём позицию в clip-space.<br>
WIRE_VERT = &quot;&quot;&quot;<br>
#version 330 core<br>
layout(location = 0) in vec3 a_position;<br>
<br>
uniform mat4 u_model;<br>
uniform mat4 u_view;<br>
uniform mat4 u_projection;<br>
<br>
void main() {<br>
    gl_Position = u_projection * u_view * u_model * vec4(a_position, 1.0);<br>
}<br>
&quot;&quot;&quot;<br>
<br>
# Геометрический шейдер: разворачивает треугольники в 3 линии.<br>
# u_line_width сейчас просто существует как uniform (пример передачи параметра).<br>
# Для реальной &quot;толстой&quot; линии нужен более сложный экранно-пространственный алгоритм.<br>
WIRE_GEOM = &quot;&quot;&quot;<br>
#version 330 core<br>
<br>
layout(triangles) in;<br>
layout(triangle_strip, max_vertices = 12) out;<br>
<br>
// Толщина в NDC (0..1 примерно как половина экрана).<br>
uniform float u_line_width;<br>
uniform mat4 u_projection; // если понадобится что-то хитрее, можно использовать<br>
<br>
// Генерация &quot;толстой&quot; полоски вокруг отрезка p0-p1 в экранном пространстве<br>
void emit_thick_segment(vec4 p0, vec4 p1)<br>
{<br>
    // Вершины в NDC<br>
    vec2 ndc0 = p0.xy / p0.w;<br>
    vec2 ndc1 = p1.xy / p1.w;<br>
<br>
    vec2 dir = ndc1 - ndc0;<br>
    float len2 = dot(dir, dir);<br>
    if (len2 &lt;= 1e-8)<br>
        return;<br>
<br>
    dir = normalize(dir);<br>
    vec2 n = vec2(-dir.y, dir.x);      // перпендикуляр<br>
    vec2 off = n * (u_line_width * 0.5);<br>
<br>
    vec2 ndc0a = ndc0 + off;<br>
    vec2 ndc0b = ndc0 - off;<br>
    vec2 ndc1a = ndc1 + off;<br>
    vec2 ndc1b = ndc1 - off;<br>
<br>
    // Обратно в clip-space<br>
    vec4 p0a = vec4(ndc0a * p0.w, p0.zw);<br>
    vec4 p0b = vec4(ndc0b * p0.w, p0.zw);<br>
    vec4 p1a = vec4(ndc1a * p1.w, p1.zw);<br>
    vec4 p1b = vec4(ndc1b * p1.w, p1.zw);<br>
<br>
    // Квад из двух треугольников (triangle_strip)<br>
    gl_Position = p0a; EmitVertex();<br>
    gl_Position = p0b; EmitVertex();<br>
    gl_Position = p1a; EmitVertex();<br>
    gl_Position = p1b; EmitVertex();<br>
    EndPrimitive();<br>
}<br>
<br>
void main()<br>
{<br>
    vec4 p0 = gl_in[0].gl_Position;<br>
    vec4 p1 = gl_in[1].gl_Position;<br>
    vec4 p2 = gl_in[2].gl_Position;<br>
<br>
    // три рёбра треугольника<br>
    emit_thick_segment(p0, p1);<br>
    emit_thick_segment(p1, p2);<br>
    emit_thick_segment(p2, p0);<br>
}<br>
<br>
&quot;&quot;&quot;<br>
<br>
WIRE_FRAG = &quot;&quot;&quot;<br>
#version 330 core<br>
<br>
uniform vec4 u_color;<br>
<br>
out vec4 FragColor;<br>
<br>
void main() {<br>
    FragColor = u_color;<br>
}<br>
&quot;&quot;&quot;<br>
<br>
<br>
# ----------------------------------------------------------------------<br>
# SCENE BUILDING<br>
# ----------------------------------------------------------------------<br>
<br>
def build_scene(world: VisualizationWorld):<br>
    # Меш куба<br>
    cube_mesh = CubeMesh()<br>
    drawable = MeshDrawable(cube_mesh)<br>
<br>
    # --- Solid материал ---<br>
    solid_shader = ShaderProgram(SOLID_VERT, SOLID_FRAG)<br>
    solid_material = Material(<br>
        shader=solid_shader,<br>
        color=np.array([0.8, 0.3, 0.3, 1.0], dtype=np.float32),<br>
    )<br>
<br>
    solid_pass = RenderPass(<br>
        material=solid_material,<br>
        state=RenderState(<br>
            polygon_mode=&quot;fill&quot;,<br>
            cull=True,<br>
            depth_test=True,<br>
            depth_write=True,<br>
            blend=False,<br>
        ),<br>
    )<br>
<br>
    # --- Wireframe материал ---<br>
    wire_shader = ShaderProgram(<br>
        vertex_source=WIRE_VERT,<br>
        fragment_source=WIRE_FRAG,<br>
        geometry_source=WIRE_GEOM,<br>
    )<br>
<br>
    wire_material = Material(<br>
        shader=wire_shader,<br>
        color=np.array([0.05, 0.05, 0.05, 1.0], dtype=np.float32),<br>
        uniforms={<br>
            # вот сюда можно подсунуть толщину, шейдер её получит:<br>
            &quot;u_line_width&quot;: 0.01,<br>
        },<br>
    )<br>
<br>
    wire_pass = RenderPass(<br>
    material=wire_material,<br>
        state=RenderState(<br>
            polygon_mode=&quot;fill&quot;,   # &lt;-- ВАЖНО: теперь fill, не line<br>
            cull=False,<br>
            depth_test=True,<br>
            depth_write=False,<br>
            blend=False,<br>
        ),<br>
    )<br>
<br>
    # --- Entity с MeshRenderer, использующим два прохода ---<br>
    entity = Entity(pose=Pose3.identity(), name=&quot;wire_cube&quot;)<br>
    entity.add_component(<br>
        MeshRenderer(<br>
            mesh=drawable,<br>
            material=solid_material,          # основной материал (для обратной совместимости)<br>
            passes=[solid_pass, wire_pass],   # мультипасс<br>
        )<br>
    )<br>
<br>
    # --- Scene + skybox + камера ---<br>
    scene = Scene()<br>
    scene.add(entity)<br>
<br>
    skybox = SkyBoxEntity()<br>
    scene.add(skybox)<br>
<br>
    world.add_scene(scene)<br>
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
def main():<br>
    world = VisualizationWorld()<br>
    scene, camera = build_scene(world)<br>
<br>
    window = world.create_window(title=&quot;termin wireframe demo&quot;)<br>
    window.add_viewport(scene, camera)<br>
<br>
    world.run()<br>
<br>
<br>
if __name__ == &quot;__main__&quot;:<br>
    main()<br>
<!-- END SCAT CODE -->
</body>
</html>
