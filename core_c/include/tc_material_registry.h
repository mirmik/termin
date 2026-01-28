// tc_material_registry.h - Global material storage with pool + hash table
#pragma once

#include "tc_material.h"

#ifdef __cplusplus
extern "C" {
#endif

// ============================================================================
// Lifecycle (called from tc_init/tc_shutdown)
// ============================================================================

TC_API void tc_material_init(void);
TC_API void tc_material_shutdown(void);

// ============================================================================
// Material operations (handle-based API)
// ============================================================================

// Create a new material with given UUID (or auto-generate if NULL) and name (required)
// Returns handle to material, or tc_material_handle_invalid() on failure
TC_API tc_material_handle tc_material_create(const char* uuid, const char* name);

// Find material by UUID, returns tc_material_handle_invalid() if not found
TC_API tc_material_handle tc_material_find(const char* uuid);

// Find material by name, returns tc_material_handle_invalid() if not found
TC_API tc_material_handle tc_material_find_by_name(const char* name);

// Get existing material or create new one if not found (name required for creation)
TC_API tc_material_handle tc_material_get_or_create(const char* uuid, const char* name);

// Get material data by handle (returns NULL if handle is invalid/stale)
TC_API tc_material* tc_material_get(tc_material_handle h);

// Get material UUID (returns NULL if invalid)
static inline const char* tc_material_uuid(tc_material_handle h) {
    tc_material* m = tc_material_get(h);
    return m ? m->header.uuid : NULL;
}

// Get material name (returns NULL if invalid or no name)
static inline const char* tc_material_name(tc_material_handle h) {
    tc_material* m = tc_material_get(h);
    return m ? m->header.name : NULL;
}

// Check if handle is valid (not stale, points to existing material)
TC_API bool tc_material_is_valid(tc_material_handle h);

// Destroy material by handle, returns true if destroyed
TC_API bool tc_material_destroy(tc_material_handle h);

// Check if material exists by UUID
TC_API bool tc_material_contains(const char* uuid);

// Get number of materials
TC_API size_t tc_material_count(void);

// ============================================================================
// Phase operations
// ============================================================================

// Add a phase to material, returns pointer to new phase or NULL on failure
TC_API tc_material_phase* tc_material_add_phase(
    tc_material* mat,
    tc_shader_handle shader,
    const char* phase_mark,
    int priority
);

// Remove phase by index
TC_API bool tc_material_remove_phase(tc_material* mat, size_t index);

// Get phases matching a mark (returns count, fills out_phases up to max_count)
TC_API size_t tc_material_get_phases_for_mark(
    tc_material* mat,
    const char* mark,
    tc_material_phase** out_phases,
    size_t max_count
);

// ============================================================================
// Material info for debugging/inspection
// ============================================================================

typedef struct tc_material_info {
    tc_material_handle handle;
    char uuid[40];
    const char* name;
    uint32_t ref_count;
    uint32_t version;
    size_t phase_count;
    size_t texture_count;
} tc_material_info;

// Get info for all materials (caller must free() returned array)
// Returns NULL if no materials, sets *count to number of entries
TC_API tc_material_info* tc_material_get_all_info(size_t* count);

// ============================================================================
// Iteration
// ============================================================================

// Iterator callback: receives handle, material pointer, user_data
// Return true to continue, false to stop
typedef bool (*tc_material_iter_fn)(tc_material_handle h, tc_material* mat, void* user_data);

// Iterate over all materials
TC_API void tc_material_foreach(tc_material_iter_fn callback, void* user_data);

// ============================================================================
// Utility
// ============================================================================

// Bump version manually (e.g., after modifying material)
static inline void tc_material_bump_version(tc_material* mat) {
    if (mat) mat->header.version++;
}

// Copy material data (creates new material with copied phases)
TC_API tc_material_handle tc_material_copy(tc_material_handle src, const char* new_uuid);

#ifdef __cplusplus
}
#endif
