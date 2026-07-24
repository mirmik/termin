#pragma once

#include <tcbase/tc_binding_types.h>
#include <tcbase/tc_uuid.h>
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#if defined(_WIN32)
  #if defined(TERMIN_VOXELS_EXPORTS)
    #define TERMIN_VOXELS_API __declspec(dllexport)
  #else
    #define TERMIN_VOXELS_API __declspec(dllimport)
  #endif
#else
  #define TERMIN_VOXELS_API __attribute__((visibility("default")))
#endif

#ifdef __cplusplus
extern "C" {
#endif


TC_DEFINE_HANDLE(tc_voxel_grid_handle)

typedef struct tc_voxel_grid tc_voxel_grid;

struct tc_voxel_grid {
    char uuid[TC_UUID_SIZE];
    const char* name;
    const char* source_path;
    uint32_t version;
    uint32_t ref_count;
    uint32_t pool_index;
    uint8_t is_loaded;
    uint8_t _pad[3];
    void* native_payload;
};

TERMIN_VOXELS_API void tc_voxel_grid_add_ref(tc_voxel_grid* grid);
TERMIN_VOXELS_API bool tc_voxel_grid_release(tc_voxel_grid* grid);

#ifdef __cplusplus
}
#endif
