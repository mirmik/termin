// Target-aware display color transform. The final OETF can be applied by
// the sRGB attachment or in the shader for a UNorm display sink.

import termin_prelude;

[[TerminScope("transient")]]
Sampler2D u_input;

struct OutputTransformParams {
    uint sampled_input_is_srgb;
    uint target_encoding_mode;
    float dither_step;
    uint dither_enabled;
};

[[TerminScope("pass")]]
ConstantBuffer<OutputTransformParams> u_params;

struct FragmentInput {
    float4 screen_pos : SV_Position;
    float2 uv : TEXCOORD0;
};

struct FragmentOutput {
    float4 color : SV_Target0;
};

float linear_to_srgb(float value) {
    value = max(value, 0.0);
    if (value <= 0.0031308) {
        return 12.92 * value;
    }
    return 1.055 * pow(value, 1.0 / 2.4) - 0.055;
}

float srgb_to_linear(float value) {
    value = max(value, 0.0);
    if (value <= 0.04045) {
        return value / 12.92;
    }
    return pow((value + 0.055) / 1.055, 2.4);
}

float3 linear_to_srgb(float3 value) {
    return float3(linear_to_srgb(value.r), linear_to_srgb(value.g), linear_to_srgb(value.b));
}

float3 srgb_to_linear(float3 value) {
    return float3(srgb_to_linear(value.r), srgb_to_linear(value.g), srgb_to_linear(value.b));
}

// Stable interleaved-gradient noise. Keeping it fixed in physical pixel space
// avoids temporal shimmer in editor UI and VR while decorrelating 8-bit
// quantization boundaries. One scalar is shared by RGB to avoid chromatic
// speckle.
float output_dither(float2 pixel_position) {
    float2 pixel = floor(pixel_position);
    return frac(52.9829189 * frac(dot(pixel, float2(0.06711056, 0.00583715)))) - 0.5;
}

[shader("fragment")]
FragmentOutput fs_main(FragmentInput input) {
    float4 sampled = u_input.Sample(input.uv);
    float3 linear = u_params.sampled_input_is_srgb != 0
                        ? srgb_to_linear(sampled.rgb)
                        : sampled.rgb;

    float noise = u_params.dither_enabled != 0
                      ? output_dither(input.screen_pos.xy) * u_params.dither_step
                      : 0.0;
    const uint linear_target = 0;
    const uint hardware_srgb_target = 1;
    float3 target_domain = u_params.target_encoding_mode != linear_target
                               ? linear_to_srgb(linear)
                               : linear;
    target_domain = clamp(target_domain + noise, 0.0, 1.0);

    // sRGB attachments expect linear shader output and encode on write. Move
    // the dithered target-domain value back to linear so that hardware
    // encoding lands on the intended 8-bit code.
    // A UNorm presentation sink stores the target-domain codes directly.
    float3 shader_output = u_params.target_encoding_mode == hardware_srgb_target
                               ? srgb_to_linear(target_domain)
                               : target_domain;

    FragmentOutput output;
    output.color = float4(shader_output, clamp(sampled.a, 0.0, 1.0));
    return output;
}
