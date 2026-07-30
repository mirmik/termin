@program CookTorrancePBR
@language slang

// ============================================================
// Standard metallic-roughness PBR surface producer
// ============================================================
//
// Lighting, shadows and final-color integration belong to the active pass.
// Artistic wrapped subsurface remains available as CookTorrancePBRSubsurface.
//
// ============================================================

@phases opaque, transparent

@settings transparent
@glDepthMask false
@glBlend true
@glCull true
@endsettings

@property Color u_color = Color(1.0, 1.0, 1.0, 1.0)
@property Float u_metallic = 0.0 range(0.0, 1.0)
@property Float u_roughness = 0.5 range(0.0, 1.0)
@property Color u_emission_color = Color(0.0, 0.0, 0.0, 1.0)
@property Float u_emission_intensity = 0.0 range(0.0, 100.0)
@property Texture2D u_albedo_texture = "white" encoding(srgb)
@property Texture2D u_normal_texture = "normal" encoding(linear)
@property Texture2D u_metallic_roughness_texture = "white" encoding(linear)
@property Texture2D u_occlusion_texture = "white" encoding(linear)
@property Texture2D u_emissive_texture = "white" encoding(srgb)
@property Float u_normal_strength = 1.0 range(0.0, 2.0)

@surface contract=termin.surface.standard-pbr version=1 type=TerminStandardSurfaceV1 entry=evaluate_standard_surface
@surfaceInput world_pos float3
@surfaceInput normal_world float3
@surfaceInput uv float2
@surfaceInput tangent_world float3
@surfaceInput bitangent_world float3
@surfaceInput tbn_valid float

@stage vertex
import termin_prelude;

struct VertexInput {
    float3 position : POSITION;
    float3 normal : NORMAL;
    float2 uv : TEXCOORD0;
    float4 tangent : TANGENT;
};

struct VertexOutput {
    float4 position : SV_Position;
    float3 world_pos : TEXCOORD0;
    float3 normal_world : TEXCOORD1;
    float2 uv : TEXCOORD2;
    float3 tangent_world : TEXCOORD3;
    float3 bitangent_world : TEXCOORD4;
    float tbn_valid : TEXCOORD5;
};

[shader("vertex")]
VertexOutput main(VertexInput input) {
    VertexOutput output;
    float4 world = mul(u_model, float4(input.position, 1.0));
    float3x3 normal_matrix = (float3x3)u_model;
    float3 N = normalize(mul(normal_matrix, input.normal));

    output.world_pos = world.xyz;
    output.normal_world = N;
    output.uv = input.uv;
    output.tangent_world = float3(0.0, 0.0, 0.0);
    output.bitangent_world = float3(0.0, 0.0, 0.0);
    output.tbn_valid = 0.0;

    float tangent_len = length(input.tangent.xyz);
    if (tangent_len > 0.001) {
        float3 T = normalize(mul(normal_matrix, input.tangent.xyz));
        T = normalize(T - dot(T, N) * N);
        float3 B = cross(N, T) * input.tangent.w;

        output.tangent_world = T;
        output.bitangent_world = B;
        output.tbn_valid = 1.0;
    }

    output.position = termin_to_native_clip(mul(u_projection, mul(u_view, world)));
    return output;
}
@endstage

@stage fragment
struct FragmentInput {
    float4 screen_pos : SV_Position;
    float3 world_pos : TEXCOORD0;
    float3 normal_world : TEXCOORD1;
    float2 uv : TEXCOORD2;
    float3 tangent_world : TEXCOORD3;
    float3 bitangent_world : TEXCOORD4;
    float tbn_valid : TEXCOORD5;
};

float3 get_normal_from_map(FragmentInput input) {
    float3 normal_sample = u_normal_texture.Sample(input.uv).rgb;
    float3 tangent_normal = normal_sample * 2.0 - 1.0;
    tangent_normal.xy *= material.u_normal_strength;
    tangent_normal = normalize(tangent_normal);

    float3 T = normalize(input.tangent_world);
    float3 B = normalize(input.bitangent_world);
    float3 N = normalize(input.normal_world);
    return normalize(
        T * tangent_normal.x +
        B * tangent_normal.y +
        N * tangent_normal.z);
}

TerminStandardSurfaceV1 evaluate_standard_surface(FragmentInput input) {
    TerminStandardSurfaceV1 surface;
    if (input.tbn_valid > 0.001 && material.u_normal_strength > 0.0) {
        surface.normal_world = get_normal_from_map(input);
    } else {
        surface.normal_world = normalize(input.normal_world);
    }

    float4 tex_color = u_albedo_texture.Sample(input.uv);
    float4 metallic_roughness_sample =
        u_metallic_roughness_texture.Sample(input.uv);
    surface.base_color =
        material.u_color.rgb * tex_color.rgb;
    surface.metallic = saturate(
        material.u_metallic * metallic_roughness_sample.b);
    surface.perceptual_roughness = max(
        saturate(material.u_roughness * metallic_roughness_sample.g),
        0.04);
    surface.occlusion = saturate(
        u_occlusion_texture.Sample(input.uv).r);
    surface.emission =
        u_emissive_texture.Sample(input.uv).rgb *
        material.u_emission_color.rgb *
        material.u_emission_intensity;
    surface.opacity = saturate(
        material.u_color.a * tex_color.a);
    return surface;
}
@endstage

// ============================================================
// Shadow caster phase
// ============================================================

@phase shadow
@priority 0
@glDepthTest true
@glDepthMask true
@glCull true

@stage vertex
import termin_prelude;

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
    output.position = termin_to_native_clip(mul(u_projection, mul(u_view, world)));
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
