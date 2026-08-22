#include "resources/tc_skeleton_registry.h"

#include <stdint.h>
#include <stdlib.h>
#include <string.h>

#include <geom/tc_quat.h>
#include <tcbase/tc_log.h>
#include <tcbase/tc_pool.h>
#include <tcbase/tc_registry_utils.h>
#include <tcbase/tc_resource_map.h>
#include <tcbase/tc_string.h>

static tc_pool g_skeleton_pool;
static tc_pool_generation_epoch g_skeleton_generation_epoch;
static tc_resource_map* g_uuid_to_index = NULL;
static uint64_t g_next_uuid = 1;
static bool g_initialized = false;

static void skeleton_free_data(tc_skeleton* skeleton) {
    if (!skeleton)
        return;
    if (skeleton->bones) {
        free((void*)skeleton->bones);
        skeleton->bones = NULL;
    }
    if (skeleton->root_indices) {
        free((void*)skeleton->root_indices);
        skeleton->root_indices = NULL;
    }
    skeleton->bone_count = 0;
    skeleton->root_count = 0;
}

static bool skeleton_destroy_unreferenced(tc_skeleton_handle h, tc_skeleton* skeleton) {
    if (!skeleton)
        return false;
    tc_resource_map_remove(g_uuid_to_index, skeleton->header.uuid);
    skeleton_free_data(skeleton);
    return tc_pool_free_slot(&g_skeleton_pool, h);
}

void tc_skeleton_init(void) {
    TC_REGISTRY_INIT_GUARD(g_initialized, "tc_skeleton");

    if (!tc_pool_init_rebootstrap(&g_skeleton_pool, sizeof(tc_skeleton), 32, &g_skeleton_generation_epoch)) {
        tc_log_error("tc_skeleton_init: failed to init pool");
        return;
    }

    g_uuid_to_index = tc_resource_map_new(NULL);
    if (!g_uuid_to_index) {
        tc_log_error("tc_skeleton_init: failed to create uuid map");
        tc_pool_free(&g_skeleton_pool);
        return;
    }

    g_next_uuid = 1;
    g_initialized = true;
}

void tc_skeleton_shutdown(void) {
    TC_REGISTRY_SHUTDOWN_GUARD(g_initialized, "tc_skeleton");

    for (uint32_t i = 0; i < g_skeleton_pool.capacity; i++) {
        if (g_skeleton_pool.states[i] == TC_SLOT_OCCUPIED) {
            tc_skeleton* skeleton = (tc_skeleton*)tc_pool_get_unchecked(&g_skeleton_pool, i);
            skeleton_free_data(skeleton);
        }
    }

    tc_pool_free(&g_skeleton_pool);
    tc_resource_map_free(g_uuid_to_index);
    g_uuid_to_index = NULL;
    g_next_uuid = 1;
    g_initialized = false;
}

tc_skeleton_handle tc_skeleton_create(const char* uuid) {
    if (!g_initialized) {
        tc_skeleton_init();
    }

    char uuid_buf[TC_UUID_SIZE];
    if (uuid && uuid[0] != '\0') {
        // Normalize (and report truncation) before acquiring a movable pool
        // address: logging may invoke user code that grows this registry.
        tc_resource_copy_uuid(uuid_buf, sizeof(uuid_buf), uuid, "tc_skeleton_create");
        if (tc_skeleton_contains(uuid_buf)) {
            tc_log_warn("tc_skeleton_create: uuid '%s' already exists", uuid_buf);
            return tc_skeleton_handle_invalid();
        }
    } else {
        tc_generate_prefixed_uuid(uuid_buf, sizeof(uuid_buf), "skel", &g_next_uuid);
    }

    tc_handle h = tc_pool_alloc(&g_skeleton_pool);
    if (tc_handle_is_invalid(h)) {
        tc_log_error("tc_skeleton_create: pool alloc failed");
        return tc_skeleton_handle_invalid();
    }

    tc_skeleton* skeleton = (tc_skeleton*)tc_pool_get(&g_skeleton_pool, h);
    memset(skeleton, 0, sizeof(tc_skeleton));
    tc_resource_header_set_uuid(&skeleton->header, uuid_buf, "tc_skeleton_create");
    skeleton->header.version = 1;
    skeleton->header.ref_count = 0;
    skeleton->header.is_loaded = 1;

    if (!tc_resource_map_add(g_uuid_to_index, skeleton->header.uuid, tc_pack_index(h.index))) {
        tc_log_error("tc_skeleton_create: failed to add to uuid map");
        tc_pool_free_slot(&g_skeleton_pool, h);
        return tc_skeleton_handle_invalid();
    }

    return h;
}

tc_skeleton_handle tc_skeleton_find(const char* uuid) {
    if (!g_initialized || !uuid) {
        return tc_skeleton_handle_invalid();
    }

    char normalized_uuid[TC_UUID_SIZE];
    tc_resource_copy_uuid(normalized_uuid, sizeof(normalized_uuid), uuid, "tc_skeleton_find");
    void* ptr = tc_resource_map_get(g_uuid_to_index, normalized_uuid);
    if (!tc_has_index(ptr)) {
        return tc_skeleton_handle_invalid();
    }

    uint32_t index = tc_unpack_index(ptr);
    if (index >= g_skeleton_pool.capacity) {
        return tc_skeleton_handle_invalid();
    }

    if (g_skeleton_pool.states[index] != TC_SLOT_OCCUPIED) {
        return tc_skeleton_handle_invalid();
    }

    tc_skeleton_handle h;
    h.index = index;
    h.generation = g_skeleton_pool.generations[index];
    return h;
}

tc_skeleton_handle tc_skeleton_find_by_name(const char* name) {
    if (!g_initialized || !name) {
        return tc_skeleton_handle_invalid();
    }

    for (uint32_t i = 0; i < g_skeleton_pool.capacity; i++) {
        if (g_skeleton_pool.states[i] == TC_SLOT_OCCUPIED) {
            tc_skeleton* skeleton = (tc_skeleton*)tc_pool_get_unchecked(&g_skeleton_pool, i);
            if (skeleton->header.name && strcmp(skeleton->header.name, name) == 0) {
                tc_skeleton_handle h;
                h.index = i;
                h.generation = g_skeleton_pool.generations[i];
                return h;
            }
        }
    }

    return tc_skeleton_handle_invalid();
}

tc_skeleton_handle tc_skeleton_get_or_create(const char* uuid) {
    if (!uuid || uuid[0] == '\0') {
        tc_log_warn("tc_skeleton_get_or_create: empty uuid");
        return tc_skeleton_handle_invalid();
    }

    char normalized_uuid[TC_UUID_SIZE];
    tc_resource_copy_uuid(normalized_uuid, sizeof(normalized_uuid), uuid, "tc_skeleton_get_or_create");
    tc_skeleton_handle h = tc_skeleton_find(normalized_uuid);
    if (!tc_skeleton_handle_is_invalid(h)) {
        return h;
    }

    return tc_skeleton_create(normalized_uuid);
}

tc_skeleton_handle tc_skeleton_declare(const char* uuid, const char* name) {
    if (!g_initialized) {
        tc_skeleton_init();
    }

    // Both operations may log. Complete them before taking a pointer into the
    // skeleton pool so a reentrant callback cannot invalidate that pointer.
    char normalized_uuid[TC_UUID_SIZE];
    tc_resource_copy_uuid(normalized_uuid, sizeof(normalized_uuid), uuid, "tc_skeleton_declare");
    const char* interned_name = name && name[0] != '\0' ? tc_intern_string(name) : NULL;

    tc_skeleton_handle existing = tc_skeleton_find(normalized_uuid);
    if (!tc_skeleton_handle_is_invalid(existing)) {
        return existing;
    }

    tc_handle h = tc_pool_alloc(&g_skeleton_pool);
    if (tc_handle_is_invalid(h)) {
        tc_log_error("tc_skeleton_declare: pool alloc failed");
        return tc_skeleton_handle_invalid();
    }

    tc_skeleton* skeleton = (tc_skeleton*)tc_pool_get(&g_skeleton_pool, h);
    memset(skeleton, 0, sizeof(tc_skeleton));
    tc_resource_header_set_uuid(&skeleton->header, normalized_uuid, "tc_skeleton_declare");
    skeleton->header.version = 0;
    skeleton->header.ref_count = 0;
    skeleton->header.is_loaded = 0;

    skeleton->header.name = interned_name;

    if (!tc_resource_map_add(g_uuid_to_index, skeleton->header.uuid, tc_pack_index(h.index))) {
        tc_log_error("tc_skeleton_declare: failed to add to uuid map");
        tc_pool_free_slot(&g_skeleton_pool, h);
        return tc_skeleton_handle_invalid();
    }

    return h;
}

tc_skeleton* tc_skeleton_get(tc_skeleton_handle h) {
    if (!g_initialized)
        return NULL;
    return (tc_skeleton*)tc_pool_get_checked(&g_skeleton_pool, h, "tc_skeleton");
}

bool tc_skeleton_is_valid(tc_skeleton_handle h) {
    if (!g_initialized)
        return false;
    return tc_pool_is_valid(&g_skeleton_pool, h);
}

bool tc_skeleton_handle_retain(tc_skeleton_handle h) {
    if (!g_initialized || !tc_pool_is_valid(&g_skeleton_pool, h))
        return false;

    tc_skeleton* skeleton = (tc_skeleton*)tc_pool_get(&g_skeleton_pool, h);
    if (skeleton->header.ref_count == UINT32_MAX) {
        tc_log_error("tc_skeleton_handle_retain: refcount overflow for '%s'", skeleton->header.uuid);
        return false;
    }
    skeleton->header.ref_count++;
    return true;
}

bool tc_skeleton_handle_release(tc_skeleton_handle h) {
    if (!g_initialized || !tc_pool_is_valid(&g_skeleton_pool, h))
        return false;

    tc_skeleton* skeleton = (tc_skeleton*)tc_pool_get(&g_skeleton_pool, h);
    if (skeleton->header.ref_count == 0) {
        tc_log_error("tc_skeleton_handle_release: resource '%s' has no strong references", skeleton->header.uuid);
        return false;
    }

    skeleton->header.ref_count--;
    if (skeleton->header.ref_count == 0)
        return skeleton_destroy_unreferenced(h, skeleton);
    return true;
}

bool tc_skeleton_destroy(tc_skeleton_handle h) {
    if (!g_initialized)
        return false;

    tc_skeleton* skeleton = tc_skeleton_get(h);
    if (!skeleton)
        return false;
    if (skeleton->header.ref_count != 0) {
        tc_log_error("tc_skeleton_destroy: resource '%s' still has %u strong reference(s)",
                     skeleton->header.uuid,
                     skeleton->header.ref_count);
        return false;
    }
    return skeleton_destroy_unreferenced(h, skeleton);
}

bool tc_skeleton_contains(const char* uuid) {
    if (!g_initialized || !uuid)
        return false;
    char normalized_uuid[TC_UUID_SIZE];
    tc_resource_copy_uuid(normalized_uuid, sizeof(normalized_uuid), uuid, "tc_skeleton_contains");
    return tc_resource_map_contains(g_uuid_to_index, normalized_uuid);
}

size_t tc_skeleton_count(void) {
    if (!g_initialized)
        return 0;
    return tc_pool_count(&g_skeleton_pool);
}

bool tc_skeleton_is_loaded(tc_skeleton_handle h) {
    tc_skeleton* skeleton = tc_skeleton_get(h);
    if (!skeleton)
        return false;
    return skeleton->header.is_loaded != 0;
}

bool tc_skeleton_ensure_loaded(tc_skeleton_handle h) {
    tc_skeleton* skeleton = tc_skeleton_get(h);
    if (!skeleton)
        return false;
    if (skeleton->header.is_loaded)
        return true;

    // The loader may create more skeleton resources and grow this pool. Keep
    // only the stable UUID/handle across the callback, then resolve the slot
    // again before committing load state.
    char uuid[TC_UUID_SIZE];
    tc_resource_copy_uuid(uuid, sizeof(uuid), skeleton->header.uuid, "tc_skeleton_ensure_loaded");
    if (!tc_resource_request_load(uuid)) {
        tc_log_error("tc_skeleton_ensure_loaded: resource loader failed for '%s'", uuid);
        return false;
    }

    skeleton = tc_skeleton_get(h);
    if (!skeleton) {
        tc_log_error("tc_skeleton_ensure_loaded: resource '%s' disappeared while its loader was running", uuid);
        return false;
    }
    skeleton->header.is_loaded = 1;
    return true;
}

static bool skeleton_desc_values_valid(const tc_skeleton_bone_desc* bone, size_t index) {
    if (!tc_mat44_is_finite(bone->inverse_bind_matrix)) {
        tc_log_error("tc_skeleton_replace_bones: bone[%zu] inverse bind matrix is not finite", index);
        return false;
    }
    if (!tc_quat_is_finite(bone->bind_rotation)) {
        tc_log_error("tc_skeleton_replace_bones: bone[%zu] rotation is not finite", index);
        return false;
    }
    tc_quat normalized;
    if (!tc_quat_try_normalized(bone->bind_rotation, 0.0, &normalized)) {
        tc_log_error("tc_skeleton_replace_bones: bone[%zu] rotation has zero length", index);
        return false;
    }
    if (!tc_vec3_is_finite(bone->bind_translation) || !tc_vec3_is_finite(bone->bind_scale)) {
        tc_log_error("tc_skeleton_replace_bones: bone[%zu] TRS is not finite", index);
        return false;
    }
    return true;
}

bool tc_skeleton_replace_bones(tc_skeleton* skeleton, const tc_skeleton_bone_desc* bones, size_t count) {
    if (!skeleton || (count > 0 && !bones)) {
        tc_log_error("tc_skeleton_replace_bones: skeleton and descriptors are required");
        return false;
    }
    if (count > INT32_MAX || count > SIZE_MAX / sizeof(tc_bone)) {
        tc_log_error("tc_skeleton_replace_bones: bone count is out of range");
        return false;
    }
    size_t root_count = 0;
    for (size_t i = 0; i < count; ++i) {
        const int32_t parent = bones[i].parent_index;
        if (parent < -1 || (parent >= 0 && (size_t)parent >= count) || parent == (int32_t)i) {
            tc_log_error("tc_skeleton_replace_bones: bone[%zu] has invalid parent=%d", i, parent);
            return false;
        }
        if (!skeleton_desc_values_valid(&bones[i], i))
            return false;
        if (parent < 0)
            ++root_count;
    }
    for (size_t i = 0; i < count; ++i) {
        int32_t ancestor = bones[i].parent_index;
        size_t depth = 0;
        while (ancestor >= 0) {
            if (++depth > count) {
                tc_log_error("tc_skeleton_replace_bones: bone hierarchy contains a cycle at bone[%zu]", i);
                return false;
            }
            ancestor = bones[(size_t)ancestor].parent_index;
        }
    }

    tc_bone* replacement = count > 0 ? (tc_bone*)calloc(count, sizeof(tc_bone)) : NULL;
    int32_t* roots = root_count > 0 ? (int32_t*)malloc(root_count * sizeof(int32_t)) : NULL;
    if ((count > 0 && !replacement) || (root_count > 0 && !roots)) {
        tc_log_error("tc_skeleton_replace_bones: payload allocation failed");
        free(replacement);
        free(roots);
        return false;
    }

    size_t root_index = 0;
    size_t truncated_name_count = 0;
    for (size_t i = 0; i < count; ++i) {
        tc_bone* destination = &replacement[i];
        const tc_skeleton_bone_desc* source = &bones[i];
        tc_bone_init(destination);
        destination->index = (int32_t)i;
        destination->parent_index = source->parent_index;
        if (source->name) {
            if (strlen(source->name) >= TC_BONE_NAME_MAX)
                ++truncated_name_count;
            strncpy(destination->name, source->name, TC_BONE_NAME_MAX - 1);
            destination->name[TC_BONE_NAME_MAX - 1] = '\0';
        }
        destination->inverse_bind_matrix = source->inverse_bind_matrix;
        destination->bind_translation = source->bind_translation;
        tc_quat normalized_rotation;
        if (!tc_quat_try_normalized(source->bind_rotation, 0.0, &normalized_rotation)) {
            tc_log_error("tc_skeleton_replace_bones: bone[%zu] rotation changed during replacement", i);
            free(replacement);
            free(roots);
            return false;
        }
        destination->bind_rotation = normalized_rotation;
        destination->bind_scale = source->bind_scale;
        if (source->parent_index < 0)
            roots[root_index++] = (int32_t)i;
    }

    free((void*)skeleton->bones);
    free((void*)skeleton->root_indices);
    skeleton->bones = replacement;
    skeleton->bone_count = count;
    skeleton->root_indices = roots;
    skeleton->root_count = root_count;
    skeleton->header.is_loaded = 1;
    skeleton->header.version++;

    // Logging can invoke user code and mutate a registry pool. Emit the
    // successful-replacement diagnostic only after the borrowed skeleton
    // pointer is no longer needed.
    if (truncated_name_count > 0) {
        tc_log_warn("tc_skeleton_replace_bones: truncated %zu bone name(s) to %d bytes",
                    truncated_name_count,
                    TC_BONE_NAME_MAX - 1);
    }
    return true;
}

const tc_bone* tc_skeleton_get_bone_const(const tc_skeleton* skeleton, size_t index) {
    if (!skeleton || index >= skeleton->bone_count)
        return NULL;
    return &skeleton->bones[index];
}

int tc_skeleton_find_bone(const tc_skeleton* skeleton, const char* name) {
    if (!skeleton || !name || !skeleton->bones)
        return -1;

    for (size_t i = 0; i < skeleton->bone_count; i++) {
        if (strcmp(skeleton->bones[i].name, name) == 0) {
            return (int)i;
        }
    }
    return -1;
}

typedef struct {
    tc_skeleton_iter_fn callback;
    void* user_data;
} skeleton_iter_ctx;

static bool skeleton_iter_adapter(uint32_t index, void* item, void* ctx_ptr) {
    skeleton_iter_ctx* ctx = (skeleton_iter_ctx*)ctx_ptr;
    tc_skeleton* skeleton = (tc_skeleton*)item;

    tc_skeleton_handle h;
    h.index = index;
    h.generation = g_skeleton_pool.generations[index];

    return ctx->callback(h, skeleton, ctx->user_data);
}

void tc_skeleton_foreach(tc_skeleton_iter_fn callback, void* user_data) {
    if (!g_initialized || !callback)
        return;
    skeleton_iter_ctx ctx = {callback, user_data};
    tc_pool_foreach(&g_skeleton_pool, skeleton_iter_adapter, &ctx);
}

typedef struct {
    tc_skeleton_info* infos;
    size_t count;
} skeleton_info_collector;

static bool collect_skeleton_info(tc_skeleton_handle h, tc_skeleton* skeleton, void* user_data) {
    skeleton_info_collector* collector = (skeleton_info_collector*)user_data;

    tc_skeleton_info* info = &collector->infos[collector->count++];
    info->handle = h;
    strncpy(info->uuid, skeleton->header.uuid, sizeof(info->uuid) - 1);
    info->uuid[sizeof(info->uuid) - 1] = '\0';
    info->name = skeleton->header.name;
    info->ref_count = skeleton->header.ref_count;
    info->version = skeleton->header.version;
    info->bone_count = skeleton->bone_count;
    info->is_loaded = skeleton->header.is_loaded;

    return true;
}

tc_skeleton_info* tc_skeleton_get_all_info(size_t* count) {
    if (!count)
        return NULL;
    *count = 0;

    if (!g_initialized)
        return NULL;

    size_t skeleton_count = tc_pool_count(&g_skeleton_pool);
    if (skeleton_count == 0)
        return NULL;

    tc_skeleton_info* infos = (tc_skeleton_info*)malloc(skeleton_count * sizeof(tc_skeleton_info));
    if (!infos)
        return NULL;

    skeleton_info_collector collector = {infos, 0};
    tc_skeleton_foreach(collect_skeleton_info, &collector);

    *count = collector.count;
    return infos;
}
