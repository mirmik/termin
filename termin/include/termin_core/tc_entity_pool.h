// tc_entity_pool.h - Entity pool with generational indices
#pragma once

#include <stdint.h>
#include <stdbool.h>
#include <stddef.h>

// DLL export/import macros for Windows
#ifdef _WIN32
    #ifdef ENTITY_LIB_EXPORTS
        #define TC_POOL_API __declspec(dllexport)
    #else
        #define TC_POOL_API __declspec(dllimport)
    #endif
#else
    #define TC_POOL_API
#endif

#ifdef __cplusplus
extern "C" {
#endif

// ============================================================================
// EntityId - generational index
// ============================================================================

#ifndef TC_ENTITY_ID_DEFINED
#define TC_ENTITY_ID_DEFINED
typedef struct {
    uint32_t index;
    uint32_t generation;
} tc_entity_id;
#endif

#ifdef __cplusplus
    #define TC_ENTITY_ID_INVALID (tc_entity_id{0xFFFFFFFF, 0})
#else
    #define TC_ENTITY_ID_INVALID ((tc_entity_id){0xFFFFFFFF, 0})
#endif

static inline bool tc_entity_id_valid(tc_entity_id id) {
    return id.index != 0xFFFFFFFF;
}

static inline bool tc_entity_id_eq(tc_entity_id a, tc_entity_id b) {
    return a.index == b.index && a.generation == b.generation;
}

// ============================================================================
// Forward declarations
// ============================================================================

typedef struct tc_entity_pool tc_entity_pool;
typedef struct tc_component tc_component;
typedef struct tc_scene tc_scene;

// ============================================================================
// Pool lifecycle
// ============================================================================

TC_POOL_API tc_entity_pool* tc_entity_pool_create(size_t initial_capacity);
TC_POOL_API void tc_entity_pool_destroy(tc_entity_pool* pool);

// Scene association (for auto-registration of components)
TC_POOL_API void tc_entity_pool_set_scene(tc_entity_pool* pool, tc_scene* scene);
TC_POOL_API tc_scene* tc_entity_pool_get_scene(tc_entity_pool* pool);

// ============================================================================
// Entity allocation
// ============================================================================

TC_POOL_API tc_entity_id tc_entity_pool_alloc(tc_entity_pool* pool, const char* name);
TC_POOL_API tc_entity_id tc_entity_pool_alloc_with_uuid(tc_entity_pool* pool, const char* name, const char* uuid);
TC_POOL_API void tc_entity_pool_free(tc_entity_pool* pool, tc_entity_id id);
TC_POOL_API bool tc_entity_pool_alive(const tc_entity_pool* pool, tc_entity_id id);

TC_POOL_API size_t tc_entity_pool_count(const tc_entity_pool* pool);
TC_POOL_API size_t tc_entity_pool_capacity(const tc_entity_pool* pool);

// ============================================================================
// Entity data access
// ============================================================================

// Identity
TC_POOL_API const char* tc_entity_pool_name(const tc_entity_pool* pool, tc_entity_id id);
TC_POOL_API void tc_entity_pool_set_name(tc_entity_pool* pool, tc_entity_id id, const char* name);

TC_POOL_API const char* tc_entity_pool_uuid(const tc_entity_pool* pool, tc_entity_id id);
TC_POOL_API void tc_entity_pool_set_uuid(tc_entity_pool* pool, tc_entity_id id, const char* uuid);
TC_POOL_API uint64_t tc_entity_pool_runtime_id(const tc_entity_pool* pool, tc_entity_id id);

// Flags (hot data)
TC_POOL_API bool tc_entity_pool_visible(const tc_entity_pool* pool, tc_entity_id id);
TC_POOL_API void tc_entity_pool_set_visible(tc_entity_pool* pool, tc_entity_id id, bool v);

TC_POOL_API bool tc_entity_pool_enabled(const tc_entity_pool* pool, tc_entity_id id);
TC_POOL_API void tc_entity_pool_set_enabled(tc_entity_pool* pool, tc_entity_id id, bool v);

TC_POOL_API bool tc_entity_pool_pickable(const tc_entity_pool* pool, tc_entity_id id);
TC_POOL_API void tc_entity_pool_set_pickable(tc_entity_pool* pool, tc_entity_id id, bool v);

TC_POOL_API bool tc_entity_pool_selectable(const tc_entity_pool* pool, tc_entity_id id);
TC_POOL_API void tc_entity_pool_set_selectable(tc_entity_pool* pool, tc_entity_id id, bool v);

TC_POOL_API bool tc_entity_pool_serializable(const tc_entity_pool* pool, tc_entity_id id);
TC_POOL_API void tc_entity_pool_set_serializable(tc_entity_pool* pool, tc_entity_id id, bool v);

TC_POOL_API int tc_entity_pool_priority(const tc_entity_pool* pool, tc_entity_id id);
TC_POOL_API void tc_entity_pool_set_priority(tc_entity_pool* pool, tc_entity_id id, int v);

TC_POOL_API uint64_t tc_entity_pool_layer(const tc_entity_pool* pool, tc_entity_id id);
TC_POOL_API void tc_entity_pool_set_layer(tc_entity_pool* pool, tc_entity_id id, uint64_t v);

TC_POOL_API uint64_t tc_entity_pool_flags(const tc_entity_pool* pool, tc_entity_id id);
TC_POOL_API void tc_entity_pool_set_flags(tc_entity_pool* pool, tc_entity_id id, uint64_t v);

TC_POOL_API uint32_t tc_entity_pool_pick_id(const tc_entity_pool* pool, tc_entity_id id);

// Fast O(1) lookup by pick_id or uuid (uses internal hash maps)
TC_POOL_API tc_entity_id tc_entity_pool_find_by_pick_id(const tc_entity_pool* pool, uint32_t pick_id);
TC_POOL_API tc_entity_id tc_entity_pool_find_by_uuid(const tc_entity_pool* pool, const char* uuid);

// ============================================================================
// Transform data
// ============================================================================

// Local pose (position, rotation, scale)
TC_POOL_API void tc_entity_pool_get_local_position(const tc_entity_pool* pool, tc_entity_id id, double* xyz);
TC_POOL_API void tc_entity_pool_set_local_position(tc_entity_pool* pool, tc_entity_id id, const double* xyz);

TC_POOL_API void tc_entity_pool_get_local_rotation(const tc_entity_pool* pool, tc_entity_id id, double* xyzw);
TC_POOL_API void tc_entity_pool_set_local_rotation(tc_entity_pool* pool, tc_entity_id id, const double* xyzw);

TC_POOL_API void tc_entity_pool_get_local_scale(const tc_entity_pool* pool, tc_entity_id id, double* xyz);
TC_POOL_API void tc_entity_pool_set_local_scale(tc_entity_pool* pool, tc_entity_id id, const double* xyz);

TC_POOL_API void tc_entity_pool_get_local_pose(
    const tc_entity_pool* pool, tc_entity_id id,
    double* position, double* rotation, double* scale
);

TC_POOL_API void tc_entity_pool_set_local_pose(
    tc_entity_pool* pool, tc_entity_id id,
    const double* position, const double* rotation, const double* scale
);

// Global(World) pose (cached, auto-updated)
TC_POOL_API void tc_entity_pool_get_global_position(const tc_entity_pool* pool, tc_entity_id id, double* xyz);
TC_POOL_API void tc_entity_pool_get_global_rotation(const tc_entity_pool* pool, tc_entity_id id, double* xyzw);
TC_POOL_API void tc_entity_pool_get_global_scale(const tc_entity_pool* pool, tc_entity_id id, double* xyz);

TC_POOL_API void tc_entity_pool_get_global_pose(
    const tc_entity_pool* pool, tc_entity_id id,
    double* position, double* rotation, double* scale
);

// World matrix (col-major 4x4)
TC_POOL_API void tc_entity_pool_get_world_matrix(const tc_entity_pool* pool, tc_entity_id id, double* m16);

// Mark transform dirty (will be recalculated)
TC_POOL_API void tc_entity_pool_mark_dirty(tc_entity_pool* pool, tc_entity_id id);

// Update all dirty world transforms
TC_POOL_API void tc_entity_pool_update_transforms(tc_entity_pool* pool);

// ============================================================================
// Hierarchy
// ============================================================================

TC_POOL_API tc_entity_id tc_entity_pool_parent(const tc_entity_pool* pool, tc_entity_id id);
TC_POOL_API void tc_entity_pool_set_parent(tc_entity_pool* pool, tc_entity_id id, tc_entity_id parent);

TC_POOL_API size_t tc_entity_pool_children_count(const tc_entity_pool* pool, tc_entity_id id);
TC_POOL_API tc_entity_id tc_entity_pool_child_at(const tc_entity_pool* pool, tc_entity_id id, size_t index);

// ============================================================================
// Components
// ============================================================================

TC_POOL_API void tc_entity_pool_add_component(tc_entity_pool* pool, tc_entity_id id, tc_component* c);
TC_POOL_API void tc_entity_pool_remove_component(tc_entity_pool* pool, tc_entity_id id, tc_component* c);
TC_POOL_API size_t tc_entity_pool_component_count(const tc_entity_pool* pool, tc_entity_id id);
TC_POOL_API tc_component* tc_entity_pool_component_at(const tc_entity_pool* pool, tc_entity_id id, size_t index);

// ============================================================================
// Migration between pools
// ============================================================================

// Migrate entity from src_pool to dst_pool.
// Copies all data (transform, flags, components, children).
// Old entity in src_pool is freed (invalidated by generation bump).
// Returns new entity_id in dst_pool, or TC_ENTITY_ID_INVALID on failure.
// Note: parent links are NOT migrated (entity becomes root in dst_pool).
// Note: children are recursively migrated to dst_pool.
TC_POOL_API tc_entity_id tc_entity_pool_migrate(
    tc_entity_pool* src_pool, tc_entity_id src_id,
    tc_entity_pool* dst_pool);

// ============================================================================
// Iteration
// ============================================================================

// Iterator callback: return true to continue, false to stop
typedef bool (*tc_entity_iter_fn)(tc_entity_pool* pool, tc_entity_id id, void* user_data);

// Iterate over all alive entities
TC_POOL_API void tc_entity_pool_foreach(tc_entity_pool* pool, tc_entity_iter_fn callback, void* user_data);

#ifdef __cplusplus
}
#endif
