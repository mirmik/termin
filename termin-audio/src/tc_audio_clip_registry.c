#include <termin/audio/tc_audio_clip_registry.h>

#include "tc_audio_internal.h"

#include <limits.h>
#include <stdlib.h>
#include <string.h>

#include <tcbase/tc_log.h>
#include <tcbase/tc_pool.h>
#include <tcbase/tc_registry_utils.h>
#include <tcbase/tc_resource_map.h>
#include <tcbase/tc_string.h>

static tc_pool g_audio_clip_pool;
static tc_resource_map* g_audio_clip_uuid_map = NULL;
static uint64_t g_audio_clip_next_uuid = 1;
static uint32_t g_audio_clip_generation_floor = 1;
static bool g_audio_clip_initialized = false;

static void audio_clip_free_pcm(tc_audio_clip* clip) {
    if (!clip) return;
    free(clip->pcm_frames);
    clip->pcm_frames = NULL;
    clip->frame_count = 0;
    clip->sample_rate = 0;
    clip->channels = 0;
    clip->sample_format = TC_AUDIO_SAMPLE_FORMAT_UNKNOWN;
    clip->header.is_loaded = 0;
}

static void audio_clip_advance_generation_floor(void) {
    uint32_t max_generation = g_audio_clip_generation_floor;
    for (uint32_t i = 0; i < g_audio_clip_pool.capacity; ++i) {
        if (g_audio_clip_pool.generations[i] > max_generation) {
            max_generation = g_audio_clip_pool.generations[i];
        }
    }
    g_audio_clip_generation_floor = max_generation + 1;
    if (g_audio_clip_generation_floor == 0) {
        g_audio_clip_generation_floor = 1;
    }
}

static tc_audio_clip_handle audio_clip_allocate(void) {
    tc_audio_clip_handle handle = tc_pool_alloc(&g_audio_clip_pool);
    if (tc_audio_clip_handle_is_invalid(handle)) {
        return handle;
    }
    if (handle.generation < g_audio_clip_generation_floor) {
        g_audio_clip_pool.generations[handle.index] = g_audio_clip_generation_floor;
        handle.generation = g_audio_clip_generation_floor;
    }
    return handle;
}

void tc_audio_clip_registry_init(void) {
    if (g_audio_clip_initialized) return;
    if (!tc_pool_init(&g_audio_clip_pool, sizeof(tc_audio_clip), 32)) {
        tc_log_error("tc_audio_clip_registry_init: failed to initialize clip pool");
        return;
    }
    for (uint32_t i = 0; i < g_audio_clip_pool.capacity; ++i) {
        g_audio_clip_pool.generations[i] = g_audio_clip_generation_floor;
    }
    g_audio_clip_uuid_map = tc_resource_map_new(NULL);
    if (!g_audio_clip_uuid_map) {
        tc_log_error("tc_audio_clip_registry_init: failed to initialize UUID map");
        tc_pool_free(&g_audio_clip_pool);
        return;
    }
    g_audio_clip_next_uuid = 1;
    g_audio_clip_initialized = true;
}

void tc_audio_clip_registry_shutdown(void) {
    if (!g_audio_clip_initialized) return;
    for (uint32_t i = 0; i < g_audio_clip_pool.capacity; ++i) {
        if (g_audio_clip_pool.states[i] == TC_SLOT_OCCUPIED) {
            audio_clip_free_pcm((tc_audio_clip*)tc_pool_get_unchecked(&g_audio_clip_pool, i));
        }
    }
    audio_clip_advance_generation_floor();
    tc_resource_map_free(g_audio_clip_uuid_map);
    g_audio_clip_uuid_map = NULL;
    tc_pool_free(&g_audio_clip_pool);
    g_audio_clip_next_uuid = 1;
    g_audio_clip_initialized = false;
}

tc_audio_clip_handle tc_audio_clip_create(const char* uuid) {
    if (!g_audio_clip_initialized) tc_audio_clip_registry_init();
    if (!g_audio_clip_initialized) return tc_audio_clip_handle_invalid();

    char generated_uuid[TC_UUID_SIZE];
    const char* final_uuid = uuid;
    if (!final_uuid || !final_uuid[0]) {
        tc_generate_prefixed_uuid(
            generated_uuid,
            sizeof(generated_uuid),
            "audio-clip",
            &g_audio_clip_next_uuid
        );
        final_uuid = generated_uuid;
    }
    if (tc_resource_map_contains(g_audio_clip_uuid_map, final_uuid)) {
        tc_log_warn("tc_audio_clip_create: UUID '%s' already exists", final_uuid);
        return tc_audio_clip_handle_invalid();
    }

    tc_audio_clip_handle handle = audio_clip_allocate();
    if (tc_audio_clip_handle_is_invalid(handle)) {
        tc_log_error("tc_audio_clip_create: pool allocation failed");
        return handle;
    }
    tc_audio_clip* clip = (tc_audio_clip*)tc_pool_get(&g_audio_clip_pool, handle);
    tc_resource_header_init(&clip->header, final_uuid);
    clip->header.pool_index = handle.index;

    if (!tc_resource_map_add(g_audio_clip_uuid_map, clip->header.uuid, tc_pack_index(handle.index))) {
        tc_log_error("tc_audio_clip_create: failed to publish UUID '%s'", final_uuid);
        tc_pool_free_slot(&g_audio_clip_pool, handle);
        return tc_audio_clip_handle_invalid();
    }
    return handle;
}

tc_audio_clip_handle tc_audio_clip_declare(
    const char* uuid,
    const char* name,
    const char* source_path
) {
    if (!uuid || !uuid[0]) {
        tc_log_error("tc_audio_clip_declare: UUID is required");
        return tc_audio_clip_handle_invalid();
    }
    tc_audio_clip_handle handle = tc_audio_clip_find(uuid);
    if (tc_audio_clip_handle_is_invalid(handle)) {
        handle = tc_audio_clip_create(uuid);
    }
    if (tc_audio_clip_handle_is_invalid(handle)) return handle;
    if (name && name[0]) tc_audio_clip_set_name(handle, name);
    if (source_path && source_path[0]) tc_audio_clip_set_source_path(handle, source_path);
    return handle;
}

tc_audio_clip_handle tc_audio_clip_find(const char* uuid) {
    if (!g_audio_clip_initialized || !uuid || !uuid[0]) {
        return tc_audio_clip_handle_invalid();
    }
    void* packed_index = tc_resource_map_get(g_audio_clip_uuid_map, uuid);
    if (!tc_has_index(packed_index)) return tc_audio_clip_handle_invalid();
    const uint32_t index = tc_unpack_index(packed_index);
    if (index >= g_audio_clip_pool.capacity ||
        g_audio_clip_pool.states[index] != TC_SLOT_OCCUPIED) {
        tc_log_error("tc_audio_clip_find: UUID map contains stale index for '%s'", uuid);
        return tc_audio_clip_handle_invalid();
    }
    tc_audio_clip_handle handle = {index, g_audio_clip_pool.generations[index]};
    return handle;
}

tc_audio_clip_handle tc_audio_clip_find_by_name(const char* name) {
    if (!g_audio_clip_initialized || !name || !name[0]) {
        return tc_audio_clip_handle_invalid();
    }
    for (uint32_t i = 0; i < g_audio_clip_pool.capacity; ++i) {
        if (g_audio_clip_pool.states[i] != TC_SLOT_OCCUPIED) continue;
        tc_audio_clip* clip = (tc_audio_clip*)tc_pool_get_unchecked(&g_audio_clip_pool, i);
        if (clip->header.name && strcmp(clip->header.name, name) == 0) {
            tc_audio_clip_handle handle = {i, g_audio_clip_pool.generations[i]};
            return handle;
        }
    }
    return tc_audio_clip_handle_invalid();
}

tc_audio_clip_handle tc_audio_clip_get_or_create(const char* uuid) {
    if (!uuid || !uuid[0]) {
        tc_log_error("tc_audio_clip_get_or_create: UUID is required");
        return tc_audio_clip_handle_invalid();
    }
    tc_audio_clip_handle handle = tc_audio_clip_find(uuid);
    return tc_audio_clip_handle_is_invalid(handle) ? tc_audio_clip_create(uuid) : handle;
}

tc_audio_clip* tc_audio_clip_get(tc_audio_clip_handle handle) {
    if (!g_audio_clip_initialized) return NULL;
    return (tc_audio_clip*)tc_pool_get(&g_audio_clip_pool, handle);
}

bool tc_audio_clip_is_valid(tc_audio_clip_handle handle) {
    return g_audio_clip_initialized && tc_pool_is_valid(&g_audio_clip_pool, handle);
}

bool tc_audio_clip_destroy(tc_audio_clip_handle handle) {
    tc_audio_clip* clip = tc_audio_clip_get(handle);
    if (!clip) {
        tc_log_warn(
            "tc_audio_clip_destroy: stale handle index=%u generation=%u",
            handle.index,
            handle.generation
        );
        return false;
    }
    if (clip->header.ref_count != 0) {
        tc_log_warn(
            "tc_audio_clip_destroy: clip '%s' still has %u references",
            clip->header.uuid,
            clip->header.ref_count
        );
        return false;
    }
    if (tc_audio_voice_pool_uses_clip(handle)) {
        tc_log_error("tc_audio_clip_destroy: clip '%s' still has active voices", clip->header.uuid);
        return false;
    }

    char uuid[TC_UUID_SIZE];
    tc_resource_copy_uuid(uuid, sizeof(uuid), clip->header.uuid, "tc_audio_clip_destroy");
    audio_clip_free_pcm(clip);
    if (!tc_resource_map_remove(g_audio_clip_uuid_map, uuid)) {
        tc_log_error("tc_audio_clip_destroy: failed to remove UUID '%s'", uuid);
        return false;
    }
    return tc_pool_free_slot(&g_audio_clip_pool, handle);
}

size_t tc_audio_clip_count(void) {
    return g_audio_clip_initialized ? tc_pool_count(&g_audio_clip_pool) : 0;
}

bool tc_audio_clip_set_name(tc_audio_clip_handle handle, const char* name) {
    tc_audio_clip* clip = tc_audio_clip_get(handle);
    if (!clip) {
        tc_log_error("tc_audio_clip_set_name: stale clip handle");
        return false;
    }
    clip->header.name = name && name[0] ? tc_intern_string(name) : NULL;
    return !name || !name[0] || clip->header.name != NULL;
}

bool tc_audio_clip_set_source_path(tc_audio_clip_handle handle, const char* source_path) {
    tc_audio_clip* clip = tc_audio_clip_get(handle);
    if (!clip) {
        tc_log_error("tc_audio_clip_set_source_path: stale clip handle");
        return false;
    }
    clip->source_path = source_path && source_path[0] ? tc_intern_string(source_path) : NULL;
    return !source_path || !source_path[0] || clip->source_path != NULL;
}

void tc_audio_clip_add_ref(tc_audio_clip* clip) {
    if (clip) ++clip->header.ref_count;
}

bool tc_audio_clip_release(tc_audio_clip* clip) {
    if (!clip) return false;
    if (clip->header.ref_count == 0) {
        tc_log_warn("tc_audio_clip_release: clip '%s' refcount is already zero", clip->header.uuid);
        return false;
    }
    --clip->header.ref_count;
    if (clip->header.ref_count != 0) return false;
    tc_audio_clip_handle handle = tc_audio_clip_find(clip->header.uuid);
    return !tc_audio_clip_handle_is_invalid(handle) && tc_audio_clip_destroy(handle);
}

size_t tc_audio_sample_size(tc_audio_sample_format format) {
    switch (format) {
        case TC_AUDIO_SAMPLE_FORMAT_U8: return 1;
        case TC_AUDIO_SAMPLE_FORMAT_S16: return 2;
        case TC_AUDIO_SAMPLE_FORMAT_S24: return 3;
        case TC_AUDIO_SAMPLE_FORMAT_S32:
        case TC_AUDIO_SAMPLE_FORMAT_F32: return 4;
        default: return 0;
    }
}

bool tc_audio_clip_set_pcm(
    tc_audio_clip_handle handle,
    const void* frames,
    uint64_t frame_count,
    uint32_t sample_rate,
    uint16_t channels,
    tc_audio_sample_format format
) {
    tc_audio_clip* clip = tc_audio_clip_get(handle);
    const size_t sample_size = tc_audio_sample_size(format);
    if (!clip || !frames || frame_count == 0 || sample_rate == 0 || channels == 0 || sample_size == 0) {
        tc_log_error("tc_audio_clip_set_pcm: invalid PCM payload");
        return false;
    }
    if (tc_audio_voice_pool_uses_clip(handle)) {
        tc_log_error("tc_audio_clip_set_pcm: clip '%s' is used by active voices", clip->header.uuid);
        return false;
    }
    if (frame_count > SIZE_MAX / channels / sample_size) {
        tc_log_error("tc_audio_clip_set_pcm: PCM payload is too large");
        return false;
    }
    const size_t byte_count = (size_t)frame_count * channels * sample_size;
    void* copy = malloc(byte_count);
    if (!copy) {
        tc_log_error("tc_audio_clip_set_pcm: failed to allocate %zu bytes", byte_count);
        return false;
    }
    memcpy(copy, frames, byte_count);
    audio_clip_free_pcm(clip);
    clip->pcm_frames = copy;
    clip->frame_count = frame_count;
    clip->sample_rate = sample_rate;
    clip->channels = channels;
    clip->sample_format = (uint16_t)format;
    clip->header.is_loaded = 1;
    ++clip->header.version;
    return true;
}

bool tc_audio_clip_load_file(tc_audio_clip_handle handle, const char* path) {
    tc_audio_clip* clip = tc_audio_clip_get(handle);
    if (!clip || !path || !path[0]) {
        tc_log_error("tc_audio_clip_load_file: invalid clip or path");
        return false;
    }
    if (tc_audio_voice_pool_uses_clip(handle)) {
        tc_log_error("tc_audio_clip_load_file: clip '%s' is used by active voices", clip->header.uuid);
        return false;
    }

    void* frames = NULL;
    uint64_t frame_count = 0;
    uint32_t sample_rate = 0;
    uint16_t channels = 0;
    if (!tc_audio_backend_decode_file(path, &frames, &frame_count, &sample_rate, &channels)) {
        return false;
    }

    audio_clip_free_pcm(clip);
    clip->pcm_frames = frames;
    clip->frame_count = frame_count;
    clip->sample_rate = sample_rate;
    clip->channels = channels;
    clip->sample_format = TC_AUDIO_SAMPLE_FORMAT_F32;
    clip->source_path = tc_intern_string(path);
    clip->header.is_loaded = 1;
    ++clip->header.version;
    return true;
}

bool tc_audio_clip_ensure_loaded(tc_audio_clip_handle handle) {
    tc_audio_clip* clip = tc_audio_clip_get(handle);
    if (!clip) {
        tc_log_error("tc_audio_clip_ensure_loaded: stale clip handle");
        return false;
    }
    if (clip->header.is_loaded) return true;
    if (!clip->source_path || !clip->source_path[0]) {
        tc_log_error("tc_audio_clip_ensure_loaded: clip '%s' has no source path", clip->header.uuid);
        return false;
    }
    return tc_audio_clip_load_file(handle, clip->source_path);
}

bool tc_audio_clip_unload(tc_audio_clip_handle handle) {
    tc_audio_clip* clip = tc_audio_clip_get(handle);
    if (!clip) {
        tc_log_error("tc_audio_clip_unload: stale clip handle");
        return false;
    }
    if (tc_audio_voice_pool_uses_clip(handle)) {
        tc_log_error("tc_audio_clip_unload: clip '%s' is used by active voices", clip->header.uuid);
        return false;
    }
    audio_clip_free_pcm(clip);
    ++clip->header.version;
    return true;
}

double tc_audio_clip_duration_seconds(tc_audio_clip_handle handle) {
    tc_audio_clip* clip = tc_audio_clip_get(handle);
    if (!clip || clip->sample_rate == 0) return 0.0;
    return (double)clip->frame_count / (double)clip->sample_rate;
}

uint64_t tc_audio_clip_duration_ms(tc_audio_clip_handle handle) {
    tc_audio_clip* clip = tc_audio_clip_get(handle);
    if (!clip || clip->sample_rate == 0) return 0;
    return (clip->frame_count * 1000u) / clip->sample_rate;
}

