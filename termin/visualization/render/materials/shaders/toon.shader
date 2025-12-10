@program Toon

@phase opaque
@priority 0
@glDepthTest true
@glDepthMask true
@glCull true

@property Color u_color = Color(1.0, 0.5, 0.0, 1.0)
@property Float u_levels = 4.0 range(2.0, 8.0)
@property Color u_outline_color = Color(0.0, 0.0, 0.0, 1.0)
@property Float u_outline_width = 0.02 range(0.0, 0.1)

@stage vertex
#version 330 core

layout(location = 0) in vec3 a_position;
layout(location = 1) in vec3 a_normal;

uniform mat4 u_model;
uniform mat4 u_view;
uniform mat4 u_projection;

out vec3 v_normal;
out vec3 v_world_pos;

void main() {
    vec4 world = u_model * vec4(a_position, 1.0);
    v_world_pos = world.xyz;
    v_normal = mat3(transpose(inverse(u_model))) * a_normal;
    gl_Position = u_projection * u_view * world;
}
@endstage

@stage fragment
#version 330 core

in vec3 v_normal;
in vec3 v_world_pos;

uniform vec4 u_color;
uniform float u_levels;

out vec4 FragColor;

void main() {
    vec3 N = normalize(v_normal);
    vec3 lightDir = normalize(vec3(1.0, 2.0, 1.5));

    // Toon shading - quantize diffuse lighting
    float NdotL = dot(N, lightDir);
    float intensity = (NdotL + 1.0) * 0.5; // remap to 0..1

    // Quantize to discrete levels
    float levels = max(u_levels, 2.0);
    intensity = floor(intensity * levels) / levels;

    // Apply color with quantized intensity
    vec3 color = u_color.rgb * (0.3 + intensity * 0.7);

    FragColor = vec4(color, u_color.a);
}
@endstage

@endphase
