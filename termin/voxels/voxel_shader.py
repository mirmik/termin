"""Voxel display shaders with slice clipping."""

from __future__ import annotations

from termin.visualization.render.shader import ShaderProgram


VOXEL_VERTEX_SHADER = """#version 330 core

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

VOXEL_FRAGMENT_SHADER = """#version 330 core

in vec3 v_world_pos;
in vec3 v_normal;

uniform vec4 u_color_below;
uniform vec4 u_color_above;
uniform vec3 u_slice_axis;      // normalized axis direction
uniform float u_fill_percent;   // 0.0 - 1.0
uniform vec3 u_bounds_min;
uniform vec3 u_bounds_max;

// Basic lighting
uniform vec3 u_camera_position;
uniform vec3 u_ambient_color;
uniform float u_ambient_intensity;

out vec4 FragColor;

void main() {
    // Use Z axis directly for slicing (slice_axis default is 0,0,1)
    float z_min = u_bounds_min.z;
    float z_max = u_bounds_max.z;
    float z_range = z_max - z_min;

    // Normalize current Z position to 0-1 range
    float normalized_pos = 0.5;
    if (z_range > 0.0001) {
        normalized_pos = (v_world_pos.z - z_min) / z_range;
    }

    // Discard fragments above fill threshold
    if (normalized_pos > u_fill_percent) {
        discard;
    }

    // Choose color based on position relative to threshold
    // Below threshold: color_below, near threshold: blend to color_above
    float blend_zone = 0.05;  // 5% blend zone near threshold
    float blend_start = u_fill_percent - blend_zone;

    vec4 base_color;
    if (normalized_pos < blend_start) {
        base_color = u_color_below;
    } else {
        float t = clamp((normalized_pos - blend_start) / blend_zone, 0.0, 1.0);
        base_color = mix(u_color_below, u_color_above, t);
    }

    // Simple Lambert diffuse lighting
    vec3 N = normalize(v_normal);
    vec3 light_dir = normalize(vec3(0.5, 0.8, 1.0));  // Fixed light direction
    float ndotl = max(dot(N, light_dir), 0.0);

    vec3 ambient = u_ambient_color * u_ambient_intensity;
    vec3 diffuse = base_color.rgb * (ambient + ndotl * 0.6);

    FragColor = vec4(diffuse, base_color.a);
}
"""


def voxel_display_shader() -> ShaderProgram:
    """Creates shader for voxel display with slice clipping."""
    return ShaderProgram(
        vertex_source=VOXEL_VERTEX_SHADER,
        fragment_source=VOXEL_FRAGMENT_SHADER,
    )
