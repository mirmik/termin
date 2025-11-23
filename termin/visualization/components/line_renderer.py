
from __future__ import annotations
from typing import Iterable
import numpy as np
from ..entity import Component, RenderContext
from ..material import Material
from ..mesh import Mesh2Drawable
from termin.visualization.shader import ShaderProgram
from termin.mesh.mesh import Mesh2



# =============================
#   Vertex Shader
# =============================
vert = """
#version 330 core

layout(location = 0) in vec3 a_position;

uniform mat4 u_model;
uniform mat4 u_view;
uniform mat4 u_projection;

out vec3 v_pos_world;

void main() {
    vec4 world = u_model * vec4(a_position, 1.0);
    v_pos_world = world.xyz;

    gl_Position = u_projection * u_view * world;
}
"""


# =============================
#   Geometry Shader (line generation)
# =============================
# geom = """
# #version 330 core

# layout(triangles) in;
# layout(line_strip, max_vertices = 6) out;

# in vec3 v_pos_world[];

# out vec3 g_pos_world;

# void main() {
#     // три вершины входного треугольника
#     for (int i = 0; i < 3; i++) {
#         int j = (i + 1) % 3;

#         g_pos_world = v_pos_world[i];
#         gl_Position = gl_in[i].gl_Position;
#         EmitVertex();

#         g_pos_world = v_pos_world[j];
#         gl_Position = gl_in[j].gl_Position;
#         EmitVertex();

#         EndPrimitive();
#     }
# }
# """


# =============================
#   Fragment Shader
# =============================
frag = """
#version 330 core

in vec3 g_pos_world;

uniform vec4 u_color;

out vec4 FragColor;

void main() {
    // просто цвет линий
    FragColor = vec4(u_color.rgb, u_color.a);
}
"""


class LineRenderer(Component):

    def __init__(self, points: Iterable[tuple[float, float, float]], color: tuple[float, float, float, float], width: float = 1.0):
        super().__init__(enabled=True)
        self.points = list(points)
        self.color = color
        self.width = width
        self.shader = ShaderProgram(
            vertex_source=vert, 
            #geometry_source=geom, 
            fragment_source=frag)
        self.material = Material(shader=self.shader, color=self.color)
        
        self.mesh2 = Mesh2.from_lists(self.points, [[i, i + 1] for i in range(0, len(self.points) - 1)])
        self.drawable = Mesh2Drawable(self.mesh2)
        
    def required_shaders(self):
        yield self.shader

    def draw(self, context: RenderContext):
        if self.entity is None:
            return


        # Рендерим линии
        model = self.entity.model_matrix()
        view  = context.view
        proj  = context.projection
        gfx   = context.graphics
        key   = context.context_key

        print("Drawing lines with color:", self.color, "and width:", self.width)

        self.material.apply(model, view, proj, graphics=gfx, context_key=key)
        self.drawable.draw(context)