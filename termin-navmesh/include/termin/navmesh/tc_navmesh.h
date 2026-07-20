// tc_navmesh.h - Detour-backed navigation mesh runtime resource
#pragma once

#include <tcbase/tc_binding_types.h>
#include <tcbase/tc_uuid.h>
#include <stdint.h>
#include <stddef.h>
#include <stdbool.h>

#if defined(_WIN32)
  #if defined(TERMIN_NAVMESH_EXPORTS)
    #define TERMIN_NAVMESH_API __declspec(dllexport)
  #else
    #define TERMIN_NAVMESH_API __declspec(dllimport)
  #endif
#else
  #define TERMIN_NAVMESH_API __attribute__((visibility("default")))
#endif

#ifdef __cplusplus
extern "C" {
#endif

TC_DEFINE_HANDLE(tc_navmesh_handle)

typedef struct tc_navmesh tc_navmesh;
typedef bool (*tc_navmesh_load_fn)(tc_navmesh* navmesh, void* user_data);

typedef struct tc_navmesh_tile {
    int32_t x;
    int32_t y;
    int32_t layer;
    unsigned char* data;
    size_t data_size;
} tc_navmesh_tile;

struct tc_navmesh {
    char uuid[TC_UUID_SIZE];
    const char* name;
    const char* agent_type;
    const char* coordinate_system;
    uint32_t version;
    uint32_t ref_count;
    uint32_t pool_index;
    uint8_t is_loaded;
    uint8_t _pad[3];
    tc_navmesh_load_fn load_callback;
    void* load_user_data;
    tc_navmesh_tile* tiles;
    size_t tile_count;
};

TERMIN_NAVMESH_API void tc_navmesh_add_ref(tc_navmesh* navmesh);
TERMIN_NAVMESH_API bool tc_navmesh_release(tc_navmesh* navmesh);

#ifdef __cplusplus
}
#endif
