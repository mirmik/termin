<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>examples/visual/geom_demo.py</title>
</head>
<body>
<!-- BEGIN SCAT CODE -->
&quot;&quot;&quot;<br>
Demo: rendering cube wireframe using a geometry shader.<br>
&quot;&quot;&quot;<br>
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
<br>
# =============================<br>
#   Vertex Shader<br>
# =============================<br>
vert = &quot;&quot;&quot;<br>
#version 330 core<br>
<br>
layout(location = 0) in vec3 a_position;<br>
<br>
uniform mat4 u_model;<br>
uniform mat4 u_view;<br>
uniform mat4 u_projection;<br>
<br>
out vec3 v_pos_world;<br>
<br>
void main() {<br>
&#9;vec4 world = u_model * vec4(a_position, 1.0);<br>
&#9;v_pos_world = world.xyz;<br>
<br>
&#9;gl_Position = u_projection * u_view * world;<br>
}<br>
&quot;&quot;&quot;<br>
<br>
<br>
# =============================<br>
#   Geometry Shader (line generation)<br>
# =============================<br>
geom = &quot;&quot;&quot;<br>
#version 330 core<br>
<br>
layout(triangles) in;<br>
layout(line_strip, max_vertices = 6) out;<br>
<br>
in vec3 v_pos_world[];<br>
<br>
out vec3 g_pos_world;<br>
<br>
void main() {<br>
&#9;// три вершины входного треугольника<br>
&#9;for (int i = 0; i &lt; 3; i++) {<br>
&#9;&#9;int j = (i + 1) % 3;<br>
<br>
&#9;&#9;g_pos_world = v_pos_world[i];<br>
&#9;&#9;gl_Position = gl_in[i].gl_Position;<br>
&#9;&#9;EmitVertex();<br>
<br>
&#9;&#9;g_pos_world = v_pos_world[j];<br>
&#9;&#9;gl_Position = gl_in[j].gl_Position;<br>
&#9;&#9;EmitVertex();<br>
<br>
&#9;&#9;EndPrimitive();<br>
&#9;}<br>
}<br>
&quot;&quot;&quot;<br>
<br>
<br>
# =============================<br>
#   Fragment Shader<br>
# =============================<br>
frag = &quot;&quot;&quot;<br>
#version 330 core<br>
<br>
in vec3 g_pos_world;<br>
<br>
uniform vec4 u_color;<br>
<br>
out vec4 FragColor;<br>
<br>
void main() {<br>
&#9;// просто цвет линий<br>
&#9;FragColor = vec4(u_color.rgb, u_color.a);<br>
}<br>
&quot;&quot;&quot;<br>
<br>
<br>
# =============================<br>
#   Scene builder<br>
# =============================<br>
def build_scene(world: VisualizationWorld):<br>
&#9;cube_mesh = CubeMesh()<br>
&#9;drawable = MeshDrawable(cube_mesh)<br>
<br>
&#9;# теперь прокидываем третий аргумент — geometry shader<br>
&#9;shader_prog = ShaderProgram(<br>
&#9;&#9;vertex_source=vert,<br>
&#9;&#9;fragment_source=frag,<br>
&#9;&#9;geometry_source=geom,<br>
&#9;)<br>
<br>
&#9;# красим линии (красный wireframe)<br>
&#9;material = Material(<br>
&#9;&#9;shader=shader_prog,<br>
&#9;&#9;color=np.array([1.0, 0.1, 0.1, 1.0], dtype=np.float32)<br>
&#9;)<br>
<br>
&#9;entity = Entity(pose=Pose3.identity(), name=&quot;wire_cube&quot;)<br>
&#9;entity.add_component(MeshRenderer(drawable, material))<br>
<br>
&#9;scene = Scene()<br>
&#9;scene.add(entity)<br>
<br>
&#9;# оставляем небо для красоты<br>
&#9;skybox = SkyBoxEntity()<br>
&#9;scene.add(skybox)<br>
<br>
&#9;world.add_scene(scene)<br>
<br>
&#9;# камера как в базовом примере<br>
&#9;camera_entity = Entity(name=&quot;camera&quot;)<br>
&#9;camera = PerspectiveCameraComponent()<br>
&#9;camera_entity.add_component(camera)<br>
&#9;camera_entity.add_component(OrbitCameraController())<br>
&#9;scene.add(camera_entity)<br>
<br>
&#9;return scene, camera<br>
<br>
<br>
# =============================<br>
#   Main<br>
# =============================<br>
def main():<br>
&#9;world = VisualizationWorld()<br>
&#9;scene, camera = build_scene(world)<br>
&#9;window = world.create_window(title=&quot;termin geometry-shader wireframe demo&quot;)<br>
&#9;window.add_viewport(scene, camera)<br>
&#9;world.run()<br>
<br>
<br>
if __name__ == &quot;__main__&quot;:<br>
&#9;main()<br>
<!-- END SCAT CODE -->
</body>
</html>
