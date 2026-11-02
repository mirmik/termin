import termin_prelude;

struct HeatmapDraw {
    column_major float4x4 u_matrix;
    float4 u_range; // normalized display min/max, opacity, reserved
};
[[TerminScope("draw")]]
ConstantBuffer<HeatmapDraw> tcplot2d_heatmap_draw;
[[TerminScope("transient")]]
Sampler2D u_values;
[[TerminScope("transient")]]
Sampler2D u_palette;

struct VertexInput { float2 position : POSITION; };
struct VertexOutput { float4 position : SV_Position; float2 uv : TEXCOORD0; };
[shader("vertex")]
VertexOutput vs_main(VertexInput input) {
    VertexOutput output;
    output.position = termin_to_native_clip(mul(tcplot2d_heatmap_draw.u_matrix, float4(input.position, 0, 1)));
    output.uv = input.position;
    return output;
}
struct FragmentOutput { float4 color : SV_Target0; };
[shader("fragment")]
FragmentOutput fs_main(VertexOutput input) {
    // The filtered numerator and validity weight preserve missing cells without
    // allowing them to pull the interpolated scalar toward zero.
    float2 data = u_values.Sample(input.uv).rg;
    if (data.y <= 0) discard;
    float value = data.x / data.y;
    float denominator = tcplot2d_heatmap_draw.u_range.y - tcplot2d_heatmap_draw.u_range.x;
    float t = saturate((value - tcplot2d_heatmap_draw.u_range.x) / max(denominator, 1e-30));
    FragmentOutput output;
    // Palette texels contain linear colors sampled from the shared native map.
    output.color = u_palette.Sample(float2((t * 256.0 + 0.5) / 257.0, 0.5));
    output.color.a *= tcplot2d_heatmap_draw.u_range.z * data.y;
    return output;
}
