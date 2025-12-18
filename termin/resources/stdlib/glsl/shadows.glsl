/**
 * Shadow mapping utilities for Termin engine.
 *
 * Usage in your shader:
 *   #include "shadows"
 *
 * This file declares all required uniforms automatically.
 * The engine sets these uniforms via upload_shadow_maps_to_shader().
 *
 * Functions:
 *   float compute_shadow(int light_index) - hard shadow with hardware PCF
 *   float compute_shadow_pcf(int light_index) - 5x5 PCF soft shadow
 *   float compute_shadow_poisson(int light_index) - Poisson disk (best quality)
 *
 * Required varying (must be defined in your shader):
 *   in vec3 v_world_pos;
 */

#ifndef SHADOWS_GLSL
#define SHADOWS_GLSL

#ifndef MAX_SHADOW_MAPS
#define MAX_SHADOW_MAPS 4
#endif

#ifndef SHADOW_BIAS
#define SHADOW_BIAS 0.005
#endif

// Shadow map uniforms (set by engine)
uniform int u_shadow_map_count;
uniform sampler2DShadow u_shadow_map[MAX_SHADOW_MAPS];
uniform mat4 u_light_space_matrix[MAX_SHADOW_MAPS];
uniform int u_shadow_light_index[MAX_SHADOW_MAPS];

// 16-sample Poisson disk for high-quality shadow sampling
const int POISSON_SAMPLES = 16;
const vec2 poissonDisk[16] = vec2[](
    vec2(-0.94201624, -0.39906216),
    vec2( 0.94558609, -0.76890725),
    vec2(-0.09418410, -0.92938870),
    vec2( 0.34495938,  0.29387760),
    vec2(-0.91588581,  0.45771432),
    vec2(-0.81544232, -0.87912464),
    vec2(-0.38277543,  0.27676845),
    vec2( 0.97484398,  0.75648379),
    vec2( 0.44323325, -0.97511554),
    vec2( 0.53742981, -0.47373420),
    vec2(-0.26496911, -0.41893023),
    vec2( 0.79197514,  0.19090188),
    vec2(-0.24188840,  0.99706507),
    vec2(-0.81409955,  0.91437590),
    vec2( 0.19984126,  0.78641367),
    vec2( 0.14383161, -0.14100790)
);

/**
 * Compute hard shadow using hardware PCF (sampler2DShadow).
 * Single sample with automatic depth comparison + bilinear filtering.
 */
float compute_shadow(int light_index) {
    for (int sm = 0; sm < u_shadow_map_count; ++sm) {
        if (u_shadow_light_index[sm] != light_index) {
            continue;
        }

        vec4 light_space_pos = u_light_space_matrix[sm] * vec4(v_world_pos, 1.0);
        vec3 proj_coords = light_space_pos.xyz / light_space_pos.w;
        proj_coords = proj_coords * 0.5 + 0.5;

        if (proj_coords.x < 0.0 || proj_coords.x > 1.0 ||
            proj_coords.y < 0.0 || proj_coords.y > 1.0 ||
            proj_coords.z < 0.0 || proj_coords.z > 1.0) {
            return 1.0;
        }

        // Hardware PCF: texture() on sampler2DShadow does depth comparison
        return texture(u_shadow_map[sm], vec3(proj_coords.xy, proj_coords.z - SHADOW_BIAS));
    }

    return 1.0;
}

/**
 * Compute soft shadow with 5x5 PCF grid.
 * 25 samples using hardware depth comparison.
 */
float compute_shadow_pcf(int light_index) {
    for (int sm = 0; sm < u_shadow_map_count; ++sm) {
        if (u_shadow_light_index[sm] != light_index) {
            continue;
        }

        vec4 light_space_pos = u_light_space_matrix[sm] * vec4(v_world_pos, 1.0);
        vec3 proj_coords = light_space_pos.xyz / light_space_pos.w;
        proj_coords = proj_coords * 0.5 + 0.5;

        if (proj_coords.x < 0.0 || proj_coords.x > 1.0 ||
            proj_coords.y < 0.0 || proj_coords.y > 1.0 ||
            proj_coords.z < 0.0 || proj_coords.z > 1.0) {
            return 1.0;
        }

        vec2 texel_size = 1.0 / vec2(textureSize(u_shadow_map[sm], 0));
        float compare_depth = proj_coords.z - SHADOW_BIAS;

        float shadow = 0.0;
        for (int x = -2; x <= 2; ++x) {
            for (int y = -2; y <= 2; ++y) {
                vec2 offset = vec2(float(x), float(y)) * texel_size;
                shadow += texture(u_shadow_map[sm], vec3(proj_coords.xy + offset, compare_depth));
            }
        }

        return shadow / 25.0;
    }

    return 1.0;
}

/**
 * Compute high-quality soft shadow with Poisson disk sampling.
 * 16 samples with better distribution than grid, reduces banding artifacts.
 */
float compute_shadow_poisson(int light_index) {
    for (int sm = 0; sm < u_shadow_map_count; ++sm) {
        if (u_shadow_light_index[sm] != light_index) {
            continue;
        }

        vec4 light_space_pos = u_light_space_matrix[sm] * vec4(v_world_pos, 1.0);
        vec3 proj_coords = light_space_pos.xyz / light_space_pos.w;
        proj_coords = proj_coords * 0.5 + 0.5;

        if (proj_coords.x < 0.0 || proj_coords.x > 1.0 ||
            proj_coords.y < 0.0 || proj_coords.y > 1.0 ||
            proj_coords.z < 0.0 || proj_coords.z > 1.0) {
            return 1.0;
        }

        vec2 texel_size = 1.0 / vec2(textureSize(u_shadow_map[sm], 0));
        float compare_depth = proj_coords.z - SHADOW_BIAS;
        float radius = 2.5;

        float shadow = 0.0;
        for (int i = 0; i < POISSON_SAMPLES; ++i) {
            vec2 offset = poissonDisk[i] * texel_size * radius;
            shadow += texture(u_shadow_map[sm], vec3(proj_coords.xy + offset, compare_depth));
        }

        return shadow / float(POISSON_SAMPLES);
    }

    return 1.0;
}

#endif // SHADOWS_GLSL
