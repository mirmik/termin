import termin_prelude;

struct StaticMeshPush {
    column_major float4x4 u_view_projection;
    column_major float4x4 u_world_from_local;
    float4 u_base_color_factor;
    float4 u_light_direction_enabled;
    float4 u_light_intensity;
    float4 u_normal_matrix_rows[3];
};

[[TerminScope("draw")]]
ConstantBuffer<StaticMeshPush> u_push;

[[TerminScope("transient")]]
Sampler2D u_base_color_texture;

struct VertexInput {
    float3 position : POSITION;
    float3 normal : NORMAL;
    float2 uv : TEXCOORD0;
};

struct VertexOutput {
    float4 position : SV_Position;
    float3 world_normal : TEXCOORD0;
    float2 uv : TEXCOORD1;
};

[shader("vertex")]
VertexOutput vs_main(VertexInput input) {
    VertexOutput output;
    float4 world_position = mul(u_push.u_world_from_local, float4(input.position, 1.0));
    output.position = termin_to_native_clip(
        mul(u_push.u_view_projection, world_position));
    output.world_normal = float3(
        dot(u_push.u_normal_matrix_rows[0].xyz, input.normal),
        dot(u_push.u_normal_matrix_rows[1].xyz, input.normal),
        dot(u_push.u_normal_matrix_rows[2].xyz, input.normal));
    output.uv = input.uv;
    return output;
}

struct FragmentOutput {
    float4 color : SV_Target0;
};

[shader("fragment")]
FragmentOutput fs_main(VertexOutput input) {
    FragmentOutput output;
    float intensity = 1.0;
    if (u_push.u_light_direction_enabled.w != 0.0) {
        float diffuse = max(
            dot(normalize(input.world_normal),
                normalize(u_push.u_light_direction_enabled.xyz)),
            0.0);
        intensity = u_push.u_light_intensity.x +
                    u_push.u_light_intensity.y * diffuse;
    }
    float4 base_color = u_base_color_texture.Sample(input.uv) *
                        u_push.u_base_color_factor;
    output.color = float4(base_color.rgb * intensity, base_color.a);
    return output;
}
