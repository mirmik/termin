struct _MatrixStorage_float4x4_ColMajorstd140_0
{
    @align(16) data_0 : array<vec4<f32>, i32(4)>,
};

struct MaterialParams_std140_0
{
    @align(16) u_inv_view_projection_0 : _MatrixStorage_float4x4_ColMajorstd140_0,
    @align(16) u_skybox_type_0 : i32,
    @align(16) u_skybox_color_0 : vec4<f32>,
    @align(16) u_skybox_top_color_0 : vec4<f32>,
    @align(16) u_skybox_horizon_color_0 : vec4<f32>,
    @align(16) u_skybox_bottom_color_0 : vec4<f32>,
    @align(16) u_skybox_top_exponent_0 : f32,
    @align(4) u_skybox_bottom_exponent_0 : f32,
};

@binding(8) @group(0) var<uniform> material_0 : MaterialParams_std140_0;
struct FragmentOutput_0
{
    @location(0) color_0 : vec4<f32>,
};

struct pixelInput_0
{
    @location(0) dir_0 : vec3<f32>,
};

@fragment
fn main( _S1 : pixelInput_0, @builtin(position) screen_pos_0 : vec4<f32>) -> FragmentOutput_0
{
    var output_0 : FragmentOutput_0;
    if((material_0.u_skybox_type_0) == i32(1))
    {
        output_0.color_0 = vec4<f32>(material_0.u_skybox_color_0.xyz, 1.0f);
    }
    else
    {
        var height_0 : f32 = clamp(normalize(_S1.dir_0).z, -1.0f, 1.0f);
        var color_1 : vec3<f32>;
        if(height_0 >= 0.0f)
        {
            color_1 = mix(material_0.u_skybox_horizon_color_0.xyz, material_0.u_skybox_top_color_0.xyz, vec3<f32>(pow(height_0, max(material_0.u_skybox_top_exponent_0, 0.00100000004749745f))));
        }
        else
        {
            color_1 = mix(material_0.u_skybox_horizon_color_0.xyz, material_0.u_skybox_bottom_color_0.xyz, vec3<f32>(pow(- height_0, max(material_0.u_skybox_bottom_exponent_0, 0.00100000004749745f))));
        }
        output_0.color_0 = vec4<f32>(color_1, 1.0f);
    }
    return output_0;
}

