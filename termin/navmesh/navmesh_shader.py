"""NavMesh display shader — простой шейдер с освещением."""

from __future__ import annotations

from tgfx import TcShader


NAVMESH_VERTEX_SHADER = """#version 330 core

layout(location = 0) in vec3 a_position;
layout(location = 1) in vec3 a_normal;

uniform mat4 u_model;
uniform mat4 u_view;
uniform mat4 u_projection;

out vec3 v_world_pos;
out vec3 v_normal;

void main() {
    vec4 world = u_model * vec4(a_position, 1.0);
    v_world_pos = world.xyz;
    v_normal = mat3(transpose(inverse(u_model))) * a_normal;
    gl_Position = u_projection * u_view * world;
}
"""

NAVMESH_FRAGMENT_SHADER = """#version 330 core

in vec3 v_world_pos;
in vec3 v_normal;

uniform vec4 u_color;
uniform vec3 u_camera_position;

out vec4 FragColor;

void main() {
    // Simple Lambert diffuse lighting
    vec3 N = normalize(v_normal);
    vec3 light_dir = normalize(vec3(0.5, 0.8, 1.0));
    float ndotl = max(dot(N, light_dir), 0.0);

    // Двухстороннее освещение
    float ndotl_back = max(dot(-N, light_dir), 0.0);
    float lighting = max(ndotl, ndotl_back * 0.5);

    vec3 ambient = vec3(0.3);
    vec3 diffuse = u_color.rgb * (ambient + lighting * 0.7);

    FragColor = vec4(diffuse, u_color.a);
}
"""


def navmesh_display_shader() -> TcShader:
    """Creates shader for NavMesh display."""
    return TcShader.from_sources(
        NAVMESH_VERTEX_SHADER,
        NAVMESH_FRAGMENT_SHADER,
        "",
        "NavMeshDisplay",
    )
