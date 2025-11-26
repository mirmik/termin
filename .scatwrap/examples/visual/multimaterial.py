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
&#9;vec4 world = u_model * vec4(a_position, 1.0);<br>
&#9;v_world_pos = world.xyz;<br>
<br>
&#9;v_normal = mat3(transpose(inverse(u_model))) * a_normal;<br>
<br>
&#9;gl_Position = u_projection * u_view * world;<br>
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
&#9;vec3 N = normalize(v_normal);<br>
&#9;vec3 L = normalize(-u_light_dir);<br>
&#9;vec3 V = normalize(u_view_pos - v_world_pos);<br>
&#9;vec3 H = normalize(L + V);<br>
<br>
&#9;const float ambientStrength  = 0.2;<br>
&#9;const float diffuseStrength  = 0.8;<br>
&#9;const float specularStrength = 0.4;<br>
&#9;const float shininess        = 32.0;<br>
<br>
&#9;vec3 ambient = ambientStrength * u_color.rgb;<br>
<br>
&#9;float ndotl = max(dot(N, L), 0.0);<br>
&#9;vec3 diffuse = diffuseStrength * ndotl * u_color.rgb;<br>
<br>
&#9;float specFactor = 0.0;<br>
&#9;if (ndotl &gt; 0.0) {<br>
&#9;&#9;specFactor = pow(max(dot(N, H), 0.0), shininess);<br>
&#9;}<br>
&#9;vec3 specular = specularStrength * specFactor * u_light_color;<br>
<br>
&#9;vec3 color = (ambient + diffuse) * u_light_color + specular;<br>
&#9;color = clamp(color, 0.0, 1.0);<br>
<br>
&#9;FragColor = vec4(color, u_color.a);<br>
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
&#9;gl_Position = u_projection * u_view * u_model * vec4(a_position, 1.0);<br>
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
&#9;// Вершины в NDC<br>
&#9;vec2 ndc0 = p0.xy / p0.w;<br>
&#9;vec2 ndc1 = p1.xy / p1.w;<br>
<br>
&#9;vec2 dir = ndc1 - ndc0;<br>
&#9;float len2 = dot(dir, dir);<br>
&#9;if (len2 &lt;= 1e-8)<br>
&#9;&#9;return;<br>
<br>
&#9;dir = normalize(dir);<br>
&#9;vec2 n = vec2(-dir.y, dir.x);      // перпендикуляр<br>
&#9;vec2 off = n * (u_line_width * 0.5);<br>
<br>
&#9;vec2 ndc0a = ndc0 + off;<br>
&#9;vec2 ndc0b = ndc0 - off;<br>
&#9;vec2 ndc1a = ndc1 + off;<br>
&#9;vec2 ndc1b = ndc1 - off;<br>
<br>
&#9;// Обратно в clip-space<br>
&#9;vec4 p0a = vec4(ndc0a * p0.w, p0.zw);<br>
&#9;vec4 p0b = vec4(ndc0b * p0.w, p0.zw);<br>
&#9;vec4 p1a = vec4(ndc1a * p1.w, p1.zw);<br>
&#9;vec4 p1b = vec4(ndc1b * p1.w, p1.zw);<br>
<br>
&#9;// Квад из двух треугольников (triangle_strip)<br>
&#9;gl_Position = p0a; EmitVertex();<br>
&#9;gl_Position = p0b; EmitVertex();<br>
&#9;gl_Position = p1a; EmitVertex();<br>
&#9;gl_Position = p1b; EmitVertex();<br>
&#9;EndPrimitive();<br>
}<br>
<br>
void main()<br>
{<br>
&#9;vec4 p0 = gl_in[0].gl_Position;<br>
&#9;vec4 p1 = gl_in[1].gl_Position;<br>
&#9;vec4 p2 = gl_in[2].gl_Position;<br>
<br>
&#9;// три рёбра треугольника<br>
&#9;emit_thick_segment(p0, p1);<br>
&#9;emit_thick_segment(p1, p2);<br>
&#9;emit_thick_segment(p2, p0);<br>
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
&#9;FragColor = u_color;<br>
}<br>
&quot;&quot;&quot;<br>
<br>
<br>
# ----------------------------------------------------------------------<br>
# SCENE BUILDING<br>
# ----------------------------------------------------------------------<br>
<br>
def build_scene(world: VisualizationWorld):<br>
&#9;# Меш куба<br>
&#9;cube_mesh = CubeMesh()<br>
&#9;drawable = MeshDrawable(cube_mesh)<br>
<br>
&#9;# --- Solid материал ---<br>
&#9;solid_shader = ShaderProgram(SOLID_VERT, SOLID_FRAG)<br>
&#9;solid_material = Material(<br>
&#9;&#9;shader=solid_shader,<br>
&#9;&#9;color=np.array([0.8, 0.3, 0.3, 1.0], dtype=np.float32),<br>
&#9;)<br>
<br>
&#9;solid_pass = RenderPass(<br>
&#9;&#9;material=solid_material,<br>
&#9;&#9;state=RenderState(<br>
&#9;&#9;&#9;polygon_mode=&quot;fill&quot;,<br>
&#9;&#9;&#9;cull=True,<br>
&#9;&#9;&#9;depth_test=True,<br>
&#9;&#9;&#9;depth_write=True,<br>
&#9;&#9;&#9;blend=False,<br>
&#9;&#9;),<br>
&#9;)<br>
<br>
&#9;# --- Wireframe материал ---<br>
&#9;wire_shader = ShaderProgram(<br>
&#9;&#9;vertex_source=WIRE_VERT,<br>
&#9;&#9;fragment_source=WIRE_FRAG,<br>
&#9;&#9;geometry_source=WIRE_GEOM,<br>
&#9;)<br>
<br>
&#9;wire_material = Material(<br>
&#9;&#9;shader=wire_shader,<br>
&#9;&#9;color=np.array([0.05, 0.05, 0.05, 1.0], dtype=np.float32),<br>
&#9;&#9;uniforms={<br>
&#9;&#9;&#9;# вот сюда можно подсунуть толщину, шейдер её получит:<br>
&#9;&#9;&#9;&quot;u_line_width&quot;: 0.01,<br>
&#9;&#9;},<br>
&#9;)<br>
<br>
&#9;wire_pass = RenderPass(<br>
&#9;material=wire_material,<br>
&#9;&#9;state=RenderState(<br>
&#9;&#9;&#9;polygon_mode=&quot;fill&quot;,   # &lt;-- ВАЖНО: теперь fill, не line<br>
&#9;&#9;&#9;cull=False,<br>
&#9;&#9;&#9;depth_test=True,<br>
&#9;&#9;&#9;depth_write=False,<br>
&#9;&#9;&#9;blend=False,<br>
&#9;&#9;),<br>
&#9;)<br>
<br>
&#9;# --- Entity с MeshRenderer, использующим два прохода ---<br>
&#9;entity = Entity(pose=Pose3.identity(), name=&quot;wire_cube&quot;)<br>
&#9;entity.add_component(<br>
&#9;&#9;MeshRenderer(<br>
&#9;&#9;&#9;mesh=drawable,<br>
&#9;&#9;&#9;material=solid_material,          # основной материал (для обратной совместимости)<br>
&#9;&#9;&#9;passes=[solid_pass, wire_pass],   # мультипасс<br>
&#9;&#9;)<br>
&#9;)<br>
<br>
&#9;# --- Scene + skybox + камера ---<br>
&#9;scene = Scene()<br>
&#9;scene.add(entity)<br>
<br>
&#9;skybox = SkyBoxEntity()<br>
&#9;scene.add(skybox)<br>
<br>
&#9;world.add_scene(scene)<br>
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
def main():<br>
&#9;world = VisualizationWorld()<br>
&#9;scene, camera = build_scene(world)<br>
<br>
&#9;window = world.create_window(title=&quot;termin wireframe demo&quot;)<br>
&#9;window.add_viewport(scene, camera)<br>
<br>
&#9;world.run()<br>
<br>
<br>
if __name__ == &quot;__main__&quot;:<br>
&#9;main()<br>
<!-- END SCAT CODE -->
</body>
</html>
