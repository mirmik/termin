#include "resources/tc_animation_registry.h"

#include <math.h>
#include <stdlib.h>
#include <string.h>

#include <geom/tc_lerp_detail.h>
#include <geom/tc_quat.h>
#include <tcbase/tc_log.h>
#include <tcbase/tc_pool.h>
#include <tcbase/tc_registry_utils.h>
#include <tcbase/tc_resource_map.h>
#include <tcbase/tc_string.h>

static tc_pool g_animation_pool;
static tc_pool_generation_epoch g_animation_generation_epoch;
static tc_resource_map* g_uuid_to_index = NULL;
static uint64_t g_next_uuid = 1;
static bool g_initialized = false;

static void animation_free_channel_array(tc_animation_channel* channels, size_t count) {
    if (!channels)
        return;
    for (size_t i = 0; i < count; ++i) {
        tc_animation_channel_free(&channels[i]);
    }
    free(channels);
}

static void animation_free_channels(tc_animation* animation) {
    if (!animation)
        return;
    animation_free_channel_array(animation->channels, animation->channel_count);
    animation->channels = NULL;
    animation->channel_count = 0;
}

static void animation_free_track_array(tc_animation_track* tracks, size_t count) {
    if (!tracks)
        return;
    for (size_t i = 0; i < count; ++i) {
        free(tracks[i].times);
        if (tracks[i].path == TC_ANIMATION_PATH_WEIGHTS) {
            free(tracks[i].values.weights.values);
        } else if (tracks[i].interpolation == TC_ANIMATION_INTERPOLATION_CUBIC_SPLINE) {
            if (tracks[i].path == TC_ANIMATION_PATH_ROTATION)
                free(tracks[i].values.cubic_rotation_keys);
            else
                free(tracks[i].values.cubic_vec3_keys);
        } else if (tracks[i].path == TC_ANIMATION_PATH_ROTATION) {
            free(tracks[i].values.rotation_values);
        } else {
            free(tracks[i].values.vec3_values);
        }
    }
    free(tracks);
}

static void animation_free_tracks(tc_animation* animation) {
    if (!animation)
        return;
    animation_free_track_array(animation->tracks, animation->track_count);
    animation->tracks = NULL;
    animation->track_count = 0;
}

static void animation_free_data(tc_animation* animation) {
    if (!animation)
        return;
    animation_free_channels(animation);
    animation_free_tracks(animation);
    animation->duration = 0.0;
}

void tc_animation_init(void) {
    TC_REGISTRY_INIT_GUARD(g_initialized, "tc_animation");

    if (!tc_pool_init_rebootstrap(&g_animation_pool, sizeof(tc_animation), 64, &g_animation_generation_epoch)) {
        tc_log_error("tc_animation_init: failed to init pool");
        return;
    }

    g_uuid_to_index = tc_resource_map_new(NULL);
    if (!g_uuid_to_index) {
        tc_log_error("tc_animation_init: failed to create uuid map");
        tc_pool_free(&g_animation_pool);
        return;
    }

    g_next_uuid = 1;
    g_initialized = true;
}

void tc_animation_shutdown(void) {
    TC_REGISTRY_SHUTDOWN_GUARD(g_initialized, "tc_animation");

    for (uint32_t i = 0; i < g_animation_pool.capacity; i++) {
        if (g_animation_pool.states[i] == TC_SLOT_OCCUPIED) {
            tc_animation* animation = (tc_animation*)tc_pool_get_unchecked(&g_animation_pool, i);
            animation_free_data(animation);
        }
    }

    tc_pool_free(&g_animation_pool);
    tc_resource_map_free(g_uuid_to_index);
    g_uuid_to_index = NULL;
    g_next_uuid = 1;
    g_initialized = false;
}

tc_animation_handle tc_animation_create(const char* uuid) {
    if (!g_initialized) {
        tc_animation_init();
    }

    char uuid_buf[TC_UUID_SIZE];
    const char* final_uuid;

    if (uuid && uuid[0] != '\0') {
        if (tc_animation_contains(uuid)) {
            tc_log_warn("tc_animation_create: uuid '%s' already exists", uuid);
            return tc_animation_handle_invalid();
        }
        final_uuid = uuid;
    } else {
        tc_generate_prefixed_uuid(uuid_buf, sizeof(uuid_buf), "anim", &g_next_uuid);
        final_uuid = uuid_buf;
    }

    tc_handle h = tc_pool_alloc(&g_animation_pool);
    if (tc_handle_is_invalid(h)) {
        tc_log_error("tc_animation_create: pool alloc failed");
        return tc_animation_handle_invalid();
    }

    tc_animation* animation = (tc_animation*)tc_pool_get(&g_animation_pool, h);
    memset(animation, 0, sizeof(tc_animation));
    tc_resource_header_set_uuid(&animation->header, final_uuid, "tc_animation_create");
    animation->header.version = 1;
    animation->header.ref_count = 0;
    animation->header.is_loaded = 1;
    animation->tps = 30.0;
    animation->loop = 1;

    if (!tc_resource_map_add(g_uuid_to_index, animation->header.uuid, tc_pack_index(h.index))) {
        tc_log_error("tc_animation_create: failed to add to uuid map");
        tc_pool_free_slot(&g_animation_pool, h);
        return tc_animation_handle_invalid();
    }

    return h;
}

tc_animation_handle tc_animation_find(const char* uuid) {
    if (!g_initialized || !uuid) {
        return tc_animation_handle_invalid();
    }

    void* ptr = tc_resource_map_get(g_uuid_to_index, uuid);
    if (!tc_has_index(ptr)) {
        return tc_animation_handle_invalid();
    }

    uint32_t index = tc_unpack_index(ptr);
    if (index >= g_animation_pool.capacity) {
        return tc_animation_handle_invalid();
    }

    if (g_animation_pool.states[index] != TC_SLOT_OCCUPIED) {
        return tc_animation_handle_invalid();
    }

    tc_animation_handle h;
    h.index = index;
    h.generation = g_animation_pool.generations[index];
    return h;
}

tc_animation_handle tc_animation_find_by_name(const char* name) {
    if (!g_initialized || !name) {
        return tc_animation_handle_invalid();
    }

    for (uint32_t i = 0; i < g_animation_pool.capacity; i++) {
        if (g_animation_pool.states[i] == TC_SLOT_OCCUPIED) {
            tc_animation* animation = (tc_animation*)tc_pool_get_unchecked(&g_animation_pool, i);
            if (animation->header.name && strcmp(animation->header.name, name) == 0) {
                tc_animation_handle h;
                h.index = i;
                h.generation = g_animation_pool.generations[i];
                return h;
            }
        }
    }

    return tc_animation_handle_invalid();
}

tc_animation_handle tc_animation_get_or_create(const char* uuid) {
    if (!uuid || uuid[0] == '\0') {
        tc_log_warn("tc_animation_get_or_create: empty uuid");
        return tc_animation_handle_invalid();
    }

    tc_animation_handle h = tc_animation_find(uuid);
    if (!tc_animation_handle_is_invalid(h)) {
        return h;
    }

    return tc_animation_create(uuid);
}

tc_animation_handle tc_animation_declare(const char* uuid, const char* name) {
    if (!g_initialized) {
        tc_animation_init();
    }

    tc_animation_handle existing = tc_animation_find(uuid);
    if (!tc_animation_handle_is_invalid(existing)) {
        return existing;
    }

    tc_handle h = tc_pool_alloc(&g_animation_pool);
    if (tc_handle_is_invalid(h)) {
        tc_log_error("tc_animation_declare: pool alloc failed");
        return tc_animation_handle_invalid();
    }

    tc_animation* animation = (tc_animation*)tc_pool_get(&g_animation_pool, h);
    memset(animation, 0, sizeof(tc_animation));
    tc_resource_header_set_uuid(&animation->header, uuid, "tc_animation_declare");
    animation->header.version = 0;
    animation->header.ref_count = 0;
    animation->header.is_loaded = 0;
    animation->tps = 30.0;
    animation->loop = 1;

    if (name && name[0] != '\0') {
        animation->header.name = tc_intern_string(name);
    }

    if (!tc_resource_map_add(g_uuid_to_index, animation->header.uuid, tc_pack_index(h.index))) {
        tc_log_error("tc_animation_declare: failed to add to uuid map");
        tc_pool_free_slot(&g_animation_pool, h);
        return tc_animation_handle_invalid();
    }

    return h;
}

tc_animation* tc_animation_get(tc_animation_handle h) {
    if (!g_initialized)
        return NULL;
    return (tc_animation*)tc_pool_get_checked(&g_animation_pool, h, "tc_animation");
}

bool tc_animation_is_valid(tc_animation_handle h) {
    if (!g_initialized)
        return false;
    return tc_pool_is_valid(&g_animation_pool, h);
}

bool tc_animation_destroy(tc_animation_handle h) {
    if (!g_initialized)
        return false;

    tc_animation* animation = tc_animation_get(h);
    if (!animation)
        return false;

    tc_resource_map_remove(g_uuid_to_index, animation->header.uuid);
    animation_free_data(animation);
    return tc_pool_free_slot(&g_animation_pool, h);
}

bool tc_animation_contains(const char* uuid) {
    if (!g_initialized || !uuid)
        return false;
    return tc_resource_map_contains(g_uuid_to_index, uuid);
}

size_t tc_animation_count(void) {
    if (!g_initialized)
        return 0;
    return tc_pool_count(&g_animation_pool);
}

bool tc_animation_is_loaded(tc_animation_handle h) {
    tc_animation* animation = tc_animation_get(h);
    if (!animation)
        return false;
    return animation->header.is_loaded != 0;
}

bool tc_animation_ensure_loaded(tc_animation_handle h) {
    tc_animation* animation = tc_animation_get(h);
    if (!animation)
        return false;

    bool success = tc_resource_header_ensure_loaded(&animation->header);
    if (!success) {
        tc_log_error("tc_animation_ensure_loaded: resource loader failed for '%s'", animation->header.uuid);
    }
    return success;
}

void tc_animation_add_ref(tc_animation* animation) {
    if (animation) {
        animation->header.ref_count++;
    }
}

bool tc_animation_release(tc_animation* animation) {
    if (!animation || animation->header.ref_count == 0)
        return false;

    animation->header.ref_count--;
    if (animation->header.ref_count == 0) {
        tc_animation_handle h = tc_animation_find(animation->header.uuid);
        if (!tc_animation_handle_is_invalid(h)) {
            tc_animation_destroy(h);
            return true;
        }
    }
    return false;
}

static bool animation_track_value_count(size_t key_count,
                                        uint32_t components,
                                        tc_animation_interpolation interpolation,
                                        size_t* result) {
    size_t multiplier = interpolation == TC_ANIMATION_INTERPOLATION_CUBIC_SPLINE ? 3u : 1u;
    if (components == 0 || key_count > SIZE_MAX / components)
        return false;
    size_t values = key_count * components;
    if (values > SIZE_MAX / multiplier)
        return false;
    *result = values * multiplier;
    return true;
}

static tc_quat animation_load_quat(const double* values) {
    return TC_QUAT(values[0], values[1], values[2], values[3]);
}

static tc_vec3 animation_load_vec3(const double* values) {
    return TC_VEC3(values[0], values[1], values[2]);
}

static tc_vec4 animation_load_vec4(const double* values) {
    return TC_VEC4(values[0], values[1], values[2], values[3]);
}

static bool animation_track_owned_size_valid(const tc_animation_track_desc* track, size_t index) {
    size_t element_size = sizeof(double);
    size_t element_count = track->value_count;
    if (track->path != TC_ANIMATION_PATH_WEIGHTS) {
        element_count = track->key_count;
        if (track->interpolation == TC_ANIMATION_INTERPOLATION_CUBIC_SPLINE) {
            element_size = track->path == TC_ANIMATION_PATH_ROTATION
                               ? sizeof(tc_animation_cubic_rotation_key)
                               : sizeof(tc_animation_cubic_vec3_key);
        } else {
            element_size = track->path == TC_ANIMATION_PATH_ROTATION ? sizeof(tc_quat) : sizeof(tc_vec3);
        }
    }
    if (element_count > SIZE_MAX / element_size) {
        tc_log_error("tc_animation_replace_tracks: track[%zu] typed payload byte size overflows allocation", index);
        return false;
    }
    return true;
}

static bool animation_track_desc_valid(const tc_animation_track_desc* track, size_t index) {
    if (!track) {
        tc_log_error("tc_animation_replace_tracks: track[%zu] descriptor is null", index);
        return false;
    }
    if (track->target_node_index < 0) {
        tc_log_error("tc_animation_replace_tracks: track[%zu] has negative target node index", index);
        return false;
    }
    if (track->path < TC_ANIMATION_PATH_TRANSLATION || track->path > TC_ANIMATION_PATH_WEIGHTS) {
        tc_log_error("tc_animation_replace_tracks: track[%zu] has invalid path=%d", index, (int)track->path);
        return false;
    }
    if (track->interpolation < TC_ANIMATION_INTERPOLATION_LINEAR ||
        track->interpolation > TC_ANIMATION_INTERPOLATION_CUBIC_SPLINE) {
        tc_log_error("tc_animation_replace_tracks: track[%zu] has invalid interpolation=%d",
                     index,
                     (int)track->interpolation);
        return false;
    }

    const uint32_t required_components =
        track->path == TC_ANIMATION_PATH_ROTATION ? 4u
        : (track->path == TC_ANIMATION_PATH_TRANSLATION || track->path == TC_ANIMATION_PATH_SCALE) ? 3u
                                                                                                   : track->components;
    if (track->components == 0 || track->components != required_components) {
        tc_log_error("tc_animation_replace_tracks: track[%zu] path=%d has invalid components=%u",
                     index,
                     (int)track->path,
                     track->components);
        return false;
    }
    if (track->key_count == 0 || !track->times || !track->values) {
        tc_log_error("tc_animation_replace_tracks: track[%zu] has incomplete key storage", index);
        return false;
    }
    if (track->key_count > SIZE_MAX / sizeof(double) || track->value_count > SIZE_MAX / sizeof(double)) {
        tc_log_error("tc_animation_replace_tracks: track[%zu] flat payload byte size overflows allocation", index);
        return false;
    }
    if (!animation_track_owned_size_valid(track, index)) {
        return false;
    }

    size_t expected_values = 0;
    if (!animation_track_value_count(
            track->key_count, track->components, track->interpolation, &expected_values) ||
        track->value_count != expected_values) {
        tc_log_error("tc_animation_replace_tracks: track[%zu] value_count=%zu does not match expected=%zu",
                     index,
                     track->value_count,
                     expected_values);
        return false;
    }
    for (size_t i = 0; i < track->key_count; ++i) {
        if (!isfinite(track->times[i]) || (i > 0 && track->times[i] <= track->times[i - 1])) {
            tc_log_error("tc_animation_replace_tracks: track[%zu] times must be finite and strictly increasing",
                         index);
            return false;
        }
    }
    for (size_t i = 0; i < track->value_count; ++i) {
        if (!isfinite(track->values[i])) {
            tc_log_error("tc_animation_replace_tracks: track[%zu] values must be finite", index);
            return false;
        }
    }
    if (track->path == TC_ANIMATION_PATH_ROTATION) {
        for (size_t key = 0; key < track->key_count; ++key) {
            const size_t tuple = track->interpolation == TC_ANIMATION_INTERPOLATION_CUBIC_SPLINE ? 3u : 1u;
            const size_t value_slot = track->interpolation == TC_ANIMATION_INTERPOLATION_CUBIC_SPLINE ? 1u : 0u;
            const double* value = track->values + (key * tuple + value_slot) * track->components;
            tc_quat normalized;
            if (!tc_quat_try_normalized(animation_load_quat(value), 1.0e-12, &normalized)) {
                tc_log_error("tc_animation_replace_tracks: track[%zu] rotation key[%zu] is degenerate",
                             index,
                             key);
                return false;
            }
        }
    }
    return true;
}

static bool animation_track_copy_values(tc_animation_track* destination,
                                        const tc_animation_track_desc* source,
                                        size_t index) {
    if (source->path == TC_ANIMATION_PATH_WEIGHTS) {
        destination->values.weights.component_count = source->components;
        destination->values.weights.values = (double*)malloc(source->value_count * sizeof(double));
        if (!destination->values.weights.values)
            return false;
        memcpy(destination->values.weights.values, source->values, source->value_count * sizeof(double));
        return true;
    }

    if (source->interpolation == TC_ANIMATION_INTERPOLATION_CUBIC_SPLINE) {
        if (source->path == TC_ANIMATION_PATH_ROTATION) {
            destination->values.cubic_rotation_keys = (tc_animation_cubic_rotation_key*)malloc(
                source->key_count * sizeof(tc_animation_cubic_rotation_key));
            if (!destination->values.cubic_rotation_keys)
                return false;
            for (size_t key = 0; key < source->key_count; ++key) {
                const double* values = source->values + key * 3u * 4u;
                tc_animation_cubic_rotation_key* result = &destination->values.cubic_rotation_keys[key];
                result->in_tangent = animation_load_vec4(values);
                if (!tc_quat_try_normalized(animation_load_quat(values + 4), 1.0e-12, &result->value)) {
                    tc_log_error("tc_animation_replace_tracks: track[%zu] rotation key[%zu] became invalid during copy",
                                 index,
                                 key);
                    return false;
                }
                result->out_tangent = animation_load_vec4(values + 8);
            }
            return true;
        }

        destination->values.cubic_vec3_keys = (tc_animation_cubic_vec3_key*)malloc(
            source->key_count * sizeof(tc_animation_cubic_vec3_key));
        if (!destination->values.cubic_vec3_keys)
            return false;
        for (size_t key = 0; key < source->key_count; ++key) {
            const double* values = source->values + key * 3u * 3u;
            tc_animation_cubic_vec3_key* result = &destination->values.cubic_vec3_keys[key];
            result->in_tangent = animation_load_vec3(values);
            result->value = animation_load_vec3(values + 3);
            result->out_tangent = animation_load_vec3(values + 6);
        }
        return true;
    }

    if (source->path == TC_ANIMATION_PATH_ROTATION) {
        destination->values.rotation_values = (tc_quat*)malloc(source->key_count * sizeof(tc_quat));
        if (!destination->values.rotation_values)
            return false;
        for (size_t key = 0; key < source->key_count; ++key) {
            if (!tc_quat_try_normalized(animation_load_quat(source->values + key * 4u),
                                        1.0e-12,
                                        &destination->values.rotation_values[key])) {
                tc_log_error("tc_animation_replace_tracks: track[%zu] rotation key[%zu] became invalid during copy",
                             index,
                             key);
                return false;
            }
        }
        return true;
    }

    destination->values.vec3_values = (tc_vec3*)malloc(source->key_count * sizeof(tc_vec3));
    if (!destination->values.vec3_values)
        return false;
    for (size_t key = 0; key < source->key_count; ++key)
        destination->values.vec3_values[key] = animation_load_vec3(source->values + key * 3u);
    return true;
}

bool tc_animation_replace_tracks(tc_animation* anim, const tc_animation_track_desc* tracks, size_t count) {
    if (!anim || (count > 0 && !tracks)) {
        tc_log_error("tc_animation_replace_tracks: animation and descriptors are required");
        return false;
    }
    if (count > SIZE_MAX / sizeof(tc_animation_track)) {
        tc_log_error("tc_animation_replace_tracks: track count overflows allocation size");
        return false;
    }
    for (size_t i = 0; i < count; ++i) {
        if (!animation_track_desc_valid(&tracks[i], i))
            return false;
    }

    tc_animation_track* replacement = NULL;
    if (count > 0) {
        replacement = (tc_animation_track*)calloc(count, sizeof(tc_animation_track));
        if (!replacement) {
            tc_log_error("tc_animation_replace_tracks: track allocation failed");
            return false;
        }
    }

    double max_ticks = 0.0;
    for (size_t i = 0; i < count; ++i) {
        const tc_animation_track_desc* source = &tracks[i];
        tc_animation_track* destination = &replacement[i];
        destination->target_node_index = source->target_node_index;
        destination->path = (uint8_t)source->path;
        destination->interpolation = (uint8_t)source->interpolation;
        destination->key_count = source->key_count;
        destination->times = (double*)malloc(source->key_count * sizeof(double));
        if (!destination->times) {
            tc_log_error("tc_animation_replace_tracks: track[%zu] timeline allocation failed", i);
            animation_free_track_array(replacement, count);
            return false;
        }
        if (!animation_track_copy_values(destination, source, i)) {
            tc_log_error("tc_animation_replace_tracks: track[%zu] typed payload construction failed", i);
            animation_free_track_array(replacement, count);
            return false;
        }
        memcpy(destination->times, source->times, source->key_count * sizeof(double));
        if (destination->times[destination->key_count - 1] > max_ticks)
            max_ticks = destination->times[destination->key_count - 1];
    }

    animation_free_channels(anim);
    animation_free_tracks(anim);
    anim->tracks = replacement;
    anim->track_count = count;
    anim->duration = anim->tps > 0.0 ? max_ticks / anim->tps : 0.0;
    anim->header.is_loaded = 1;
    anim->header.version++;
    return true;
}

const tc_animation_track* tc_animation_get_track(const tc_animation* anim, size_t index) {
    if (!anim || index >= anim->track_count)
        return NULL;
    return &anim->tracks[index];
}

const tc_animation_channel* tc_animation_get_channel(const tc_animation* anim, size_t index) {
    if (!anim || index >= anim->channel_count)
        return NULL;
    return &anim->channels[index];
}

int tc_animation_find_channel(const tc_animation* anim, const char* target_name) {
    if (!anim || !target_name || !anim->channels)
        return -1;

    for (size_t i = 0; i < anim->channel_count; i++) {
        if (strcmp(anim->channels[i].target_name, target_name) == 0) {
            return (int)i;
        }
    }
    return -1;
}

static bool animation_vec3_keys_valid(const tc_keyframe_vec3* keys, size_t count) {
    if (count > SIZE_MAX / sizeof(tc_keyframe_vec3) || (count > 0 && !keys))
        return false;
    for (size_t key = 0; key < count; ++key) {
        if (!isfinite(keys[key].time) || !tc_vec3_is_finite(keys[key].value) ||
            (key > 0 && keys[key].time <= keys[key - 1].time)) {
            return false;
        }
    }
    return true;
}

static bool animation_quat_keys_valid(const tc_keyframe_quat* keys, size_t count) {
    if (count > SIZE_MAX / sizeof(tc_keyframe_quat) || (count > 0 && !keys))
        return false;
    for (size_t key = 0; key < count; ++key) {
        tc_quat normalized;
        if (!isfinite(keys[key].time) || !tc_quat_try_normalized(keys[key].value, 1.0e-12, &normalized) ||
            (key > 0 && keys[key].time <= keys[key - 1].time)) {
            return false;
        }
    }
    return true;
}

static bool animation_scalar_keys_valid(const tc_keyframe_scalar* keys, size_t count) {
    if (count > SIZE_MAX / sizeof(tc_keyframe_scalar) || (count > 0 && !keys))
        return false;
    for (size_t key = 0; key < count; ++key) {
        if (!isfinite(keys[key].time) || !isfinite(keys[key].value) ||
            (key > 0 && keys[key].time <= keys[key - 1].time)) {
            return false;
        }
    }
    return true;
}

static bool animation_channel_desc_valid(const tc_animation_channel_desc* channel, size_t index) {
    if (!channel) {
        tc_log_error("tc_animation_replace_channels: channel[%zu] descriptor is null", index);
        return false;
    }
    if ((channel->translation_count > 0 && !channel->translation_keys) ||
        (channel->rotation_count > 0 && !channel->rotation_keys) ||
        (channel->scale_count > 0 && !channel->scale_keys)) {
        tc_log_error("tc_animation_replace_channels: channel[%zu] has incomplete key storage", index);
        return false;
    }
    if (channel->translation_count > SIZE_MAX / sizeof(tc_keyframe_vec3) ||
        channel->rotation_count > SIZE_MAX / sizeof(tc_keyframe_quat) ||
        channel->scale_count > SIZE_MAX / sizeof(tc_keyframe_scalar)) {
        tc_log_error("tc_animation_replace_channels: channel[%zu] key count overflows allocation size", index);
        return false;
    }
    if (!animation_vec3_keys_valid(channel->translation_keys, channel->translation_count)) {
        tc_log_error("tc_animation_replace_channels: channel[%zu] translation keys are invalid", index);
        return false;
    }
    if (!animation_quat_keys_valid(channel->rotation_keys, channel->rotation_count)) {
        tc_log_error("tc_animation_replace_channels: channel[%zu] rotation keys are invalid", index);
        return false;
    }
    if (!animation_scalar_keys_valid(channel->scale_keys, channel->scale_count)) {
        tc_log_error("tc_animation_replace_channels: channel[%zu] scale keys are invalid", index);
        return false;
    }
    return true;
}

bool tc_animation_replace_channels(tc_animation* anim,
                                   const tc_animation_channel_desc* channels,
                                   size_t count) {
    if (!anim || (count > 0 && !channels)) {
        tc_log_error("tc_animation_replace_channels: animation and descriptors are required");
        return false;
    }
    if (count > SIZE_MAX / sizeof(tc_animation_channel)) {
        tc_log_error("tc_animation_replace_channels: channel count overflows allocation size");
        return false;
    }
    for (size_t index = 0; index < count; ++index) {
        if (!animation_channel_desc_valid(&channels[index], index))
            return false;
    }

    tc_animation_channel* replacement = NULL;
    if (count > 0) {
        replacement = (tc_animation_channel*)calloc(count, sizeof(tc_animation_channel));
        if (!replacement) {
            tc_log_error("tc_animation_replace_channels: channel allocation failed");
            return false;
        }
    }

    for (size_t index = 0; index < count; ++index) {
        const tc_animation_channel_desc* source = &channels[index];
        tc_animation_channel* destination = &replacement[index];
        tc_animation_channel_init(destination);
        if (source->target_name) {
            strncpy(destination->target_name, source->target_name, TC_CHANNEL_NAME_MAX - 1);
            destination->target_name[TC_CHANNEL_NAME_MAX - 1] = '\0';
        }

        if (source->translation_count > 0) {
            destination->translation_keys =
                (tc_keyframe_vec3*)malloc(source->translation_count * sizeof(tc_keyframe_vec3));
            if (destination->translation_keys) {
                memcpy(destination->translation_keys,
                       source->translation_keys,
                       source->translation_count * sizeof(tc_keyframe_vec3));
                destination->translation_count = source->translation_count;
            }
        }
        if (source->rotation_count > 0) {
            destination->rotation_keys =
                (tc_keyframe_quat*)malloc(source->rotation_count * sizeof(tc_keyframe_quat));
            if (destination->rotation_keys) {
                for (size_t key = 0; key < source->rotation_count; ++key) {
                    destination->rotation_keys[key].time = source->rotation_keys[key].time;
                    if (!tc_quat_try_normalized(source->rotation_keys[key].value,
                                                1.0e-12,
                                                &destination->rotation_keys[key].value)) {
                        tc_log_error(
                            "tc_animation_replace_channels: channel[%zu] rotation key[%zu] became invalid during copy",
                            index,
                            key);
                        animation_free_channel_array(replacement, count);
                        return false;
                    }
                    destination->rotation_count = key + 1;
                }
            }
        }
        if (source->scale_count > 0) {
            destination->scale_keys =
                (tc_keyframe_scalar*)malloc(source->scale_count * sizeof(tc_keyframe_scalar));
            if (destination->scale_keys) {
                memcpy(destination->scale_keys,
                       source->scale_keys,
                       source->scale_count * sizeof(tc_keyframe_scalar));
                destination->scale_count = source->scale_count;
            }
        }
        if ((source->translation_count > 0 && !destination->translation_keys) ||
            (source->rotation_count > 0 && !destination->rotation_keys) ||
            (source->scale_count > 0 && !destination->scale_keys)) {
            tc_log_error("tc_animation_replace_channels: channel[%zu] payload allocation failed", index);
            animation_free_channel_array(replacement, count);
            return false;
        }

        double duration = 0.0;
        if (source->translation_count > 0)
            duration = fmax(duration, source->translation_keys[source->translation_count - 1].time);
        if (source->rotation_count > 0)
            duration = fmax(duration, source->rotation_keys[source->rotation_count - 1].time);
        if (source->scale_count > 0)
            duration = fmax(duration, source->scale_keys[source->scale_count - 1].time);
        destination->duration = duration;
    }

    animation_free_data(anim);
    anim->channels = replacement;
    anim->channel_count = count;
    tc_animation_recompute_duration(anim);
    anim->header.is_loaded = 1;
    anim->header.version++;
    return true;
}

void tc_animation_recompute_duration(tc_animation* anim) {
    if (!anim)
        return;

    double max_ticks = 0.0;
    for (size_t i = 0; i < anim->channel_count; i++) {
        if (anim->channels[i].duration > max_ticks) {
            max_ticks = anim->channels[i].duration;
        }
    }
    for (size_t i = 0; i < anim->track_count; i++) {
        const tc_animation_track* track = &anim->tracks[i];
        if (track->key_count > 0 && track->times[track->key_count - 1] > max_ticks) {
            max_ticks = track->times[track->key_count - 1];
        }
    }
    anim->duration = (anim->tps > 0.0) ? max_ticks / anim->tps : 0.0;
}

typedef struct {
    tc_animation_iter_fn callback;
    void* user_data;
} animation_iter_ctx;

static bool animation_iter_adapter(uint32_t index, void* item, void* ctx_ptr) {
    animation_iter_ctx* ctx = (animation_iter_ctx*)ctx_ptr;
    tc_animation* animation = (tc_animation*)item;

    tc_animation_handle h;
    h.index = index;
    h.generation = g_animation_pool.generations[index];

    return ctx->callback(h, animation, ctx->user_data);
}

void tc_animation_foreach(tc_animation_iter_fn callback, void* user_data) {
    if (!g_initialized || !callback)
        return;
    animation_iter_ctx ctx = {callback, user_data};
    tc_pool_foreach(&g_animation_pool, animation_iter_adapter, &ctx);
}

static size_t find_keyframe_index_vec3(const tc_keyframe_vec3* keys, size_t count, double t) {
    if (count == 0)
        return 0;
    if (t <= keys[0].time)
        return 0;
    if (t >= keys[count - 1].time)
        return count - 1;

    size_t lo = 0;
    size_t hi = count - 1;
    while (lo + 1 < hi) {
        size_t mid = (lo + hi) / 2;
        if (keys[mid].time <= t)
            lo = mid;
        else
            hi = mid;
    }
    return lo;
}

static size_t find_keyframe_index_quat(const tc_keyframe_quat* keys, size_t count, double t) {
    if (count == 0)
        return 0;
    if (t <= keys[0].time)
        return 0;
    if (t >= keys[count - 1].time)
        return count - 1;

    size_t lo = 0;
    size_t hi = count - 1;
    while (lo + 1 < hi) {
        size_t mid = (lo + hi) / 2;
        if (keys[mid].time <= t)
            lo = mid;
        else
            hi = mid;
    }
    return lo;
}

static size_t find_keyframe_index_scalar(const tc_keyframe_scalar* keys, size_t count, double t) {
    if (count == 0)
        return 0;
    if (t <= keys[0].time)
        return 0;
    if (t >= keys[count - 1].time)
        return count - 1;

    size_t lo = 0;
    size_t hi = count - 1;
    while (lo + 1 < hi) {
        size_t mid = (lo + hi) / 2;
        if (keys[mid].time <= t)
            lo = mid;
        else
            hi = mid;
    }
    return lo;
}

static size_t find_track_keyframe_index(const tc_animation_track* track, double t) {
    if (t <= track->times[0])
        return 0;
    if (t >= track->times[track->key_count - 1])
        return track->key_count - 1;

    size_t lo = 0;
    size_t hi = track->key_count - 1;
    while (lo + 1 < hi) {
        size_t mid = lo + (hi - lo) / 2;
        if (track->times[mid] <= t)
            lo = mid;
        else
            hi = mid;
    }
    return lo;
}

bool tc_animation_track_sample(const tc_animation_track* track,
                               double t_ticks,
                               tc_animation_track_sample_result* out_sample) {
    if (!track || !out_sample || track->key_count == 0 || !track->times) {
        tc_log_error("tc_animation_track_sample: invalid track or output storage");
        return false;
    }
    if (!isfinite(t_ticks)) {
        tc_log_error("tc_animation_track_sample: sample time must be finite");
        return false;
    }
    if (track->key_count > SIZE_MAX / sizeof(double)) {
        tc_log_error("tc_animation_track_sample: track timeline byte size overflows addressable storage");
        return false;
    }
    if (track->interpolation == TC_ANIMATION_INTERPOLATION_CUBIC_SPLINE) {
        tc_log_error("tc_animation_track_sample: CUBIC_SPLINE sampling is unsupported");
        return false;
    }
    if (track->path == TC_ANIMATION_PATH_WEIGHTS) {
        tc_log_error("tc_animation_track_sample: morph weights sampling is unsupported");
        return false;
    }
    if (track->path != TC_ANIMATION_PATH_TRANSLATION && track->path != TC_ANIMATION_PATH_ROTATION &&
        track->path != TC_ANIMATION_PATH_SCALE) {
        tc_log_error("tc_animation_track_sample: path=%u is invalid", (unsigned)track->path);
        return false;
    }
    if (track->interpolation != TC_ANIMATION_INTERPOLATION_LINEAR &&
        track->interpolation != TC_ANIMATION_INTERPOLATION_STEP) {
        tc_log_error("tc_animation_track_sample: interpolation=%u is invalid", (unsigned)track->interpolation);
        return false;
    }
    if ((track->path == TC_ANIMATION_PATH_ROTATION && !track->values.rotation_values) ||
        (track->path != TC_ANIMATION_PATH_ROTATION && !track->values.vec3_values)) {
        tc_log_error("tc_animation_track_sample: typed value storage is missing");
        return false;
    }
    for (size_t key = 0; key < track->key_count; ++key) {
        if (!isfinite(track->times[key]) || (key > 0 && track->times[key] <= track->times[key - 1])) {
            tc_log_error("tc_animation_track_sample: key times must be finite and strictly increasing");
            return false;
        }
    }

    const size_t index = find_track_keyframe_index(track, t_ticks);
    const bool use_first = track->interpolation == TC_ANIMATION_INTERPOLATION_STEP ||
                           index >= track->key_count - 1 || t_ticks <= track->times[0];
    tc_animation_track_sample_result sampled = {0};
    sampled.path = (tc_animation_path)track->path;

    if (track->path == TC_ANIMATION_PATH_ROTATION) {
        const tc_quat first = track->values.rotation_values[index];
        if (use_first) {
            if (!tc_quat_try_normalized(first, 1.0e-12, &sampled.value.rotation)) {
                tc_log_error("tc_animation_track_sample: rotation key is non-finite or degenerate");
                return false;
            }
        } else {
            const tc_quat second = track->values.rotation_values[index + 1];
            const double delta = track->times[index + 1] - track->times[index];
            const double alpha = (t_ticks - track->times[index]) / delta;
            if (!isfinite(delta) || delta <= 0.0 || !isfinite(alpha) ||
                !tc_quat_try_slerp(first, second, alpha, 1.0e-12, &sampled.value.rotation)) {
                tc_log_error("tc_animation_track_sample: rotation interpolation has invalid endpoints or factor");
                return false;
            }
        }
        *out_sample = sampled;
        return true;
    }

    const tc_vec3 first = track->values.vec3_values[index];
    tc_vec3 vector;
    if (use_first) {
        vector = first;
    } else {
        const tc_vec3 second = track->values.vec3_values[index + 1];
        const double delta = track->times[index + 1] - track->times[index];
        const double alpha = (t_ticks - track->times[index]) / delta;
        if (!isfinite(delta) || delta <= 0.0 || !isfinite(alpha)) {
            tc_log_error("tc_animation_track_sample: interpolation factor is invalid");
            return false;
        }
        vector = tc_vec3_lerp(first, second, alpha);
    }
    if (!tc_vec3_is_finite(vector)) {
        tc_log_error("tc_animation_track_sample: interpolation produced a non-finite value");
        return false;
    }
    if (track->path == TC_ANIMATION_PATH_TRANSLATION)
        sampled.value.translation = vector;
    else
        sampled.value.scale = vector;
    *out_sample = sampled;
    return true;
}

bool tc_animation_channel_sample(const tc_animation_channel* ch, double t_ticks, tc_channel_sample* out) {
    if (!ch || !out) {
        tc_log_error("tc_animation_channel_sample: channel and output are required");
        return false;
    }
    if (!isfinite(t_ticks)) {
        tc_log_error("tc_animation_channel_sample: sample time must be finite");
        return false;
    }

    tc_channel_sample sampled;
    tc_channel_sample_init(&sampled);

    if (ch->translation_count > 0) {
        if (!animation_vec3_keys_valid(ch->translation_keys, ch->translation_count)) {
            tc_log_error("tc_animation_channel_sample: translation keys are invalid");
            return false;
        }
        size_t idx = find_keyframe_index_vec3(ch->translation_keys, ch->translation_count, t_ticks);
        if (idx >= ch->translation_count - 1 || t_ticks <= ch->translation_keys[0].time) {
            sampled.translation = ch->translation_keys[idx].value;
        } else {
            const tc_keyframe_vec3* first = &ch->translation_keys[idx];
            const tc_keyframe_vec3* second = &ch->translation_keys[idx + 1];
            const double delta = second->time - first->time;
            const double alpha = (t_ticks - first->time) / delta;
            if (!isfinite(first->time) || !isfinite(second->time) || !isfinite(delta) || delta <= 0.0 ||
                !isfinite(alpha)) {
                tc_log_error("tc_animation_channel_sample: translation key interval is invalid");
                return false;
            }
            sampled.translation = tc_vec3_lerp(first->value, second->value, alpha);
        }
        if (!tc_vec3_is_finite(sampled.translation)) {
            tc_log_error("tc_animation_channel_sample: translation sample is non-finite");
            return false;
        }
        sampled.has_translation = 1;
    }

    if (ch->rotation_count > 0) {
        if (!animation_quat_keys_valid(ch->rotation_keys, ch->rotation_count)) {
            tc_log_error("tc_animation_channel_sample: rotation keys are invalid");
            return false;
        }
        const size_t idx = find_keyframe_index_quat(ch->rotation_keys, ch->rotation_count, t_ticks);
        if (idx >= ch->rotation_count - 1 || t_ticks <= ch->rotation_keys[0].time) {
            if (!tc_quat_try_normalized(ch->rotation_keys[idx].value, 1.0e-12, &sampled.rotation)) {
                tc_log_error("tc_animation_channel_sample: rotation key is non-finite or degenerate");
                return false;
            }
        } else {
            const tc_keyframe_quat* first = &ch->rotation_keys[idx];
            const tc_keyframe_quat* second = &ch->rotation_keys[idx + 1];
            const double delta = second->time - first->time;
            const double alpha = (t_ticks - first->time) / delta;
            if (!isfinite(first->time) || !isfinite(second->time) || !isfinite(delta) || delta <= 0.0 ||
                !isfinite(alpha) ||
                !tc_quat_try_slerp(first->value, second->value, alpha, 1.0e-12, &sampled.rotation)) {
                tc_log_error("tc_animation_channel_sample: rotation interpolation has invalid endpoints or factor");
                return false;
            }
        }
        sampled.has_rotation = 1;
    }

    if (ch->scale_count > 0) {
        if (!animation_scalar_keys_valid(ch->scale_keys, ch->scale_count)) {
            tc_log_error("tc_animation_channel_sample: scale keys are invalid");
            return false;
        }
        const size_t idx = find_keyframe_index_scalar(ch->scale_keys, ch->scale_count, t_ticks);
        if (idx >= ch->scale_count - 1 || t_ticks <= ch->scale_keys[0].time) {
            sampled.scale = ch->scale_keys[idx].value;
        } else {
            const tc_keyframe_scalar* first = &ch->scale_keys[idx];
            const tc_keyframe_scalar* second = &ch->scale_keys[idx + 1];
            const double delta = second->time - first->time;
            const double alpha = (t_ticks - first->time) / delta;
            if (!isfinite(first->time) || !isfinite(second->time) || !isfinite(delta) || delta <= 0.0 ||
                !isfinite(alpha)) {
                tc_log_error("tc_animation_channel_sample: scale key interval is invalid");
                return false;
            }
            sampled.scale = tc_detail_lerp_f64_component(first->value, second->value, alpha);
        }
        if (!isfinite(sampled.scale)) {
            tc_log_error("tc_animation_channel_sample: scale sample is non-finite");
            return false;
        }
        sampled.has_scale = 1;
    }

    *out = sampled;
    return true;
}

size_t tc_animation_sample(const tc_animation* anim, double t_seconds, tc_channel_sample* out_samples) {
    if (!anim || !out_samples || anim->channel_count == 0)
        return 0;

    if (anim->loop && anim->duration > 0.0) {
        t_seconds = fmod(t_seconds, anim->duration);
        if (t_seconds < 0.0)
            t_seconds += anim->duration;
    }

    double t_ticks = t_seconds * anim->tps;
    for (size_t i = 0; i < anim->channel_count; i++) {
        tc_channel_sample_init(&out_samples[i]);
        (void)tc_animation_channel_sample(&anim->channels[i], t_ticks, &out_samples[i]);
    }
    return anim->channel_count;
}

typedef struct {
    tc_animation_info* infos;
    size_t count;
} animation_info_collector;

static bool collect_animation_info(tc_animation_handle h, tc_animation* animation, void* user_data) {
    animation_info_collector* collector = (animation_info_collector*)user_data;

    tc_animation_info* info = &collector->infos[collector->count++];
    info->handle = h;
    strncpy(info->uuid, animation->header.uuid, sizeof(info->uuid) - 1);
    info->uuid[sizeof(info->uuid) - 1] = '\0';
    info->name = animation->header.name;
    info->ref_count = animation->header.ref_count;
    info->version = animation->header.version;
    info->duration = animation->duration;
    info->channel_count = animation->channel_count;
    info->is_loaded = animation->header.is_loaded;
    info->loop = animation->loop;

    return true;
}

tc_animation_info* tc_animation_get_all_info(size_t* count) {
    if (!count)
        return NULL;
    *count = 0;

    if (!g_initialized)
        return NULL;

    size_t animation_count = tc_pool_count(&g_animation_pool);
    if (animation_count == 0)
        return NULL;

    tc_animation_info* infos = (tc_animation_info*)malloc(animation_count * sizeof(tc_animation_info));
    if (!infos)
        return NULL;

    animation_info_collector collector = {infos, 0};
    tc_animation_foreach(collect_animation_info, &collector);

    *count = collector.count;
    return infos;
}
