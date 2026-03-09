@program LineShader2

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
// с круглыми заглушками на концах для сглаживания стыков
// ============================================================
@stage geometry
#version 330 core

layout(lines) in;
// 4 вершины для quad + 2 * (CAP_SEGMENTS + 1) для полукругов на концах
// CAP_SEGMENTS = 4 -> max_vertices = 4 + 2*5*3 = 34 (triangle fan как strip)
layout(triangle_strip, max_vertices = 34) out;

in vec3 v_world_pos[];

uniform mat4 u_view;
uniform mat4 u_projection;
uniform float u_width;

const int CAP_SEGMENTS = 4;  // Сегментов в полукруге
const float PI = 3.14159265359;

// Позиция камеры (извлекаем из view matrix)
vec3 get_camera_pos(mat4 view) {
    mat3 rot = mat3(view);
    vec3 d = vec3(view[3]);
    return -d * rot;
}

void emit_cap(vec3 center, vec3 perp, vec3 line_dir, vec3 to_cam, float radius, mat4 vp, bool is_start) {
    // Полукруг на конце линии
    // perp — перпендикуляр в плоскости billboard
    // line_dir — направление линии (для ориентации полукруга)

    float start_angle = is_start ? PI * 0.5 : -PI * 0.5;
    float end_angle = is_start ? PI * 1.5 : PI * 0.5;

    for (int i = 0; i <= CAP_SEGMENTS; i++) {
        float t = float(i) / float(CAP_SEGMENTS);
        float angle = mix(start_angle, end_angle, t);

        // Вектор в плоскости billboard
        vec3 offset = perp * cos(angle) + line_dir * sin(angle);
        vec3 p = center + offset * radius;

        // Каждый сегмент — треугольник от центра
        gl_Position = vp * vec4(center, 1.0);
        EmitVertex();

        gl_Position = vp * vec4(p, 1.0);
        EmitVertex();
    }
    EndPrimitive();
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

    mat4 vp = u_projection * u_view;

    // Основной quad линии
    vec3 v0 = p0 - perp * half_width;
    vec3 v1 = p0 + perp * half_width;
    vec3 v2 = p1 - perp * half_width;
    vec3 v3 = p1 + perp * half_width;

    gl_Position = vp * vec4(v0, 1.0);
    EmitVertex();
    gl_Position = vp * vec4(v1, 1.0);
    EmitVertex();
    gl_Position = vp * vec4(v2, 1.0);
    EmitVertex();
    gl_Position = vp * vec4(v3, 1.0);
    EmitVertex();
    EndPrimitive();

    // Круглые заглушки на концах
    emit_cap(p0, perp, line_dir, to_camera, half_width, vp, true);
    emit_cap(p1, perp, line_dir, to_camera, half_width, vp, false);
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
