// tc_animation.h - Animation clip data structures
#pragma once

#include "tc_types.h"
#include "tc_handle.h"
#include "tc_resource.h"
#include <stdlib.h>

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
    double value[3];
} tc_keyframe_vec3;

typedef struct tc_keyframe_quat {
    double time;
    double value[4];  // [x, y, z, w]
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
    char target_name[TC_CHANNEL_NAME_MAX];  // bone/node name

    tc_keyframe_vec3* translation_keys;     // owned, malloc'd
    size_t translation_count;

    tc_keyframe_quat* rotation_keys;        // owned, malloc'd
    size_t rotation_count;

    tc_keyframe_scalar* scale_keys;         // owned, malloc'd
    size_t scale_count;

    double duration;  // in ticks
} tc_animation_channel;

// ============================================================================
// Animation clip
// ============================================================================

typedef struct tc_animation {
    tc_resource_header header;  // common resource fields

    tc_animation_channel* channels;  // array of channels (owned, malloc'd)
    size_t channel_count;

    double duration;    // in seconds
    double tps;         // ticks per second
    uint8_t loop;
    uint8_t _pad[7];
} tc_animation;

// ============================================================================
// Channel helpers
// ============================================================================

// Initialize channel to empty
static inline void tc_animation_channel_init(tc_animation_channel* ch) {
    if (!ch) return;
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
    if (!ch) return;
    if (ch->translation_keys) { free(ch->translation_keys); ch->translation_keys = NULL; }
    if (ch->rotation_keys) { free(ch->rotation_keys); ch->rotation_keys = NULL; }
    if (ch->scale_keys) { free(ch->scale_keys); ch->scale_keys = NULL; }
    ch->translation_count = 0;
    ch->rotation_count = 0;
    ch->scale_count = 0;
    ch->duration = 0.0;
}

// ============================================================================
// Reference counting
// ============================================================================

TC_API void tc_animation_add_ref(tc_animation* animation);
TC_API bool tc_animation_release(tc_animation* animation);

#ifdef __cplusplus
}
#endif
