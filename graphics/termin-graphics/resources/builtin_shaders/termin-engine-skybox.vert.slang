struct MaterialParams {
    column_major float4x4 u_inv_view_projection;
    int u_skybox_type;
    float4 u_skybox_color;
    float4 u_skybox_top_color;
    float4 u_skybox_horizon_color;
    float4 u_skybox_bottom_color;
    float u_skybox_top_exponent;
    float u_skybox_bottom_exponent;
};
[[TerminScope("material")]]
ConstantBuffer<MaterialParams> material;
import termin_prelude;

struct VertexInput {
    float2 position : POSITION;
};

struct VertexOutput {
    float4 position : SV_Position;
    float3 dir : TEXCOORD0;
};

[shader("vertex")]
VertexOutput main(VertexInput input) {
    VertexOutput output;
    float4 near_h = mul(
        material.u_inv_view_projection,
        float4(input.position, 0.0, 1.0));
    float4 far_h = mul(
        material.u_inv_view_projection,
        float4(input.position, 1.0, 1.0));
    float3 near_world = near_h.xyz / near_h.w;
    float3 far_world = far_h.xyz / far_h.w;
    output.dir = far_world - near_world;
    output.position = termin_to_native_clip(
        float4(input.position, 0.0, 1.0));
    return output;
}
