#pragma once

#include "termin/voxels/tc_voxel_grid.h"

#ifdef __cplusplus
extern "C" {
#endif

TERMIN_VOXELS_API void tc_voxel_grid_init(void);
TERMIN_VOXELS_API void tc_voxel_grid_shutdown(void);

TERMIN_VOXELS_API tc_voxel_grid_handle tc_voxel_grid_create(const char* uuid);
TERMIN_VOXELS_API tc_voxel_grid_handle tc_voxel_grid_find(const char* uuid);
TERMIN_VOXELS_API tc_voxel_grid_handle tc_voxel_grid_find_by_name(const char* name);
TERMIN_VOXELS_API tc_voxel_grid_handle tc_voxel_grid_get_or_create(const char* uuid);
TERMIN_VOXELS_API tc_voxel_grid_handle tc_voxel_grid_declare(const char* uuid, const char* name);
TERMIN_VOXELS_API tc_voxel_grid* tc_voxel_grid_get(tc_voxel_grid_handle h);
TERMIN_VOXELS_API bool tc_voxel_grid_is_valid(tc_voxel_grid_handle h);
TERMIN_VOXELS_API bool tc_voxel_grid_destroy(tc_voxel_grid_handle h);
TERMIN_VOXELS_API bool tc_voxel_grid_contains(const char* uuid);
TERMIN_VOXELS_API size_t tc_voxel_grid_count(void);

typedef struct tc_voxel_grid_info {
    tc_voxel_grid_handle handle;
    char uuid[TC_UUID_SIZE];
    const char* name;
    const char* source_path;
    uint32_t ref_count;
    uint32_t version;
    uint8_t is_loaded;
    uint8_t _pad[7];
} tc_voxel_grid_info;

TERMIN_VOXELS_API tc_voxel_grid_info* tc_voxel_grid_get_all_info(size_t* count);

TERMIN_VOXELS_API void tc_voxel_grid_set_load_callback(
    tc_voxel_grid_handle h,
    tc_voxel_grid_load_fn callback,
    void* user_data
);
TERMIN_VOXELS_API bool tc_voxel_grid_is_loaded(tc_voxel_grid_handle h);
TERMIN_VOXELS_API bool tc_voxel_grid_ensure_loaded(tc_voxel_grid_handle h);

TERMIN_VOXELS_API bool tc_voxel_grid_set_metadata(
    tc_voxel_grid* grid,
    const char* name,
    const char* source_path
);

static inline const char* tc_voxel_grid_uuid(tc_voxel_grid_handle h) {
    tc_voxel_grid* grid = tc_voxel_grid_get(h);
    return grid ? grid->uuid : NULL;
}

static inline const char* tc_voxel_grid_name(tc_voxel_grid_handle h) {
    tc_voxel_grid* grid = tc_voxel_grid_get(h);
    return grid ? grid->name : NULL;
}

#ifdef __cplusplus
}
#endif
