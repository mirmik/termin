@program NewShader

@phase opaque

@property Float u_time = 0.0
@property Color u_color = Color(1.0, 1.0, 1.0, 1.0)

@stage vertex
#version 330 core

layout(location = 0) in vec3 a_position;
layout(location = 1) in vec3 a_normal;
layout(location = 2) in vec2 a_texcoord;

uniform mat4 u_model;
uniform mat4 u_view;
uniform mat4 u_projection;

out vec3 v_normal;
out vec2 v_texcoord;

void main() {
    v_normal = mat3(u_model) * a_normal;
    v_texcoord = a_texcoord;
    gl_Position = u_projection * u_view * u_model * vec4(a_position, 1.0);
}

@stage fragment
#version 330 core

in vec3 v_normal;
in vec2 v_texcoord;

uniform vec4 u_color;

out vec4 frag_color;

void main() {
    vec3 normal = normalize(v_normal);
    float light = max(dot(normal, vec3(0.0, 1.0, 0.0)), 0.2);
    frag_color = vec4(u_color.rgb * light, u_color.a);
}
