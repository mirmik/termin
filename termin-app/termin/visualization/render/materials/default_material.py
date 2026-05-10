from __future__ import annotations

from termin._native.render import TcMaterial

# Матрицы работают в однородных координатах: gl_Position = P * V * M * [x, y, z, 1]^T
DEFAULT_VERT = """#version 330 core

layout(location = 0) in vec3 a_position;
layout(location = 1) in vec3 a_normal;
layout(location = 2) in vec2 a_uv;

uniform mat4 u_model;
uniform mat4 u_view;
uniform mat4 u_projection;

out vec3 v_world_pos;
out vec3 v_normal;
out vec2 v_uv;

void main() {
    vec4 world = u_model * vec4(a_position, 1.0);
    v_world_pos = world.xyz;
    v_normal = mat3(transpose(inverse(u_model))) * a_normal;
    v_uv = a_uv;
    gl_Position = u_projection * u_view * world;
}
"""

DEFAULT_FRAG = """#version 330 core

in vec3 v_world_pos;
in vec3 v_normal;
in vec2 v_uv;

const int LIGHT_TYPE_DIRECTIONAL = 0;
const int LIGHT_TYPE_POINT = 1;
const int LIGHT_TYPE_SPOT = 2;
const int MAX_LIGHTS = 8;
const int MAX_SHADOW_MAPS = 16;

struct LightData {
    vec4 color_intensity;
    vec4 direction_range;
    vec4 position_type;
    vec4 attenuation_inner;
    vec4 outer_cascade;
};

layout(std140, binding = 0) uniform LightingBlock {
    LightData u_lights[MAX_LIGHTS];
    vec4 u_ambient_data;
    vec4 u_camera_light_count;
    vec4 u_shadow_settings;
};

layout(std140, binding = 3) uniform ShadowBlock {
    int u_shadow_map_count;
    mat4 u_light_space_matrix[MAX_SHADOW_MAPS];
    int u_shadow_light_index[MAX_SHADOW_MAPS];
    int u_shadow_cascade_index[MAX_SHADOW_MAPS];
    float u_shadow_split_near[MAX_SHADOW_MAPS];
    float u_shadow_split_far[MAX_SHADOW_MAPS];
};

layout(binding = 8) uniform sampler2DShadow u_shadow_map[MAX_SHADOW_MAPS];

uniform vec4 u_color;
uniform sampler2D u_albedo_texture;
uniform float u_shininess;
uniform vec4 u_emission_color;
uniform float u_emission_intensity;

out vec4 FragColor;

int get_light_count() { return int(u_camera_light_count.w); }
int get_light_type(int i) { return int(u_lights[i].position_type.w); }
vec3 get_light_color(int i) { return u_lights[i].color_intensity.rgb; }
float get_light_intensity(int i) { return u_lights[i].color_intensity.w; }
vec3 get_light_direction(int i) { return u_lights[i].direction_range.xyz; }
vec3 get_light_position(int i) { return u_lights[i].position_type.xyz; }
float get_light_range(int i) { return u_lights[i].direction_range.w; }
vec3 get_light_attenuation(int i) { return u_lights[i].attenuation_inner.xyz; }
float get_light_inner_angle(int i) { return u_lights[i].attenuation_inner.w; }
float get_light_outer_angle(int i) { return u_lights[i].outer_cascade.x; }
vec3 get_ambient_color() { return u_ambient_data.rgb; }
float get_ambient_intensity() { return u_ambient_data.w; }
vec3 get_camera_position() { return u_camera_light_count.xyz; }
float get_shadow_bias() { return u_shadow_settings.z; }

float compute_distance_attenuation(vec3 attenuation, float range, float dist) {
    float denom = attenuation.x + attenuation.y * dist + attenuation.z * dist * dist;
    if (denom <= 0.0) {
        return 1.0;
    }
    float w = 1.0 / denom;
    if (range > 0.0 && dist > range) {
        w = 0.0;
    }
    return w;
}

float compute_spot_weight(vec3 light_dir, vec3 L, float inner_angle, float outer_angle) {
    float cos_theta = dot(light_dir, -L);
    float cos_outer = cos(outer_angle);
    float cos_inner = cos(inner_angle);

    if (cos_theta <= cos_outer) return 0.0;
    if (cos_theta >= cos_inner) return 1.0;

    float t = (cos_theta - cos_outer) / (cos_inner - cos_outer);
    return t * t * (3.0 - 2.0 * t);
}

float blinn_phong_specular(vec3 N, vec3 L, vec3 V, float shininess) {
    vec3 H = normalize(L + V);
    float NdotH = max(dot(N, H), 0.0);
    return pow(NdotH, shininess);
}

float compute_shadow_auto(int light_index) {
    for (int sm = 0; sm < u_shadow_map_count; ++sm) {
        if (u_shadow_light_index[sm] != light_index) {
            continue;
        }

        vec4 light_space_pos = u_light_space_matrix[sm] * vec4(v_world_pos, 1.0);
        vec3 proj_coords = light_space_pos.xyz / light_space_pos.w;
        proj_coords = proj_coords * 0.5 + 0.5;

        if (proj_coords.x < 0.0 || proj_coords.x > 1.0 ||
            proj_coords.y < 0.0 || proj_coords.y > 1.0 ||
            proj_coords.z < 0.0 || proj_coords.z > 1.0) {
            return 1.0;
        }

        return texture(u_shadow_map[sm], vec3(proj_coords.xy, proj_coords.z - get_shadow_bias()));
    }

    return 1.0;
}

void main() {
    vec3 N = normalize(v_normal);
    vec3 V = normalize(get_camera_position() - v_world_pos);

    vec4 tex_color = texture(u_albedo_texture, v_uv);
    vec3 base_color = u_color.rgb * tex_color.rgb;

    vec3 result = base_color * get_ambient_color() * get_ambient_intensity();

    for (int i = 0; i < get_light_count(); ++i) {
        int type = get_light_type(i);
        vec3 radiance = get_light_color(i) * get_light_intensity(i);

        vec3 L;
        float dist;
        float weight = 1.0;

        if (type == LIGHT_TYPE_DIRECTIONAL) {
            L = normalize(-get_light_direction(i));
            dist = 1e9;
        } else {
            vec3 to_light = get_light_position(i) - v_world_pos;
            dist = length(to_light);
            L = dist > 0.0001 ? to_light / dist : vec3(0.0, 1.0, 0.0);

            weight *= compute_distance_attenuation(
                get_light_attenuation(i),
                get_light_range(i),
                dist
            );

            if (type == LIGHT_TYPE_SPOT) {
                weight *= compute_spot_weight(
                    get_light_direction(i),
                    L,
                    get_light_inner_angle(i),
                    get_light_outer_angle(i)
                );
            }
        }

        float shadow = 1.0;
        if (type == LIGHT_TYPE_DIRECTIONAL) {
            shadow = compute_shadow_auto(i);
        }

        float ndotl = max(dot(N, L), 0.0);
        vec3 diffuse = base_color * ndotl;
        float spec = blinn_phong_specular(N, L, V, u_shininess);
        vec3 specular = vec3(spec);

        result += (diffuse + specular) * radiance * weight * shadow;
    }

    result += u_emission_color.rgb * u_emission_intensity;
    FragColor = vec4(result, u_color.a * tex_color.a);
}
"""

DEFAULT_SHADER_TEXT = """@program DefaultShader
@features lighting_ubo

@phase opaque
@priority 0
@glDepthTest true
@glDepthMask true
@glCull true

@property Color u_color = Color(1.0, 1.0, 1.0, 1.0)
@property Float u_shininess = 32.0 range(1.0, 128.0)
@property Color u_emission_color = Color(0.0, 0.0, 0.0, 1.0)
@property Float u_emission_intensity = 0.0 range(0.0, 100.0)
@property Texture u_albedo_texture = "white"

@stage vertex
""" + DEFAULT_VERT + """@endstage

@stage fragment
""" + DEFAULT_FRAG + """@endstage

@endphase
"""


def create_default_material(
    name: str = "DefaultMaterial",
    color: tuple[float, float, float, float] | None = None,
) -> TcMaterial:
    """
    Создаёт материал по умолчанию с диффузным освещением по Ламберту и бликом по Фонгу.

    Args:
        name: Имя материала.
        color: RGBA цвет (по умолчанию белый).

    Returns:
        TcMaterial с одной фазой "opaque".
    """
    from termin.visualization.render.shader_parser import parse_shader_text

    mat = TcMaterial.from_parsed(
        parse_shader_text(DEFAULT_SHADER_TEXT),
        name=name,
    )

    phase = mat.default_phase()
    if phase is not None:
        # Set default color
        c = color or (1.0, 1.0, 1.0, 1.0)
        phase.set_color(c[0], c[1], c[2], c[3])

    return mat


class DefaultMaterial(TcMaterial):
    """
    Базовый материал сцены. Диффузная часть следует модели Ламберта, блик — Фонга.

    NOTE: This is a factory class that returns TcMaterial.
    Use create_default_material() for explicit creation.
    """

    def __new__(cls, color: tuple[float, float, float, float] | None = None) -> TcMaterial:
        return create_default_material(name="DefaultMaterial", color=color)
