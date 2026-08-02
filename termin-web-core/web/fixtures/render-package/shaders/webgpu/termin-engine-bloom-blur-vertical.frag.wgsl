struct BloomBlurParams_std140_0
{
    @align(16) texel_size_0 : vec2<f32>,
};

@binding(7) @group(0) var<uniform> u_params_0 : BloomBlurParams_std140_0;
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
    var offset_0 : f32 = u_params_0.texel_size_0.y;
    var _S2 : vec2<f32> = _S1.uv_0 + vec2<f32>(0.0f, -3.23076915740966797f * offset_0);
    ;
    var _S3 : vec3<f32> = vec3<f32>(0.07027027010917664f);
    var result_0 : vec3<f32> = (textureSample((u_texture_texture_0), (u_texture_sampler_0), (_S2))).xyz * _S3;
    var _S4 : vec2<f32> = _S1.uv_0 + vec2<f32>(0.0f, -1.38461542129516602f * offset_0);
    ;
    var _S5 : vec3<f32> = vec3<f32>(0.31621623039245605f);
    var result_1 : vec3<f32> = result_0 + (textureSample((u_texture_texture_0), (u_texture_sampler_0), (_S4))).xyz * _S5;
    ;
    var result_2 : vec3<f32> = result_1 + (textureSample((u_texture_texture_0), (u_texture_sampler_0), (_S1.uv_0))).xyz * vec3<f32>(0.22702702879905701f);
    var _S6 : vec2<f32> = _S1.uv_0 + vec2<f32>(0.0f, 1.38461542129516602f * offset_0);
    ;
    var result_3 : vec3<f32> = result_2 + (textureSample((u_texture_texture_0), (u_texture_sampler_0), (_S6))).xyz * _S5;
    var _S7 : vec2<f32> = _S1.uv_0 + vec2<f32>(0.0f, 3.23076915740966797f * offset_0);
    ;
    var output_0 : FragmentOutput_0;
    output_0.color_0 = vec4<f32>(result_3 + (textureSample((u_texture_texture_0), (u_texture_sampler_0), (_S7))).xyz * _S3, 1.0f);
    return output_0;
}

