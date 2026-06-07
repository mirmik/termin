# termin/visualization/render/materials/pbr_material.py
"""PBR (Physically Based Rendering) material using GGX/Cook-Torrance BRDF."""

from __future__ import annotations

from termin.materials import TcMaterial


PBR_VERT = """#version 330 core

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

PBR_FRAG = """#version 330 core

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

float shadow_bias_depth(int sm) {
    float depth_range = max(u_shadow_split_far[sm] - u_shadow_split_near[sm], 0.0001);
    return max(get_shadow_bias(), 0.0) / depth_range;
}

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

float compute_shadow_auto(int light_index) {
    for (int sm = 0; sm < u_shadow_map_count; ++sm) {
        if (u_shadow_light_index[sm] != light_index) {
            continue;
        }

        vec4 light_space_pos = u_light_space_matrix[sm] * vec4(v_world_pos, 1.0);
        vec3 proj_coords = light_space_pos.xyz / light_space_pos.w;
        proj_coords.xy = proj_coords.xy * 0.5 + 0.5;

        if (proj_coords.x < 0.0 || proj_coords.x > 1.0 ||
            proj_coords.y < 0.0 || proj_coords.y > 1.0 ||
            proj_coords.z < 0.0 || proj_coords.z > 1.0) {
            continue;
        }

        return texture(u_shadow_map[sm], vec3(proj_coords.xy, proj_coords.z - shadow_bias_depth(sm)));
    }

    return 1.0;
}

// Material parameters
uniform vec4 u_color;
uniform sampler2D u_albedo_texture;
uniform sampler2D u_metallic_roughness_texture;
uniform sampler2D u_occlusion_texture;
uniform sampler2D u_emissive_texture;
uniform float u_metallic;
uniform float u_roughness;
uniform vec4 u_emission_color;
uniform float u_emission_intensity;

out vec4 FragColor;

const float PI = 3.14159265359;

// Normal Distribution Function (GGX/Trowbridge-Reitz)
float D_GGX(float NdotH, float roughness) {
    float a = roughness * roughness;
    float a2 = a * a;
    float denom = NdotH * NdotH * (a2 - 1.0) + 1.0;
    return a2 / (PI * denom * denom);
}

// Geometry Function (Smith's method with GGX)
float G_Smith(float NdotV, float NdotL, float roughness) {
    float r = roughness + 1.0;
    float k = (r * r) / 8.0;
    float G1_V = NdotV / (NdotV * (1.0 - k) + k);
    float G1_L = NdotL / (NdotL * (1.0 - k) + k);
    return G1_V * G1_L;
}

// Fresnel (Schlick approximation)
vec3 F_Schlick(float cosTheta, vec3 F0) {
    return F0 + (1.0 - F0) * pow(1.0 - cosTheta, 5.0);
}

void main() {
    vec3 N = normalize(v_normal);
    vec3 V = normalize(get_camera_position() - v_world_pos);

    // Sample albedo
    vec4 tex_color = texture(u_albedo_texture, v_uv);
    vec3 albedo = u_color.rgb * tex_color.rgb;

    vec4 metallic_roughness_sample = texture(u_metallic_roughness_texture, v_uv);
    float metallic = clamp(u_metallic * metallic_roughness_sample.b, 0.0, 1.0);
    float roughness = max(clamp(u_roughness * metallic_roughness_sample.g, 0.0, 1.0), 0.04);
    float occlusion = texture(u_occlusion_texture, v_uv).r;
    vec3 F0 = mix(vec3(0.04), albedo, metallic);

    // Ambient
    vec3 ambient = get_ambient_color() * get_ambient_intensity() * albedo * (1.0 - metallic * 0.5) * occlusion;

    vec3 Lo = vec3(0.0);
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

        float NdotL = max(dot(N, L), 0.0);
        float NdotV = max(dot(N, V), 0.001);
        vec3 H = normalize(V + L);
        float NdotH = max(dot(N, H), 0.0);
        float HdotV = max(dot(H, V), 0.0);

        // Cook-Torrance BRDF
        float D = D_GGX(NdotH, roughness);
        float G = G_Smith(NdotV, NdotL, roughness);
        vec3 F = F_Schlick(HdotV, F0);

        vec3 numerator = D * G * F;
        float denominator = 4.0 * NdotV * NdotL + 0.0001;
        vec3 specular = numerator / denominator;

        vec3 kD = (1.0 - F) * (1.0 - metallic);
        float shadow = (type == LIGHT_TYPE_DIRECTIONAL) ? compute_shadow_auto(i) : 1.0;
        Lo += (kD * albedo + specular) * radiance * NdotL * weight * shadow;
    }

    vec3 color = ambient + Lo + texture(u_emissive_texture, v_uv).rgb * u_emission_color.rgb * u_emission_intensity;
    FragColor = vec4(color, 1.0);
}
"""

PBR_SHADER_TEXT = """@program PBRShader
@features lighting_ubo

@phase opaque
@priority 0
@glDepthTest true
@glDepthMask true
@glCull true

@property Color u_color = Color(1.0, 1.0, 1.0, 1.0)
@property Texture u_albedo_texture = "white"
@property Texture u_metallic_roughness_texture = "white"
@property Texture u_occlusion_texture = "white"
@property Texture u_emissive_texture = "white"
@property Float u_metallic = 0.0 range(0.0, 1.0)
@property Float u_roughness = 0.5 range(0.0, 1.0)
@property Color u_emission_color = Color(0.0, 0.0, 0.0, 1.0)
@property Float u_emission_intensity = 0.0 range(0.0, 100.0)

@stage vertex
""" + PBR_VERT + """@endstage

@stage fragment
""" + PBR_FRAG + """@endstage

@endphase
"""


def create_pbr_material(
    color: tuple[float, float, float, float] | None = None,
    metallic: float = 0.0,
    roughness: float = 0.5,
    name: str = "PBRMaterial",
) -> TcMaterial:
    """
    Create a PBR material using Cook-Torrance BRDF.

    Args:
        color: Base color (albedo) multiplier.
        metallic: 0 = dielectric, 1 = metal.
        roughness: 0 = smooth/mirror, 1 = rough/matte.
        name: Material name.

    Returns:
        TcMaterial with PBR shader.
    """
    from termin.geombase import Vec4
    from termin.materials import create_material_from_parsed, parse_shader_text
    from termin.assets.texture_handle import (
        get_normal_texture_handle,
        get_white_texture_handle,
    )

    white_tex = get_white_texture_handle().get()
    normal_tex = get_normal_texture_handle().get()

    mat = create_material_from_parsed(
        parse_shader_text(PBR_SHADER_TEXT),
        color=color or (1.0, 1.0, 1.0, 1.0),
        name=name,
        default_white_texture=white_tex,
        default_normal_texture=normal_tex,
    )

    phase = mat.default_phase()
    if phase is not None:
        # Set PBR parameters
        phase.set_uniform_float("u_metallic", metallic)
        phase.set_uniform_float("u_roughness", roughness)
        phase.set_uniform_vec4("u_emission_color", Vec4(0.0, 0.0, 0.0, 1.0))
        phase.set_uniform_float("u_emission_intensity", 0.0)

    return mat


# Legacy alias
def pbr_shader():
    """Deprecated: Use create_pbr_material() instead."""
    raise NotImplementedError("pbr_shader() is deprecated. Use create_pbr_material() instead.")


class PBRMaterial(TcMaterial):
    """
    PBR material using Cook-Torrance BRDF. Returns TcMaterial.

    Parameters:
        color: Base color (albedo) multiplier
        metallic: 0 = dielectric, 1 = metal
        roughness: 0 = smooth/mirror, 1 = rough/matte
    """

    def __new__(
        cls,
        color: tuple[float, float, float, float] | None = None,
        metallic: float = 0.0,
        roughness: float = 0.5,
    ) -> TcMaterial:
        return create_pbr_material(color=color, metallic=metallic, roughness=roughness)
