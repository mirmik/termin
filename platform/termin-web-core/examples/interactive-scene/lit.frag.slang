import termin_prelude;
import termin_lighting;
import termin_single_shadow;

struct MaterialParams { float4 u_color; };
[[TerminScope("material")]] ConstantBuffer<MaterialParams> material;

struct FragmentInput {
    float4 position : SV_Position;
    float3 normal : TEXCOORD0;
    float3 world : TEXCOORD1;
    float3 center : TEXCOORD2;
};

[shader("fragment")]
float4 main(FragmentInput input) : SV_Target0 {
    float3 n = normalize(input.normal);
    float3 v = normalize(get_camera_position() - input.world);
    float3 lighting = get_ambient_color() * get_ambient_intensity();
    float3 reflection = 0;
    float lampPower = 0;
    for (int i = 0; i < min(get_light_count(), MAX_LIGHTS); ++i) {
        float3 lightDirection;
        float lightWeight;
        if (get_light_type(i) == LIGHT_TYPE_DIRECTIONAL) {
            lightDirection = -get_light_direction(i);
            lightWeight = compute_single_shadow(i, input.world);
        } else {
            float3 lightPosition = get_light_position(i);
            float3 toLight = lightPosition - input.world;
            float dist = max(length(toLight), 0.0001);
            lightDirection = toLight / dist;
            lightWeight = compute_distance_attenuation(get_light_attenuation(i), get_light_range(i), dist);
            // A bulb's point light and mesh share one entity and hence one origin.
            if (distance(lightPosition, input.center) < 0.001)
                lampPower = saturate(get_light_intensity(i));
        }
        float diffuse = max(dot(n, lightDirection), 0);
        float specular = pow(max(dot(n, normalize(lightDirection + v)), 0), 40);
        float3 radiance = lightWeight * get_light_color(i) * get_light_intensity(i);
        reflection += radiance * specular;
        lighting += radiance * (0.78 * diffuse + 0.23 * specular);
    }
    if (material.u_color.a > 0.5) {
        float facing = saturate(dot(n, v));
        float3 glass = material.u_color.rgb * (0.09 + 0.10 * facing);
        float3 glow = material.u_color.rgb * (0.65 + 0.35 * facing) + 0.24 * pow(facing, 6);
        return float4(lerp(glass, glow, lampPower) + 0.25 * reflection, 1);
    }
    return float4(lighting * material.u_color.rgb, 1);
}
