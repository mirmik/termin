"""
Материал для генерации shadow map.

Пишет глубину в стандартный depth buffer, без линеаризации —
используется нативная нелинейная глубина OpenGL для shadow mapping.
"""

from __future__ import annotations

from termin.visualization.core.material import Material
from termin.visualization.render.shader import ShaderProgram


SHADOW_VERT = """
#version 330 core

layout(location = 0) in vec3 a_position;

uniform mat4 u_model;
uniform mat4 u_view;
uniform mat4 u_projection;

void main()
{
    gl_Position = u_projection * u_view * u_model * vec4(a_position, 1.0);
}
"""

SHADOW_FRAG = """
#version 330 core

out vec4 FragColor;

void main()
{
    // Глубина пишется автоматически в depth buffer.
    // Для отладки можно визуализировать gl_FragCoord.z:
    float depth = gl_FragCoord.z;
    FragColor = vec4(depth, depth, depth, 1.0);
}
"""


class ShadowMaterial(Material):
    """
    Минимальный материал для shadow pass.
    
    Рендерит геометрию без освещения и текстур — только позиции.
    Глубина записывается в depth buffer средствами OpenGL.
    """

    def __init__(self):
        shader = ShaderProgram(SHADOW_VERT, SHADOW_FRAG)
        super().__init__(shader=shader, uniforms={})
