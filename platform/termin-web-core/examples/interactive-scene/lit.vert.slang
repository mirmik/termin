import termin_prelude;

struct PerFrame {
    column_major float4x4 u_view;
    column_major float4x4 u_projection;
};
[[TerminScope("frame")]] ConstantBuffer<PerFrame> per_frame;

struct DrawData { column_major float4x4 u_model; };
[[TerminScope("draw")]] ConstantBuffer<DrawData> draw_data;

struct VertexInput {
    float3 position : POSITION;
    float3 normal : NORMAL;
};
struct VertexOutput {
    float4 position : SV_Position;
    float3 normal : TEXCOORD0;
    float3 world : TEXCOORD1;
    float3 center : TEXCOORD2;
};

[shader("vertex")]
VertexOutput main(VertexInput input) {
    VertexOutput output;
    float4 world = mul(draw_data.u_model, float4(input.position, 1));
    output.position = termin_to_native_clip(mul(per_frame.u_projection, mul(per_frame.u_view, world)));
    output.normal = normalize(mul((float3x3)draw_data.u_model, input.normal));
    output.world = world.xyz;
    output.center = mul(draw_data.u_model, float4(0, 0, 0, 1)).xyz;
    return output;
}
