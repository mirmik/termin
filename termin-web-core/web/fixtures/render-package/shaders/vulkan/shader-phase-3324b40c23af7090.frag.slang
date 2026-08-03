import termin_prelude;
struct MaterialParams {
    float4 u_tint_color;
};
[[TerminScope("material")]]
ConstantBuffer<MaterialParams> material;
[[TerminScope("material")]]
Sampler2D u_tint_texture;
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
