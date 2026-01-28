@program NavMeshPost

@phase opaque
@priority 0
@glDepthTest false
@glDepthMask false
@glCull false

@property Texture2D u_input_tex = "white"
@property Texture2D u_depth_texture = "depth_default"
@property Texture2D u_normal_texture = "normal_default"

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

out vec4 FragColor;

vec4 doit()
{
    vec4 color = texture(u_input_tex, v_uv);
    return color + vec4(0.0, 1.0, 0.0, 1.0); 
}

void main() 
{
    FragColor = doit();
}
@endstage

@endphase
