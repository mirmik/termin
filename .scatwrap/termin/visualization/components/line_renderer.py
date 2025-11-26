<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>termin/visualization/components/line_renderer.py</title>
</head>
<body>
<!-- BEGIN SCAT CODE -->
<br>
from __future__ import annotations<br>
from typing import Iterable<br>
import numpy as np<br>
from ..entity import Component, RenderContext<br>
from ..material import Material<br>
from ..mesh import Mesh2Drawable<br>
from termin.visualization.shader import ShaderProgram<br>
from termin.mesh.mesh import Mesh2<br>
<br>
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
# geom = &quot;&quot;&quot;<br>
# #version 330 core<br>
<br>
# layout(triangles) in;<br>
# layout(line_strip, max_vertices = 6) out;<br>
<br>
# in vec3 v_pos_world[];<br>
<br>
# out vec3 g_pos_world;<br>
<br>
# void main() {<br>
#     // три вершины входного треугольника<br>
#     for (int i = 0; i &lt; 3; i++) {<br>
#         int j = (i + 1) % 3;<br>
<br>
#         g_pos_world = v_pos_world[i];<br>
#         gl_Position = gl_in[i].gl_Position;<br>
#         EmitVertex();<br>
<br>
#         g_pos_world = v_pos_world[j];<br>
#         gl_Position = gl_in[j].gl_Position;<br>
#         EmitVertex();<br>
<br>
#         EndPrimitive();<br>
#     }<br>
# }<br>
# &quot;&quot;&quot;<br>
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
class LineRenderer(Component):<br>
<br>
&#9;def __init__(self, points: Iterable[tuple[float, float, float]], color: tuple[float, float, float, float], width: float = 1.0):<br>
&#9;&#9;super().__init__(enabled=True)<br>
&#9;&#9;self.points = list(points)<br>
&#9;&#9;self.color = color<br>
&#9;&#9;self.width = width<br>
&#9;&#9;self.shader = ShaderProgram(<br>
&#9;&#9;&#9;vertex_source=vert, <br>
&#9;&#9;&#9;#geometry_source=geom, <br>
&#9;&#9;&#9;fragment_source=frag)<br>
&#9;&#9;self.material = Material(shader=self.shader, color=self.color)<br>
&#9;&#9;<br>
&#9;&#9;self.mesh2 = Mesh2.from_lists(self.points, [[i, i + 1] for i in range(0, len(self.points) - 1)])<br>
&#9;&#9;self.drawable = Mesh2Drawable(self.mesh2)<br>
&#9;&#9;<br>
&#9;def required_shaders(self):<br>
&#9;&#9;yield self.shader<br>
<br>
&#9;def draw(self, context: RenderContext):<br>
&#9;&#9;if self.entity is None:<br>
&#9;&#9;&#9;return<br>
<br>
<br>
&#9;&#9;# Рендерим линии<br>
&#9;&#9;model = self.entity.model_matrix()<br>
&#9;&#9;view  = context.view<br>
&#9;&#9;proj  = context.projection<br>
&#9;&#9;gfx   = context.graphics<br>
&#9;&#9;key   = context.context_key<br>
<br>
&#9;&#9;print(&quot;Drawing lines with color:&quot;, self.color, &quot;and width:&quot;, self.width)<br>
<br>
&#9;&#9;self.material.apply(model, view, proj, graphics=gfx, context_key=key)<br>
&#9;&#9;self.drawable.draw(context)<br>
<!-- END SCAT CODE -->
</body>
</html>
