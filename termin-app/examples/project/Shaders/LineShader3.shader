@program LineShader3

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
// 4 для quad + 2 круга * 6 сегментов * 3 вершины = 4 + 36 = 40
layout(triangle_strip, max_vertices = 48) out;

in vec3 v_world_pos[];

uniform mat4 u_view;
uniform mat4 u_projection;
uniform float u_width;

const int CIRCLE_SEGMENTS = 6;
const float PI = 3.14159265359;

// Позиция камеры (извлекаем из view matrix)
vec3 get_camera_pos(mat4 view) {
    mat3 rot = mat3(view);
    vec3 d = vec3(view[3]);
    return -d * rot;
}

// Рисует полный круг в точке стыка (отдельными треугольниками)
void emit_circle(vec3 center, vec3 perp, vec3 tangent, float radius, mat4 vp) {
    for (int i = 0; i < CIRCLE_SEGMENTS; i++) {
        float a0 = float(i) / float(CIRCLE_SEGMENTS) * 2.0 * PI;
        float a1 = float(i + 1) / float(CIRCLE_SEGMENTS) * 2.0 * PI;

        vec3 p0 = center + (perp * cos(a0) + tangent * sin(a0)) * radius;
        vec3 p1 = center + (perp * cos(a1) + tangent * sin(a1)) * radius;

        // Треугольник: center -> p0 -> p1
        gl_Position = vp * vec4(center, 1.0);
        EmitVertex();
        gl_Position = vp * vec4(p0, 1.0);
        EmitVertex();
        gl_Position = vp * vec4(p1, 1.0);
        EmitVertex();
        EndPrimitive();
    }
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

    // Круглые заглушки на обоих концах сегмента
    // tangent = line_dir для ориентации круга в плоскости billboard
    emit_circle(p0, perp, line_dir, half_width, vp);
    emit_circle(p1, perp, line_dir, half_width, vp);
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
