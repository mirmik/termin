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
};

struct vertexInput_0
{
    @location(0) position_1 : vec2<f32>,
    @location(1) uv_1 : vec2<f32>,
};

@vertex
fn vs_main( _S2 : vertexInput_0) -> VertexOutput_0
{
    var output_0 : VertexOutput_0;
    output_0.position_0 = termin_to_native_clip_0(vec4<f32>(_S2.position_1, 0.0f, 1.0f));
    output_0.uv_0 = _S2.uv_1;
    return output_0;
}

