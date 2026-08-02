struct _MatrixStorage_float4x4_ColMajorstd140_0
{
    @align(16) data_0 : array<vec4<f32>, i32(4)>,
};

struct ShadowDraw_std140_0
{
    @align(16) u_model_0 : _MatrixStorage_float4x4_ColMajorstd140_0,
};

@binding(20) @group(0) var<uniform> shadow_draw_0 : ShadowDraw_std140_0;
struct PerFrame_std140_0
{
    @align(16) u_view_0 : _MatrixStorage_float4x4_ColMajorstd140_0,
    @align(16) u_projection_0 : _MatrixStorage_float4x4_ColMajorstd140_0,
};

@binding(2) @group(0) var<uniform> per_frame_0 : PerFrame_std140_0;
fn termin_to_native_clip_0( clip_0 : vec4<f32>) -> vec4<f32>
{
    var _S1 : vec4<f32> = clip_0;
    _S1[i32(1)] = - clip_0.y;
    return _S1;
}

struct VertexOutput_0
{
    @builtin(position) position_0 : vec4<f32>,
};

struct vertexInput_0
{
    @location(0) position_1 : vec3<f32>,
};

@vertex
fn vs_main( _S2 : vertexInput_0) -> VertexOutput_0
{
    var output_0 : VertexOutput_0;
    output_0.position_0 = termin_to_native_clip_0((((((((((vec4<f32>(_S2.position_1, 1.0f)) * (mat4x4<f32>(shadow_draw_0.u_model_0.data_0[i32(0)][i32(0)], shadow_draw_0.u_model_0.data_0[i32(1)][i32(0)], shadow_draw_0.u_model_0.data_0[i32(2)][i32(0)], shadow_draw_0.u_model_0.data_0[i32(3)][i32(0)], shadow_draw_0.u_model_0.data_0[i32(0)][i32(1)], shadow_draw_0.u_model_0.data_0[i32(1)][i32(1)], shadow_draw_0.u_model_0.data_0[i32(2)][i32(1)], shadow_draw_0.u_model_0.data_0[i32(3)][i32(1)], shadow_draw_0.u_model_0.data_0[i32(0)][i32(2)], shadow_draw_0.u_model_0.data_0[i32(1)][i32(2)], shadow_draw_0.u_model_0.data_0[i32(2)][i32(2)], shadow_draw_0.u_model_0.data_0[i32(3)][i32(2)], shadow_draw_0.u_model_0.data_0[i32(0)][i32(3)], shadow_draw_0.u_model_0.data_0[i32(1)][i32(3)], shadow_draw_0.u_model_0.data_0[i32(2)][i32(3)], shadow_draw_0.u_model_0.data_0[i32(3)][i32(3)]))))) * (mat4x4<f32>(per_frame_0.u_view_0.data_0[i32(0)][i32(0)], per_frame_0.u_view_0.data_0[i32(1)][i32(0)], per_frame_0.u_view_0.data_0[i32(2)][i32(0)], per_frame_0.u_view_0.data_0[i32(3)][i32(0)], per_frame_0.u_view_0.data_0[i32(0)][i32(1)], per_frame_0.u_view_0.data_0[i32(1)][i32(1)], per_frame_0.u_view_0.data_0[i32(2)][i32(1)], per_frame_0.u_view_0.data_0[i32(3)][i32(1)], per_frame_0.u_view_0.data_0[i32(0)][i32(2)], per_frame_0.u_view_0.data_0[i32(1)][i32(2)], per_frame_0.u_view_0.data_0[i32(2)][i32(2)], per_frame_0.u_view_0.data_0[i32(3)][i32(2)], per_frame_0.u_view_0.data_0[i32(0)][i32(3)], per_frame_0.u_view_0.data_0[i32(1)][i32(3)], per_frame_0.u_view_0.data_0[i32(2)][i32(3)], per_frame_0.u_view_0.data_0[i32(3)][i32(3)]))))) * (mat4x4<f32>(per_frame_0.u_projection_0.data_0[i32(0)][i32(0)], per_frame_0.u_projection_0.data_0[i32(1)][i32(0)], per_frame_0.u_projection_0.data_0[i32(2)][i32(0)], per_frame_0.u_projection_0.data_0[i32(3)][i32(0)], per_frame_0.u_projection_0.data_0[i32(0)][i32(1)], per_frame_0.u_projection_0.data_0[i32(1)][i32(1)], per_frame_0.u_projection_0.data_0[i32(2)][i32(1)], per_frame_0.u_projection_0.data_0[i32(3)][i32(1)], per_frame_0.u_projection_0.data_0[i32(0)][i32(2)], per_frame_0.u_projection_0.data_0[i32(1)][i32(2)], per_frame_0.u_projection_0.data_0[i32(2)][i32(2)], per_frame_0.u_projection_0.data_0[i32(3)][i32(2)], per_frame_0.u_projection_0.data_0[i32(0)][i32(3)], per_frame_0.u_projection_0.data_0[i32(1)][i32(3)], per_frame_0.u_projection_0.data_0[i32(2)][i32(3)], per_frame_0.u_projection_0.data_0[i32(3)][i32(3)])))));
    return output_0;
}

