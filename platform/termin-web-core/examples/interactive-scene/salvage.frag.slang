import termin_prelude;
import termin_lighting;

struct MaterialParams { float4 u_color; };
[[TerminScope("material")]] ConstantBuffer<MaterialParams> material;

struct FragmentInput {
    float4 position : SV_Position;
    float3 normal : TEXCOORD0;
    float3 world : TEXCOORD1;
    float3 center : TEXCOORD2;
};

float shafts(float2 p) {
    float axis = p.x - .34 * p.y;
    float broad = .5 + .5 * cos(axis * 2.1 + .4 * sin(axis * 3.8));
    float fine = .5 + .5 * cos(axis * 13.8 + .6 * sin(axis * 2.9));
    return broad * broad * (.64 + .36 * fine) * saturate(.42 + .10 * p.y);
}

[shader("fragment")]
float4 main(FragmentInput input) : SV_Target0 {
    float3 p = input.world;
    float shaft = shafts(p.xz);
    if (p.y > 4.35) {
        float depth = saturate((p.z + 3.3) / 7.5);
        float3 dark = float3(.0025, .013, .025);
        float3 blue = float3(.006, .071, .10);
        return float4(lerp(dark, blue, depth) + shaft * float3(.008, .064, .065), 1);
    }

    float3 n = normalize(input.normal);
    float3 view = normalize(get_camera_position() - p);
    float3 lighting = float3(.11, .18, .205) + shaft * float3(.09, .19, .20);
    float3 reflection = 0;
    for (int i = 0; i < min(get_light_count(), MAX_LIGHTS); ++i) {
        float3 toLight = get_light_position(i) - p;
        float d = max(length(toLight), .001);
        float3 dir = toLight / d;
        // The water absorbs light over a few metres. This also bounds the moving ROV lamp.
        float3 radiance = get_light_color(i) * get_light_intensity(i) / (1 + .24*d + .18*d*d);
        lighting += radiance * max(0, dot(n, dir));
        reflection += radiance * pow(saturate(dot(n, normalize(view + dir))), 42);
    }
    float3 base = material.u_color.rgb;
    float3 color = base * lighting + reflection * (.08 + .14 * base);
    if (material.u_color.a > .5)
        color += base * .43;
    // Mist softens the frames on the far side of the flooded hold.
    float fog = saturate((p.y - .85) * .22);
    return float4(lerp(color, float3(.006, .036, .052), fog), 1);
}
