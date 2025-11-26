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
    vec4 world = u_model * vec4(a_position, 1.0);<br>
    v_pos_world = world.xyz;<br>
<br>
    gl_Position = u_projection * u_view * world;<br>
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
    // просто цвет линий<br>
    FragColor = vec4(u_color.rgb, u_color.a);<br>
}<br>
&quot;&quot;&quot;<br>
<br>
<br>
class LineRenderer(Component):<br>
<br>
    def __init__(self, points: Iterable[tuple[float, float, float]], color: tuple[float, float, float, float], width: float = 1.0):<br>
        super().__init__(enabled=True)<br>
        self.points = list(points)<br>
        self.color = color<br>
        self.width = width<br>
        self.shader = ShaderProgram(<br>
            vertex_source=vert, <br>
            #geometry_source=geom, <br>
            fragment_source=frag)<br>
        self.material = Material(shader=self.shader, color=self.color)<br>
        <br>
        self.mesh2 = Mesh2.from_lists(self.points, [[i, i + 1] for i in range(0, len(self.points) - 1)])<br>
        self.drawable = Mesh2Drawable(self.mesh2)<br>
        <br>
    def required_shaders(self):<br>
        yield self.shader<br>
<br>
    def draw(self, context: RenderContext):<br>
        if self.entity is None:<br>
            return<br>
<br>
<br>
        # Рендерим линии<br>
        model = self.entity.model_matrix()<br>
        view  = context.view<br>
        proj  = context.projection<br>
        gfx   = context.graphics<br>
        key   = context.context_key<br>
<br>
        print(&quot;Drawing lines with color:&quot;, self.color, &quot;and width:&quot;, self.width)<br>
<br>
        self.material.apply(model, view, proj, graphics=gfx, context_key=key)<br>
        self.drawable.draw(context)<br>
<!-- END SCAT CODE -->
</body>
</html>
