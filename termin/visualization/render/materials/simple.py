from __future__ import annotations
from termin.visualization.core.material import Material
from termin.visualization.render.shader import ShaderProgram

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
        shader = ShaderProgram(ColorMaterial_VERT, ColorMaterial_FRAG)
        super().__init__(shader=shader, color=color)


# Unlit shader - просто цвет без освещения
UNLIT_VERT = """
#version 330 core
layout(location = 0) in vec3 a_position;

uniform mat4 u_model;
uniform mat4 u_view;
uniform mat4 u_projection;

void main() {
    gl_Position = u_projection * u_view * u_model * vec4(a_position, 1.0);
}
"""

UNLIT_FRAG = """
#version 330 core
uniform vec4 u_color;

out vec4 FragColor;

void main() {
    FragColor = u_color;
}
"""

_unlit_shader: ShaderProgram | None = None

def unlit_shader() -> ShaderProgram:
    """Возвращает кэшированный unlit шейдер."""
    global _unlit_shader
    if _unlit_shader is None:
        _unlit_shader = ShaderProgram(UNLIT_VERT, UNLIT_FRAG)
    return _unlit_shader


class UnlitMaterial(Material):
    """Материал без освещения - просто цвет."""
    def __init__(self, color: tuple[float, float, float, float], **kwargs):
        super().__init__(shader=unlit_shader(), color=color, **kwargs)
