#pragma once

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#include <tcbase/tc_binding_types.h>
#include <tcbase/tc_resource.h>
#include <termin/audio/termin_audio_api.h>

#ifdef __cplusplus
extern "C" {
#endif

TC_DEFINE_HANDLE(tc_audio_clip_handle)

typedef enum tc_audio_sample_format {
    TC_AUDIO_SAMPLE_FORMAT_UNKNOWN = 0,
    TC_AUDIO_SAMPLE_FORMAT_U8 = 1,
    TC_AUDIO_SAMPLE_FORMAT_S16 = 2,
    TC_AUDIO_SAMPLE_FORMAT_S24 = 3,
    TC_AUDIO_SAMPLE_FORMAT_S32 = 4,
    TC_AUDIO_SAMPLE_FORMAT_F32 = 5,
} tc_audio_sample_format;

typedef struct tc_audio_clip {
    tc_resource_header header;
    void* pcm_frames;
    uint64_t frame_count;
    uint32_t sample_rate;
    uint16_t channels;
    uint16_t sample_format;
    const char* source_path;
} tc_audio_clip;

TERMIN_AUDIO_API void tc_audio_clip_add_ref(tc_audio_clip* clip);
TERMIN_AUDIO_API bool tc_audio_clip_release(tc_audio_clip* clip);

TERMIN_AUDIO_API bool tc_audio_clip_set_pcm(
    tc_audio_clip_handle handle,
    const void* frames,
    uint64_t frame_count,
    uint32_t sample_rate,
    uint16_t channels,
    tc_audio_sample_format format
);
TERMIN_AUDIO_API bool tc_audio_clip_load_file(tc_audio_clip_handle handle, const char* path);
TERMIN_AUDIO_API bool tc_audio_clip_ensure_loaded(tc_audio_clip_handle handle);
TERMIN_AUDIO_API bool tc_audio_clip_unload(tc_audio_clip_handle handle);

TERMIN_AUDIO_API size_t tc_audio_sample_size(tc_audio_sample_format format);
TERMIN_AUDIO_API double tc_audio_clip_duration_seconds(tc_audio_clip_handle handle);
TERMIN_AUDIO_API uint64_t tc_audio_clip_duration_ms(tc_audio_clip_handle handle);

#ifdef __cplusplus
}
#endif
