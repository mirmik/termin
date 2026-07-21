#pragma once

#include <stdbool.h>
#include <stdint.h>

#include <termin/audio/tc_audio_clip.h>

bool tc_audio_backend_decode_file(
    const char* path,
    void** frames,
    uint64_t* frame_count,
    uint32_t* sample_rate,
    uint16_t* channels
);

bool tc_audio_voice_pool_uses_clip(tc_audio_clip_handle clip);

