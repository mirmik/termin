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
    @location(0) world_pos_0 : vec3<f32>,
    @location(1) offset_uv_0 : vec4<f32>,
};

@vertex
fn vs_main( _S2 : vertexInput_0) -> VertexOutput_0
{
    var output_0 : VertexOutput_0;
    if((text3d_draw_0.u_flags_0.x) != 0.0f)
    {
        var _S3 : vec4<f32> = (((vec4<f32>(_S2.world_pos_0, 1.0f)) * (mat4x4<f32>(text3d_draw_0.u_mvp_0.data_0[i32(0)][i32(0)], text3d_draw_0.u_mvp_0.data_0[i32(1)][i32(0)], text3d_draw_0.u_mvp_0.data_0[i32(2)][i32(0)], text3d_draw_0.u_mvp_0.data_0[i32(3)][i32(0)], text3d_draw_0.u_mvp_0.data_0[i32(0)][i32(1)], text3d_draw_0.u_mvp_0.data_0[i32(1)][i32(1)], text3d_draw_0.u_mvp_0.data_0[i32(2)][i32(1)], text3d_draw_0.u_mvp_0.data_0[i32(3)][i32(1)], text3d_draw_0.u_mvp_0.data_0[i32(0)][i32(2)], text3d_draw_0.u_mvp_0.data_0[i32(1)][i32(2)], text3d_draw_0.u_mvp_0.data_0[i32(2)][i32(2)], text3d_draw_0.u_mvp_0.data_0[i32(3)][i32(2)], text3d_draw_0.u_mvp_0.data_0[i32(0)][i32(3)], text3d_draw_0.u_mvp_0.data_0[i32(1)][i32(3)], text3d_draw_0.u_mvp_0.data_0[i32(2)][i32(3)], text3d_draw_0.u_mvp_0.data_0[i32(3)][i32(3)]))));
        var clip_1 : vec4<f32> = _S3;
        clip_1[i32(0)] = clip_1[i32(0)] + _S2.offset_uv_0.x * text3d_draw_0.u_flags_0.y * _S3.w;
        clip_1[i32(1)] = clip_1[i32(1)] - _S2.offset_uv_0.y * text3d_draw_0.u_flags_0.z * clip_1.w;
        output_0.pos_0 = termin_to_native_clip_0(clip_1);
        output_0.uv_0 = _S2.offset_uv_0.zw;
        return output_0;
    }
    output_0.pos_0 = termin_to_native_clip_0((((vec4<f32>(_S2.world_pos_0 + text3d_draw_0.u_cam_right_0.xyz * vec3<f32>(_S2.offset_uv_0.x) + text3d_draw_0.u_cam_up_0.xyz * vec3<f32>(_S2.offset_uv_0.y), 1.0f)) * (mat4x4<f32>(text3d_draw_0.u_mvp_0.data_0[i32(0)][i32(0)], text3d_draw_0.u_mvp_0.data_0[i32(1)][i32(0)], text3d_draw_0.u_mvp_0.data_0[i32(2)][i32(0)], text3d_draw_0.u_mvp_0.data_0[i32(3)][i32(0)], text3d_draw_0.u_mvp_0.data_0[i32(0)][i32(1)], text3d_draw_0.u_mvp_0.data_0[i32(1)][i32(1)], text3d_draw_0.u_mvp_0.data_0[i32(2)][i32(1)], text3d_draw_0.u_mvp_0.data_0[i32(3)][i32(1)], text3d_draw_0.u_mvp_0.data_0[i32(0)][i32(2)], text3d_draw_0.u_mvp_0.data_0[i32(1)][i32(2)], text3d_draw_0.u_mvp_0.data_0[i32(2)][i32(2)], text3d_draw_0.u_mvp_0.data_0[i32(3)][i32(2)], text3d_draw_0.u_mvp_0.data_0[i32(0)][i32(3)], text3d_draw_0.u_mvp_0.data_0[i32(1)][i32(3)], text3d_draw_0.u_mvp_0.data_0[i32(2)][i32(3)], text3d_draw_0.u_mvp_0.data_0[i32(3)][i32(3)])))));
    output_0.uv_0 = _S2.offset_uv_0.zw;
    return output_0;
}

