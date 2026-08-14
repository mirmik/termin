@binding(188) @group(0) var u_texture_texture_0 : texture_2d<f32>;

@binding(190) @group(0) var u_texture_sampler_0 : sampler;

struct FragmentOutput_0
{
    @location(0) color_0 : vec4<f32>,
};

struct pixelInput_0
{
    @location(0) uv_0 : vec2<f32>,
    @location(1) tint_0 : vec4<f32>,
};

@fragment
fn fs_main( _S1 : pixelInput_0, @builtin(position) position_0 : vec4<f32>) -> FragmentOutput_0
{
    var output_0 : FragmentOutput_0;
    ;
    output_0.color_0 = (textureSample((u_texture_texture_0), (u_texture_sampler_0), (_S1.uv_0))) * _S1.tint_0;
    return output_0;
}

