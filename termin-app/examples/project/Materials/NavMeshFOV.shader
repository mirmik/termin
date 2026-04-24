@program NavMeshFOV

@phase transparent

@glDepthTest true
@glDepthMask false
@glCull false
@glBlend true

@property Color u_color = Color(0.0, 1.0, 0.0, 0.2)
@property Texture u_fov = "white"
@property Float u_fov_distance = 100.0
@property Float u_depth_bias = 0.02

@stage vertex
#version 330 core

layout(location = 0) in vec3 a_position;
layout(location = 1) in vec3 a_normal;
layout(location = 2) in vec2 a_texcoord;

uniform mat4 u_model;
uniform mat4 u_view;
uniform mat4 u_projection;

uniform mat4 u_fov_view;
uniform mat4 u_fov_projection;

out vec3 v_world_pos;
out vec3 v_normal;
out vec4 v_fov_clip_pos;
out float v_fov_linear_depth;

void main() {
    vec4 world_pos = u_model * vec4(a_position, 1.0);
    v_world_pos = world_pos.xyz;
    v_normal = mat3(u_model) * a_normal;

    // Transform to FOV camera clip space
    vec4 fov_view_pos = u_fov_view * world_pos;
    v_fov_clip_pos = u_fov_projection * fov_view_pos;

    // Linear depth in FOV camera space (forward = +Y)
    v_fov_linear_depth = fov_view_pos.y;

    gl_Position = u_projection * u_view * world_pos;
}

@stage fragment
#version 330 core

in vec3 v_world_pos;
in vec3 v_normal;
in vec4 v_fov_clip_pos;
in float v_fov_linear_depth;

uniform vec4 u_color;
uniform sampler2D u_fov;
uniform float u_fov_distance;
uniform float u_depth_bias;

uniform mat4 u_fov_view;

out vec4 frag_color;

void main() {
    // Perspective divide
    vec3 ndc = v_fov_clip_pos.xyz / v_fov_clip_pos.w;

    // Check if within FOV frustum [-1, 1]
    if (ndc.x < -1.0 || ndc.x > 1.0 || ndc.y < -1.0 || ndc.y > 1.0) {
        discard;
    }

    // Check if in front of FOV camera (positive Y in view space)
    if (v_fov_linear_depth < 0.0) {
        discard;
    }

    // Check max distance
    if (v_fov_linear_depth > u_fov_distance) {
        discard;
    }

    // Convert NDC to UV [0, 1]
    vec2 fov_uv = ndc.xy * 0.5 + 0.5;

    // Sample depth from FOV depth texture (linear Y depth, normalized to u_fov_distance)
    float stored_depth = texture(u_fov, fov_uv).r * u_fov_distance;

    // Current pixel depth (normalized)
    float current_depth = v_fov_linear_depth;

    // Visibility test: pixel is visible if its depth <= stored depth + bias
    if (current_depth > stored_depth + u_depth_bias) {
        discard;
    }

    // Pixel is visible from FOV camera
    frag_color = u_color;
}
