#include "termin/render/normal_pass.hpp"

namespace termin {

const char* NORMAL_PASS_VERT = R"(
#version 330 core

layout(location = 0) in vec3 a_position;
layout(location = 1) in vec3 a_normal;
layout(location = 2) in vec2 a_texcoord;

uniform mat4 u_model;
uniform mat4 u_view;
uniform mat4 u_projection;

out vec3 v_world_normal;

void main()
{
    mat3 normal_matrix = transpose(inverse(mat3(u_model)));
    v_world_normal = normalize(normal_matrix * a_normal);

    vec4 world_pos = u_model * vec4(a_position, 1.0);
    gl_Position = u_projection * u_view * world_pos;
}
)";

const char* NORMAL_PASS_FRAG = R"(
#version 330 core

in vec3 v_world_normal;
out vec4 FragColor;

void main()
{
    vec3 encoded = normalize(v_world_normal) * 0.5 + 0.5;
    FragColor = vec4(encoded, 1.0);
}
)";

// Register NormalPass in tc_pass_registry for C#/standalone C++ usage
TC_REGISTER_FRAME_PASS_DERIVED(NormalPass, GeometryPassBase);

} // namespace termin
