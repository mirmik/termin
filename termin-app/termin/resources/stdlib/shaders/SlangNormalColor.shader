@program SlangNormalColor
@language slang

@phase opaque
@priority 0
@glDepthTest true
@glDepthMask true
@glCull true

@stage vertex
struct PerFrame
{
    float4x4 u_view;
    float4x4 u_projection;
    float4x4 u_view_projection;
    float4x4 u_inv_view;
    float4x4 u_inv_proj;
    float4 u_camera_position;
    float2 u_resolution;
    float u_near;
    float u_far;
};

[[vk::binding(2, 0)]]
ConstantBuffer<PerFrame> per_frame;

struct ColorPushData
{
    float4x4 u_model;
};

[[vk::push_constant]]
ConstantBuffer<ColorPushData> pc;

struct VertexInput
{
    [[vk::location(0)]]
    float3 position : POSITION;

    [[vk::location(1)]]
    float3 normal : NORMAL;
};

struct VertexOutput
{
    float4 position : SV_Position;

    [[vk::location(0)]]
    float3 normal_world : NORMAL;
};

[shader("vertex")]
VertexOutput main(VertexInput input)
{
    VertexOutput output;
    float4 world = mul(pc.u_model, float4(input.position, 1.0));
    output.position = mul(per_frame.u_projection, mul(per_frame.u_view, world));
    output.normal_world = mul((float3x3)pc.u_model, input.normal);
    return output;
}
@endstage

@stage fragment
struct FragmentInput
{
    [[vk::location(0)]]
    float3 normal_world : NORMAL;
};

struct FragmentOutput
{
    [[vk::location(0)]]
    float4 color : SV_Target0;
};

[shader("fragment")]
FragmentOutput main(FragmentInput input)
{
    FragmentOutput output;
    float3 n = normalize(input.normal_world);
    output.color = float4(n * 0.5 + 0.5, 1.0);
    return output;
}
@endstage
