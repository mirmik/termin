import termin_prelude;

[[TerminScope("transient")]]
Sampler2D u_tex;

struct FrameGraphPresenterPushData {
    int channel_mode;
    int highlight_hdr;
    int _pad0;
    int _pad1;
};

[[TerminScope("draw")]]
ConstantBuffer<FrameGraphPresenterPushData> presenter_draw;

struct FragmentInput {
    float4 screen_pos : SV_Position;
    float2 uv : TEXCOORD0;
};

struct FragmentOutput {
    float4 color : SV_Target0;
};

[shader("fragment")]
FragmentOutput fs_main(FragmentInput input) {
    float4 sampled = u_tex.Sample(input.uv);
    float3 result;
    if (presenter_draw.channel_mode == 5) {
        result = float3(pow(clamp(1.0 - sampled.r, 0.0, 1.0), 0.25));
    } else if (presenter_draw.channel_mode == 1) {
        result = float3(sampled.r);
    } else if (presenter_draw.channel_mode == 2) {
        result = float3(sampled.g);
    } else if (presenter_draw.channel_mode == 3) {
        result = float3(sampled.b);
    } else if (presenter_draw.channel_mode == 4) {
        result = float3(sampled.a);
    } else {
        result = sampled.rgb;
    }

    if (presenter_draw.highlight_hdr == 1) {
        float max_value = max(max(sampled.r, sampled.g), sampled.b);
        if (max_value > 1.0) {
            float intensity = clamp((max_value - 1.0) / 2.0, 0.0, 1.0);
            result = lerp(result, float3(1.0, 0.0, 1.0), 0.5 + intensity * 0.5);
        }
    }

    FragmentOutput output;
    output.color = float4(result, 1.0);
    return output;
}
