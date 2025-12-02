from __future__ import annotations

from termin.visualization.core.material import Material
from termin.visualization.render.shader import ShaderProgram

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

    // z в системе камеры (камера смотрит вдоль -Z)
    float z = -view_pos.z;

    float depth = (z - u_near) / (u_far - u_near);
    depth = clamp(depth, 0.0, 1.0);

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
    FragColor = vec4(d, d, d, 1.0);
}
"""


class DepthMaterial(Material):
    """
    Простой материал, который пишет линейную глубину в канал цвета.
    """

    def __init__(self):
        shader = ShaderProgram(DEPTH_VERT, DEPTH_FRAG)
        super().__init__(
            shader=shader,
            uniforms={
                "u_near": 0.1,
                "u_far": 100.0,
            },
        )

    def update_camera_planes(self, near_plane: float, far_plane: float):
        self.uniforms["u_near"] = float(near_plane)
        self.uniforms["u_far"] = float(far_plane)
