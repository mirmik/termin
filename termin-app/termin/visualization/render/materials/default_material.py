from __future__ import annotations

from termin.materials import TcMaterial

DEFAULT_SHADER_TEXT = """@program DefaultShader
@language slang
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
struct VertexInput {
    float3 position : POSITION;
    float3 normal : NORMAL;
    float2 uv : TEXCOORD0;
};

struct VertexOutput {
    float4 position : SV_Position;
    float3 world_pos : TEXCOORD0;
    float3 normal_world : TEXCOORD1;
    float2 uv : TEXCOORD2;
};

[shader("vertex")]
VertexOutput main(VertexInput input) {
    VertexOutput output;
    float4 world = mul(u_model, float4(input.position, 1.0));
    output.world_pos = world.xyz;
    output.normal_world = mul((float3x3)u_model, input.normal);
    output.uv = input.uv;
    output.position = mul(u_projection, mul(u_view, world));
    return output;
}
@endstage

@stage fragment
static const int LIGHT_TYPE_DIRECTIONAL = 0;
static const int LIGHT_TYPE_POINT = 1;
static const int LIGHT_TYPE_SPOT = 2;
static const int MAX_LIGHTS = 8;
static const int MAX_SHADOW_MAPS = 16;

struct LightData {
    float4 color_intensity;
    float4 direction_range;
    float4 position_type;
    float4 attenuation_inner;
    float4 outer_cascade;
};

struct LightingBlock {
    LightData u_lights[MAX_LIGHTS];
    float4 u_ambient_data;
    float4 u_camera_light_count;
    float4 u_shadow_settings;
};

[[TerminScope("pass")]]
ConstantBuffer<LightingBlock> lighting;

struct ShadowBlock {
    int u_shadow_map_count;
    column_major float4x4 u_light_space_matrix[MAX_SHADOW_MAPS];
    int u_shadow_light_index[MAX_SHADOW_MAPS];
    int u_shadow_cascade_index[MAX_SHADOW_MAPS];
    float u_shadow_split_near[MAX_SHADOW_MAPS];
    float u_shadow_split_far[MAX_SHADOW_MAPS];
};

[[TerminScope("pass")]]
ConstantBuffer<ShadowBlock> shadow_block;

[[TerminScope("pass")]]
Sampler2DShadow shadow_maps[MAX_SHADOW_MAPS];

struct FragmentInput {
    float3 world_pos : TEXCOORD0;
    float3 normal_world : TEXCOORD1;
    float2 uv : TEXCOORD2;
};

struct FragmentOutput {
    float4 color : SV_Target0;
};

int get_light_count() { return int(lighting.u_camera_light_count.w); }
int get_light_type(int i) { return int(lighting.u_lights[i].position_type.w); }
float3 get_light_color(int i) { return lighting.u_lights[i].color_intensity.rgb; }
float get_light_intensity(int i) { return lighting.u_lights[i].color_intensity.w; }
float3 get_light_direction(int i) { return lighting.u_lights[i].direction_range.xyz; }
float3 get_light_position(int i) { return lighting.u_lights[i].position_type.xyz; }
float get_light_range(int i) { return lighting.u_lights[i].direction_range.w; }
float3 get_light_attenuation(int i) { return lighting.u_lights[i].attenuation_inner.xyz; }
float get_light_inner_angle(int i) { return lighting.u_lights[i].attenuation_inner.w; }
float get_light_outer_angle(int i) { return lighting.u_lights[i].outer_cascade.x; }
float3 get_ambient_color() { return lighting.u_ambient_data.rgb; }
float get_ambient_intensity() { return lighting.u_ambient_data.w; }
float3 get_camera_position() { return lighting.u_camera_light_count.xyz; }
float get_shadow_bias() { return lighting.u_shadow_settings.z; }

float shadow_bias_depth(int sm) {
    float depth_range = max(
        shadow_block.u_shadow_split_far[sm] - shadow_block.u_shadow_split_near[sm],
        0.0001);
    return max(get_shadow_bias(), 0.0) / depth_range;
}

float compute_distance_attenuation(float3 attenuation, float range, float dist) {
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

float compute_spot_weight(float3 light_dir, float3 L, float inner_angle, float outer_angle) {
    float cos_theta = dot(light_dir, -L);
    float cos_outer = cos(outer_angle);
    float cos_inner = cos(inner_angle);

    if (cos_theta <= cos_outer) return 0.0;
    if (cos_theta >= cos_inner) return 1.0;

    float t = (cos_theta - cos_outer) / (cos_inner - cos_outer);
    return t * t * (3.0 - 2.0 * t);
}

float blinn_phong_specular(float3 N, float3 L, float3 V, float shininess) {
    float3 H = normalize(L + V);
    float NdotH = max(dot(N, H), 0.0);
    return pow(NdotH, shininess);
}

float compute_shadow_auto(int light_index, float3 world_pos) {
    for (int sm = 0; sm < shadow_block.u_shadow_map_count; ++sm) {
        if (shadow_block.u_shadow_light_index[sm] != light_index) {
            continue;
        }

        float4 light_space_pos =
            mul(shadow_block.u_light_space_matrix[sm], float4(world_pos, 1.0));
        float3 proj_coords = light_space_pos.xyz / light_space_pos.w;
        proj_coords.xy = proj_coords.xy * 0.5 + 0.5;

        if (proj_coords.x < 0.0 || proj_coords.x > 1.0 ||
            proj_coords.y < 0.0 || proj_coords.y > 1.0 ||
            proj_coords.z < 0.0 || proj_coords.z > 1.0) {
            continue;
        }

        return shadow_maps[sm].SampleCmp(
            proj_coords.xy,
            proj_coords.z - shadow_bias_depth(sm));
    }

    return 1.0;
}

[shader("fragment")]
FragmentOutput main(FragmentInput input) {
    FragmentOutput output;
    float3 N = normalize(input.normal_world);
    float3 V = normalize(get_camera_position() - input.world_pos);

    float4 tex_color = u_albedo_texture.Sample(input.uv);
    float3 base_color = material.u_color.rgb * tex_color.rgb;

    float3 result = base_color * get_ambient_color() * get_ambient_intensity();

    for (int i = 0; i < get_light_count(); ++i) {
        int type = get_light_type(i);
        float3 radiance = get_light_color(i) * get_light_intensity(i);

        float3 L;
        float dist;
        float weight = 1.0;

        if (type == LIGHT_TYPE_DIRECTIONAL) {
            L = normalize(-get_light_direction(i));
            dist = 1e9;
        } else {
            float3 to_light = get_light_position(i) - input.world_pos;
            dist = length(to_light);
            L = dist > 0.0001 ? to_light / dist : float3(0.0, 1.0, 0.0);

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
            shadow = compute_shadow_auto(i, input.world_pos);
        }

        float ndotl = max(dot(N, L), 0.0);
        float3 diffuse = base_color * ndotl;
        float spec = blinn_phong_specular(N, L, V, material.u_shininess);
        float3 specular = float3(spec);

        result += (diffuse + specular) * radiance * weight * shadow;
    }

    result += material.u_emission_color.rgb * material.u_emission_intensity;
    output.color = float4(result, material.u_color.a * tex_color.a);
    return output;
}
@endstage

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
    from termin.materials import create_material_from_parsed, parse_shader_text
    from termin.assets.texture_handle import (
        get_normal_texture_handle,
        get_white_texture_handle,
    )

    white_tex = get_white_texture_handle().get()
    normal_tex = get_normal_texture_handle().get()

    mat = create_material_from_parsed(
        parse_shader_text(DEFAULT_SHADER_TEXT),
        name=name,
        default_white_texture=white_tex,
        default_normal_texture=normal_tex,
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
