struct BloomBrightParams_std140_0
{
    @align(16) texel_size_0 : vec2<f32>,
    @align(8) threshold_0 : f32,
    @align(4) soft_threshold_0 : f32,
};

@binding(7) @group(0) var<uniform> u_params_0 : BloomBrightParams_std140_0;
@binding(188) @group(0) var u_texture_texture_0 : texture_2d<f32>;

@binding(190) @group(0) var u_texture_sampler_0 : sampler;

struct FragmentOutput_0
{
    @location(0) color_0 : vec4<f32>,
};

struct pixelInput_0
{
    @location(0) uv_0 : vec2<f32>,
};

@fragment
fn fs_main( _S1 : pixelInput_0, @builtin(position) screen_pos_0 : vec4<f32>) -> FragmentOutput_0
{
    var offset_0 : vec2<f32> = u_params_0.texel_size_0 * vec2<f32>(1.20000004768371582f);
    var _S2 : f32 = offset_0.x;
    var _S3 : f32 = - _S2;
    var _S4 : f32 = offset_0.y;
    var _S5 : f32 = - _S4;
    var _S6 : vec2<f32> = _S1.uv_0 + vec2<f32>(_S3, _S5);
    ;
    var a_0 : vec3<f32> = (textureSample((u_texture_texture_0), (u_texture_sampler_0), (_S6))).xyz;
    var _S7 : vec2<f32> = _S1.uv_0 + vec2<f32>(0.0f, _S5);
    ;
    var b_0 : vec3<f32> = (textureSample((u_texture_texture_0), (u_texture_sampler_0), (_S7))).xyz;
    var _S8 : vec2<f32> = _S1.uv_0 + vec2<f32>(_S2, _S5);
    ;
    var c_0 : vec3<f32> = (textureSample((u_texture_texture_0), (u_texture_sampler_0), (_S8))).xyz;
    var _S9 : vec2<f32> = _S1.uv_0 + vec2<f32>(_S3, 0.0f);
    ;
    var d_0 : vec3<f32> = (textureSample((u_texture_texture_0), (u_texture_sampler_0), (_S9))).xyz;
    ;
    var e_0 : vec3<f32> = (textureSample((u_texture_texture_0), (u_texture_sampler_0), (_S1.uv_0))).xyz;
    var _S10 : vec2<f32> = _S1.uv_0 + vec2<f32>(_S2, 0.0f);
    ;
    var f_0 : vec3<f32> = (textureSample((u_texture_texture_0), (u_texture_sampler_0), (_S10))).xyz;
    var _S11 : vec2<f32> = _S1.uv_0 + vec2<f32>(_S3, _S4);
    ;
    var g_0 : vec3<f32> = (textureSample((u_texture_texture_0), (u_texture_sampler_0), (_S11))).xyz;
    var _S12 : vec2<f32> = _S1.uv_0 + vec2<f32>(0.0f, _S4);
    ;
    var h_0 : vec3<f32> = (textureSample((u_texture_texture_0), (u_texture_sampler_0), (_S12))).xyz;
    var _S13 : vec2<f32> = _S1.uv_0 + vec2<f32>(_S2, _S4);
    ;
    var color_1 : vec3<f32> = (a_0 + c_0 + g_0 + (textureSample((u_texture_texture_0), (u_texture_sampler_0), (_S13))).xyz) * vec3<f32>(0.09765625f) + (b_0 + d_0 + f_0 + h_0) * vec3<f32>(0.1171875f) + e_0 * vec3<f32>(0.140625f);
    var _S14 : f32 = max(color_1.x, max(color_1.y, color_1.z));
    var knee_0 : f32 = u_params_0.threshold_0 * u_params_0.soft_threshold_0;
    var soft_0 : f32 = clamp(_S14 - u_params_0.threshold_0 + knee_0, 0.0f, 2.0f * knee_0);
    var output_0 : FragmentOutput_0;
    output_0.color_0 = vec4<f32>(max(color_1, vec3<f32>(0.0f, 0.0f, 0.0f)) * vec3<f32>(max(max(soft_0 * soft_0 / (4.0f * knee_0 + 0.00000999999974738f), _S14 - u_params_0.threshold_0) / max(_S14, 0.00000999999974738f), 0.0f)), 1.0f);
    return output_0;
}

