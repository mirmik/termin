@binding(179) @group(0) var u_input_texture_0 : texture_2d<f32>;

@binding(153) @group(0) var u_input_sampler_0 : sampler;

struct TonemapParams_std140_0
{
    @align(16) exposure_0 : f32,
    @align(4) method_0 : i32,
};

@binding(7) @group(0) var<uniform> u_params_0 : TonemapParams_std140_0;
fn aces_tonemap_0( x_0 : vec3<f32>) -> vec3<f32>
{
    return clamp(x_0 * (vec3<f32>(2.50999999046325684f) * x_0 + vec3<f32>(0.02999999932944775f)) / (x_0 * (vec3<f32>(2.43000006675720215f) * x_0 + vec3<f32>(0.5899999737739563f)) + vec3<f32>(0.14000000059604645f)), vec3<f32>(0.0f), vec3<f32>(1.0f));
}

fn reinhard_tonemap_0( x_1 : vec3<f32>) -> vec3<f32>
{
    return x_1 / (x_1 + vec3<f32>(1.0f, 1.0f, 1.0f));
}

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
    var color_1 : vec3<f32> = (textureSample((u_input_texture_0), (u_input_sampler_0), (_S1.uv_0))).xyz * vec3<f32>(u_params_0.exposure_0);
    var color_2 : vec3<f32>;
    if((u_params_0.method_0) == i32(0))
    {
        color_2 = aces_tonemap_0(color_1);
    }
    else
    {
        if((u_params_0.method_0) == i32(1))
        {
            color_2 = reinhard_tonemap_0(color_1);
        }
        else
        {
            color_2 = color_1;
        }
    }
    var output_0 : FragmentOutput_0;
    output_0.color_0 = vec4<f32>(color_2, 1.0f);
    return output_0;
}

