#pragma once

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#include <tcbase/tc_binding_types.h>
#include <termin/audio/tc_audio_clip.h>
#include <termin/audio/termin_audio_api.h>

#ifdef __cplusplus
extern "C" {
#endif

TC_DEFINE_HANDLE(tc_audio_voice_handle)

typedef struct tc_audio_engine_config {
    uint32_t sample_rate;
    uint16_t channels;
    bool no_device;
} tc_audio_engine_config;

TERMIN_AUDIO_API tc_audio_engine_config tc_audio_engine_config_default(void);
TERMIN_AUDIO_API bool tc_audio_engine_init(const tc_audio_engine_config* config);
TERMIN_AUDIO_API void tc_audio_engine_shutdown(void);
TERMIN_AUDIO_API bool tc_audio_engine_is_initialized(void);
TERMIN_AUDIO_API bool tc_audio_engine_has_device(void);
TERMIN_AUDIO_API uint32_t tc_audio_engine_sample_rate(void);
TERMIN_AUDIO_API uint16_t tc_audio_engine_channels(void);
TERMIN_AUDIO_API bool tc_audio_engine_render(float* output, uint64_t frame_count);
TERMIN_AUDIO_API void tc_audio_engine_set_master_volume(float volume);
TERMIN_AUDIO_API float tc_audio_engine_get_master_volume(void);
TERMIN_AUDIO_API void tc_audio_engine_set_listener_position(float x, float y, float z);
TERMIN_AUDIO_API void tc_audio_engine_get_listener_position(float* x, float* y, float* z);
TERMIN_AUDIO_API void tc_audio_engine_set_listener_direction(float x, float y, float z);
TERMIN_AUDIO_API void tc_audio_engine_set_listener_velocity(float x, float y, float z);

TERMIN_AUDIO_API tc_audio_voice_handle tc_audio_voice_create(tc_audio_clip_handle clip);
TERMIN_AUDIO_API bool tc_audio_voice_destroy(tc_audio_voice_handle voice);
TERMIN_AUDIO_API bool tc_audio_voice_is_valid(tc_audio_voice_handle voice);
TERMIN_AUDIO_API tc_audio_clip_handle tc_audio_voice_clip(tc_audio_voice_handle voice);
TERMIN_AUDIO_API bool tc_audio_voice_start(tc_audio_voice_handle voice);
TERMIN_AUDIO_API bool tc_audio_voice_stop(tc_audio_voice_handle voice, uint32_t fade_out_ms);
TERMIN_AUDIO_API bool tc_audio_voice_pause(tc_audio_voice_handle voice);
TERMIN_AUDIO_API bool tc_audio_voice_resume(tc_audio_voice_handle voice);
TERMIN_AUDIO_API bool tc_audio_voice_is_playing(tc_audio_voice_handle voice);
TERMIN_AUDIO_API bool tc_audio_voice_is_paused(tc_audio_voice_handle voice);
TERMIN_AUDIO_API void tc_audio_voice_set_looping(tc_audio_voice_handle voice, bool looping);
TERMIN_AUDIO_API bool tc_audio_voice_is_looping(tc_audio_voice_handle voice);
TERMIN_AUDIO_API void tc_audio_voice_set_volume(tc_audio_voice_handle voice, float volume);
TERMIN_AUDIO_API float tc_audio_voice_get_volume(tc_audio_voice_handle voice);
TERMIN_AUDIO_API void tc_audio_voice_set_pitch(tc_audio_voice_handle voice, float pitch);
TERMIN_AUDIO_API float tc_audio_voice_get_pitch(tc_audio_voice_handle voice);
TERMIN_AUDIO_API void tc_audio_voice_set_spatialization(tc_audio_voice_handle voice, bool enabled);
TERMIN_AUDIO_API void tc_audio_voice_set_position(tc_audio_voice_handle voice, float x, float y, float z);
TERMIN_AUDIO_API void tc_audio_voice_get_position(tc_audio_voice_handle voice, float* x, float* y, float* z);
TERMIN_AUDIO_API void tc_audio_voice_set_velocity(tc_audio_voice_handle voice, float x, float y, float z);
TERMIN_AUDIO_API void tc_audio_voice_set_distance_range(tc_audio_voice_handle voice, float min_distance, float max_distance);
TERMIN_AUDIO_API size_t tc_audio_voice_count(void);
TERMIN_AUDIO_API size_t tc_audio_voice_capacity(void);
TERMIN_AUDIO_API tc_audio_voice_handle tc_audio_voice_at(size_t pool_index);

#ifdef __cplusplus
}
#endif
