@binding(188) @group(0) var u_texture_texture_0 : texture_2d<f32>;

@binding(190) @group(0) var u_texture_sampler_0 : sampler;

struct _MatrixStorage_float4x4_ColMajorstd140_0
{
    @align(16) data_0 : array<vec4<f32>, i32(4)>,
};

struct CanvasPushData_std140_0
{
    @align(16) u_projection_0 : _MatrixStorage_float4x4_ColMajorstd140_0,
    @align(16) u_color_0 : vec4<f32>,
};

@binding(20) @group(0) var<uniform> canvas_draw_0 : CanvasPushData_std140_0;
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
    output_0.color_0 = (textureSample((u_texture_texture_0), (u_texture_sampler_0), (_S1.uv_0))) * canvas_draw_0.u_color_0;
    return output_0;
}

