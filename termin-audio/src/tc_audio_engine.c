#include <termin/audio/tc_audio_engine.h>
#include <termin/audio/tc_audio_clip_registry.h>

#include "tc_audio_internal.h"

#include <string.h>

#include <tcbase/tc_log.h>
#include <tcbase/tc_pool.h>

#include <miniaudio.h>

typedef struct tc_audio_voice_slot {
    tc_audio_clip_handle clip;
    ma_audio_buffer_ref buffer;
    ma_sound sound;
    bool buffer_initialized;
    bool sound_initialized;
    bool paused;
} tc_audio_voice_slot;

static ma_engine g_audio_engine;
static tc_pool g_audio_voice_pool;
static uint32_t g_audio_voice_generation_floor = 1;
static bool g_audio_engine_initialized = false;
static bool g_audio_engine_has_device = false;
static bool g_audio_voice_pool_initialized = false;

static ma_format audio_format_to_miniaudio(tc_audio_sample_format format) {
    switch (format) {
        case TC_AUDIO_SAMPLE_FORMAT_U8: return ma_format_u8;
        case TC_AUDIO_SAMPLE_FORMAT_S16: return ma_format_s16;
        case TC_AUDIO_SAMPLE_FORMAT_S24: return ma_format_s24;
        case TC_AUDIO_SAMPLE_FORMAT_S32: return ma_format_s32;
        case TC_AUDIO_SAMPLE_FORMAT_F32: return ma_format_f32;
        default: return ma_format_unknown;
    }
}

static void audio_voice_advance_generation_floor(void) {
    uint32_t max_generation = g_audio_voice_generation_floor;
    for (uint32_t i = 0; i < g_audio_voice_pool.capacity; ++i) {
        if (g_audio_voice_pool.generations[i] > max_generation) {
            max_generation = g_audio_voice_pool.generations[i];
        }
    }
    g_audio_voice_generation_floor = max_generation + 1;
    if (g_audio_voice_generation_floor == 0) {
        g_audio_voice_generation_floor = 1;
    }
}

static bool audio_voice_pool_init(void) {
    if (g_audio_voice_pool_initialized) return true;
    if (!tc_pool_init(&g_audio_voice_pool, sizeof(tc_audio_voice_slot), 32)) {
        tc_log_error("audio_voice_pool_init: failed to initialize voice pool");
        return false;
    }
    for (uint32_t i = 0; i < g_audio_voice_pool.capacity; ++i) {
        g_audio_voice_pool.generations[i] = g_audio_voice_generation_floor;
    }
    g_audio_voice_pool_initialized = true;
    return true;
}

static tc_audio_voice_handle audio_voice_allocate(void) {
    tc_audio_voice_handle handle = tc_pool_alloc(&g_audio_voice_pool);
    if (tc_audio_voice_handle_is_invalid(handle)) return handle;
    if (handle.generation < g_audio_voice_generation_floor) {
        g_audio_voice_pool.generations[handle.index] = g_audio_voice_generation_floor;
        handle.generation = g_audio_voice_generation_floor;
    }
    return handle;
}

static tc_audio_voice_slot* audio_voice_get(tc_audio_voice_handle voice) {
    if (!g_audio_voice_pool_initialized) return NULL;
    return (tc_audio_voice_slot*)tc_pool_get(&g_audio_voice_pool, voice);
}

static void audio_voice_pool_shutdown(void) {
    if (!g_audio_voice_pool_initialized) return;
    for (uint32_t i = 0; i < g_audio_voice_pool.capacity; ++i) {
        if (g_audio_voice_pool.states[i] != TC_SLOT_OCCUPIED) continue;
        tc_audio_voice_handle voice = {i, g_audio_voice_pool.generations[i]};
        tc_audio_voice_destroy(voice);
    }
    audio_voice_advance_generation_floor();
    tc_pool_free(&g_audio_voice_pool);
    g_audio_voice_pool_initialized = false;
}

bool tc_audio_voice_pool_uses_clip(tc_audio_clip_handle clip) {
    if (!g_audio_voice_pool_initialized || tc_audio_clip_handle_is_invalid(clip)) return false;
    for (uint32_t i = 0; i < g_audio_voice_pool.capacity; ++i) {
        if (g_audio_voice_pool.states[i] != TC_SLOT_OCCUPIED) continue;
        tc_audio_voice_slot* voice = (tc_audio_voice_slot*)tc_pool_get_unchecked(&g_audio_voice_pool, i);
        if (tc_audio_clip_handle_eq(voice->clip, clip)) return true;
    }
    return false;
}

tc_audio_engine_config tc_audio_engine_config_default(void) {
    tc_audio_engine_config config;
    config.sample_rate = 48000;
    config.channels = 2;
    config.no_device = false;
    return config;
}

bool tc_audio_engine_init(const tc_audio_engine_config* config) {
    if (g_audio_engine_initialized) return true;
    tc_audio_engine_config selected = config ? *config : tc_audio_engine_config_default();
    if (selected.sample_rate == 0 || selected.channels == 0) {
        tc_log_error("tc_audio_engine_init: sample rate and channel count must be non-zero");
        return false;
    }
    if (!audio_voice_pool_init()) return false;

    ma_engine_config engine_config = ma_engine_config_init();
    engine_config.sampleRate = selected.sample_rate;
    engine_config.channels = selected.channels;
    engine_config.noDevice = selected.no_device ? MA_TRUE : MA_FALSE;
    ma_result result = ma_engine_init(&engine_config, &g_audio_engine);
    if (result != MA_SUCCESS) {
        tc_log_error("tc_audio_engine_init: %s", ma_result_description(result));
        audio_voice_pool_shutdown();
        return false;
    }

    g_audio_engine_initialized = true;
    g_audio_engine_has_device = !selected.no_device;
    tc_log_info(
        "tc_audio_engine_init: initialized %u Hz, %u channels, device=%s",
        ma_engine_get_sample_rate(&g_audio_engine),
        ma_engine_get_channels(&g_audio_engine),
        g_audio_engine_has_device ? "yes" : "no"
    );
    return true;
}

void tc_audio_engine_shutdown(void) {
    if (!g_audio_engine_initialized) {
        audio_voice_pool_shutdown();
        return;
    }
    audio_voice_pool_shutdown();
    ma_engine_uninit(&g_audio_engine);
    memset(&g_audio_engine, 0, sizeof(g_audio_engine));
    g_audio_engine_initialized = false;
    g_audio_engine_has_device = false;
}

bool tc_audio_engine_is_initialized(void) {
    return g_audio_engine_initialized;
}

bool tc_audio_engine_has_device(void) {
    return g_audio_engine_initialized && g_audio_engine_has_device;
}

uint32_t tc_audio_engine_sample_rate(void) {
    return g_audio_engine_initialized ? ma_engine_get_sample_rate(&g_audio_engine) : 0;
}

uint16_t tc_audio_engine_channels(void) {
    return g_audio_engine_initialized ? (uint16_t)ma_engine_get_channels(&g_audio_engine) : 0;
}

bool tc_audio_engine_render(float* output, uint64_t frame_count) {
    if (!g_audio_engine_initialized || !output || frame_count == 0) {
        tc_log_error("tc_audio_engine_render: engine, output, and frame count are required");
        return false;
    }
    if (g_audio_engine_has_device) {
        tc_log_error("tc_audio_engine_render: offline rendering requires a no-device engine");
        return false;
    }
    ma_uint64 frames_read = 0;
    ma_result result = ma_engine_read_pcm_frames(&g_audio_engine, output, frame_count, &frames_read);
    if (result != MA_SUCCESS || frames_read != frame_count) {
        tc_log_error(
            "tc_audio_engine_render: requested %llu frames, got %llu: %s",
            (unsigned long long)frame_count,
            (unsigned long long)frames_read,
            ma_result_description(result)
        );
        return false;
    }
    return true;
}

void tc_audio_engine_set_master_volume(float volume) {
    if (!g_audio_engine_initialized) return;
    ma_engine_set_volume(&g_audio_engine, volume < 0.0f ? 0.0f : volume);
}

float tc_audio_engine_get_master_volume(void) {
    return g_audio_engine_initialized ? ma_engine_get_volume(&g_audio_engine) : 0.0f;
}

void tc_audio_engine_set_listener_position(float x, float y, float z) {
    if (g_audio_engine_initialized) ma_engine_listener_set_position(&g_audio_engine, 0, x, y, z);
}

void tc_audio_engine_get_listener_position(float* x, float* y, float* z) {
    ma_vec3f position = {0.0f, 0.0f, 0.0f};
    if (g_audio_engine_initialized) {
        position = ma_engine_listener_get_position(&g_audio_engine, 0);
    }
    if (x) *x = position.x;
    if (y) *y = position.y;
    if (z) *z = position.z;
}

void tc_audio_engine_set_listener_direction(float x, float y, float z) {
    if (g_audio_engine_initialized) ma_engine_listener_set_direction(&g_audio_engine, 0, x, y, z);
}

void tc_audio_engine_set_listener_velocity(float x, float y, float z) {
    if (g_audio_engine_initialized) ma_engine_listener_set_velocity(&g_audio_engine, 0, x, y, z);
}

tc_audio_voice_handle tc_audio_voice_create(tc_audio_clip_handle clip_handle) {
    if (!g_audio_engine_initialized) {
        tc_log_error("tc_audio_voice_create: audio engine is not initialized");
        return tc_audio_voice_handle_invalid();
    }
    tc_audio_clip* clip = tc_audio_clip_get(clip_handle);
    if (!clip) {
        tc_log_error("tc_audio_voice_create: stale clip handle");
        return tc_audio_voice_handle_invalid();
    }
    if (!tc_audio_clip_ensure_loaded(clip_handle)) return tc_audio_voice_handle_invalid();
    const ma_format format = audio_format_to_miniaudio((tc_audio_sample_format)clip->sample_format);
    if (format == ma_format_unknown) {
        tc_log_error("tc_audio_voice_create: unsupported sample format for '%s'", clip->header.uuid);
        return tc_audio_voice_handle_invalid();
    }

    tc_audio_voice_handle voice_handle = audio_voice_allocate();
    if (tc_audio_voice_handle_is_invalid(voice_handle)) {
        tc_log_error("tc_audio_voice_create: voice pool allocation failed");
        return voice_handle;
    }
    tc_audio_voice_slot* voice = audio_voice_get(voice_handle);
    voice->clip = clip_handle;

    ma_result result = ma_audio_buffer_ref_init(
        format,
        clip->channels,
        clip->pcm_frames,
        clip->frame_count,
        &voice->buffer
    );
    if (result != MA_SUCCESS) {
        tc_log_error("tc_audio_voice_create: buffer init failed: %s", ma_result_description(result));
        tc_pool_free_slot(&g_audio_voice_pool, voice_handle);
        return tc_audio_voice_handle_invalid();
    }
    voice->buffer.sampleRate = clip->sample_rate;
    voice->buffer_initialized = true;

    result = ma_sound_init_from_data_source(
        &g_audio_engine,
        (ma_data_source*)&voice->buffer,
        0,
        NULL,
        &voice->sound
    );
    if (result != MA_SUCCESS) {
        tc_log_error("tc_audio_voice_create: sound init failed: %s", ma_result_description(result));
        ma_audio_buffer_ref_uninit(&voice->buffer);
        tc_pool_free_slot(&g_audio_voice_pool, voice_handle);
        return tc_audio_voice_handle_invalid();
    }
    voice->sound_initialized = true;
    tc_audio_clip_add_ref(clip);
    return voice_handle;
}

bool tc_audio_voice_destroy(tc_audio_voice_handle voice_handle) {
    tc_audio_voice_slot* voice = audio_voice_get(voice_handle);
    if (!voice) return false;
    tc_audio_clip_handle clip_handle = voice->clip;
    if (voice->sound_initialized) ma_sound_uninit(&voice->sound);
    if (voice->buffer_initialized) ma_audio_buffer_ref_uninit(&voice->buffer);
    voice->sound_initialized = false;
    voice->buffer_initialized = false;
    voice->clip = tc_audio_clip_handle_invalid();
    if (!tc_pool_free_slot(&g_audio_voice_pool, voice_handle)) {
        tc_log_error("tc_audio_voice_destroy: failed to free voice slot");
        return false;
    }
    tc_audio_clip* clip = tc_audio_clip_get(clip_handle);
    if (clip) tc_audio_clip_release(clip);
    return true;
}

bool tc_audio_voice_is_valid(tc_audio_voice_handle voice) {
    return audio_voice_get(voice) != NULL;
}

tc_audio_clip_handle tc_audio_voice_clip(tc_audio_voice_handle voice) {
    tc_audio_voice_slot* slot = audio_voice_get(voice);
    return slot ? slot->clip : tc_audio_clip_handle_invalid();
}

bool tc_audio_voice_start(tc_audio_voice_handle voice) {
    tc_audio_voice_slot* slot = audio_voice_get(voice);
    if (!slot) return false;
    if (ma_sound_at_end(&slot->sound)) ma_sound_seek_to_pcm_frame(&slot->sound, 0);
    const ma_result result = ma_sound_start(&slot->sound);
    if (result != MA_SUCCESS) {
        tc_log_error("tc_audio_voice_start: %s", ma_result_description(result));
        return false;
    }
    slot->paused = false;
    return true;
}

bool tc_audio_voice_stop(tc_audio_voice_handle voice, uint32_t fade_out_ms) {
    tc_audio_voice_slot* slot = audio_voice_get(voice);
    if (!slot) return false;
    ma_result result;
    if (fade_out_ms > 0) {
        result = ma_sound_stop_with_fade_in_milliseconds(&slot->sound, fade_out_ms);
    } else {
        result = ma_sound_stop(&slot->sound);
        if (result == MA_SUCCESS) result = ma_sound_seek_to_pcm_frame(&slot->sound, 0);
    }
    if (result != MA_SUCCESS) {
        tc_log_error("tc_audio_voice_stop: %s", ma_result_description(result));
        return false;
    }
    slot->paused = false;
    return true;
}

bool tc_audio_voice_pause(tc_audio_voice_handle voice) {
    tc_audio_voice_slot* slot = audio_voice_get(voice);
    if (!slot) return false;
    const ma_result result = ma_sound_stop(&slot->sound);
    if (result != MA_SUCCESS) {
        tc_log_error("tc_audio_voice_pause: %s", ma_result_description(result));
        return false;
    }
    slot->paused = true;
    return true;
}

bool tc_audio_voice_resume(tc_audio_voice_handle voice) {
    tc_audio_voice_slot* slot = audio_voice_get(voice);
    if (!slot || !slot->paused) return false;
    const ma_result result = ma_sound_start(&slot->sound);
    if (result != MA_SUCCESS) {
        tc_log_error("tc_audio_voice_resume: %s", ma_result_description(result));
        return false;
    }
    slot->paused = false;
    return true;
}

bool tc_audio_voice_is_playing(tc_audio_voice_handle voice) {
    tc_audio_voice_slot* slot = audio_voice_get(voice);
    return slot && ma_sound_is_playing(&slot->sound) == MA_TRUE;
}

bool tc_audio_voice_is_paused(tc_audio_voice_handle voice) {
    tc_audio_voice_slot* slot = audio_voice_get(voice);
    return slot && slot->paused;
}

void tc_audio_voice_set_looping(tc_audio_voice_handle voice, bool looping) {
    tc_audio_voice_slot* slot = audio_voice_get(voice);
    if (slot) ma_sound_set_looping(&slot->sound, looping ? MA_TRUE : MA_FALSE);
}

bool tc_audio_voice_is_looping(tc_audio_voice_handle voice) {
    tc_audio_voice_slot* slot = audio_voice_get(voice);
    return slot && ma_sound_is_looping(&slot->sound) == MA_TRUE;
}

void tc_audio_voice_set_volume(tc_audio_voice_handle voice, float volume) {
    tc_audio_voice_slot* slot = audio_voice_get(voice);
    if (slot) ma_sound_set_volume(&slot->sound, volume < 0.0f ? 0.0f : volume);
}

float tc_audio_voice_get_volume(tc_audio_voice_handle voice) {
    tc_audio_voice_slot* slot = audio_voice_get(voice);
    return slot ? ma_sound_get_volume(&slot->sound) : 0.0f;
}

void tc_audio_voice_set_pitch(tc_audio_voice_handle voice, float pitch) {
    tc_audio_voice_slot* slot = audio_voice_get(voice);
    if (slot) ma_sound_set_pitch(&slot->sound, pitch > 0.0f ? pitch : 0.001f);
}

float tc_audio_voice_get_pitch(tc_audio_voice_handle voice) {
    tc_audio_voice_slot* slot = audio_voice_get(voice);
    return slot ? ma_sound_get_pitch(&slot->sound) : 0.0f;
}

void tc_audio_voice_set_spatialization(tc_audio_voice_handle voice, bool enabled) {
    tc_audio_voice_slot* slot = audio_voice_get(voice);
    if (slot) ma_sound_set_spatialization_enabled(&slot->sound, enabled ? MA_TRUE : MA_FALSE);
}

void tc_audio_voice_set_position(tc_audio_voice_handle voice, float x, float y, float z) {
    tc_audio_voice_slot* slot = audio_voice_get(voice);
    if (slot) ma_sound_set_position(&slot->sound, x, y, z);
}

void tc_audio_voice_get_position(tc_audio_voice_handle voice, float* x, float* y, float* z) {
    tc_audio_voice_slot* slot = audio_voice_get(voice);
    const ma_vec3f position = slot ? ma_sound_get_position(&slot->sound) : (ma_vec3f){0, 0, 0};
    if (x) *x = position.x;
    if (y) *y = position.y;
    if (z) *z = position.z;
}

void tc_audio_voice_set_velocity(tc_audio_voice_handle voice, float x, float y, float z) {
    tc_audio_voice_slot* slot = audio_voice_get(voice);
    if (slot) ma_sound_set_velocity(&slot->sound, x, y, z);
}

void tc_audio_voice_set_distance_range(
    tc_audio_voice_handle voice,
    float min_distance,
    float max_distance
) {
    tc_audio_voice_slot* slot = audio_voice_get(voice);
    if (!slot) return;
    if (min_distance < 0.0f) min_distance = 0.0f;
    if (max_distance < min_distance) max_distance = min_distance;
    ma_sound_set_min_distance(&slot->sound, min_distance);
    ma_sound_set_max_distance(&slot->sound, max_distance);
}

size_t tc_audio_voice_count(void) {
    return g_audio_voice_pool_initialized ? tc_pool_count(&g_audio_voice_pool) : 0;
}

size_t tc_audio_voice_capacity(void) {
    return g_audio_voice_pool_initialized ? g_audio_voice_pool.capacity : 0;
}

tc_audio_voice_handle tc_audio_voice_at(size_t pool_index) {
    if (!g_audio_voice_pool_initialized || pool_index >= g_audio_voice_pool.capacity ||
        g_audio_voice_pool.states[pool_index] != TC_SLOT_OCCUPIED) {
        return tc_audio_voice_handle_invalid();
    }
    tc_audio_voice_handle voice = {
        (uint32_t)pool_index,
        g_audio_voice_pool.generations[pool_index]
    };
    return voice;
}
