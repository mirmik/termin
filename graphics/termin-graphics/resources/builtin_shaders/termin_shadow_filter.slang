// Shared filtering and projection for the receiver's sample_shadow_map implementation.
public float sample_shadow_filtered(int sm, float2 uv, float depth) {
    int method = get_shadow_method();
    float result = 1.0;
    if (method == SHADOW_METHOD_HARD) {
        // The comparison sampler is linear, so a single lookup gives the
        // portable hardware 2x2 PCF normally expected from a hard shadow.
        result = sample_shadow_map(sm, uv, depth);
    } else {
        float2 texel_size = shadow_block.u_shadow_texel_size[sm].xy;
        float softness = max(get_shadow_softness(), 0.0);
        if (method == SHADOW_METHOD_POISSON) {
            float visibility = 0.0;
            float radius = 2.5 * softness;
            for (int i = 0; i < POISSON_SAMPLE_COUNT; ++i) {
                visibility += sample_shadow_map(
                    sm,
                    uv + POISSON_DISK[i] * texel_size * radius,
                    depth);
            }
            result = visibility / float(POISSON_SAMPLE_COUNT);
        } else {
            // Unknown values deliberately use the default PCF method, matching
            // the scene setting's default and keeping corrupted data visibly
            // filtered.
            float visibility = 0.0;
            for (int y = -2; y <= 2; ++y) {
                for (int x = -2; x <= 2; ++x) {
                    visibility += sample_shadow_map(
                        sm,
                        uv + float2(float(x), float(y)) * texel_size * softness,
                        depth);
                }
            }
            result = visibility / 25.0;
        }
    }
    return result;
}

public float compute_shadow_candidate(int sm, int light_index, float3 world_pos) {
    if (shadow_block.u_shadow_map_count <= sm ||
        shadow_block.u_shadow_light_index[sm] != light_index) {
        return -1.0;
    }

    float4 world = float4(world_pos, 1.0);
    int row = sm * 4;
    float4 light_space_pos = float4(
        dot(shadow_block.u_light_space_matrix[row + 0], world),
        dot(shadow_block.u_light_space_matrix[row + 1], world),
        dot(shadow_block.u_light_space_matrix[row + 2], world),
        dot(shadow_block.u_light_space_matrix[row + 3], world));
    float3 proj_coords = light_space_pos.xyz / light_space_pos.w;
    proj_coords.xy = proj_coords.xy * 0.5 + 0.5;

    if (proj_coords.x < 0.0 || proj_coords.x > 1.0 ||
        proj_coords.y < 0.0 || proj_coords.y > 1.0 ||
        proj_coords.z < 0.0 || proj_coords.z > 1.0) {
        return -1.0;
    }

    return sample_shadow_filtered(
        sm,
        proj_coords.xy,
        proj_coords.z - shadow_bias_depth(sm));
}
