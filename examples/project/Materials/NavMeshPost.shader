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
@property Float u_fov_distance = 100.0
@property Float u_depth_bias = 0.02

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
uniform float u_fov_distance;
uniform float u_depth_bias;

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

// Check if pixel is visible from FOV camera
bool is_visible_from_fov(vec3 world_pos) {
    // Transform world position to FOV camera view space
    vec4 fov_view_pos = u_fov_view * vec4(world_pos, 1.0);

    // Linear depth in FOV camera space (forward = +Y)
    float fov_linear_depth = fov_view_pos.y;

    // Check if in front of FOV camera
    if (fov_linear_depth < 0.0) {
        return false;
    }

    // Check max distance
    if (fov_linear_depth > u_fov_distance) {
        return false;
    }

    // Transform to FOV camera clip space
    vec4 fov_clip_pos = u_fov_projection * fov_view_pos;

    // Perspective divide
    vec3 ndc = fov_clip_pos.xyz / fov_clip_pos.w;

    // Check if within FOV frustum [-1, 1]
    if (ndc.x < -1.0 || ndc.x > 1.0 || ndc.y < -1.0 || ndc.y > 1.0) {
        return false;
    }

    // Convert NDC to UV [0, 1]
    vec2 fov_uv = ndc.xy * 0.5 + 0.5;

    // Sample depth from FOV depth texture (linear depth normalized to [0,1])
    float stored_depth = texture(u_fov, fov_uv).r * u_fov_distance;

    // Visibility test: pixel is visible if its depth <= stored depth + bias
    if (fov_linear_depth > stored_depth + u_depth_bias) {
        return false;
    }

    return true;
}

float fov_linear_depth_from_world_pos(vec3 world_pos) {
    // Transform world position to FOV camera view space
    vec4 fov_view_pos = u_fov_view * vec4(world_pos, 1.0);
    return fov_view_pos.y;
}

void main()
{
    vec4 color = texture(u_input_tex, v_uv);

    // Get linear depth from depth texture
    float linear_depth = texture(u_depth_texture, v_uv).r;

    //Debug: just pass through depth value unchanged
    FragColor = vec4(linear_depth, linear_depth, linear_depth, 1.0);
    return;

    // // Skip sky/far pixels
    // if (linear_depth >= 1.0) {
    //     FragColor = color;
    //     return;
    // }

    // Reconstruct world position
    vec3 world_pos = reconstruct_world_pos(v_uv, linear_depth);

        // DEBUG
        // float debug_depth = fov_linear_depth_from_world_pos(world_pos) / u_fov_distance;
        // FragColor = vec4(vec3(debug_depth), 1.0);
        // return;

    // Check FOV visibility and tint green if visible
    if (is_visible_from_fov(world_pos)) {
        color.rgb = mix(color.rgb, vec3(0.0, 1.0, 0.0), 0.3);
    
    }

    FragColor = color;
}
@endstage

@endphase
