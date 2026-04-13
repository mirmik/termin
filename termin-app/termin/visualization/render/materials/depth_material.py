from __future__ import annotations

from termin._native.render import TcMaterial, TcRenderState

DEPTH_VERT = """
#version 330 core

layout(location = 0) in vec3 a_position;
layout(location = 1) in vec3 a_normal;
layout(location = 2) in vec2 a_texcoord;

uniform mat4 u_model;
uniform mat4 u_view;
uniform mat4 u_projection;
uniform float u_near;
uniform float u_far;

out float v_linear_depth;

void main()
{
    vec4 world_pos = u_model * vec4(a_position, 1.0);
    vec4 view_pos  = u_view * world_pos;

    float y = view_pos.y; // forward = +Y in view space
    float depth = (y - u_near) / (u_far - u_near);

    v_linear_depth = depth;
    gl_Position = u_projection * view_pos;
}
"""

DEPTH_FRAG = """
#version 330 core

in float v_linear_depth;
out vec4 FragColor;

void main()
{
    float d = clamp(v_linear_depth, 0.0, 1.0);
    // R16F format - only red channel is used
    FragColor = vec4(d, 0.0, 0.0, 1.0);
}
"""


def create_depth_material(
    near: float = 0.1,
    far: float = 100.0,
    name: str = "DepthMaterial",
) -> TcMaterial:
    """Create a depth material that writes linear depth to color channel."""
    mat = TcMaterial.create(name, "")
    mat.shader_name = "DepthShader"

    state = TcRenderState.opaque()
    phase = mat.add_phase_from_sources(
        vertex_source=DEPTH_VERT,
        fragment_source=DEPTH_FRAG,
        geometry_source="",
        shader_name="DepthShader",
        phase_mark="depth",
        priority=0,
        state=state,
    )

    if phase is not None:
        phase.set_uniform_float("u_near", near)
        phase.set_uniform_float("u_far", far)

    return mat


class DepthMaterial(TcMaterial):
    """
    Простой материал, который пишет линейную глубину в канал цвета.
    Returns TcMaterial.
    """

    def __new__(cls) -> TcMaterial:
        return create_depth_material()
