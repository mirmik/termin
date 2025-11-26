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
    // Убираем трансляцию камеры — skybox не должен двигаться<br>
    mat4 view_no_translation = mat4(mat3(u_view));<br>
    v_dir = a_position;<br>
    gl_Position = u_projection * view_no_translation * vec4(a_position, 1.0);<br>
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
    // Простой вертикальный градиент неба<br>
    float t = normalize(v_dir).y * 0.5 + 0.5;<br>
    vec3 top = vec3(0.05, 0.1, 0.25);<br>
    vec3 bottom = vec3(0.3, 0.3, 0.35);<br>
    FragColor = vec4(mix(bottom, top, t), 1.0);<br>
}<br>
&quot;&quot;&quot;<br>
<br>
<br>
def _skybox_cube():<br>
    F = 1.0  # большой размер куба<br>
    vertices = np.array([<br>
        [-F, -F, -F],<br>
        [ F, -F, -F],<br>
        [ F,  F, -F],<br>
        [-F,  F, -F],<br>
        [-F, -F,  F],<br>
        [ F, -F,  F],<br>
        [ F,  F,  F],<br>
        [-F,  F,  F],<br>
    ], dtype=np.float32)<br>
<br>
    triangles = np.array([<br>
        [0, 1, 2], [0, 2, 3],      # back<br>
        [4, 6, 5], [4, 7, 6],      # front<br>
        [0, 4, 5], [0, 5, 1],      # bottom<br>
        [3, 2, 6], [3, 6, 7],      # top<br>
        [1, 5, 6], [1, 6, 2],      # right<br>
        [0, 3, 7], [0, 7, 4],      # left<br>
    ], dtype=np.uint32)<br>
<br>
    return vertices, triangles<br>
<br>
<br>
class SkyBoxEntity(Entity):<br>
    &quot;&quot;&quot;<br>
    Небесный куб, который всегда окружает камеру.<br>
    Не использует освещение, цвет и прочее — отдельный шейдер.<br>
    &quot;&quot;&quot;<br>
<br>
    def __init__(self, size: float = 1.0):<br>
        verts, tris = _skybox_cube()<br>
        mesh = MeshDrawable(Mesh3(vertices=verts, triangles=tris))<br>
<br>
        shader = ShaderProgram(<br>
            vertex_source=SKYBOX_VERTEX_SHADER,<br>
            fragment_source=SKYBOX_FRAGMENT_SHADER<br>
        )<br>
        material = Material(shader=shader)<br>
        material.color = None  # skybox не использует u_color<br>
<br>
        super().__init__(<br>
            pose=Pose3.identity(),<br>
            scale=size,<br>
            name=&quot;skybox&quot;,<br>
            priority=-100,  # рисуем в самом начале<br>
            pickable=False,<br>
            selectable=False,<br>
        )<br>
        self.renderer = self.add_component(SkyboxRenderer(mesh, material))<br>
<!-- END SCAT CODE -->
</body>
</html>
