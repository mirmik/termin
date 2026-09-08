// Merged static meshes retain the original entity ID on every triangle.
import termin_id_batched_vertex_output_adapter;
import termin_pick_encoding;
struct VertexInput {
    float3 position : POSITION;
    uint a_pick_id : TEXCOORD7;
};
[shader("vertex")]
VertexOutput vs_main(VertexInput input) {
    return termin_id_batched_vertex_output(mul(id_model.model, float4(input.position, 1.0)).xyz, input.a_pick_id);
}
[shader("fragment")]
float4 fs_main(VertexOutput input) : SV_Target0 {
    uint color = termin_pick_encode(input.pick_id);
    return float4(float(color & 255u), float((color >> 8) & 255u), float((color >> 16) & 255u), 255.0) / 255.0;
}
