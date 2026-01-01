// tc_mesh_registry.h - Global mesh storage by UUID
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
// Mesh operations
// ============================================================================

// Add a new mesh with given UUID (or auto-generate if NULL)
// Returns pointer to mesh, or NULL on failure (including if UUID exists)
TC_API tc_mesh* tc_mesh_add(const char* uuid);

// Get mesh by UUID, returns NULL if not found
TC_API tc_mesh* tc_mesh_get(const char* uuid);

// Get mesh by name, returns NULL if not found
TC_API tc_mesh* tc_mesh_get_by_name(const char* name);

// Get existing mesh or create new one if not found
// If created, ref_count is 1. If existing, ref_count is incremented.
// IMPORTANT: After creating a new mesh, set mesh->name for debugging!
TC_API tc_mesh* tc_mesh_get_or_create(const char* uuid);

// Remove mesh by UUID, returns true if removed
TC_API bool tc_mesh_remove(const char* uuid);

// Check if mesh exists
TC_API bool tc_mesh_contains(const char* uuid);

// Get number of meshes
TC_API size_t tc_mesh_count(void);

// ============================================================================
// Iteration
// ============================================================================

// Mesh info for debugging/inspection
typedef struct tc_mesh_info {
    char uuid[40];
    const char* name;
    uint32_t ref_count;
    uint32_t version;
    size_t vertex_count;
    size_t index_count;
    size_t stride;
    size_t memory_bytes;  // vertices + indices
} tc_mesh_info;

// Iterator callback: return true to continue, false to stop
typedef bool (*tc_mesh_iter_fn)(const tc_mesh* mesh, void* user_data);

// Iterate over all meshes
TC_API void tc_mesh_foreach(tc_mesh_iter_fn callback, void* user_data);

// Get info for all meshes (caller must free() returned array)
// Returns NULL if no meshes, sets *count to number of entries
TC_API tc_mesh_info* tc_mesh_get_all_info(size_t* count);

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
// name is optional (can be NULL)
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

#ifdef __cplusplus
}
#endif
