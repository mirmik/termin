@binding(156) @group(0) var u_font_atlas_texture_0 : texture_2d<f32>;

@binding(190) @group(0) var u_font_atlas_sampler_0 : sampler;

struct _MatrixStorage_float4x4_ColMajorstd140_0
{
    @align(16) data_0 : array<vec4<f32>, i32(4)>,
};

struct Text3DPush_std140_0
{
    @align(16) u_mvp_0 : _MatrixStorage_float4x4_ColMajorstd140_0,
    @align(16) u_color_0 : vec4<f32>,
    @align(16) u_cam_right_0 : vec4<f32>,
    @align(16) u_cam_up_0 : vec4<f32>,
    @align(16) u_flags_0 : vec4<f32>,
};

@binding(28) @group(0) var<uniform> text3d_draw_0 : Text3DPush_std140_0;
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
    var sample_0 : f32 = (textureSample((u_font_atlas_texture_0), (u_font_atlas_sampler_0), (_S1.uv_0))).x;
    var glyph_alpha_0 : f32;
    if((text3d_draw_0.u_flags_0.w) != 0.0f)
    {
        glyph_alpha_0 = smoothstep(0.5f - text3d_draw_0.u_flags_0.w, 0.5f + text3d_draw_0.u_flags_0.w, sample_0);
    }
    else
    {
        glyph_alpha_0 = sample_0;
    }
    var a_0 : f32 = glyph_alpha_0 * text3d_draw_0.u_color_0.w;
    if(a_0 < 0.00392156885936856f)
    {
        discard;
    }
    output_0.color_0 = vec4<f32>(text3d_draw_0.u_color_0.xyz, a_0);
    return output_0;
}

