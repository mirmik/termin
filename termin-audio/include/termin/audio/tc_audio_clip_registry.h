#pragma once

#include <termin/audio/tc_audio_clip.h>

#ifdef __cplusplus
extern "C" {
#endif

TERMIN_AUDIO_API void tc_audio_clip_registry_init(void);
TERMIN_AUDIO_API void tc_audio_clip_registry_shutdown(void);

TERMIN_AUDIO_API tc_audio_clip_handle tc_audio_clip_create(const char* uuid);
TERMIN_AUDIO_API tc_audio_clip_handle tc_audio_clip_declare(
    const char* uuid,
    const char* name,
    const char* source_path
);
TERMIN_AUDIO_API tc_audio_clip_handle tc_audio_clip_find(const char* uuid);
TERMIN_AUDIO_API tc_audio_clip_handle tc_audio_clip_find_by_name(const char* name);
TERMIN_AUDIO_API tc_audio_clip_handle tc_audio_clip_get_or_create(const char* uuid);
TERMIN_AUDIO_API tc_audio_clip* tc_audio_clip_get(tc_audio_clip_handle handle);
TERMIN_AUDIO_API bool tc_audio_clip_is_valid(tc_audio_clip_handle handle);
TERMIN_AUDIO_API bool tc_audio_clip_destroy(tc_audio_clip_handle handle);
TERMIN_AUDIO_API size_t tc_audio_clip_count(void);

TERMIN_AUDIO_API bool tc_audio_clip_set_name(tc_audio_clip_handle handle, const char* name);
TERMIN_AUDIO_API bool tc_audio_clip_set_source_path(tc_audio_clip_handle handle, const char* source_path);

#ifdef __cplusplus
}
#endif
