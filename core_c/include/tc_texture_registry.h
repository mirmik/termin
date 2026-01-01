// tc_texture_registry.h - Global texture storage with pool + hash table
#pragma once

#include "tc_texture.h"

#ifdef __cplusplus
extern "C" {
#endif

// ============================================================================
// Lifecycle (called from tc_init/tc_shutdown)
// ============================================================================

TC_API void tc_texture_init(void);
TC_API void tc_texture_shutdown(void);

// ============================================================================
// Texture operations (handle-based API)
// ============================================================================

// Create a new texture with given UUID (or auto-generate if NULL)
TC_API tc_texture_handle tc_texture_create(const char* uuid);

// Find texture by UUID
TC_API tc_texture_handle tc_texture_find(const char* uuid);

// Find texture by name
TC_API tc_texture_handle tc_texture_find_by_name(const char* name);

// Get existing texture or create new one if not found
TC_API tc_texture_handle tc_texture_get_or_create(const char* uuid);

// Get texture data by handle (returns NULL if handle is invalid/stale)
TC_API tc_texture* tc_texture_get(tc_texture_handle h);

// Check if handle is valid
TC_API bool tc_texture_is_valid(tc_texture_handle h);

// Destroy texture by handle
TC_API bool tc_texture_destroy(tc_texture_handle h);

// Check if texture exists by UUID
TC_API bool tc_texture_contains(const char* uuid);

// Get number of textures
TC_API size_t tc_texture_count(void);

// ============================================================================
// Texture info for debugging/inspection
// ============================================================================

typedef struct tc_texture_info {
    tc_texture_handle handle;
    char uuid[40];
    const char* name;
    const char* source_path;
    uint32_t ref_count;
    uint32_t version;
    uint32_t width;
    uint32_t height;
    uint8_t channels;
    uint8_t format;
    size_t memory_bytes;
} tc_texture_info;

// Get info for all textures (caller must free() returned array)
TC_API tc_texture_info* tc_texture_get_all_info(size_t* count);

// ============================================================================
// Iteration
// ============================================================================

// Iterator callback
typedef bool (*tc_texture_iter_fn)(tc_texture_handle h, tc_texture* tex, void* user_data);

// Iterate over all textures
TC_API void tc_texture_foreach(tc_texture_iter_fn callback, void* user_data);

// ============================================================================
// Texture data helpers
// ============================================================================

// Set texture data (copies data, increments version)
TC_API bool tc_texture_set_data(
    tc_texture* tex,
    const void* data,
    uint32_t width,
    uint32_t height,
    uint8_t channels,
    const char* name,
    const char* source_path
);

// Set transform flags
TC_API void tc_texture_set_transforms(
    tc_texture* tex,
    bool flip_x,
    bool flip_y,
    bool transpose
);

// Bump version manually
static inline void tc_texture_bump_version(tc_texture* tex) {
    if (tex) tex->version++;
}

// ============================================================================
// Legacy API (deprecated)
// ============================================================================

TC_API tc_texture* tc_texture_add(const char* uuid);
TC_API bool tc_texture_remove(const char* uuid);

#ifdef __cplusplus
}
#endif
