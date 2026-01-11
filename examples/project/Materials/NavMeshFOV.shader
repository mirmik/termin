@program NavMeshFOV

@phase transparent

@glDepthTest true
@glDepthMask false
@glCull false
@glBlend true

@property Color u_color = Color(1.0, 1.0, 1.0, 1.0)
@property Texture2D u_fov = "white"

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
out vec3 world_pos;

void main() {
    v_normal = mat3(u_model) * a_normal;
    v_texcoord = a_texcoord;
    world_pos = (u_model * vec4(a_position, 1.0)).xyz;
    gl_Position = u_projection * u_view * u_model * vec4(a_position, 1.0);
}

@stage fragment
#version 330 core

in vec3 v_normal;
in vec2 v_texcoord;
in vec3 world_pos;

uniform vec4 u_color;
uniform sampler2D u_fov;

uniform mat4 u_fov_view;
uniform mat4 u_fov_projection;

out vec4 frag_color;

void main() {
    vec4 fov_sample = texture(u_fov, world_pos.xy);
    frag_color = fov_sample; 
}
