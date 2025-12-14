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

uniform mat4 u_model;
uniform vec4 u_color_below;
uniform vec4 u_color_above;
uniform vec3 u_slice_axis;      // slice axis in entity local space
uniform float u_fill_percent;   // 0.0 - 1.0
uniform vec3 u_bounds_min;      // bounds in mesh space (before model transform)
uniform vec3 u_bounds_max;

// Basic lighting
uniform vec3 u_camera_position;
uniform vec3 u_ambient_color;
uniform float u_ambient_intensity;

out vec4 FragColor;

void main() {
    // Transform everything to world space
    vec3 world_bounds_min = (u_model * vec4(u_bounds_min, 1.0)).xyz;
    vec3 world_bounds_max = (u_model * vec4(u_bounds_max, 1.0)).xyz;
    vec3 world_slice_axis = normalize(mat3(u_model) * u_slice_axis);

    // Project bounds onto slice axis
    float axis_min = dot(world_bounds_min, world_slice_axis);
    float axis_max = dot(world_bounds_max, world_slice_axis);
    float axis_range = axis_max - axis_min;

    // Project current world position onto slice axis
    float pos_on_axis = dot(v_world_pos, world_slice_axis);

    // Normalize position to 0-1 range along axis
    float normalized_pos = 0.5;
    if (axis_range > 0.0001) {
        normalized_pos = (pos_on_axis - axis_min) / axis_range;
    }

    // blend_zone is ABOVE fill_percent
    // fill 100%: blend 100-105% (doesn't exist), entire object is color_below
    // fill 90%: discard > 95%, blend 90-95%, below 90% is color_below
    // fill 50%: discard > 55%, blend 50-55%, below 50% is color_below
    float blend_zone = 0.05;
    float cut_threshold = u_fill_percent + blend_zone;

    // Discard fragments above cut threshold
    if (normalized_pos > cut_threshold) {
        discard;
    }

    vec4 base_color;
    if (normalized_pos > u_fill_percent) {
        // In blend zone
        float t = (normalized_pos - u_fill_percent) / blend_zone;
        base_color = mix(u_color_below, u_color_above, t);
    } else {
        base_color = u_color_below;
    }

    // Simple Lambert diffuse lighting
    vec3 N = normalize(v_normal);
    vec3 light_dir = normalize(vec3(0.5, 0.8, 1.0));
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
