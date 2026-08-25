import termin_prelude;

struct StaticMeshPush {
    column_major float4x4 u_view_projection;
    column_major float4x4 u_world_from_local;
    float4 u_base_color_factor;
    float4 u_light_direction_enabled;
    float4 u_light_intensity;
};

[[TerminScope("draw")]]
ConstantBuffer<StaticMeshPush> u_push;

struct VertexInput {
    float3 position : POSITION;
};

struct VertexOutput {
    float4 position : SV_Position;
    float3 world_position : TEXCOORD0;
};

[shader("vertex")]
VertexOutput vs_main(VertexInput input) {
    VertexOutput output;
    float4 world_position = mul(u_push.u_world_from_local, float4(input.position, 1.0));
    output.position = termin_to_native_clip(
        mul(u_push.u_view_projection, world_position));
    output.world_position = world_position.xyz;
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
        float3 dx = ddx(input.world_position);
        float3 dy = ddy(input.world_position);
        float3 normal = normalize(cross(dx, dy));
        float diffuse = max(
            dot(normal, normalize(u_push.u_light_direction_enabled.xyz)),
            0.0);
        intensity = u_push.u_light_intensity.x +
                    u_push.u_light_intensity.y * diffuse;
    }
    output.color = float4(
        u_push.u_base_color_factor.rgb * intensity,
        u_push.u_base_color_factor.a);
    return output;
}
