@binding(179) @group(0) var u_input_texture_0 : texture_2d<f32>;

@binding(153) @group(0) var u_input_sampler_0 : sampler;

struct GrayscaleParams_std140_0
{
    @align(16) strength_0 : f32,
};

@binding(7) @group(0) var<uniform> u_params_0 : GrayscaleParams_std140_0;
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
    var color_1 : vec3<f32> = (textureSample((u_input_texture_0), (u_input_sampler_0), (_S1.uv_0))).xyz;
    var gray_0 : f32 = dot(color_1, vec3<f32>(0.2125999927520752f, 0.71520000696182251f, 0.07220000028610229f));
    var output_0 : FragmentOutput_0;
    output_0.color_0 = vec4<f32>(mix(color_1, vec3<f32>(gray_0, gray_0, gray_0), vec3<f32>(u_params_0.strength_0)), 1.0f);
    return output_0;
}

