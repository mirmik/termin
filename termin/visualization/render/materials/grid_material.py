"""Grid/calibration material - draws grid lines parallel to XY, YZ, ZX planes."""

from __future__ import annotations

from termin.visualization.core.material import Material
from termin.visualization.render.shader import ShaderProgram


GRID_VERT = """
#version 330 core
layout(location = 0) in vec3 a_position;
layout(location = 1) in vec3 a_normal;

uniform mat4 u_model;
uniform mat4 u_view;
uniform mat4 u_projection;

out vec3 v_local_pos;
out vec3 v_normal;

void main() {
    // Pass local position for grid calculation
    v_local_pos = a_position;
    v_normal = mat3(transpose(inverse(u_model))) * a_normal;
    gl_Position = u_projection * u_view * u_model * vec4(a_position, 1.0);
}
"""


GRID_FRAG = """
#version 330 core
in vec3 v_local_pos;
in vec3 v_normal;

uniform vec4 u_color;
uniform float u_grid_spacing;  // Grid cell size (default 1.0)
uniform float u_line_width;    // Line width in units (default 0.02)

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

    // Scale position by grid spacing
    vec3 p = v_local_pos / spacing;

    // Calculate grid lines for each axis
    // Lines parallel to X axis (in YZ plane)
    float line_x = max(grid_line(p.y, line_width), grid_line(p.z, line_width));
    // Lines parallel to Y axis (in XZ plane)
    float line_y = max(grid_line(p.x, line_width), grid_line(p.z, line_width));
    // Lines parallel to Z axis (in XY plane)
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


_grid_shader: ShaderProgram | None = None


def grid_shader() -> ShaderProgram:
    """Returns cached grid shader."""
    global _grid_shader
    if _grid_shader is None:
        _grid_shader = ShaderProgram(GRID_VERT, GRID_FRAG)
    return _grid_shader


class GridMaterial(Material):
    """
    Calibration material that draws grid lines parallel to XY, YZ, ZX planes.

    Grid lines are drawn at integer intervals in local object space.

    Args:
        color: Base color (r, g, b, a)
        grid_spacing: Distance between grid lines (default 1.0)
        line_width: Width of grid lines in local units (default 0.02)
    """

    def __init__(
        self,
        color: tuple[float, float, float, float] = (0.8, 0.8, 0.8, 1.0),
        grid_spacing: float = 1.0,
        line_width: float = 0.02,
    ):
        self.grid_spacing = grid_spacing
        self.line_width = line_width
        super().__init__(
            shader=grid_shader(),
            color=color,
            u_grid_spacing=grid_spacing,
            u_line_width=line_width,
        )
