// tc_shader_registry.h - Global shader storage with pool + hash table and variant support
#pragma once

#include "tc_shader.h"

#ifdef __cplusplus
extern "C" {
#endif

// ============================================================================
// Lifecycle (called from tc_init/tc_shutdown)
// ============================================================================

TC_API void tc_shader_init(void);
TC_API void tc_shader_shutdown(void);

// ============================================================================
// Shader operations (handle-based API)
// ============================================================================

// Create a new shader with given UUID (or auto-generate if NULL)
// Returns handle to shader, or tc_shader_handle_invalid() on failure
TC_API tc_shader_handle tc_shader_create(const char* uuid);

// Find shader by UUID, returns tc_shader_handle_invalid() if not found
TC_API tc_shader_handle tc_shader_find(const char* uuid);

// Find shader by source hash, returns tc_shader_handle_invalid() if not found
TC_API tc_shader_handle tc_shader_find_by_hash(const char* source_hash);

// Find shader by name, returns tc_shader_handle_invalid() if not found
TC_API tc_shader_handle tc_shader_find_by_name(const char* name);

// Get existing shader or create new one if not found
TC_API tc_shader_handle tc_shader_get_or_create(const char* uuid);

// Get shader data by handle (returns NULL if handle is invalid/stale)
TC_API tc_shader* tc_shader_get(tc_shader_handle h);

// Check if handle is valid (not stale, points to existing shader)
TC_API bool tc_shader_is_valid(tc_shader_handle h);

// Destroy shader by handle, returns true if destroyed
TC_API bool tc_shader_destroy(tc_shader_handle h);

// Check if shader exists by UUID
TC_API bool tc_shader_contains(const char* uuid);

// Get number of shaders
TC_API size_t tc_shader_count(void);

// ============================================================================
// Shader source operations
// ============================================================================

// Set shader sources (copies strings, updates hash, increments version)
TC_API bool tc_shader_set_sources(
    tc_shader* shader,
    const char* vertex_source,
    const char* fragment_source,
    const char* geometry_source,  // may be NULL
    const char* name,             // may be NULL
    const char* source_path       // may be NULL
);

// Create shader from sources (convenience function)
// Returns handle to new or existing shader (if hash matches)
TC_API tc_shader_handle tc_shader_from_sources(
    const char* vertex_source,
    const char* fragment_source,
    const char* geometry_source,  // may be NULL
    const char* name,             // may be NULL
    const char* source_path       // may be NULL
);

// ============================================================================
// Variant support (registry only stores relationship, doesn't create variants)
// ============================================================================

// Set variant metadata on a shader (called by Python after creating variant)
TC_API void tc_shader_set_variant_info(
    tc_shader* shader,
    tc_shader_handle original,
    tc_shader_variant_op op
);

// Check if variant needs recompilation (original version changed)
// Returns true if original.version != variant.original_version
TC_API bool tc_shader_variant_is_stale(tc_shader_handle variant);

// ============================================================================
// Shader info for debugging/inspection
// ============================================================================

typedef struct tc_shader_info {
    tc_shader_handle handle;
    char uuid[40];
    char source_hash[TC_SHADER_HASH_LEN];
    const char* name;
    const char* source_path;
    uint32_t ref_count;
    uint32_t version;
    size_t source_size;     // total source bytes
    uint8_t is_variant;
    uint8_t variant_op;
    uint8_t has_geometry;
    uint8_t _pad;
} tc_shader_info;

// Get info for all shaders (caller must free() returned array)
// Returns NULL if no shaders, sets *count to number of entries
TC_API tc_shader_info* tc_shader_get_all_info(size_t* count);

// ============================================================================
// Iteration
// ============================================================================

// Iterator callback: receives handle, shader pointer, user_data
// Return true to continue, false to stop
typedef bool (*tc_shader_iter_fn)(tc_shader_handle h, tc_shader* shader, void* user_data);

// Iterate over all shaders
TC_API void tc_shader_foreach(tc_shader_iter_fn callback, void* user_data);

// ============================================================================
// Utility
// ============================================================================

// Bump version manually (e.g., after modifying sources in-place)
static inline void tc_shader_bump_version(tc_shader* shader) {
    if (shader) shader->version++;
}

#ifdef __cplusplus
}
#endif
