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
fn termin_to_native_clip_0( clip_0 : vec4<f32>) -> vec4<f32>
{
    var _S1 : vec4<f32> = clip_0;
    _S1[i32(1)] = - clip_0.y;
    return _S1;
}

struct VertexOutput_0
{
    @builtin(position) pos_0 : vec4<f32>,
    @location(0) uv_0 : vec2<f32>,
};

struct vertexInput_0
{
    @location(0) pos_1 : vec3<f32>,
    @location(1) uv_pad_0 : vec4<f32>,
};

@vertex
fn vs_main( _S2 : vertexInput_0) -> VertexOutput_0
{
    var output_0 : VertexOutput_0;
    output_0.pos_0 = termin_to_native_clip_0((((vec4<f32>(_S2.pos_1.xy, 0.0f, 1.0f)) * (mat4x4<f32>(text2d_sdf_draw_0.u_projection_0.data_0[i32(0)][i32(0)], text2d_sdf_draw_0.u_projection_0.data_0[i32(1)][i32(0)], text2d_sdf_draw_0.u_projection_0.data_0[i32(2)][i32(0)], text2d_sdf_draw_0.u_projection_0.data_0[i32(3)][i32(0)], text2d_sdf_draw_0.u_projection_0.data_0[i32(0)][i32(1)], text2d_sdf_draw_0.u_projection_0.data_0[i32(1)][i32(1)], text2d_sdf_draw_0.u_projection_0.data_0[i32(2)][i32(1)], text2d_sdf_draw_0.u_projection_0.data_0[i32(3)][i32(1)], text2d_sdf_draw_0.u_projection_0.data_0[i32(0)][i32(2)], text2d_sdf_draw_0.u_projection_0.data_0[i32(1)][i32(2)], text2d_sdf_draw_0.u_projection_0.data_0[i32(2)][i32(2)], text2d_sdf_draw_0.u_projection_0.data_0[i32(3)][i32(2)], text2d_sdf_draw_0.u_projection_0.data_0[i32(0)][i32(3)], text2d_sdf_draw_0.u_projection_0.data_0[i32(1)][i32(3)], text2d_sdf_draw_0.u_projection_0.data_0[i32(2)][i32(3)], text2d_sdf_draw_0.u_projection_0.data_0[i32(3)][i32(3)])))));
    output_0.uv_0 = _S2.uv_pad_0.xy;
    return output_0;
}

