@binding(186) @group(0) var u_original_texture_0 : texture_2d<f32>;

@binding(144) @group(0) var u_original_sampler_0 : sampler;

@binding(164) @group(0) var u_bloom_texture_0 : texture_2d<f32>;

@binding(166) @group(0) var u_bloom_sampler_0 : sampler;

struct BloomCompositeParams_std140_0
{
    @align(16) intensity_0 : f32,
};

@binding(7) @group(0) var<uniform> u_params_0 : BloomCompositeParams_std140_0;
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
    ;
    var original_0 : vec3<f32> = (textureSample((u_original_texture_0), (u_original_sampler_0), (_S1.uv_0))).xyz;
    ;
    var output_0 : FragmentOutput_0;
    output_0.color_0 = vec4<f32>(original_0 + (textureSample((u_bloom_texture_0), (u_bloom_sampler_0), (_S1.uv_0))).xyz * vec3<f32>(u_params_0.intensity_0), 1.0f);
    return output_0;
}

