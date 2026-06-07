struct FragmentInput
{
    [[vk::location(0)]]
    float3 color : COLOR0;
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
    output.color = float4(input.color, 1.0);
    return output;
}
