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
fn termin_to_native_clip_0( clip_0 : vec4<f32>) -> vec4<f32>
{
    var _S1 : vec4<f32> = clip_0;
    _S1[i32(1)] = - clip_0.y;
    return _S1;
}

struct VertexOutput_0
{
    @builtin(position) position_0 : vec4<f32>,
    @location(0) dir_0 : vec3<f32>,
};

struct vertexInput_0
{
    @location(0) position_1 : vec2<f32>,
};

@vertex
fn main( _S2 : vertexInput_0) -> VertexOutput_0
{
    var _S3 : vec4<f32> = vec4<f32>(_S2.position_1, 0.0f, 1.0f);
    var near_h_0 : vec4<f32> = (((_S3) * (mat4x4<f32>(material_0.u_inv_view_projection_0.data_0[i32(0)][i32(0)], material_0.u_inv_view_projection_0.data_0[i32(1)][i32(0)], material_0.u_inv_view_projection_0.data_0[i32(2)][i32(0)], material_0.u_inv_view_projection_0.data_0[i32(3)][i32(0)], material_0.u_inv_view_projection_0.data_0[i32(0)][i32(1)], material_0.u_inv_view_projection_0.data_0[i32(1)][i32(1)], material_0.u_inv_view_projection_0.data_0[i32(2)][i32(1)], material_0.u_inv_view_projection_0.data_0[i32(3)][i32(1)], material_0.u_inv_view_projection_0.data_0[i32(0)][i32(2)], material_0.u_inv_view_projection_0.data_0[i32(1)][i32(2)], material_0.u_inv_view_projection_0.data_0[i32(2)][i32(2)], material_0.u_inv_view_projection_0.data_0[i32(3)][i32(2)], material_0.u_inv_view_projection_0.data_0[i32(0)][i32(3)], material_0.u_inv_view_projection_0.data_0[i32(1)][i32(3)], material_0.u_inv_view_projection_0.data_0[i32(2)][i32(3)], material_0.u_inv_view_projection_0.data_0[i32(3)][i32(3)]))));
    var far_h_0 : vec4<f32> = (((vec4<f32>(_S2.position_1, 1.0f, 1.0f)) * (mat4x4<f32>(material_0.u_inv_view_projection_0.data_0[i32(0)][i32(0)], material_0.u_inv_view_projection_0.data_0[i32(1)][i32(0)], material_0.u_inv_view_projection_0.data_0[i32(2)][i32(0)], material_0.u_inv_view_projection_0.data_0[i32(3)][i32(0)], material_0.u_inv_view_projection_0.data_0[i32(0)][i32(1)], material_0.u_inv_view_projection_0.data_0[i32(1)][i32(1)], material_0.u_inv_view_projection_0.data_0[i32(2)][i32(1)], material_0.u_inv_view_projection_0.data_0[i32(3)][i32(1)], material_0.u_inv_view_projection_0.data_0[i32(0)][i32(2)], material_0.u_inv_view_projection_0.data_0[i32(1)][i32(2)], material_0.u_inv_view_projection_0.data_0[i32(2)][i32(2)], material_0.u_inv_view_projection_0.data_0[i32(3)][i32(2)], material_0.u_inv_view_projection_0.data_0[i32(0)][i32(3)], material_0.u_inv_view_projection_0.data_0[i32(1)][i32(3)], material_0.u_inv_view_projection_0.data_0[i32(2)][i32(3)], material_0.u_inv_view_projection_0.data_0[i32(3)][i32(3)]))));
    var output_0 : VertexOutput_0;
    output_0.dir_0 = far_h_0.xyz / vec3<f32>(far_h_0.w) - near_h_0.xyz / vec3<f32>(near_h_0.w);
    output_0.position_0 = termin_to_native_clip_0(_S3);
    return output_0;
}

