// Termin material pipeline vertex glue.
// provider=builtin_shaders/termin_vertex_transform.slang
// adapter=builtin_shaders/termin_shadow_vertex_output_adapter.slang
import termin_vertex_transform;
import termin_shadow_vertex_output_adapter;


struct VertexInput {
    float3 position : POSITION;
};

[shader("vertex")]
VertexOutput vs_main(VertexInput input) {
    return termin_shadow_clip_output(termin_static_world_position(input.position, shadow_draw.u_model));
}
