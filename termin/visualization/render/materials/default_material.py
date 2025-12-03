from __future__ import annotations

from termin.visualization.core.material import Material
from termin.visualization.render.shader import ShaderProgram

# Матрицы работают в однородных координатах: gl_Position = P * V * M * [x, y, z, 1]^T
DEFAULT_VERT = """#version 330 core

layout(location = 0) in vec3 a_position;
layout(location = 1) in vec3 a_normal;

uniform mat4 u_model;
uniform mat4 u_view;
uniform mat4 u_projection;

out vec3 v_world_pos;
out vec3 v_normal;

void main() {
    vec4 world = u_model * vec4(a_position, 1.0);
    v_world_pos = world.xyz;
    v_normal = mat3(transpose(inverse(u_model))) * a_normal;
    gl_Position = u_projection * u_view * world;
}
"""

DEFAULT_FRAG = """#version 330 core

in vec3 v_world_pos;
in vec3 v_normal;

uniform vec4 u_color; // RGBA базового материала

// ============== Источники света ==============
const int LIGHT_TYPE_DIRECTIONAL = 0;
const int LIGHT_TYPE_POINT       = 1;
const int LIGHT_TYPE_SPOT        = 2;
const int LIGHT_TYPE_AMBIENT     = 3;

const int MAX_LIGHTS = 8;

uniform int   u_light_count;
uniform int   u_light_type[MAX_LIGHTS];
uniform vec3  u_light_color[MAX_LIGHTS];
uniform float u_light_intensity[MAX_LIGHTS];
uniform vec3  u_light_direction[MAX_LIGHTS];
uniform vec3  u_light_position[MAX_LIGHTS];
uniform float u_light_range[MAX_LIGHTS];
uniform vec3  u_light_attenuation[MAX_LIGHTS]; // (constant, linear, quadratic)
uniform float u_light_inner_angle[MAX_LIGHTS];
uniform float u_light_outer_angle[MAX_LIGHTS];

// ============== Shadow Mapping ==============
const int MAX_SHADOW_MAPS = 4;

uniform int u_shadow_map_count;
uniform sampler2D u_shadow_map[MAX_SHADOW_MAPS];
uniform mat4 u_light_space_matrix[MAX_SHADOW_MAPS];
uniform int u_shadow_light_index[MAX_SHADOW_MAPS];

// Bias для устранения shadow acne
const float SHADOW_BIAS = 0.005;

out vec4 FragColor;

float compute_distance_attenuation(int idx, float dist) {
    vec3 att = u_light_attenuation[idx];
    float denom = att.x + att.y * dist + att.z * dist * dist;
    if (denom <= 0.0) {
        return 1.0;
    }
    float w = 1.0 / denom;
    float range = u_light_range[idx];
    if (range > 0.0 && dist > range) {
        w = 0.0;
    }
    return w;
}

float compute_spot_weight(int idx, vec3 L) {
    float cos_theta = dot(u_light_direction[idx], -L);
    float cos_outer = cos(u_light_outer_angle[idx]);
    float cos_inner = cos(u_light_inner_angle[idx]);

    if (cos_theta <= cos_outer) return 0.0;
    if (cos_theta >= cos_inner) return 1.0;

    float t = (cos_theta - cos_outer) / (cos_inner - cos_outer);
    return t * t * (3.0 - 2.0 * t); // smoothstep
}

/**
 * Вычисляет коэффициент тени для источника света.
 *
 * Алгоритм:
 * 1. Преобразуем мировую позицию в light-space: p_light = L * p_world
 * 2. Переводим в NDC: ndc = p_light.xyz / p_light.w
 * 3. Переводим в текстурные координаты: uv = ndc.xy * 0.5 + 0.5
 * 4. Сравниваем глубину фрагмента с глубиной в shadow map
 *
 * Возвращает:
 *   1.0 — фрагмент освещён
 *   0.0 — фрагмент в тени
 */
float compute_shadow(int light_index) {
    // Ищем shadow map для этого источника
    for (int sm = 0; sm < u_shadow_map_count; ++sm) {
        if (u_shadow_light_index[sm] != light_index) {
            continue;
        }
        
        // Преобразуем в light-space
        vec4 light_space_pos = u_light_space_matrix[sm] * vec4(v_world_pos, 1.0);
        
        // Perspective divide (для ортографической проекции w=1, но делаем для общности)
        vec3 proj_coords = light_space_pos.xyz / light_space_pos.w;
        
        // Переводим из [-1, 1] в [0, 1] для текстурных координат
        proj_coords = proj_coords * 0.5 + 0.5;
        
        // Проверяем, что координаты внутри shadow map
        if (proj_coords.x < 0.0 || proj_coords.x > 1.0 ||
            proj_coords.y < 0.0 || proj_coords.y > 1.0 ||
            proj_coords.z < 0.0 || proj_coords.z > 1.0) {
            return 1.0; // Вне frustum'а — считаем освещённым
        }
        
        // Читаем глубину из shadow map (записана в R канал как серый цвет)
        float closest_depth = texture(u_shadow_map[sm], proj_coords.xy).r;
        
        // Текущая глубина фрагмента
        float current_depth = proj_coords.z;
        
        // Сравниваем с bias для устранения shadow acne
        float shadow = current_depth - SHADOW_BIAS > closest_depth ? 0.0 : 1.0;
        
        return shadow;
    }
    
    // Нет shadow map для этого источника — полностью освещён
    return 1.0;
}

void main() {
    vec3 N = normalize(v_normal);
    vec3 base_color = u_color.rgb;
    vec3 result = vec3(0.0);

    for (int i = 0; i < u_light_count; ++i) {
        int type = u_light_type[i];
        vec3 radiance = u_light_color[i] * u_light_intensity[i];

        if (type == LIGHT_TYPE_AMBIENT) {
            result += base_color * radiance;
            continue;
        }

        vec3 L;
        float dist;
        float weight = 1.0;

        if (type == LIGHT_TYPE_DIRECTIONAL) {
            L = normalize(-u_light_direction[i]); // направление на свет
            dist = 1e9;
        } else {
            vec3 to_light = u_light_position[i] - v_world_pos;
            dist = length(to_light);
            if (dist > 0.0001)
                L = to_light / dist;
            else
                L = vec3(0.0, 1.0, 0.0);

            weight *= compute_distance_attenuation(i, dist);

            if (type == LIGHT_TYPE_SPOT) {
                weight *= compute_spot_weight(i, L);
            }
        }

        // Вычисляем тень для directional lights
        float shadow = 1.0;
        if (type == LIGHT_TYPE_DIRECTIONAL) {
            shadow = compute_shadow(i);
        }

        float ndotl = max(dot(N, L), 0.0);
        vec3 diffuse = base_color * ndotl; // Ламбертовский диффуз: L_d = c * max(N·L, 0)

        vec3 V = normalize(-v_world_pos); // камера в (0,0,0) для простоты
        vec3 H = normalize(L + V);
        float ndoth = max(dot(N, H), 0.0);
        float shininess = 16.0;
        float spec = pow(ndoth, shininess);

        vec3 specular_color = vec3(1.0);
        vec3 specular = spec * specular_color; // Блик Фонга: L_s = (max(N·H, 0))^n

        // Применяем тень к диффузу и спекуляру
        result += (diffuse + specular) * radiance * weight * shadow;
    }

    FragColor = vec4(result, u_color.a);
}
"""


def default_shader() -> ShaderProgram:
    """Создает шейдер по умолчанию с комбинированным диффузным и бликовым освещением."""
    return ShaderProgram(vertex_source=DEFAULT_VERT, fragment_source=DEFAULT_FRAG)


class DefaultMaterial(Material):
    """
    Базовый материал сцены. Диффузная часть следует модели Ламберта, блик — Фонга.
    """

    def __init__(self, color: tuple[float, float, float, float] | None = None):
        shader = default_shader()
        super().__init__(shader=shader, color=color)
