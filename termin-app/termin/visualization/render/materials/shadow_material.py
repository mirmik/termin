"""
Материал для генерации shadow map.

Пишет глубину в стандартный depth buffer, без линеаризации —
используется нативная нелинейная глубина OpenGL для shadow mapping.
"""

from __future__ import annotations

from termin._native.render import TcMaterial, TcRenderState


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

void main()
{
    // Depth-only pass: глубина пишется автоматически в depth buffer.
    // Никакого color output - shadow FBO не имеет color attachment.
}
"""


def create_shadow_material(name: str = "ShadowMaterial") -> TcMaterial:
    """Create a shadow pass material."""
    mat = TcMaterial.create(name, "")
    mat.shader_name = "ShadowShader"

    state = TcRenderState.opaque()
    phase = mat.add_phase_from_sources(
        vertex_source=SHADOW_VERT,
        fragment_source=SHADOW_FRAG,
        geometry_source="",
        shader_name="ShadowShader",
        phase_mark="shadow",
        priority=0,
        state=state,
    )

    return mat


class ShadowMaterial(TcMaterial):
    """
    Минимальный материал для shadow pass. Returns TcMaterial.

    Рендерит геометрию без освещения и текстур — только позиции.
    Глубина записывается в depth buffer средствами OpenGL.
    """

    def __new__(cls) -> TcMaterial:
        return create_shadow_material()
