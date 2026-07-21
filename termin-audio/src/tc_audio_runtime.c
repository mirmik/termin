#include <termin/audio/tc_audio_runtime.h>

#include <termin/audio/tc_audio_clip_registry.h>
#include <termin/audio/tc_audio_engine.h>

void tc_audio_runtime_init(void) {
    tc_audio_clip_registry_init();
}

void tc_audio_runtime_shutdown(void) {
    tc_audio_engine_shutdown();
    tc_audio_clip_registry_shutdown();
}

