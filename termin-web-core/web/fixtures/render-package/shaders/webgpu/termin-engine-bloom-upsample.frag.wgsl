struct BloomUpsampleParams_std140_0
{
    @align(16) texel_size_0 : vec2<f32>,
    @align(8) scatter_0 : f32,
};

@binding(7) @group(0) var<uniform> u_params_0 : BloomUpsampleParams_std140_0;
@binding(153) @group(0) var u_low_texture_0 : texture_2d<f32>;

@binding(147) @group(0) var u_low_sampler_0 : sampler;

@binding(181) @group(0) var u_high_texture_0 : texture_2d<f32>;

@binding(167) @group(0) var u_high_sampler_0 : sampler;

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
    var a_0 : vec3<f32> = (textureSample((u_low_texture_0), (u_low_sampler_0), (_S6))).xyz;
    var _S7 : vec2<f32> = _S1.uv_0 + vec2<f32>(0.0f, _S5);
    ;
    var b_0 : vec3<f32> = (textureSample((u_low_texture_0), (u_low_sampler_0), (_S7))).xyz;
    var _S8 : vec2<f32> = _S1.uv_0 + vec2<f32>(_S2, _S5);
    ;
    var c_0 : vec3<f32> = (textureSample((u_low_texture_0), (u_low_sampler_0), (_S8))).xyz;
    var _S9 : vec2<f32> = _S1.uv_0 + vec2<f32>(_S3, 0.0f);
    ;
    var d_0 : vec3<f32> = (textureSample((u_low_texture_0), (u_low_sampler_0), (_S9))).xyz;
    ;
    var e_0 : vec3<f32> = (textureSample((u_low_texture_0), (u_low_sampler_0), (_S1.uv_0))).xyz;
    var _S10 : vec2<f32> = _S1.uv_0 + vec2<f32>(_S2, 0.0f);
    ;
    var f_0 : vec3<f32> = (textureSample((u_low_texture_0), (u_low_sampler_0), (_S10))).xyz;
    var _S11 : vec2<f32> = _S1.uv_0 + vec2<f32>(_S3, _S4);
    ;
    var g_0 : vec3<f32> = (textureSample((u_low_texture_0), (u_low_sampler_0), (_S11))).xyz;
    var _S12 : vec2<f32> = _S1.uv_0 + vec2<f32>(0.0f, _S4);
    ;
    var h_0 : vec3<f32> = (textureSample((u_low_texture_0), (u_low_sampler_0), (_S12))).xyz;
    var _S13 : vec2<f32> = _S1.uv_0 + vec2<f32>(_S2, _S4);
    ;
    var low_0 : vec3<f32> = (a_0 + c_0 + g_0 + (textureSample((u_low_texture_0), (u_low_sampler_0), (_S13))).xyz) * vec3<f32>(0.09765625f) + (b_0 + d_0 + f_0 + h_0) * vec3<f32>(0.1171875f) + e_0 * vec3<f32>(0.140625f);
    ;
    var output_0 : FragmentOutput_0;
    output_0.color_0 = vec4<f32>(mix((textureSample((u_high_texture_0), (u_high_sampler_0), (_S1.uv_0))).xyz, low_0, vec3<f32>(u_params_0.scatter_0)), 1.0f);
    return output_0;
}

