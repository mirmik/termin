"""Grid/calibration material - draws grid lines parallel to XY, YZ, ZX planes."""

from __future__ import annotations

from termin._native.render import TcMaterial, TcRenderState


GRID_VERT = """
#version 330 core
layout(location = 0) in vec3 a_position;
layout(location = 1) in vec3 a_normal;

uniform mat4 u_model;
uniform mat4 u_view;
uniform mat4 u_projection;

out vec3 v_world_pos;
out vec3 v_normal;

void main() {
    // Pass world position for grid calculation
    v_world_pos = (u_model * vec4(a_position, 1.0)).xyz;
    v_normal = mat3(transpose(inverse(u_model))) * a_normal;
    gl_Position = u_projection * u_view * u_model * vec4(a_position, 1.0);
}
"""


GRID_FRAG = """
#version 330 core
in vec3 v_world_pos;
in vec3 v_normal;

uniform vec4 u_color;
uniform float u_grid_spacing;  // Grid cell size in world units (default 1.0)
uniform float u_line_width;    // Line width in world units (default 0.02)

out vec4 FragColor;

float grid_line(float coord, float line_width) {
    // Distance to nearest grid line
    float d = abs(fract(coord + 0.5) - 0.5);
    // Smooth step based on line width
    float half_width = line_width * 0.5;
    return 1.0 - smoothstep(0.0, half_width, d);
}

void main() {
    float spacing = u_grid_spacing > 0.0 ? u_grid_spacing : 1.0;
    float line_width = u_line_width > 0.0 ? u_line_width : 0.02;

    // Use world position scaled by grid spacing
    vec3 p = v_world_pos / spacing;

    // Calculate grid lines for each axis (in world space)
    // Lines parallel to X axis (in YZ plane at integer X)
    float line_x = max(grid_line(p.y, line_width), grid_line(p.z, line_width));
    // Lines parallel to Y axis (in XZ plane at integer Y)
    float line_y = max(grid_line(p.x, line_width), grid_line(p.z, line_width));
    // Lines parallel to Z axis (in XY plane at integer Z)
    float line_z = max(grid_line(p.x, line_width), grid_line(p.y, line_width));

    // Combine all grid lines
    float grid = max(max(line_x, line_y), line_z);

    // Simple lighting
    vec3 n = normalize(v_normal);
    float ndotl = max(dot(n, normalize(vec3(0.2, 0.6, 0.5))), 0.0);
    float light = 0.3 + 0.7 * ndotl;

    // Base color with grid overlay
    vec3 base_color = u_color.rgb * light;
    vec3 grid_color = vec3(0.0, 0.0, 0.0);  // Black grid lines

    vec3 final_color = mix(base_color, grid_color, grid * 0.8);
    FragColor = vec4(final_color, u_color.a);
}
"""


def create_grid_material(
    color: tuple[float, float, float, float] = (0.8, 0.8, 0.8, 1.0),
    grid_spacing: float = 1.0,
    line_width: float = 0.02,
    name: str = "GridMaterial",
) -> TcMaterial:
    """
    Create a grid/calibration material.

    Grid lines are drawn at integer intervals in local object space.

    Args:
        color: Base color (r, g, b, a)
        grid_spacing: Distance between grid lines (default 1.0)
        line_width: Width of grid lines in local units (default 0.02)
        name: Material name

    Returns:
        TcMaterial with grid shader.
    """
    mat = TcMaterial.create(name, "")
    mat.shader_name = "GridShader"

    state = TcRenderState.opaque()
    phase = mat.add_phase_from_sources(
        vertex_source=GRID_VERT,
        fragment_source=GRID_FRAG,
        geometry_source="",
        shader_name="GridShader",
        phase_mark="opaque",
        priority=0,
        state=state,
    )

    if phase is not None:
        phase.set_color(color[0], color[1], color[2], color[3])
        phase.set_uniform_float("u_grid_spacing", grid_spacing)
        phase.set_uniform_float("u_line_width", line_width)

    return mat


# Legacy alias for backward compatibility
def grid_shader():
    """Deprecated: Use create_grid_material() instead."""
    raise NotImplementedError("grid_shader() is deprecated. Use create_grid_material() instead.")


class GridMaterial(TcMaterial):
    """
    Calibration material that draws grid lines parallel to XY, YZ, ZX planes.

    Grid lines are drawn at integer intervals in local object space.
    Returns TcMaterial.
    """

    def __new__(
        cls,
        color: tuple[float, float, float, float] = (0.8, 0.8, 0.8, 1.0),
        grid_spacing: float = 1.0,
        line_width: float = 0.02,
    ) -> TcMaterial:
        return create_grid_material(color=color, grid_spacing=grid_spacing, line_width=line_width)
