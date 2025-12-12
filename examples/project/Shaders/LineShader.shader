@program LineShader

@phase opaque

@property Float u_width = 0.05
@property Color u_color = Color(1.0, 1.0, 1.0, 1.0)

// ============================================================
// Vertex Shader — просто передаёт позицию в мировых координатах
// ============================================================
@stage vertex
#version 330 core

layout(location = 0) in vec3 a_position;

uniform mat4 u_model;

out vec3 v_world_pos;

void main() {
    v_world_pos = (u_model * vec4(a_position, 1.0)).xyz;
}

// ============================================================
// Geometry Shader — разворачивает GL_LINES в billboard quads
// ============================================================
@stage geometry
#version 330 core

layout(lines) in;
layout(triangle_strip, max_vertices = 4) out;

in vec3 v_world_pos[];

uniform mat4 u_view;
uniform mat4 u_projection;
uniform float u_width;

// Позиция камеры (извлекаем из view matrix)
vec3 get_camera_pos(mat4 view) {
    mat3 rot = mat3(view);
    vec3 d = vec3(view[3]);
    return -d * rot;
}

void main() {
    vec3 p0 = v_world_pos[0];
    vec3 p1 = v_world_pos[1];

    vec3 camera_pos = get_camera_pos(u_view);

    // Направление линии
    vec3 line_dir = normalize(p1 - p0);

    // Направление к камере (среднее для обоих концов)
    vec3 mid = (p0 + p1) * 0.5;
    vec3 to_camera = normalize(camera_pos - mid);

    // Перпендикуляр к линии в плоскости, обращённой к камере
    vec3 perp = normalize(cross(line_dir, to_camera));

    float half_width = u_width * 0.5;

    // 4 вершины quad'а
    vec3 v0 = p0 - perp * half_width;
    vec3 v1 = p0 + perp * half_width;
    vec3 v2 = p1 - perp * half_width;
    vec3 v3 = p1 + perp * half_width;

    mat4 vp = u_projection * u_view;

    gl_Position = vp * vec4(v0, 1.0);
    EmitVertex();

    gl_Position = vp * vec4(v1, 1.0);
    EmitVertex();

    gl_Position = vp * vec4(v2, 1.0);
    EmitVertex();

    gl_Position = vp * vec4(v3, 1.0);
    EmitVertex();

    EndPrimitive();
}

// ============================================================
// Fragment Shader — выводит цвет
// ============================================================
@stage fragment
#version 330 core

uniform vec4 u_color;

out vec4 frag_color;

void main() {
    frag_color = u_color;
}
