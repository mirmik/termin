// tc_navmesh_registry.h - Global navmesh storage with pool + hash table
#pragma once

#include "termin/navmesh/tc_navmesh.h"

#ifdef __cplusplus
extern "C" {
#endif

TERMIN_NAVMESH_API void tc_navmesh_init(void);
TERMIN_NAVMESH_API void tc_navmesh_shutdown(void);

TERMIN_NAVMESH_API tc_navmesh_handle tc_navmesh_create(const char* uuid);
TERMIN_NAVMESH_API tc_navmesh_handle tc_navmesh_find(const char* uuid);
TERMIN_NAVMESH_API tc_navmesh_handle tc_navmesh_find_by_name(const char* name);
TERMIN_NAVMESH_API tc_navmesh_handle tc_navmesh_get_or_create(const char* uuid);
TERMIN_NAVMESH_API tc_navmesh_handle tc_navmesh_declare(const char* uuid, const char* name);
TERMIN_NAVMESH_API tc_navmesh* tc_navmesh_get(tc_navmesh_handle h);
TERMIN_NAVMESH_API bool tc_navmesh_is_valid(tc_navmesh_handle h);
TERMIN_NAVMESH_API bool tc_navmesh_destroy(tc_navmesh_handle h);
TERMIN_NAVMESH_API bool tc_navmesh_contains(const char* uuid);
TERMIN_NAVMESH_API size_t tc_navmesh_count(void);

TERMIN_NAVMESH_API void tc_navmesh_set_load_callback(tc_navmesh_handle h, tc_navmesh_load_fn callback, void* user_data);
TERMIN_NAVMESH_API bool tc_navmesh_is_loaded(tc_navmesh_handle h);
TERMIN_NAVMESH_API bool tc_navmesh_ensure_loaded(tc_navmesh_handle h);

TERMIN_NAVMESH_API bool tc_navmesh_set_metadata(
    tc_navmesh* navmesh,
    const char* name,
    const char* agent_type,
    const char* coordinate_system
);
TERMIN_NAVMESH_API bool tc_navmesh_set_tiles(
    tc_navmesh* navmesh,
    const tc_navmesh_tile* tiles,
    size_t tile_count
);
TERMIN_NAVMESH_API void tc_navmesh_clear_tiles(tc_navmesh* navmesh);

typedef struct tc_navmesh_info {
    tc_navmesh_handle handle;
    char uuid[TC_UUID_SIZE];
    const char* name;
    const char* agent_type;
    uint32_t ref_count;
    uint32_t version;
    size_t tile_count;
    size_t memory_bytes;
    uint8_t is_loaded;
    uint8_t has_load_callback;
    uint8_t _pad[6];
} tc_navmesh_info;

TERMIN_NAVMESH_API tc_navmesh_info* tc_navmesh_get_all_info(size_t* count);

typedef bool (*tc_navmesh_iter_fn)(tc_navmesh_handle h, tc_navmesh* navmesh, void* user_data);
TERMIN_NAVMESH_API void tc_navmesh_foreach(tc_navmesh_iter_fn callback, void* user_data);

static inline const char* tc_navmesh_uuid(tc_navmesh_handle h) {
    tc_navmesh* navmesh = tc_navmesh_get(h);
    return navmesh ? navmesh->uuid : NULL;
}

static inline const char* tc_navmesh_name(tc_navmesh_handle h) {
    tc_navmesh* navmesh = tc_navmesh_get(h);
    return navmesh ? navmesh->name : NULL;
}

#ifdef __cplusplus
}
#endif
