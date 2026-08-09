@program WebTextured
@language slang

@phase opaque
@priority 0
@glDepthTest true
@glDepthMask true
@glCull false

@property SrgbColor u_tint_color = SrgbColor(1.0, 1.0, 1.0, 1.0)
@property Texture2D u_tint_texture = "white" encoding(srgb)

@stage vertex
import termin_prelude;

struct PerFrame
{
    column_major float4x4 u_view;
    column_major float4x4 u_projection;
    column_major float4x4 u_view_projection;
    column_major float4x4 u_inv_view;
    column_major float4x4 u_inv_proj;
    float4 u_camera_position;
    float2 u_resolution;
    float u_near;
    float u_far;
};

[[TerminScope("frame")]]
ConstantBuffer<PerFrame> per_frame;

struct DrawData
{
    column_major float4x4 u_model;
};

[[TerminScope("draw")]]
ConstantBuffer<DrawData> draw_data;

struct VertexInput
{
    float3 position : POSITION;
    float3 normal : NORMAL;
    float2 uv : TEXCOORD0;
};

struct VertexOutput
{
    float4 position : SV_Position;
    float2 uv : TEXCOORD0;
};

[shader("vertex")]
VertexOutput main(VertexInput input)
{
    VertexOutput output;
    float4 world = mul(draw_data.u_model, float4(input.position, 1.0));
    output.position = termin_to_native_clip(
        mul(per_frame.u_projection, mul(per_frame.u_view, world)));
    output.uv = input.uv;
    return output;
}
@endstage

@stage fragment
struct FragmentInput
{
    float4 screen_pos : SV_Position;
    float2 uv : TEXCOORD0;
};

struct FragmentOutput
{
    float4 color : SV_Target0;
};

[shader("fragment")]
FragmentOutput main(FragmentInput input)
{
    FragmentOutput output;
    output.color = u_tint_texture.Sample(input.uv) * material.u_tint_color;
    return output;
}
@endstage
