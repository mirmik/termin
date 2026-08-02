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

@fragment
fn fs_main() -> FragmentOutput_0
{
    var output_0 : FragmentOutput_0;
    output_0.color_0 = canvas_draw_0.u_color_0;
    return output_0;
}

