@binding(156) @group(0) var u_font_atlas_texture_0 : texture_2d<f32>;

@binding(190) @group(0) var u_font_atlas_sampler_0 : sampler;

struct _MatrixStorage_float4x4_ColMajorstd140_0
{
    @align(16) data_0 : array<vec4<f32>, i32(4)>,
};

struct Text2DSdfPushData_std140_0
{
    @align(16) u_projection_0 : _MatrixStorage_float4x4_ColMajorstd140_0,
    @align(16) u_color_0 : vec4<f32>,
    @align(16) u_smoothing_0 : f32,
};

@binding(31) @group(0) var<uniform> text2d_sdf_draw_0 : Text2DSdfPushData_std140_0;
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
    var output_0 : FragmentOutput_0;
    ;
    var a_0 : f32 = smoothstep(0.5f - text2d_sdf_draw_0.u_smoothing_0, 0.5f + text2d_sdf_draw_0.u_smoothing_0, (textureSample((u_font_atlas_texture_0), (u_font_atlas_sampler_0), (_S1.uv_0))).x) * text2d_sdf_draw_0.u_color_0.w;
    if(a_0 < 0.00392156885936856f)
    {
        discard;
    }
    output_0.color_0 = vec4<f32>(text2d_sdf_draw_0.u_color_0.xyz, a_0);
    return output_0;
}

