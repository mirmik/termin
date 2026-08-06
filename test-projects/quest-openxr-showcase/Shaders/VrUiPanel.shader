@program VrUiPanel
@language slang

@phase opaque
@priority 0
@glDepthTest true
@glDepthMask true
@glCull true

@property Texture2D u_panel_texture = "white" encoding(linear)

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
    output.world_pos = world.xyz;
    output.normal_world = normalize(mul((float3x3)u_model, input.normal));
    output.uv = input.uv;
    output.tangent_world = float3(0.0, 0.0, 0.0);
    output.bitangent_world = float3(0.0, 0.0, 0.0);
    output.tbn_valid = 0.0;
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

TerminStandardSurfaceV1 evaluate_standard_surface(FragmentInput input) {
    TerminStandardSurfaceV1 surface;
    float2 panel_uv = float2(input.uv.x, 1.0 - input.uv.y);
    float4 panel = u_panel_texture.Sample(panel_uv);
    surface.normal_world = normalize(input.normal_world);
    surface.base_color = panel.rgb * 0.08;
    surface.metallic = 0.0;
    surface.perceptual_roughness = 1.0;
    surface.occlusion = 1.0;
    surface.emission = panel.rgb * 1.35;
    surface.opacity = 1.0;
    return surface;
}
@endstage
