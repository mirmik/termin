@program FOV_View

@phase opaque
@priority 0
@glDepthTest false
@glDepthMask false
@glCull false

@property Texture2D u_input_tex = "white"
@property Texture2D u_depth_texture = "depth_default"
@property Texture2D u_fov_texture = "white"

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
uniform sampler2D u_fov_texture;

out vec4 FragColor;

vec4 doit() {
    vec4 color = texture(u_input_tex, v_uv);

    color.b = 0.0;

    return color;
}

void main() {
    FragColor = doit();
}
@endstage

@endphase
