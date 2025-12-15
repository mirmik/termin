# termin/visualization/render/materials/pbr_material.py
"""PBR (Physically Based Rendering) material using GGX/Cook-Torrance BRDF."""

from __future__ import annotations

from termin.visualization.core.material import Material
from termin.visualization.render.shader import ShaderProgram


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

// Material parameters
uniform vec4 u_color;
uniform sampler2D u_albedo_texture;
uniform float u_metallic;
uniform float u_roughness;

// Camera
uniform vec3 u_camera_position;

// Lighting
const int MAX_LIGHTS = 8;
const int LIGHT_TYPE_DIRECTIONAL = 0;
const int LIGHT_TYPE_POINT = 1;
const int LIGHT_TYPE_SPOT = 2;

uniform vec3  u_ambient_color;
uniform float u_ambient_intensity;

uniform int   u_light_count;
uniform int   u_light_type[MAX_LIGHTS];
uniform vec3  u_light_color[MAX_LIGHTS];
uniform float u_light_intensity[MAX_LIGHTS];
uniform vec3  u_light_direction[MAX_LIGHTS];
uniform vec3  u_light_position[MAX_LIGHTS];
uniform float u_light_range[MAX_LIGHTS];
uniform vec3  u_light_attenuation[MAX_LIGHTS];
uniform float u_light_inner_angle[MAX_LIGHTS];
uniform float u_light_outer_angle[MAX_LIGHTS];

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

float compute_distance_attenuation(int idx, float dist) {
    vec3 att = u_light_attenuation[idx];
    float denom = att.x + att.y * dist + att.z * dist * dist;
    if (denom <= 0.0) return 1.0;
    float w = 1.0 / denom;
    float range = u_light_range[idx];
    if (range > 0.0 && dist > range) w = 0.0;
    return w;
}

float compute_spot_weight(int idx, vec3 L) {
    float cos_theta = dot(u_light_direction[idx], -L);
    float cos_outer = cos(u_light_outer_angle[idx]);
    float cos_inner = cos(u_light_inner_angle[idx]);
    if (cos_theta <= cos_outer) return 0.0;
    if (cos_theta >= cos_inner) return 1.0;
    float t = (cos_theta - cos_outer) / (cos_inner - cos_outer);
    return t * t * (3.0 - 2.0 * t);
}

void main() {
    // DEBUG: output NdotL for first light
    vec3 N = normalize(v_normal);
    vec3 L = normalize(-u_light_direction[0]);
    float NdotL = max(dot(N, L), 0.0);
    FragColor = vec4(NdotL, NdotL, NdotL, 1.0);
    return;

    vec3 N = normalize(v_normal);
    vec3 V = normalize(u_camera_position - v_world_pos);

    // Sample albedo
    vec4 tex_color = texture(u_albedo_texture, v_uv);
    vec3 albedo = u_color.rgb * tex_color.rgb;

    float metallic = u_metallic;
    float roughness = max(u_roughness, 0.04); // Prevent division issues

    // F0: reflectance at normal incidence
    // Dielectrics: 0.04, Metals: albedo color
    vec3 F0 = mix(vec3(0.04), albedo, metallic);

    // Ambient (simple approximation)
    vec3 ambient = u_ambient_color * u_ambient_intensity * albedo * (1.0 - metallic * 0.5);

    vec3 Lo = vec3(0.0); // Accumulated outgoing radiance

    for (int i = 0; i < u_light_count; ++i) {
        vec3 L;
        float attenuation = 1.0;

        if (u_light_type[i] == LIGHT_TYPE_DIRECTIONAL) {
            L = normalize(-u_light_direction[i]);
        } else {
            vec3 to_light = u_light_position[i] - v_world_pos;
            float dist = length(to_light);
            L = to_light / max(dist, 0.0001);
            attenuation = compute_distance_attenuation(i, dist);

            if (u_light_type[i] == LIGHT_TYPE_SPOT) {
                attenuation *= compute_spot_weight(i, L);
            }
        }

        vec3 H = normalize(V + L);

        float NdotL = max(dot(N, L), 0.0);
        float NdotV = max(dot(N, V), 0.001);
        float NdotH = max(dot(N, H), 0.0);
        float HdotV = max(dot(H, V), 0.0);

        // Cook-Torrance BRDF
        float D = D_GGX(NdotH, roughness);
        float G = G_Smith(NdotV, NdotL, roughness);
        vec3 F = F_Schlick(HdotV, F0);

        // Specular
        vec3 numerator = D * G * F;
        float denominator = 4.0 * NdotV * NdotL + 0.0001;
        vec3 specular = numerator / denominator;

        // Energy conservation: what's not reflected is refracted (diffuse)
        vec3 kD = (1.0 - F) * (1.0 - metallic);

        // Diffuse (Lambertian, without /PI for brighter result in LDR)
        vec3 diffuse = kD * albedo;

        // Combine
        vec3 radiance = u_light_color[i] * u_light_intensity[i] * attenuation;
        Lo += (diffuse + specular) * radiance * NdotL;
    }

    vec3 color = ambient + Lo;

    // Simple tone mapping (Reinhard)
    color = color / (color + vec3(1.0));

    FragColor = vec4(color, u_color.a * tex_color.a);
}
"""


def pbr_shader() -> ShaderProgram:
    """Create PBR shader program."""
    return ShaderProgram(vertex_source=PBR_VERT, fragment_source=PBR_FRAG)


class PBRMaterial(Material):
    """
    PBR material using Cook-Torrance BRDF.

    Parameters:
        color: Base color (albedo) multiplier
        metallic: 0 = dielectric, 1 = metal
        roughness: 0 = smooth/mirror, 1 = rough/matte
    """

    def __init__(
        self,
        color: tuple[float, float, float, float] | None = None,
        metallic: float = 0.0,
        roughness: float = 0.5,
    ):
        from termin.visualization.render.texture import get_white_texture

        shader = pbr_shader()
        white_tex = get_white_texture()
        super().__init__(shader=shader, color=color, textures={"u_albedo_texture": white_tex})
        self.metallic = metallic
        self.roughness = roughness

    def apply(self, graphics):
        super().apply(graphics)
        self.shader.set_uniform("u_metallic", self.metallic)
        self.shader.set_uniform("u_roughness", self.roughness)
