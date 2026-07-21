#include "tc_audio_internal.h"

#include <limits.h>
#include <stdlib.h>
#include <string.h>

#include <tcbase/tc_log.h>

#include <miniaudio.h>

bool tc_audio_backend_decode_file(
    const char* path,
    void** frames,
    uint64_t* frame_count,
    uint32_t* sample_rate,
    uint16_t* channels
) {
    if (!path || !path[0] || !frames || !frame_count || !sample_rate || !channels) {
        tc_log_error("tc_audio_backend_decode_file: invalid arguments");
        return false;
    }

    ma_decoder_config config = ma_decoder_config_init(ma_format_f32, 0, 0);
    ma_uint64 decoded_frame_count = 0;
    void* decoded_frames = NULL;
    ma_result result = ma_decode_file(path, &config, &decoded_frame_count, &decoded_frames);
    if (result != MA_SUCCESS) {
        tc_log_error(
            "tc_audio_backend_decode_file: failed to decode '%s': %s",
            path,
            ma_result_description(result)
        );
        return false;
    }

    if (!decoded_frames || decoded_frame_count == 0 || config.channels == 0 || config.sampleRate == 0) {
        tc_log_error("tc_audio_backend_decode_file: decoder returned empty audio for '%s'", path);
        ma_free(decoded_frames, NULL);
        return false;
    }
    if (config.channels > UINT16_MAX) {
        tc_log_error(
            "tc_audio_backend_decode_file: unsupported channel count %u for '%s'",
            config.channels,
            path
        );
        ma_free(decoded_frames, NULL);
        return false;
    }
    if (decoded_frame_count > SIZE_MAX / config.channels / sizeof(float)) {
        tc_log_error("tc_audio_backend_decode_file: decoded audio is too large for '%s'", path);
        ma_free(decoded_frames, NULL);
        return false;
    }

    const size_t byte_count = (size_t)decoded_frame_count * config.channels * sizeof(float);
    void* owned_frames = malloc(byte_count);
    if (!owned_frames) {
        tc_log_error(
            "tc_audio_backend_decode_file: failed to allocate %zu bytes for '%s'",
            byte_count,
            path
        );
        ma_free(decoded_frames, NULL);
        return false;
    }
    memcpy(owned_frames, decoded_frames, byte_count);
    ma_free(decoded_frames, NULL);

    *frames = owned_frames;
    *frame_count = decoded_frame_count;
    *sample_rate = config.sampleRate;
    *channels = (uint16_t)config.channels;
    return true;
}

