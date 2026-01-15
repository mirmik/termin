# Pick material for object picking pass

from __future__ import annotations

from termin._native.render import TcMaterial, TcRenderState

PICK_VERT = """
#version 330 core

layout(location=0) in vec3 a_position;
layout(location=1) in vec3 a_normal;
layout(location=2) in vec2 a_texcoord;

uniform mat4 u_model;
uniform mat4 u_view;
uniform mat4 u_projection;

void main() {
    gl_Position = u_projection * u_view * u_model * vec4(a_position, 1.0);
}
"""

PICK_FRAG = """
#version 330 core
uniform vec3 u_pickColor;
out vec4 fragColor;

void main() {
    fragColor = vec4(u_pickColor, 1.0);
}
"""


def create_pick_material(name: str = "PickMaterial") -> TcMaterial:
    """Create a pick material for object selection pass."""
    mat = TcMaterial.create(name, "")
    mat.shader_name = "PickShader"

    state = TcRenderState.opaque()
    phase = mat.add_phase_from_sources(
        vertex_source=PICK_VERT,
        fragment_source=PICK_FRAG,
        geometry_source="",
        shader_name="PickShader",
        phase_mark="pick",
        priority=0,
        state=state,
    )

    return mat


class PickMaterial(TcMaterial):
    """Pick material for object selection. Returns TcMaterial."""

    def __new__(cls) -> TcMaterial:
        return create_pick_material()