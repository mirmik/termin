<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>termin/visualization/skybox.py</title>
</head>
<body>
<!-- BEGIN SCAT CODE -->
# skybox.py<br>
<br>
from __future__ import annotations<br>
import numpy as np<br>
<br>
from termin.geombase.pose3 import Pose3<br>
<br>
from termin.mesh.mesh import Mesh3<br>
from .entity import Entity<br>
from .mesh import MeshDrawable<br>
from .material import Material<br>
from .shader import ShaderProgram<br>
from .components import SkyboxRenderer<br>
<br>
<br>
SKYBOX_VERTEX_SHADER = &quot;&quot;&quot;<br>
#version 330 core<br>
layout(location = 0) in vec3 a_position;<br>
<br>
uniform mat4 u_view;<br>
uniform mat4 u_projection;<br>
<br>
out vec3 v_dir;<br>
<br>
void main() {<br>
&#9;// Убираем трансляцию камеры — skybox не должен двигаться<br>
&#9;mat4 view_no_translation = mat4(mat3(u_view));<br>
&#9;v_dir = a_position;<br>
&#9;gl_Position = u_projection * view_no_translation * vec4(a_position, 1.0);<br>
}<br>
&quot;&quot;&quot;<br>
<br>
SKYBOX_FRAGMENT_SHADER = &quot;&quot;&quot;<br>
#version 330 core<br>
<br>
in vec3 v_dir;<br>
out vec4 FragColor;<br>
<br>
void main() {<br>
&#9;// Простой вертикальный градиент неба<br>
&#9;float t = normalize(v_dir).y * 0.5 + 0.5;<br>
&#9;vec3 top = vec3(0.05, 0.1, 0.25);<br>
&#9;vec3 bottom = vec3(0.3, 0.3, 0.35);<br>
&#9;FragColor = vec4(mix(bottom, top, t), 1.0);<br>
}<br>
&quot;&quot;&quot;<br>
<br>
<br>
def _skybox_cube():<br>
&#9;F = 1.0  # большой размер куба<br>
&#9;vertices = np.array([<br>
&#9;&#9;[-F, -F, -F],<br>
&#9;&#9;[ F, -F, -F],<br>
&#9;&#9;[ F,  F, -F],<br>
&#9;&#9;[-F,  F, -F],<br>
&#9;&#9;[-F, -F,  F],<br>
&#9;&#9;[ F, -F,  F],<br>
&#9;&#9;[ F,  F,  F],<br>
&#9;&#9;[-F,  F,  F],<br>
&#9;], dtype=np.float32)<br>
<br>
&#9;triangles = np.array([<br>
&#9;&#9;[0, 1, 2], [0, 2, 3],      # back<br>
&#9;&#9;[4, 6, 5], [4, 7, 6],      # front<br>
&#9;&#9;[0, 4, 5], [0, 5, 1],      # bottom<br>
&#9;&#9;[3, 2, 6], [3, 6, 7],      # top<br>
&#9;&#9;[1, 5, 6], [1, 6, 2],      # right<br>
&#9;&#9;[0, 3, 7], [0, 7, 4],      # left<br>
&#9;], dtype=np.uint32)<br>
<br>
&#9;return vertices, triangles<br>
<br>
<br>
class SkyBoxEntity(Entity):<br>
&#9;&quot;&quot;&quot;<br>
&#9;Небесный куб, который всегда окружает камеру.<br>
&#9;Не использует освещение, цвет и прочее — отдельный шейдер.<br>
&#9;&quot;&quot;&quot;<br>
<br>
&#9;def __init__(self, size: float = 1.0):<br>
&#9;&#9;verts, tris = _skybox_cube()<br>
&#9;&#9;mesh = MeshDrawable(Mesh3(vertices=verts, triangles=tris))<br>
<br>
&#9;&#9;shader = ShaderProgram(<br>
&#9;&#9;&#9;vertex_source=SKYBOX_VERTEX_SHADER,<br>
&#9;&#9;&#9;fragment_source=SKYBOX_FRAGMENT_SHADER<br>
&#9;&#9;)<br>
&#9;&#9;material = Material(shader=shader)<br>
&#9;&#9;material.color = None  # skybox не использует u_color<br>
<br>
&#9;&#9;super().__init__(<br>
&#9;&#9;&#9;pose=Pose3.identity(),<br>
&#9;&#9;&#9;scale=size,<br>
&#9;&#9;&#9;name=&quot;skybox&quot;,<br>
&#9;&#9;&#9;priority=-100,  # рисуем в самом начале<br>
&#9;&#9;&#9;pickable=False,<br>
&#9;&#9;&#9;selectable=False,<br>
&#9;&#9;)<br>
&#9;&#9;self.renderer = self.add_component(SkyboxRenderer(mesh, material))<br>
<!-- END SCAT CODE -->
</body>
</html>
