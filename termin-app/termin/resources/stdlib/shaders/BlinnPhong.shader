@program BlinnPhong
@language slang
@features lighting_ubo

// ============================================================
// Blinn-Phong Shader - Canonical Implementation
// ============================================================
//
// Classic Blinn-Phong illumination model:
//   I = Ka*Ia + Kd*Id*(N dot L) + Ks*Is*(N dot H)^n
//
// ============================================================

@phase opaque
@priority 0
@glDepthTest true
@glDepthMask true
@glCull true

@property Color u_diffuse_color = Color(1.0, 1.0, 1.0, 1.0)
@property Color u_specular_color = Color(1.0, 1.0, 1.0, 1.0)
@property Float u_ambient_factor = 1.0 range(0.0, 1.0)
@property Float u_shininess = 32.0 range(1.0, 256.0)
@property Texture2D u_diffuse_texture = "white"

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
    float3x3 normal_matrix = (float3x3)u_model;

    output.world_pos = world.xyz;
    output.normal_world = normalize(mul(normal_matrix, input.normal));
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

float compute_distance_attenuation(float3 attenuation, float range, float dist) {
    float denom = attenuation.x + attenuation.y * dist + attenuation.z * dist * dist;
    if (denom <= 0.0) {
        return 1.0;
    }
    float weight = 1.0 / denom;
    if (range > 0.0 && dist > range) {
        weight = 0.0;
    }
    return weight;
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

[shader("fragment")]
FragmentOutput main(FragmentInput input) {
    FragmentOutput output;

    float3 N = normalize(input.normal_world);
    float3 V = normalize(get_camera_position() - input.world_pos);

    float4 tex_color = u_diffuse_texture.Sample(input.uv);
    float3 Kd = material.u_diffuse_color.rgb * tex_color.rgb;
    float3 Ks = material.u_specular_color.rgb;
    float alpha = material.u_diffuse_color.a * tex_color.a;

    float3 ambient =
        Kd * material.u_ambient_factor * get_ambient_color() * get_ambient_intensity();

    float3 diffuse_sum = float3(0.0, 0.0, 0.0);
    float3 specular_sum = float3(0.0, 0.0, 0.0);

    for (int i = 0; i < get_light_count(); ++i) {
        float3 L;
        float attenuation = 1.0;

        if (get_light_type(i) == LIGHT_TYPE_DIRECTIONAL) {
            L = normalize(-get_light_direction(i));
        } else {
            float3 to_light = get_light_position(i) - input.world_pos;
            float dist = length(to_light);
            L = to_light / max(dist, 0.0001);

            attenuation =
                compute_distance_attenuation(get_light_attenuation(i), get_light_range(i), dist);

            if (get_light_type(i) == LIGHT_TYPE_SPOT) {
                attenuation *= compute_spot_weight(
                    get_light_direction(i),
                    L,
                    get_light_inner_angle(i),
                    get_light_outer_angle(i));
            }
        }

        float shadow = 1.0;
        if (get_light_type(i) == LIGHT_TYPE_DIRECTIONAL) {
            shadow = compute_shadow_auto(i, input.world_pos);
        }

        float3 light_intensity =
            get_light_color(i) * get_light_intensity(i) * attenuation * shadow;

        float NdotL = max(dot(N, L), 0.0);
        diffuse_sum += Kd * light_intensity * NdotL;

        if (NdotL > 0.0) {
            float3 H = normalize(L + V);
            float NdotH = max(dot(N, H), 0.0);
            float specular = pow(NdotH, material.u_shininess);
            specular_sum += Ks * light_intensity * specular;
        }
    }

    output.color = float4(ambient + diffuse_sum + specular_sum, alpha);
    return output;
}
@endstage

@endphase

// ============================================================
// Shadow caster phase
// ============================================================

@phase shadow
@priority 0
@glDepthTest true
@glDepthMask true
@glCull true

@stage vertex
struct ShadowVertexInput {
    float3 position : POSITION;
};

struct ShadowVertexOutput {
    float4 position : SV_Position;
};

[shader("vertex")]
ShadowVertexOutput main(ShadowVertexInput input) {
    ShadowVertexOutput output;
    float4 world = mul(u_model, float4(input.position, 1.0));
    output.position = mul(u_projection, mul(u_view, world));
    return output;
}
@endstage

@stage fragment
struct ShadowFragmentInput {
    float4 position : SV_Position;
};

struct ShadowFragmentOutput {
    float4 color : SV_Target0;
};

[shader("fragment")]
ShadowFragmentOutput main(ShadowFragmentInput input) {
    ShadowFragmentOutput output;
    output.color = float4(input.position.z, 0.0, 0.0, 1.0);
    return output;
}
@endstage

@endphase
