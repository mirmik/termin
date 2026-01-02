// tc_mesh_registry.h - Global mesh storage with pool + hash table
#pragma once

#include "tc_mesh.h"

#ifdef __cplusplus
extern "C" {
#endif

// ============================================================================
// Lifecycle (called from tc_init/tc_shutdown)
// ============================================================================

TC_API void tc_mesh_init(void);
TC_API void tc_mesh_shutdown(void);

// ============================================================================
// Mesh operations (handle-based API)
// ============================================================================

// Create a new mesh with given UUID (or auto-generate if NULL)
// Returns handle to mesh, or tc_mesh_handle_invalid() on failure
TC_API tc_mesh_handle tc_mesh_create(const char* uuid);

// Find mesh by UUID, returns tc_mesh_handle_invalid() if not found
TC_API tc_mesh_handle tc_mesh_find(const char* uuid);

// Find mesh by name, returns tc_mesh_handle_invalid() if not found
TC_API tc_mesh_handle tc_mesh_find_by_name(const char* name);

// Get existing mesh or create new one if not found
TC_API tc_mesh_handle tc_mesh_get_or_create(const char* uuid);

// Declare a mesh that will be loaded lazily (creates entry with is_loaded=false)
// Returns handle to mesh, or existing handle if already declared/created
TC_API tc_mesh_handle tc_mesh_declare(const char* uuid, const char* name);

// Set load callback for lazy loading
TC_API void tc_mesh_set_load_callback(
    tc_mesh_handle h,
    tc_mesh_load_fn callback,
    void* user_data
);

// Check if mesh data is loaded
TC_API bool tc_mesh_is_loaded(tc_mesh_handle h);

// Ensure mesh is loaded (triggers callback if not loaded)
// Returns true if mesh is now loaded, false if loading failed or no callback
TC_API bool tc_mesh_ensure_loaded(tc_mesh_handle h);

// Get mesh data by handle (returns NULL if handle is invalid/stale)
// Note: does NOT trigger lazy loading - use tc_mesh_ensure_loaded first
TC_API tc_mesh* tc_mesh_get(tc_mesh_handle h);

// Check if handle is valid (not stale, points to existing mesh)
TC_API bool tc_mesh_is_valid(tc_mesh_handle h);

// Destroy mesh by handle, returns true if destroyed
TC_API bool tc_mesh_destroy(tc_mesh_handle h);

// Check if mesh exists by UUID
TC_API bool tc_mesh_contains(const char* uuid);

// Get number of meshes
TC_API size_t tc_mesh_count(void);

// ============================================================================
// Mesh info for debugging/inspection
// ============================================================================

typedef struct tc_mesh_info {
    tc_mesh_handle handle;
    char uuid[40];
    const char* name;
    uint32_t ref_count;
    uint32_t version;
    size_t vertex_count;
    size_t index_count;
    size_t stride;
    size_t memory_bytes;
    uint8_t is_loaded;
    uint8_t has_load_callback;
    uint8_t _pad[6];
} tc_mesh_info;

// Get info for all meshes (caller must free() returned array)
// Returns NULL if no meshes, sets *count to number of entries
TC_API tc_mesh_info* tc_mesh_get_all_info(size_t* count);

// ============================================================================
// Iteration
// ============================================================================

// Iterator callback: receives handle, mesh pointer, user_data
// Return true to continue, false to stop
typedef bool (*tc_mesh_iter_fn)(tc_mesh_handle h, tc_mesh* mesh, void* user_data);

// Iterate over all meshes
TC_API void tc_mesh_foreach(tc_mesh_iter_fn callback, void* user_data);

// ============================================================================
// Mesh data helpers
// ============================================================================

// Set vertex data (copies data, increments version)
TC_API bool tc_mesh_set_vertices(
    tc_mesh* mesh,
    const void* data,
    size_t vertex_count,
    const tc_vertex_layout* layout
);

// Set index data (copies data, increments version)
TC_API bool tc_mesh_set_indices(
    tc_mesh* mesh,
    const uint32_t* data,
    size_t index_count
);

// Set both vertex and index data (copies data, increments version)
TC_API bool tc_mesh_set_data(
    tc_mesh* mesh,
    const void* vertices,
    size_t vertex_count,
    const tc_vertex_layout* layout,
    const uint32_t* indices,
    size_t index_count,
    const char* name
);

// Bump version manually (e.g., after modifying data in-place)
static inline void tc_mesh_bump_version(tc_mesh* mesh) {
    if (mesh) mesh->version++;
}

// ============================================================================
// Legacy API (deprecated - use handle-based API)
// ============================================================================

// Add mesh - returns pointer (deprecated, use tc_mesh_create)
TC_API tc_mesh* tc_mesh_add(const char* uuid);

// Remove mesh by UUID (deprecated, use tc_mesh_destroy)
TC_API bool tc_mesh_remove(const char* uuid);

#ifdef __cplusplus
}
#endif
