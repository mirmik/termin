// tc_navmesh_registry.c - Navmesh registry with pool + hash table
#include "termin/navmesh/tc_navmesh_registry.h"
#include <tcbase/tc_pool.h>
#include <tcbase/tc_resource_map.h>
#include <tcbase/tc_log.h>
#include <tcbase/tgfx_intern_string.h>
#include <stdlib.h>
#include <stdio.h>
#include <string.h>

static tc_pool g_navmesh_pool;
static tc_resource_map* g_uuid_to_index = NULL;
static uint64_t g_next_uuid = 1;
static bool g_initialized = false;

static void* navmesh_pack_index(uint32_t index) {
    return (void*)(uintptr_t)(index + 1u);
}

static bool navmesh_has_index(void* ptr) {
    return ptr != NULL;
}

static uint32_t navmesh_unpack_index(void* ptr) {
    return (uint32_t)((uintptr_t)ptr - 1u);
}

static void navmesh_free_data(tc_navmesh* navmesh) {
    if (!navmesh) return;
    if (navmesh->tiles) {
        for (size_t i = 0; i < navmesh->tile_count; ++i) {
            free(navmesh->tiles[i].data);
            navmesh->tiles[i].data = NULL;
            navmesh->tiles[i].data_size = 0;
        }
        free(navmesh->tiles);
        navmesh->tiles = NULL;
    }
    navmesh->tile_count = 0;
}

static void navmesh_bump_version(tc_navmesh* navmesh) {
    if (navmesh) navmesh->version++;
}

static void navmesh_init_slot(tc_navmesh* navmesh, tc_handle h, const char* uuid, bool loaded) {
    memset(navmesh, 0, sizeof(tc_navmesh));
    if (uuid && uuid[0] != '\0') {
        strncpy(navmesh->uuid, uuid, sizeof(navmesh->uuid) - 1);
        navmesh->uuid[sizeof(navmesh->uuid) - 1] = '\0';
    }
    navmesh->version = loaded ? 1 : 0;
    navmesh->pool_index = h.index;
    navmesh->is_loaded = loaded ? 1 : 0;
}

void tc_navmesh_init(void) {
    if (g_initialized) return;
    if (!tc_pool_init(&g_navmesh_pool, sizeof(tc_navmesh), 32)) {
        tc_log(TC_LOG_ERROR, "tc_navmesh_init: failed to init pool");
        return;
    }
    g_uuid_to_index = tc_resource_map_new(NULL);
    if (!g_uuid_to_index) {
        tc_log(TC_LOG_ERROR, "tc_navmesh_init: failed to create uuid map");
        tc_pool_free(&g_navmesh_pool);
        return;
    }
    g_next_uuid = 1;
    g_initialized = true;
}

void tc_navmesh_shutdown(void) {
    if (!g_initialized) return;
    for (uint32_t i = 0; i < g_navmesh_pool.capacity; ++i) {
        if (g_navmesh_pool.states[i] == TC_SLOT_OCCUPIED) {
            tc_navmesh* navmesh = (tc_navmesh*)tc_pool_get_unchecked(&g_navmesh_pool, i);
            navmesh_free_data(navmesh);
        }
    }
    tc_pool_free(&g_navmesh_pool);
    tc_resource_map_free(g_uuid_to_index);
    g_uuid_to_index = NULL;
    g_next_uuid = 1;
    g_initialized = false;
}

tc_navmesh_handle tc_navmesh_create(const char* uuid) {
    if (!g_initialized) tc_navmesh_init();

    char uuid_buf[TC_UUID_SIZE];
    const char* final_uuid = uuid;
    if (!final_uuid || final_uuid[0] == '\0') {
        snprintf(uuid_buf, sizeof(uuid_buf), "navmesh-%llu", (unsigned long long)g_next_uuid++);
        final_uuid = uuid_buf;
    }
    if (tc_navmesh_contains(final_uuid)) {
        tc_log(TC_LOG_WARN, "tc_navmesh_create: uuid '%s' already exists", final_uuid);
        return tc_navmesh_handle_invalid();
    }

    tc_handle h = tc_pool_alloc(&g_navmesh_pool);
    if (tc_handle_is_invalid(h)) {
        tc_log(TC_LOG_ERROR, "tc_navmesh_create: pool alloc failed");
        return tc_navmesh_handle_invalid();
    }

    tc_navmesh* navmesh = (tc_navmesh*)tc_pool_get(&g_navmesh_pool, h);
    navmesh_init_slot(navmesh, h, final_uuid, true);
    if (!tc_resource_map_add(g_uuid_to_index, navmesh->uuid, navmesh_pack_index(h.index))) {
        tc_log(TC_LOG_ERROR, "tc_navmesh_create: failed to add to uuid map");
        tc_pool_free_slot(&g_navmesh_pool, h);
        return tc_navmesh_handle_invalid();
    }
    return h;
}

tc_navmesh_handle tc_navmesh_find(const char* uuid) {
    if (!g_initialized || !uuid) return tc_navmesh_handle_invalid();
    void* ptr = tc_resource_map_get(g_uuid_to_index, uuid);
    if (!navmesh_has_index(ptr)) return tc_navmesh_handle_invalid();
    uint32_t index = navmesh_unpack_index(ptr);
    if (index >= g_navmesh_pool.capacity || g_navmesh_pool.states[index] != TC_SLOT_OCCUPIED) {
        return tc_navmesh_handle_invalid();
    }
    tc_navmesh_handle h;
    h.index = index;
    h.generation = g_navmesh_pool.generations[index];
    return h;
}

tc_navmesh_handle tc_navmesh_find_by_name(const char* name) {
    if (!g_initialized || !name) return tc_navmesh_handle_invalid();
    for (uint32_t i = 0; i < g_navmesh_pool.capacity; ++i) {
        if (g_navmesh_pool.states[i] != TC_SLOT_OCCUPIED) continue;
        tc_navmesh* navmesh = (tc_navmesh*)tc_pool_get_unchecked(&g_navmesh_pool, i);
        if (navmesh->name && strcmp(navmesh->name, name) == 0) {
            tc_navmesh_handle h;
            h.index = i;
            h.generation = g_navmesh_pool.generations[i];
            return h;
        }
    }
    return tc_navmesh_handle_invalid();
}

tc_navmesh_handle tc_navmesh_get_or_create(const char* uuid) {
    if (!uuid || uuid[0] == '\0') return tc_navmesh_handle_invalid();
    tc_navmesh_handle h = tc_navmesh_find(uuid);
    return tc_navmesh_handle_is_invalid(h) ? tc_navmesh_create(uuid) : h;
}

tc_navmesh_handle tc_navmesh_declare(const char* uuid, const char* name) {
    if (!g_initialized) tc_navmesh_init();
    if (!uuid || uuid[0] == '\0') return tc_navmesh_handle_invalid();
    tc_navmesh_handle existing = tc_navmesh_find(uuid);
    if (!tc_navmesh_handle_is_invalid(existing)) return existing;

    tc_handle h = tc_pool_alloc(&g_navmesh_pool);
    if (tc_handle_is_invalid(h)) {
        tc_log(TC_LOG_ERROR, "tc_navmesh_declare: pool alloc failed");
        return tc_navmesh_handle_invalid();
    }

    tc_navmesh* navmesh = (tc_navmesh*)tc_pool_get(&g_navmesh_pool, h);
    navmesh_init_slot(navmesh, h, uuid, false);
    if (name && name[0] != '\0') {
        navmesh->name = tgfx_intern_string(name);
    }

    if (!tc_resource_map_add(g_uuid_to_index, navmesh->uuid, navmesh_pack_index(h.index))) {
        tc_log(TC_LOG_ERROR, "tc_navmesh_declare: failed to add to uuid map");
        tc_pool_free_slot(&g_navmesh_pool, h);
        return tc_navmesh_handle_invalid();
    }
    return h;
}

tc_navmesh* tc_navmesh_get(tc_navmesh_handle h) {
    if (!g_initialized) return NULL;
    return (tc_navmesh*)tc_pool_get(&g_navmesh_pool, h);
}

bool tc_navmesh_is_valid(tc_navmesh_handle h) {
    return g_initialized && tc_pool_is_valid(&g_navmesh_pool, h);
}

bool tc_navmesh_destroy(tc_navmesh_handle h) {
    if (!g_initialized) return false;
    tc_navmesh* navmesh = tc_navmesh_get(h);
    if (!navmesh) return false;
    tc_resource_map_remove(g_uuid_to_index, navmesh->uuid);
    navmesh_free_data(navmesh);
    return tc_pool_free_slot(&g_navmesh_pool, h);
}

bool tc_navmesh_contains(const char* uuid) {
    return g_initialized && uuid && tc_resource_map_contains(g_uuid_to_index, uuid);
}

size_t tc_navmesh_count(void) {
    return g_initialized ? tc_pool_count(&g_navmesh_pool) : 0;
}

void tc_navmesh_set_load_callback(tc_navmesh_handle h, tc_navmesh_load_fn callback, void* user_data) {
    tc_navmesh* navmesh = tc_navmesh_get(h);
    if (!navmesh) return;
    navmesh->load_callback = callback;
    navmesh->load_user_data = user_data;
}

bool tc_navmesh_is_loaded(tc_navmesh_handle h) {
    tc_navmesh* navmesh = tc_navmesh_get(h);
    return navmesh && navmesh->is_loaded != 0;
}

bool tc_navmesh_ensure_loaded(tc_navmesh_handle h) {
    tc_navmesh* navmesh = tc_navmesh_get(h);
    if (!navmesh) return false;
    if (navmesh->is_loaded) return true;
    if (!navmesh->load_callback) return false;
    bool success = navmesh->load_callback(navmesh, navmesh->load_user_data);
    if (success) {
        navmesh->is_loaded = 1;
    }
    return success;
}

bool tc_navmesh_set_metadata(tc_navmesh* navmesh, const char* name, const char* agent_type, const char* coordinate_system) {
    if (!navmesh) return false;
    if (name && name[0] != '\0') navmesh->name = tgfx_intern_string(name);
    navmesh->agent_type = (agent_type && agent_type[0] != '\0') ? tgfx_intern_string(agent_type) : NULL;
    navmesh->coordinate_system = (coordinate_system && coordinate_system[0] != '\0') ? tgfx_intern_string(coordinate_system) : NULL;
    navmesh_bump_version(navmesh);
    return true;
}

void tc_navmesh_clear_tiles(tc_navmesh* navmesh) {
    if (!navmesh) return;
    navmesh_free_data(navmesh);
    navmesh_bump_version(navmesh);
}

bool tc_navmesh_set_tiles(tc_navmesh* navmesh, const tc_navmesh_tile* tiles, size_t tile_count) {
    if (!navmesh) return false;
    tc_navmesh_tile* new_tiles = NULL;
    if (tile_count > 0) {
        new_tiles = (tc_navmesh_tile*)calloc(tile_count, sizeof(tc_navmesh_tile));
        if (!new_tiles) return false;
        for (size_t i = 0; i < tile_count; ++i) {
            new_tiles[i].x = tiles[i].x;
            new_tiles[i].y = tiles[i].y;
            new_tiles[i].layer = tiles[i].layer;
            new_tiles[i].data_size = tiles[i].data_size;
            if (tiles[i].data_size > 0) {
                new_tiles[i].data = (unsigned char*)malloc(tiles[i].data_size);
                if (!new_tiles[i].data) {
                    for (size_t j = 0; j < i; ++j) free(new_tiles[j].data);
                    free(new_tiles);
                    return false;
                }
                memcpy(new_tiles[i].data, tiles[i].data, tiles[i].data_size);
            }
        }
    }

    navmesh_free_data(navmesh);
    navmesh->tiles = new_tiles;
    navmesh->tile_count = tile_count;
    navmesh->is_loaded = 1;
    navmesh_bump_version(navmesh);
    return true;
}

void tc_navmesh_add_ref(tc_navmesh* navmesh) {
    if (navmesh) navmesh->ref_count++;
}

bool tc_navmesh_release(tc_navmesh* navmesh) {
    if (!navmesh || navmesh->ref_count == 0) return false;
    navmesh->ref_count--;
    return navmesh->ref_count == 0;
}

typedef struct {
    tc_navmesh_iter_fn callback;
    void* user_data;
} navmesh_iter_ctx;

static bool navmesh_iter_adapter(uint32_t index, void* item, void* ctx_ptr) {
    navmesh_iter_ctx* ctx = (navmesh_iter_ctx*)ctx_ptr;
    tc_navmesh_handle h;
    h.index = index;
    h.generation = g_navmesh_pool.generations[index];
    return ctx->callback(h, (tc_navmesh*)item, ctx->user_data);
}

void tc_navmesh_foreach(tc_navmesh_iter_fn callback, void* user_data) {
    if (!g_initialized || !callback) return;
    navmesh_iter_ctx ctx = { callback, user_data };
    tc_pool_foreach(&g_navmesh_pool, navmesh_iter_adapter, &ctx);
}

typedef struct {
    tc_navmesh_info* infos;
    size_t count;
} navmesh_info_ctx;

static bool collect_navmesh_info(tc_navmesh_handle h, tc_navmesh* navmesh, void* user_data) {
    navmesh_info_ctx* ctx = (navmesh_info_ctx*)user_data;
    tc_navmesh_info* info = &ctx->infos[ctx->count++];
    info->handle = h;
    strncpy(info->uuid, navmesh->uuid, sizeof(info->uuid) - 1);
    info->uuid[sizeof(info->uuid) - 1] = '\0';
    info->name = navmesh->name;
    info->agent_type = navmesh->agent_type;
    info->ref_count = navmesh->ref_count;
    info->version = navmesh->version;
    info->tile_count = navmesh->tile_count;
    info->memory_bytes = 0;
    for (size_t i = 0; i < navmesh->tile_count; ++i) {
        info->memory_bytes += navmesh->tiles[i].data_size;
    }
    info->is_loaded = navmesh->is_loaded;
    info->has_load_callback = navmesh->load_callback != NULL;
    return true;
}

tc_navmesh_info* tc_navmesh_get_all_info(size_t* count) {
    if (!count) return NULL;
    *count = 0;
    if (!g_initialized) return NULL;
    size_t navmesh_count = tc_pool_count(&g_navmesh_pool);
    if (navmesh_count == 0) return NULL;
    tc_navmesh_info* infos = (tc_navmesh_info*)calloc(navmesh_count, sizeof(tc_navmesh_info));
    if (!infos) return NULL;
    navmesh_info_ctx ctx = { infos, 0 };
    tc_navmesh_foreach(collect_navmesh_info, &ctx);
    *count = ctx.count;
    return infos;
}
