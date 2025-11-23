from __future__ import annotations
from termin.visualization.material import Material
from termin.visualization.shader import ShaderProgram

ColorMaterial_VERT = """
#version 330 core
layout(location = 0) in vec3 a_position;
layout(location = 1) in vec3 a_normal;

uniform mat4 u_model;
uniform mat4 u_view;
uniform mat4 u_projection;

out vec3 v_normal;

void main() {
    v_normal = mat3(transpose(inverse(u_model))) * a_normal;
    gl_Position = u_projection * u_view * u_model * vec4(a_position, 1.0);
}
"""


ColorMaterial_FRAG = """
#version 330 core
in vec3 v_normal;
uniform vec4 u_color;

out vec4 FragColor;

void main() {
    vec3 n = normalize(v_normal);
    float ndotl = max(dot(n, vec3(0.2, 0.6, 0.5)), 0.0);
    vec3 color = u_color.rgb * (0.25 + 0.75 * ndotl);
    FragColor = vec4(color, u_color.a);
}
"""

class ColorMaterial(Material):
    def __init__(self, color: tuple[float, float, float, float]):
        self.color = color
        self.shader = ShaderProgram(ColorMaterial_VERT, ColorMaterial_FRAG)
        super().__init__(shader=self.shader, color=color)

    