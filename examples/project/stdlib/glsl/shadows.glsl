/**
 * Shadow mapping utilities for Termin engine.
 *
 * Usage in your shader:
 *   #include "shadows"
 *
 * Required uniforms (automatically set by engine):
 *   uniform int u_shadow_map_count;
 *   uniform sampler2D u_shadow_map[MAX_SHADOW_MAPS];
 *   uniform mat4 u_light_space_matrix[MAX_SHADOW_MAPS];
 *   uniform int u_shadow_light_index[MAX_SHADOW_MAPS];
 *
 * Functions:
 *   float compute_shadow(int light_index, vec3 world_pos)
 *   float compute_shadow_pcf(int light_index, vec3 world_pos)
 */

#ifndef SHADOWS_GLSL
#define SHADOWS_GLSL

const int MAX_SHADOW_MAPS = 4;
const float SHADOW_BIAS = 0.005;

/**
 * Compute hard shadow for a light at given world position.
 *
 * Parameters:
 *   light_index: index of the light in scene
 *   world_pos: fragment world position
 *   shadow_map_count: number of active shadow maps
 *   shadow_maps: array of shadow map samplers
 *   light_space_matrices: array of light-space matrices
 *   shadow_light_indices: array mapping shadow map index to light index
 *
 * Returns:
 *   1.0 = fully lit
 *   0.0 = fully in shadow
 */
float compute_shadow(
    int light_index,
    vec3 world_pos,
    int shadow_map_count,
    sampler2D shadow_maps[MAX_SHADOW_MAPS],
    mat4 light_space_matrices[MAX_SHADOW_MAPS],
    int shadow_light_indices[MAX_SHADOW_MAPS]
) {
    for (int sm = 0; sm < shadow_map_count; ++sm) {
        if (shadow_light_indices[sm] != light_index) {
            continue;
        }

        // Transform to light space
        vec4 light_space_pos = light_space_matrices[sm] * vec4(world_pos, 1.0);

        // Perspective divide
        vec3 proj_coords = light_space_pos.xyz / light_space_pos.w;

        // Map from [-1, 1] to [0, 1]
        proj_coords = proj_coords * 0.5 + 0.5;

        // Check if outside shadow map frustum
        if (proj_coords.x < 0.0 || proj_coords.x > 1.0 ||
            proj_coords.y < 0.0 || proj_coords.y > 1.0 ||
            proj_coords.z < 0.0 || proj_coords.z > 1.0) {
            return 1.0;  // Outside frustum = lit
        }

        // Sample shadow map
        float closest_depth = texture(shadow_maps[sm], proj_coords.xy).r;
        float current_depth = proj_coords.z;

        // Compare with bias
        float shadow = current_depth - SHADOW_BIAS > closest_depth ? 0.0 : 1.0;

        return shadow;
    }

    // No shadow map for this light
    return 1.0;
}

/**
 * Compute soft shadow with PCF (Percentage Closer Filtering).
 *
 * Same parameters as compute_shadow, but samples multiple texels
 * for smoother shadow edges.
 *
 * Returns:
 *   0.0-1.0 shadow factor (soft edges)
 */
float compute_shadow_pcf(
    int light_index,
    vec3 world_pos,
    int shadow_map_count,
    sampler2D shadow_maps[MAX_SHADOW_MAPS],
    mat4 light_space_matrices[MAX_SHADOW_MAPS],
    int shadow_light_indices[MAX_SHADOW_MAPS]
) {
    for (int sm = 0; sm < shadow_map_count; ++sm) {
        if (shadow_light_indices[sm] != light_index) {
            continue;
        }

        // Transform to light space
        vec4 light_space_pos = light_space_matrices[sm] * vec4(world_pos, 1.0);
        vec3 proj_coords = light_space_pos.xyz / light_space_pos.w;
        proj_coords = proj_coords * 0.5 + 0.5;

        // Check bounds
        if (proj_coords.x < 0.0 || proj_coords.x > 1.0 ||
            proj_coords.y < 0.0 || proj_coords.y > 1.0 ||
            proj_coords.z < 0.0 || proj_coords.z > 1.0) {
            return 1.0;
        }

        // Get texel size for PCF
        vec2 texel_size = 1.0 / vec2(textureSize(shadow_maps[sm], 0));

        // 3x3 PCF sampling
        float shadow = 0.0;
        for (int x = -1; x <= 1; ++x) {
            for (int y = -1; y <= 1; ++y) {
                vec2 offset = vec2(float(x), float(y)) * texel_size;
                float depth = texture(shadow_maps[sm], proj_coords.xy + offset).r;
                shadow += proj_coords.z - SHADOW_BIAS > depth ? 0.0 : 1.0;
            }
        }

        return shadow / 9.0;
    }

    return 1.0;
}

#endif // SHADOWS_GLSL
