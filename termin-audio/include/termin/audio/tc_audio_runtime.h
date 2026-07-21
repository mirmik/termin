#pragma once

#include <termin/audio/termin_audio_api.h>

#ifdef __cplusplus
extern "C" {
#endif

TERMIN_AUDIO_API void tc_audio_runtime_init(void);
TERMIN_AUDIO_API void tc_audio_runtime_shutdown(void);

#ifdef __cplusplus
}
#endif
