import termin_prelude;
struct PerFrame { float4x4 view; float4x4 projection; };
struct IdModelData { float4x4 model; };
[[TerminScope("frame")]] ConstantBuffer<PerFrame> per_frame;
[[TerminScope("draw")]] ConstantBuffer<IdModelData> id_model;
struct VertexOutput {
    float4 position : SV_Position;
    nointerpolation uint pick_id : TEXCOORD0;
};
VertexOutput termin_id_batched_vertex_output(float3 world_pos, uint pick_id) {
    VertexOutput output;
    output.position = termin_to_native_clip(mul(per_frame.projection, mul(per_frame.view, float4(world_pos, 1.0))));
    output.pick_id = pick_id;
    return output;
}
