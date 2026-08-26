import termin_prelude;

struct StaticMeshTexturedPush {
    column_major float4x4 u_view_projection;
    column_major float4x4 u_world_from_local;
    float4 u_base_color_factor;
    float4 u_light_direction_enabled;
    float4 u_light_intensity;
    float4 u_normal_matrix_rows[3];
};

[[TerminScope("draw")]]
ConstantBuffer<StaticMeshTexturedPush> u_push;

[[TerminScope("transient")]]
Sampler2D u_base_color_texture;

struct VertexInput {
    float3 position : POSITION;
    float2 uv : TEXCOORD0;
};

struct VertexOutput {
    float4 position : SV_Position;
    float2 uv : TEXCOORD0;
    float3 world_position : TEXCOORD1;
};

[shader("vertex")]
VertexOutput vs_main(VertexInput input) {
    VertexOutput output;
    float4 world_position = mul(u_push.u_world_from_local, float4(input.position, 1.0));
    output.position = termin_to_native_clip(
        mul(u_push.u_view_projection, world_position));
    output.uv = input.uv;
    output.world_position = world_position.xyz;
    return output;
}

struct FragmentInput {
    float4 position : SV_Position;
    float2 uv : TEXCOORD0;
    float3 world_position : TEXCOORD1;
};

struct FragmentOutput {
    float4 color : SV_Target0;
};

[shader("fragment")]
FragmentOutput fs_main(FragmentInput input) {
    FragmentOutput output;
    float intensity = 1.0;
    if (u_push.u_light_direction_enabled.w != 0.0) {
        float3 dx = ddx(input.world_position);
        float3 dy = ddy(input.world_position);
        // Termin clip/screen space is Y-down. Swap the derivative order so
        // the preview normal faces the visible side of the triangle.
        float3 normal = normalize(cross(dy, dx));
        float diffuse = max(
            dot(normal, normalize(u_push.u_light_direction_enabled.xyz)),
            0.0);
        intensity = u_push.u_light_intensity.x +
                    u_push.u_light_intensity.y * diffuse;
    }
    float4 base_color = u_base_color_texture.Sample(input.uv) *
                        u_push.u_base_color_factor;
    output.color = float4(base_color.rgb * intensity, base_color.a);
    return output;
}
