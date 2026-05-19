#version 450

layout(push_constant) uniform PushConstants {
    mat4 u_mvp;
} pc;

layout(location = 0) in vec3 in_pos;
layout(location = 1) in vec3 in_color;
layout(location = 0) out vec3 v_color;

void main() {
    v_color = in_color;
    gl_Position = pc.u_mvp * vec4(in_pos, 1.0);
}
