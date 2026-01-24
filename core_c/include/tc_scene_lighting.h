// tc_scene_lighting.h - Scene lighting properties (ambient, shadows)
#ifndef TC_SCENE_LIGHTING_H
#define TC_SCENE_LIGHTING_H

#include "tc_types.h"

#ifdef __cplusplus
extern "C" {
#endif

// Shadow sampling method
typedef enum tc_shadow_method {
    TC_SHADOW_METHOD_HARD = 0,
    TC_SHADOW_METHOD_PCF = 1,
    TC_SHADOW_METHOD_POISSON = 2
} tc_shadow_method;

// Scene lighting properties
typedef struct tc_scene_lighting {
    // Ambient lighting
    float ambient_color[3];   // RGB, default (1, 1, 1)
    float ambient_intensity;  // Default 0.1

    // Shadow settings
    int shadow_method;        // tc_shadow_method, default PCF
    float shadow_softness;    // Sampling radius multiplier, default 1.0
    float shadow_bias;        // Depth bias, default 0.005
} tc_scene_lighting;

// Initialize with defaults
TC_API void tc_scene_lighting_init(tc_scene_lighting* lighting);

// ============================================================================
// Scene Lighting API
// ============================================================================

// Get lighting properties from scene (returns internal pointer, do not free)
TC_API tc_scene_lighting* tc_scene_get_lighting(tc_scene* s);

// Convenience setters
TC_API void tc_scene_set_ambient(tc_scene* s, float r, float g, float b, float intensity);
TC_API void tc_scene_set_shadow_settings(tc_scene* s, int method, float softness, float bias);

#ifdef __cplusplus
}
#endif

#endif // TC_SCENE_LIGHTING_H
