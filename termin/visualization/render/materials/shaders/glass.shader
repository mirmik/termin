@program Glass

@phase opaque
@priority 0
@glDepthTest true
@glDepthMask true
@glCull true
@glBlend false

@uniform color u_color 0.1 0.3 0.8 1.0
@uniform float u_opacity 0.3 range(0.0, 1.0)

@stage vertex
#version 330 core

layout(location = 0) in vec3 a_position;
layout(location = 1) in vec3 a_normal;

uniform mat4 u_model;
uniform mat4 u_view;
uniform mat4 u_projection;

out vec3 v_normal;
out vec3 v_world_pos;
out vec3 v_view_pos;

void main() {
    vec4 world = u_model * vec4(a_position, 1.0);
    v_world_pos = world.xyz;
    v_normal = mat3(transpose(inverse(u_model))) * a_normal;

    vec4 view_pos = u_view * world;
    v_view_pos = view_pos.xyz;

    gl_Position = u_projection * view_pos;
}
@endstage

@stage fragment
#version 330 core

in vec3 v_normal;
in vec3 v_world_pos;
in vec3 v_view_pos;

uniform vec4 u_color;
uniform float u_opacity;

out vec4 FragColor;

void main() {
    vec3 N = normalize(v_normal);
    vec3 V = normalize(-v_view_pos);

    // Fresnel effect
    float fresnel = pow(1.0 - max(dot(N, V), 0.0), 3.0);

    vec3 lightDir = normalize(vec3(1.0, 1.0, 1.0));
    float diffuse = max(dot(N, lightDir), 0.0) * 0.5 + 0.5;

    vec3 color = u_color.rgb * diffuse;

    // Opaque pass renders only where mostly opaque
    float alpha = u_opacity + fresnel * 0.5;
    if (alpha < 0.9) {
        discard;
    }

    FragColor = vec4(color, 1.0);
}
@endstage

@endphase

@phase transparent
@priority 1000
@glDepthTest true
@glDepthMask false
@glCull false
@glBlend true

@uniform color u_color 0.1 0.3 0.8 1.0
@uniform float u_opacity 0.3 range(0.0, 1.0)

@stage vertex
#version 330 core

layout(location = 0) in vec3 a_position;
layout(location = 1) in vec3 a_normal;

uniform mat4 u_model;
uniform mat4 u_view;
uniform mat4 u_projection;

out vec3 v_normal;
out vec3 v_world_pos;
out vec3 v_view_pos;

void main() {
    vec4 world = u_model * vec4(a_position, 1.0);
    v_world_pos = world.xyz;
    v_normal = mat3(transpose(inverse(u_model))) * a_normal;

    vec4 view_pos = u_view * world;
    v_view_pos = view_pos.xyz;

    gl_Position = u_projection * view_pos;
}
@endstage

@stage fragment
#version 330 core

in vec3 v_normal;
in vec3 v_world_pos;
in vec3 v_view_pos;

uniform vec4 u_color;
uniform float u_opacity;

out vec4 FragColor;

void main() {
    vec3 N = normalize(v_normal);
    vec3 V = normalize(-v_view_pos);

    // Fresnel effect - more reflective at grazing angles
    float fresnel = pow(1.0 - max(dot(N, V), 0.0), 3.0);

    vec3 lightDir = normalize(vec3(1.0, 1.0, 1.0));
    float diffuse = max(dot(N, lightDir), 0.0) * 0.5 + 0.5;

    // Specular highlight
    vec3 H = normalize(lightDir + V);
    float spec = pow(max(dot(N, H), 0.0), 64.0);

    vec3 color = u_color.rgb * diffuse + vec3(1.0) * spec * 0.5;

    float alpha = u_opacity + fresnel * 0.5;

    // Transparent pass renders semi-transparent parts
    if (alpha >= 0.9) {
        discard;
    }

    FragColor = vec4(color, alpha);
}
@endstage

@endphase
