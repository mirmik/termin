@binding(96) @group(0) var u_tint_texture_texture_0 : texture_2d<f32>;

@binding(106) @group(0) var u_tint_texture_sampler_0 : sampler;

struct MaterialParams_std140_0
{
    @align(16) u_tint_color_0 : vec4<f32>,
};

@binding(8) @group(0) var<uniform> material_0 : MaterialParams_std140_0;
struct FragmentOutput_0
{
    @location(0) color_0 : vec4<f32>,
};

struct pixelInput_0
{
    @location(0) uv_0 : vec2<f32>,
};

@fragment
fn main( _S1 : pixelInput_0, @builtin(position) screen_pos_0 : vec4<f32>) -> FragmentOutput_0
{
    var output_0 : FragmentOutput_0;
    ;
    output_0.color_0 = (textureSample((u_tint_texture_texture_0), (u_tint_texture_sampler_0), (_S1.uv_0))) * material_0.u_tint_color_0;
    return output_0;
}

