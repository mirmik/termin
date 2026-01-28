@program NavMeshPost

@phase opaque
@priority 0
@glDepthTest false
@glDepthMask false
@glCull false

@property Texture2D u_input_tex = "white"
@property Texture2D u_depth_texture = "depth_default"
@property Texture2D u_normal_texture = "normal_default"
@property Texture2D u_fov = "white"

@stage vertex
#version 330 core

layout(location = 0) in vec2 a_pos;
layout(location = 1) in vec2 a_uv;

out vec2 v_uv;

void main() {
    v_uv = a_uv;
    gl_Position = vec4(a_pos, 0.0, 1.0);
}
@endstage

@stage fragment
#version 330 core

in vec2 v_uv;

uniform sampler2D u_input_tex;
uniform sampler2D u_depth_texture;
uniform sampler2D u_normal_texture;
uniform vec2 u_resolution;
uniform float u_time_modifier;
uniform float u_grid_intensity;
uniform float u_grid_scale;
uniform float u_grid_line_width;
uniform vec4 u_grid_color;

uniform float u_near;
uniform float u_far;
uniform mat4 u_inv_view;
uniform mat4 u_inv_proj;

uniform sampler2D u_fov;
uniform mat4 u_fov_view;
uniform mat4 u_fov_projection;

out vec4 FragColor;

// Reconstruct world position from depth and screen UV
vec3 reconstruct_world_pos(vec2 uv, float linear_depth) {
    // Screen UV to NDC xy (-1 to 1)
    vec2 ndc_xy = uv * 2.0 - 1.0;

    // Unproject near and far points
    vec4 near_ndc = vec4(ndc_xy, -1.0, 1.0);
    vec4 far_ndc = vec4(ndc_xy, 1.0, 1.0);

    vec4 near_view = u_inv_proj * near_ndc;
    vec4 far_view = u_inv_proj * far_ndc;
    near_view /= near_view.w;
    far_view /= far_view.w;

    // Interpolate between near and far based on linear depth
    vec3 view_pos = mix(near_view.xyz, far_view.xyz, linear_depth);

    // Transform to world space
    vec4 world_pos = u_inv_view * vec4(view_pos, 1.0);

    return world_pos.xyz;
}

vec4 doit()
{
    vec3 fov = texture(u_fov, v_uv).xyz;
    return vec4(fov, 1.0);

    // vec3 world_pos = reconstruct_world_pos(v_uv, texture(u_depth_texture, v_uv).r);
    // return vec4(world_pos, 1.0);

    vec4 color = texture(u_input_tex, v_uv);
    return color;
}

void main() 
{
    FragColor = doit();
}
@endstage

@endphase
