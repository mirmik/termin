#include "termin/voxels/tc_voxel_grid_registry.h"
#include "termin/voxels/tc_voxel_grid_payload.hpp"

#include <tcbase/tc_log.h>
#include <tcbase/tc_pool.h>
#include <tcbase/tc_resource.h>
#include <tcbase/tc_resource_map.h>
#include <tcbase/tgfx_intern_string.h>

#include <cstdio>
#include <cstring>

static tc_pool g_voxel_grid_pool;
static tc_resource_map* g_uuid_to_index = nullptr;
static uint64_t g_next_uuid = 1;
static bool g_initialized = false;

static void* voxel_grid_pack_index(uint32_t index) {
    return reinterpret_cast<void*>(static_cast<uintptr_t>(index + 1u));
}

static bool voxel_grid_has_index(void* ptr) {
    return ptr != nullptr;
}

static uint32_t voxel_grid_unpack_index(void* ptr) {
    return static_cast<uint32_t>(reinterpret_cast<uintptr_t>(ptr) - 1u);
}

static void voxel_grid_bump_version(tc_voxel_grid* grid) {
    if (grid) grid->version++;
}

static void voxel_grid_free_payload(tc_voxel_grid* grid) {
    if (!grid || !grid->native_payload) return;
    delete static_cast<termin::voxels::VoxelGrid*>(grid->native_payload);
    grid->native_payload = nullptr;
}

static void voxel_grid_init_slot(tc_voxel_grid* grid, tc_handle h, const char* uuid, bool loaded) {
    std::memset(grid, 0, sizeof(tc_voxel_grid));
    tc_resource_copy_uuid(grid->uuid, sizeof(grid->uuid), uuid, "tc_voxel_grid_init_slot");
    grid->version = loaded ? 1 : 0;
    grid->pool_index = h.index;
    grid->is_loaded = loaded ? 1 : 0;
}

void tc_voxel_grid_init(void) {
    if (g_initialized) return;
    if (!tc_pool_init(&g_voxel_grid_pool, sizeof(tc_voxel_grid), 32)) {
        tc_log(TC_LOG_ERROR, "tc_voxel_grid_init: failed to init pool");
        return;
    }
    g_uuid_to_index = tc_resource_map_new(nullptr);
    if (!g_uuid_to_index) {
        tc_log(TC_LOG_ERROR, "tc_voxel_grid_init: failed to create uuid map");
        tc_pool_free(&g_voxel_grid_pool);
        return;
    }
    g_next_uuid = 1;
    g_initialized = true;
}

void tc_voxel_grid_shutdown(void) {
    if (!g_initialized) return;
    for (uint32_t i = 0; i < g_voxel_grid_pool.capacity; ++i) {
        if (g_voxel_grid_pool.states[i] == TC_SLOT_OCCUPIED) {
            tc_voxel_grid* grid = static_cast<tc_voxel_grid*>(
                tc_pool_get_unchecked(&g_voxel_grid_pool, i));
            voxel_grid_free_payload(grid);
        }
    }
    tc_pool_free(&g_voxel_grid_pool);
    tc_resource_map_free(g_uuid_to_index);
    g_uuid_to_index = nullptr;
    g_next_uuid = 1;
    g_initialized = false;
}

tc_voxel_grid_handle tc_voxel_grid_create(const char* uuid) {
    if (!g_initialized) tc_voxel_grid_init();

    char uuid_buf[TC_UUID_SIZE];
    const char* final_uuid = uuid;
    if (!final_uuid || final_uuid[0] == '\0') {
        std::snprintf(uuid_buf, sizeof(uuid_buf), "voxel-grid-%llu", static_cast<unsigned long long>(g_next_uuid++));
        final_uuid = uuid_buf;
    }
    if (tc_voxel_grid_contains(final_uuid)) {
        tc_log(TC_LOG_WARN, "tc_voxel_grid_create: uuid '%s' already exists", final_uuid);
        return tc_voxel_grid_handle_invalid();
    }

    tc_handle h = tc_pool_alloc(&g_voxel_grid_pool);
    if (tc_handle_is_invalid(h)) {
        tc_log(TC_LOG_ERROR, "tc_voxel_grid_create: pool alloc failed");
        return tc_voxel_grid_handle_invalid();
    }

    tc_voxel_grid* grid = static_cast<tc_voxel_grid*>(tc_pool_get(&g_voxel_grid_pool, h));
    voxel_grid_init_slot(grid, h, final_uuid, true);
    if (!tc_resource_map_add(g_uuid_to_index, grid->uuid, voxel_grid_pack_index(h.index))) {
        tc_log(TC_LOG_ERROR, "tc_voxel_grid_create: failed to add to uuid map");
        tc_pool_free_slot(&g_voxel_grid_pool, h);
        return tc_voxel_grid_handle_invalid();
    }
    return h;
}

tc_voxel_grid_handle tc_voxel_grid_find(const char* uuid) {
    if (!g_initialized || !uuid) return tc_voxel_grid_handle_invalid();
    void* ptr = tc_resource_map_get(g_uuid_to_index, uuid);
    if (!voxel_grid_has_index(ptr)) return tc_voxel_grid_handle_invalid();
    uint32_t index = voxel_grid_unpack_index(ptr);
    if (index >= g_voxel_grid_pool.capacity || g_voxel_grid_pool.states[index] != TC_SLOT_OCCUPIED) {
        return tc_voxel_grid_handle_invalid();
    }
    tc_voxel_grid_handle h;
    h.index = index;
    h.generation = g_voxel_grid_pool.generations[index];
    return h;
}

tc_voxel_grid_handle tc_voxel_grid_find_by_name(const char* name) {
    if (!g_initialized || !name) return tc_voxel_grid_handle_invalid();
    for (uint32_t i = 0; i < g_voxel_grid_pool.capacity; ++i) {
        if (g_voxel_grid_pool.states[i] != TC_SLOT_OCCUPIED) continue;
        tc_voxel_grid* grid = static_cast<tc_voxel_grid*>(tc_pool_get_unchecked(&g_voxel_grid_pool, i));
        if (grid->name && std::strcmp(grid->name, name) == 0) {
            tc_voxel_grid_handle h;
            h.index = i;
            h.generation = g_voxel_grid_pool.generations[i];
            return h;
        }
    }
    return tc_voxel_grid_handle_invalid();
}

tc_voxel_grid_handle tc_voxel_grid_get_or_create(const char* uuid) {
    if (!uuid || uuid[0] == '\0') return tc_voxel_grid_handle_invalid();
    tc_voxel_grid_handle h = tc_voxel_grid_find(uuid);
    return tc_voxel_grid_handle_is_invalid(h) ? tc_voxel_grid_create(uuid) : h;
}

tc_voxel_grid_handle tc_voxel_grid_declare(const char* uuid, const char* name) {
    if (!g_initialized) tc_voxel_grid_init();
    if (!uuid || uuid[0] == '\0') return tc_voxel_grid_handle_invalid();
    tc_voxel_grid_handle existing = tc_voxel_grid_find(uuid);
    if (!tc_voxel_grid_handle_is_invalid(existing)) return existing;

    tc_handle h = tc_pool_alloc(&g_voxel_grid_pool);
    if (tc_handle_is_invalid(h)) {
        tc_log(TC_LOG_ERROR, "tc_voxel_grid_declare: pool alloc failed");
        return tc_voxel_grid_handle_invalid();
    }

    tc_voxel_grid* grid = static_cast<tc_voxel_grid*>(tc_pool_get(&g_voxel_grid_pool, h));
    voxel_grid_init_slot(grid, h, uuid, false);
    if (name && name[0] != '\0') {
        grid->name = tgfx_intern_string(name);
    }

    if (!tc_resource_map_add(g_uuid_to_index, grid->uuid, voxel_grid_pack_index(h.index))) {
        tc_log(TC_LOG_ERROR, "tc_voxel_grid_declare: failed to add to uuid map");
        tc_pool_free_slot(&g_voxel_grid_pool, h);
        return tc_voxel_grid_handle_invalid();
    }
    return h;
}

tc_voxel_grid* tc_voxel_grid_get(tc_voxel_grid_handle h) {
    if (!g_initialized) return nullptr;
    return static_cast<tc_voxel_grid*>(tc_pool_get(&g_voxel_grid_pool, h));
}

bool tc_voxel_grid_is_valid(tc_voxel_grid_handle h) {
    return g_initialized && tc_pool_is_valid(&g_voxel_grid_pool, h);
}

bool tc_voxel_grid_destroy(tc_voxel_grid_handle h) {
    if (!g_initialized) return false;
    tc_voxel_grid* grid = tc_voxel_grid_get(h);
    if (!grid) return false;
    tc_resource_map_remove(g_uuid_to_index, grid->uuid);
    voxel_grid_free_payload(grid);
    return tc_pool_free_slot(&g_voxel_grid_pool, h);
}

bool tc_voxel_grid_contains(const char* uuid) {
    return g_initialized && uuid && tc_resource_map_contains(g_uuid_to_index, uuid);
}

size_t tc_voxel_grid_count(void) {
    return g_initialized ? tc_pool_count(&g_voxel_grid_pool) : 0;
}

void tc_voxel_grid_set_load_callback(
    tc_voxel_grid_handle h,
    tc_voxel_grid_load_fn callback,
    void* user_data
) {
    tc_voxel_grid* grid = tc_voxel_grid_get(h);
    if (!grid) return;
    grid->load_callback = callback;
    grid->load_user_data = user_data;
}

bool tc_voxel_grid_is_loaded(tc_voxel_grid_handle h) {
    tc_voxel_grid* grid = tc_voxel_grid_get(h);
    return grid && grid->is_loaded != 0;
}

bool tc_voxel_grid_ensure_loaded(tc_voxel_grid_handle h) {
    tc_voxel_grid* grid = tc_voxel_grid_get(h);
    if (!grid) return false;
    if (grid->is_loaded) return true;
    if (!grid->load_callback) return false;
    bool success = grid->load_callback(grid, grid->load_user_data);
    if (success) {
        grid->is_loaded = 1;
        voxel_grid_bump_version(grid);
    }
    return success;
}

bool tc_voxel_grid_set_metadata(tc_voxel_grid* grid, const char* name, const char* source_path) {
    if (!grid) return false;
    if (name && name[0] != '\0') grid->name = tgfx_intern_string(name);
    if (source_path && source_path[0] != '\0') grid->source_path = tgfx_intern_string(source_path);
    voxel_grid_bump_version(grid);
    return true;
}

namespace termin {
namespace voxels {

VoxelGrid* tc_voxel_grid_payload(tc_voxel_grid_handle h) {
    tc_voxel_grid* grid = tc_voxel_grid_get(h);
    return grid ? static_cast<VoxelGrid*>(grid->native_payload) : nullptr;
}

const VoxelGrid* tc_voxel_grid_payload_const(tc_voxel_grid_handle h) {
    tc_voxel_grid* grid = tc_voxel_grid_get(h);
    return grid ? static_cast<const VoxelGrid*>(grid->native_payload) : nullptr;
}

bool tc_voxel_grid_set_payload_copy(tc_voxel_grid_handle h, const VoxelGrid& payload) {
    tc_voxel_grid* grid = tc_voxel_grid_get(h);
    if (!grid) return false;
    voxel_grid_free_payload(grid);
    grid->native_payload = new VoxelGrid(payload);
    grid->is_loaded = 1;
    if (grid->name == nullptr || grid->name[0] == '\0') {
        const std::string& payload_name = payload.name();
        if (!payload_name.empty()) {
            grid->name = tgfx_intern_string(payload_name.c_str());
        }
    }
    const std::string& payload_source_path = payload.source_path();
    if (!payload_source_path.empty()) {
        grid->source_path = tgfx_intern_string(payload_source_path.c_str());
    }
    voxel_grid_bump_version(grid);
    return true;
}

bool tc_voxel_grid_clear_payload(tc_voxel_grid_handle h) {
    tc_voxel_grid* grid = tc_voxel_grid_get(h);
    if (!grid) return false;
    voxel_grid_free_payload(grid);
    grid->is_loaded = 0;
    voxel_grid_bump_version(grid);
    return true;
}

} // namespace voxels
} // namespace termin

void tc_voxel_grid_add_ref(tc_voxel_grid* grid) {
    if (grid) grid->ref_count++;
}

bool tc_voxel_grid_release(tc_voxel_grid* grid) {
    if (!grid) return false;
    if (grid->ref_count > 0) grid->ref_count--;
    return grid->ref_count == 0;
}
