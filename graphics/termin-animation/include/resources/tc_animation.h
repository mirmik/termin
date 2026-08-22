// tc_animation.h - Animation clip data structures
#pragma once

#include <geom/tc_vec4.h>
#include <stdlib.h>
#include <tcbase/tc_binding_types.h>
#include <tcbase/tc_resource.h>
#include <tcbase/tc_types.h>

#ifdef __cplusplus
extern "C" {
#endif

// ============================================================================
// Animation handle - safe reference to animation in pool
// ============================================================================

TC_DEFINE_HANDLE(tc_animation_handle)

// ============================================================================
// Keyframe types
// ============================================================================

typedef struct tc_keyframe_vec3 {
    double time;
    tc_vec3 value;
} tc_keyframe_vec3;

typedef struct tc_keyframe_quat {
    double time;
    tc_quat value;
} tc_keyframe_quat;

typedef struct tc_keyframe_scalar {
    double time;
    double value;
} tc_keyframe_scalar;

// ============================================================================
// Animation channel (one per bone/node)
// ============================================================================

#define TC_CHANNEL_NAME_MAX 64

typedef struct tc_animation_channel {
    char target_name[TC_CHANNEL_NAME_MAX]; // bone/node name

    tc_keyframe_vec3* translation_keys; // owned, malloc'd
    size_t translation_count;

    tc_keyframe_quat* rotation_keys; // owned, malloc'd
    size_t rotation_count;

    tc_keyframe_scalar* scale_keys; // owned, malloc'd
    size_t scale_count;

    double duration; // in ticks
} tc_animation_channel;

// ============================================================================
// Bulk animation tracks
// ============================================================================

typedef enum tc_animation_path {
    TC_ANIMATION_PATH_TRANSLATION = 0,
    TC_ANIMATION_PATH_ROTATION = 1,
    TC_ANIMATION_PATH_SCALE = 2,
    TC_ANIMATION_PATH_WEIGHTS = 3,
} tc_animation_path;

typedef enum tc_animation_interpolation {
    TC_ANIMATION_INTERPOLATION_LINEAR = 0,
    TC_ANIMATION_INTERPOLATION_STEP = 1,
    TC_ANIMATION_INTERPOLATION_CUBIC_SPLINE = 2,
} tc_animation_interpolation;

typedef struct tc_animation_cubic_vec3_key {
    tc_vec3 in_tangent;
    tc_vec3 value;
    tc_vec3 out_tangent;
} tc_animation_cubic_vec3_key;

// glTF quaternion spline tangents are ordinary vec4 derivatives. They are
// finite but are not rotations and must never be normalized.
typedef struct tc_animation_cubic_rotation_key {
    tc_vec4 in_tangent;
    tc_quat value;
    tc_vec4 out_tangent;
} tc_animation_cubic_rotation_key;

typedef struct tc_animation_weight_values {
    uint32_t component_count;
    double* values;
} tc_animation_weight_values;

// path + interpolation discriminate the active member. Geometry tracks own
// typed values; only variable-width morph weights remain a packed scalar array.
typedef union tc_animation_track_values {
    tc_vec3* vec3_values;
    tc_quat* rotation_values;
    tc_animation_cubic_vec3_key* cubic_vec3_keys;
    tc_animation_cubic_rotation_key* cubic_rotation_keys;
    tc_animation_weight_values weights;
} tc_animation_track_values;

// One self-contained owned runtime track. Flat component arrays are accepted
// only through tc_animation_track_desc and converted at publication.
typedef struct tc_animation_track {
    int32_t target_node_index;
    uint8_t path;          // tc_animation_path
    uint8_t interpolation; // tc_animation_interpolation
    uint16_t _pad;
    size_t key_count;
    double* times;
    tc_animation_track_values values;
} tc_animation_track;

// Non-owning input used by transactional bulk replacement.
typedef struct tc_animation_track_desc {
    int32_t target_node_index;
    tc_animation_path path;
    tc_animation_interpolation interpolation;
    uint32_t components;
    size_t key_count;
    size_t value_count;
    const double* times;
    const double* values;
} tc_animation_track_desc;

// ============================================================================
// Animation clip
// ============================================================================

typedef struct tc_animation {
    tc_resource_header header; // common resource fields

    tc_animation_channel* channels; // array of channels (owned, malloc'd)
    size_t channel_count;

    tc_animation_track* tracks; // bulk tracks (owned, malloc'd)
    size_t track_count;

    double duration; // in seconds
    double tps;      // ticks per second
    uint8_t loop;
    uint8_t _pad[7];
} tc_animation;

// ============================================================================
// Channel helpers
// ============================================================================

// Initialize channel to empty
static inline void tc_animation_channel_init(tc_animation_channel* ch) {
    if (!ch)
        return;
    ch->target_name[0] = '\0';
    ch->translation_keys = NULL;
    ch->translation_count = 0;
    ch->rotation_keys = NULL;
    ch->rotation_count = 0;
    ch->scale_keys = NULL;
    ch->scale_count = 0;
    ch->duration = 0.0;
}

// Free channel data (does not free the channel struct itself)
static inline void tc_animation_channel_free(tc_animation_channel* ch) {
    if (!ch)
        return;
    if (ch->translation_keys) {
        free(ch->translation_keys);
        ch->translation_keys = NULL;
    }
    if (ch->rotation_keys) {
        free(ch->rotation_keys);
        ch->rotation_keys = NULL;
    }
    if (ch->scale_keys) {
        free(ch->scale_keys);
        ch->scale_keys = NULL;
    }
    ch->translation_count = 0;
    ch->rotation_count = 0;
    ch->scale_count = 0;
    ch->duration = 0.0;
}

// ============================================================================
// Channel sample result
// ============================================================================

typedef struct tc_channel_sample {
    tc_vec3 translation;
    tc_quat rotation;
    double scale;
    uint8_t has_translation;
    uint8_t has_rotation;
    uint8_t has_scale;
    uint8_t _pad[5];
} tc_channel_sample;

typedef union tc_animation_track_sample_value {
    tc_vec3 translation;
    tc_quat rotation;
    tc_vec3 scale;
} tc_animation_track_sample_value;

// Typed result for the supported bulk TRS track paths. The path is the union
// discriminator. Sampling is transactional and writes the result only on
// success.
typedef struct tc_animation_track_sample_result {
    tc_animation_path path;
    tc_animation_track_sample_value value;
} tc_animation_track_sample_result;

// Initialize sample to empty
static inline void tc_channel_sample_init(tc_channel_sample* s) {
    if (!s)
        return;
    s->translation.x = 0.0;
    s->translation.y = 0.0;
    s->translation.z = 0.0;
    s->rotation.x = 0.0;
    s->rotation.y = 0.0;
    s->rotation.z = 0.0;
    s->rotation.w = 1.0;
    s->scale = 1.0;
    s->has_translation = 0;
    s->has_rotation = 0;
    s->has_scale = 0;
    s->_pad[0] = 0;
    s->_pad[1] = 0;
    s->_pad[2] = 0;
    s->_pad[3] = 0;
    s->_pad[4] = 0;
}

// ============================================================================
// Sampling functions
// ============================================================================

// Sample a single channel at time t_ticks. Quaternion keys are normalized at
// the sampling boundary. Invalid input is logged and leaves out unchanged.
TC_API bool tc_animation_channel_sample(const tc_animation_channel* ch,
                                        double t_ticks,
                                        tc_channel_sample* out);

// Sample animation at time t_seconds (handles looping and tps conversion)
// out_samples must be preallocated with animation->channel_count elements
// Returns number of channels sampled
TC_API size_t tc_animation_sample(const tc_animation* anim, double t_seconds, tc_channel_sample* out_samples);

// ============================================================================
// Reference counting
// ============================================================================

TC_API void tc_animation_add_ref(tc_animation* animation);
TC_API bool tc_animation_release(tc_animation* animation);

#ifdef __cplusplus
}
#endif
