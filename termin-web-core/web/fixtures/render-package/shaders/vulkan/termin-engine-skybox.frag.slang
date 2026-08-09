import termin_prelude;
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
struct FragmentInput {
    float4 screen_pos : SV_Position;
    float3 dir : TEXCOORD0;
};

struct FragmentOutput {
    float4 color : SV_Target0;
};

[shader("fragment")]
FragmentOutput main(FragmentInput input) {
    FragmentOutput output;
    if (material.u_skybox_type == 1) {
        output.color = float4(material.u_skybox_color.rgb, 1.0);
    } else {
        float height = clamp(normalize(input.dir).z, -1.0, 1.0);
        float3 color;
        if (height >= 0.0) {
            float t = pow(height, max(material.u_skybox_top_exponent, 0.001));
            color = lerp(
                material.u_skybox_horizon_color.rgb,
                material.u_skybox_top_color.rgb,
                t);
        } else {
            float t = pow(-height, max(material.u_skybox_bottom_exponent, 0.001));
            color = lerp(
                material.u_skybox_horizon_color.rgb,
                material.u_skybox_bottom_color.rgb,
                t);
        }
        output.color = float4(color, 1.0);
    }
    return output;
}
