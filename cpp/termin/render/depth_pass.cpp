#include "termin/render/depth_pass.hpp"

namespace termin {

const char* DEPTH_PASS_VERT = R"(
#version 330 core

layout(location = 0) in vec3 a_position;
layout(location = 1) in vec3 a_normal;
layout(location = 2) in vec2 a_texcoord;

uniform mat4 u_model;
uniform mat4 u_view;
uniform mat4 u_projection;
uniform float u_near;
uniform float u_far;

out float v_linear_depth;

void main()
{
    vec4 world_pos = u_model * vec4(a_position, 1.0);
    vec4 view_pos  = u_view * world_pos;

    // Y-forward convention: depth is along +Y axis in view space
    float y = view_pos.y;
    float depth = (y - u_near) / (u_far - u_near);

    v_linear_depth = depth;
    gl_Position = u_projection * view_pos;
}
)";

const char* DEPTH_PASS_FRAG = R"(
#version 330 core

in float v_linear_depth;
out vec4 FragColor;

void main()
{
    float d = clamp(v_linear_depth, 0.0, 1.0);
    FragColor = vec4(d, 0.0, 0.0, 1.0);
}
)";

// Register DepthPass in tc_pass_registry for C#/standalone C++ usage
TC_REGISTER_FRAME_PASS(DepthPass);

} // namespace termin
