struct _MatrixStorage_float4x4_ColMajorstd140_0
{
    @align(16) data_0 : array<vec4<f32>, i32(4)>,
};

struct World2DFrame_std140_0
{
    @align(16) view_projection_0 : _MatrixStorage_float4x4_ColMajorstd140_0,
};

@binding(31) @group(0) var<uniform> world2d_frame_0 : World2DFrame_std140_0;
fn termin_to_native_clip_0( clip_0 : vec4<f32>) -> vec4<f32>
{
    var _S1 : vec4<f32> = clip_0;
    _S1[i32(1)] = - clip_0.y;
    return _S1;
}

struct VertexOutput_0
{
    @builtin(position) position_0 : vec4<f32>,
    @location(0) uv_0 : vec2<f32>,
    @location(1) tint_0 : vec4<f32>,
};

struct vertexInput_0
{
    @location(0) position_1 : vec3<f32>,
    @location(1) uv_1 : vec2<f32>,
    @location(2) tint_1 : vec4<f32>,
};

@vertex
fn vs_main( _S2 : vertexInput_0) -> VertexOutput_0
{
    var output_0 : VertexOutput_0;
    output_0.position_0 = termin_to_native_clip_0((((vec4<f32>(_S2.position_1, 1.0f)) * (mat4x4<f32>(world2d_frame_0.view_projection_0.data_0[i32(0)][i32(0)], world2d_frame_0.view_projection_0.data_0[i32(1)][i32(0)], world2d_frame_0.view_projection_0.data_0[i32(2)][i32(0)], world2d_frame_0.view_projection_0.data_0[i32(3)][i32(0)], world2d_frame_0.view_projection_0.data_0[i32(0)][i32(1)], world2d_frame_0.view_projection_0.data_0[i32(1)][i32(1)], world2d_frame_0.view_projection_0.data_0[i32(2)][i32(1)], world2d_frame_0.view_projection_0.data_0[i32(3)][i32(1)], world2d_frame_0.view_projection_0.data_0[i32(0)][i32(2)], world2d_frame_0.view_projection_0.data_0[i32(1)][i32(2)], world2d_frame_0.view_projection_0.data_0[i32(2)][i32(2)], world2d_frame_0.view_projection_0.data_0[i32(3)][i32(2)], world2d_frame_0.view_projection_0.data_0[i32(0)][i32(3)], world2d_frame_0.view_projection_0.data_0[i32(1)][i32(3)], world2d_frame_0.view_projection_0.data_0[i32(2)][i32(3)], world2d_frame_0.view_projection_0.data_0[i32(3)][i32(3)])))));
    output_0.uv_0 = _S2.uv_1;
    output_0.tint_0 = _S2.tint_1;
    return output_0;
}

