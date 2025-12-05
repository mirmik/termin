@program SolidColor

@phase opaque
@priority 0
@glDepthTest true
@glDepthMask true
@glCull true

@uniform color u_color 0.8 0.2 0.2 1.0

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

out vec4 FragColor;

void main() {
    vec3 N = normalize(v_normal);
    vec3 lightDir = normalize(vec3(1.0, 1.0, 1.0));

    float ambient = 0.3;
    float diffuse = max(dot(N, lightDir), 0.0) * 0.7;

    vec3 color = u_color.rgb * (ambient + diffuse);
    FragColor = vec4(color, u_color.a);
}
@endstage

@endphase
