/**
 * Lighting utilities for Termin engine.
 *
 * Usage in your shader:
 *   #include "lighting"
 *
 * Provides:
 *   - Light type constants
 *   - Attenuation functions
 *   - Spotlight falloff
 */

#ifndef LIGHTING_GLSL
#define LIGHTING_GLSL

// ============== Light Types ==============
const int LIGHT_TYPE_DIRECTIONAL = 0;
const int LIGHT_TYPE_POINT       = 1;
const int LIGHT_TYPE_SPOT        = 2;

const int MAX_LIGHTS = 8;

/**
 * Compute distance attenuation for point/spot lights.
 *
 * Uses the formula: 1 / (constant + linear*d + quadratic*d^2)
 * With range cutoff.
 *
 * Parameters:
 *   attenuation: vec3(constant, linear, quadratic)
 *   range: maximum light range (0 = infinite)
 *   dist: distance from light to fragment
 *
 * Returns:
 *   Attenuation factor [0, 1]
 */
float compute_distance_attenuation(vec3 attenuation, float range, float dist) {
    float denom = attenuation.x + attenuation.y * dist + attenuation.z * dist * dist;
    if (denom <= 0.0) {
        return 1.0;
    }
    float w = 1.0 / denom;
    if (range > 0.0 && dist > range) {
        w = 0.0;
    }
    return w;
}

/**
 * Compute spotlight cone falloff.
 *
 * Parameters:
 *   light_dir: normalized direction the spotlight is pointing
 *   L: normalized direction from fragment to light
 *   inner_angle: inner cone angle in radians (full intensity)
 *   outer_angle: outer cone angle in radians (zero intensity)
 *
 * Returns:
 *   Spotlight weight [0, 1] with smooth falloff
 */
float compute_spot_weight(vec3 light_dir, vec3 L, float inner_angle, float outer_angle) {
    float cos_theta = dot(light_dir, -L);
    float cos_outer = cos(outer_angle);
    float cos_inner = cos(inner_angle);

    if (cos_theta <= cos_outer) return 0.0;
    if (cos_theta >= cos_inner) return 1.0;

    float t = (cos_theta - cos_outer) / (cos_inner - cos_outer);
    return t * t * (3.0 - 2.0 * t); // smoothstep
}

/**
 * Blinn-Phong specular highlight.
 *
 * Parameters:
 *   N: surface normal (normalized)
 *   L: direction to light (normalized)
 *   V: direction to viewer (normalized)
 *   shininess: specular exponent (higher = smaller highlight)
 *
 * Returns:
 *   Specular intensity
 */
float blinn_phong_specular(vec3 N, vec3 L, vec3 V, float shininess) {
    vec3 H = normalize(L + V);
    float NdotH = max(dot(N, H), 0.0);
    return pow(NdotH, shininess);
}

#endif // LIGHTING_GLSL
