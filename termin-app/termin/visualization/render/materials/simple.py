from __future__ import annotations

from termin._native.render import TcMaterial, TcRenderState

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


def create_color_material(
    color: tuple[float, float, float, float],
    name: str = "ColorMaterial",
) -> TcMaterial:
    """Create a simple colored material with basic lighting."""
    mat = TcMaterial.create(name, "")
    mat.shader_name = "ColorShader"

    state = TcRenderState.opaque()
    phase = mat.add_phase_from_sources(
        vertex_source=ColorMaterial_VERT,
        fragment_source=ColorMaterial_FRAG,
        geometry_source="",
        shader_name="ColorShader",
        phase_mark="opaque",
        priority=0,
        state=state,
    )

    if phase is not None:
        phase.set_color(color[0], color[1], color[2], color[3])

    return mat


class ColorMaterial(TcMaterial):
    """Simple colored material with basic lighting. Returns TcMaterial."""

    def __new__(cls, color: tuple[float, float, float, float]) -> TcMaterial:
        return create_color_material(color=color)


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


def create_unlit_material(
    color: tuple[float, float, float, float],
    name: str = "UnlitMaterial",
) -> TcMaterial:
    """Create an unlit material (no lighting, just solid color)."""
    mat = TcMaterial.create(name, "")
    mat.shader_name = "UnlitShader"

    state = TcRenderState.opaque()
    phase = mat.add_phase_from_sources(
        vertex_source=UNLIT_VERT,
        fragment_source=UNLIT_FRAG,
        geometry_source="",
        shader_name="UnlitShader",
        phase_mark="opaque",
        priority=0,
        state=state,
    )

    if phase is not None:
        phase.set_color(color[0], color[1], color[2], color[3])

    return mat


class UnlitMaterial(TcMaterial):
    """Unlit material (no lighting). Returns TcMaterial."""

    def __new__(cls, color: tuple[float, float, float, float], **kwargs) -> TcMaterial:
        return create_unlit_material(color=color)
