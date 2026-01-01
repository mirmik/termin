// tc_texture_registry.h - Global texture storage by UUID
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
// Texture operations
// ============================================================================

// Add a new texture with given UUID (or auto-generate if NULL)
TC_API tc_texture* tc_texture_add(const char* uuid);

// Get texture by UUID, returns NULL if not found
TC_API tc_texture* tc_texture_get(const char* uuid);

// Get texture by name, returns NULL if not found
TC_API tc_texture* tc_texture_get_by_name(const char* name);

// Get existing texture or create new one if not found
TC_API tc_texture* tc_texture_get_or_create(const char* uuid);

// Remove texture by UUID, returns true if removed
TC_API bool tc_texture_remove(const char* uuid);

// Check if texture exists
TC_API bool tc_texture_contains(const char* uuid);

// Get number of textures
TC_API size_t tc_texture_count(void);

// ============================================================================
// Iteration
// ============================================================================

// Texture info for debugging/inspection
typedef struct tc_texture_info {
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

// Iterator callback: return true to continue, false to stop
typedef bool (*tc_texture_iter_fn)(const tc_texture* tex, void* user_data);

// Iterate over all textures
TC_API void tc_texture_foreach(tc_texture_iter_fn callback, void* user_data);

// Get info for all textures (caller must free() returned array)
TC_API tc_texture_info* tc_texture_get_all_info(size_t* count);

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

#ifdef __cplusplus
}
#endif
