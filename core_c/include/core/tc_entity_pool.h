// tc_entity_pool.h - Entity pool with generational indices
#pragma once

#include <stdint.h>
#include <stdbool.h>
#include <stddef.h>

// DLL export/import macros for Windows
// TC_POOL_API is dllexport when building termin_core (TC_EXPORTS) or entity_lib (ENTITY_LIB_EXPORTS)
#ifdef _WIN32
    #if defined(TC_EXPORTS) || defined(ENTITY_LIB_EXPORTS)
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

// Include pool registry for tc_entity_pool_handle
#include "core/tc_entity_pool_registry.h"

// Include scene handle type
#include "core/tc_scene_pool.h"

// ============================================================================
// Entity Handle - unified handle combining pool + entity_id
// (inline functions are defined after tc_entity_pool_alive declaration)
// ============================================================================

#ifndef TC_ENTITY_HANDLE_DEFINED
#define TC_ENTITY_HANDLE_DEFINED
typedef struct {
    tc_entity_pool_handle pool;
    tc_entity_id id;
} tc_entity_handle;
#endif

#ifdef __cplusplus
    #define TC_ENTITY_HANDLE_INVALID (tc_entity_handle{TC_ENTITY_POOL_HANDLE_INVALID, TC_ENTITY_ID_INVALID})
#else
    #define TC_ENTITY_HANDLE_INVALID ((tc_entity_handle){TC_ENTITY_POOL_HANDLE_INVALID, TC_ENTITY_ID_INVALID})
#endif

// ============================================================================
// Pool lifecycle
// ============================================================================

TC_POOL_API tc_entity_pool* tc_entity_pool_create(size_t initial_capacity);
TC_POOL_API void tc_entity_pool_destroy(tc_entity_pool* pool);

// Scene association (for auto-registration of components)
TC_POOL_API void tc_entity_pool_set_scene(tc_entity_pool* pool, tc_scene_handle scene);
TC_POOL_API tc_scene_handle tc_entity_pool_get_scene(tc_entity_pool* pool);

// ============================================================================
// Entity allocation
// ============================================================================

TC_POOL_API tc_entity_id tc_entity_pool_alloc(tc_entity_pool* pool, const char* name);
TC_POOL_API tc_entity_id tc_entity_pool_alloc_with_uuid(tc_entity_pool* pool, const char* name, const char* uuid);
TC_POOL_API void tc_entity_pool_free(tc_entity_pool* pool, tc_entity_id id);
TC_POOL_API bool tc_entity_pool_alive(const tc_entity_pool* pool, tc_entity_id id);

// Entity handle inline functions (after tc_entity_pool_alive declaration)
static inline bool tc_entity_handle_valid(tc_entity_handle h) {
    tc_entity_pool* pool = tc_entity_pool_registry_get(h.pool);
    return pool && tc_entity_pool_alive(pool, h.id);
}

static inline bool tc_entity_handle_eq(tc_entity_handle a, tc_entity_handle b) {
    return tc_entity_pool_handle_eq(a.pool, b.pool) && tc_entity_id_eq(a.id, b.id);
}

static inline tc_entity_handle tc_entity_handle_make(tc_entity_pool_handle pool, tc_entity_id id) {
    tc_entity_handle h;
    h.pool = pool;
    h.id = id;
    return h;
}

TC_POOL_API size_t tc_entity_pool_count(const tc_entity_pool* pool);
TC_POOL_API size_t tc_entity_pool_capacity(const tc_entity_pool* pool);

// Returns the entity ID at the given slot index if alive, or INVALID if dead/out of range.
// Use with tc_entity_pool_capacity() for complete iteration without generation guessing.
TC_POOL_API tc_entity_id tc_entity_pool_id_at(const tc_entity_pool* pool, uint32_t index);

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

// ============================================================================
// Input Handler Iteration (for internal_entities dispatch)
// ============================================================================

// Callback type for component iteration (same as tc_scene.h)
typedef bool (*tc_component_iter_fn)(tc_component* c, void* user_data);

// Iterate input handler components in entity subtree (entity and all descendants)
// Calls callback for each enabled component with input_vtable set
TC_POOL_API void tc_entity_pool_foreach_input_handler_subtree(
    tc_entity_pool* pool,
    tc_entity_id root_id,
    tc_component_iter_fn callback,
    void* user_data
);

// Iterate input handler components in entity subtree (handle-based API)
static inline void tc_entity_foreach_input_handler_subtree(
    tc_entity_handle h,
    tc_component_iter_fn callback,
    void* user_data)
{
    tc_entity_pool* pool = tc_entity_pool_registry_get(h.pool);
    if (!pool) return;
    tc_entity_pool_foreach_input_handler_subtree(pool, h.id, callback, user_data);
}

// ============================================================================
// SoA Archetype Components
// ============================================================================

// Forward declarations (full definitions in tc_archetype.h)
typedef uint8_t tc_soa_type_id;
struct tc_soa_type_desc;

// Register a SoA component type with the pool's registry.
// Returns type id (0..63) or TC_SOA_TYPE_INVALID (0xFF) if full.
TC_POOL_API tc_soa_type_id tc_entity_pool_register_soa_type(tc_entity_pool* pool, const struct tc_soa_type_desc* desc);

// Add a SoA component to entity. Moves entity to a new archetype.
TC_POOL_API void tc_entity_pool_add_soa(tc_entity_pool* pool, tc_entity_id id, tc_soa_type_id type);

// Remove a SoA component from entity. Moves entity to a new archetype.
TC_POOL_API void tc_entity_pool_remove_soa(tc_entity_pool* pool, tc_entity_id id, tc_soa_type_id type);

// Check if entity has a SoA component.
TC_POOL_API bool tc_entity_pool_has_soa(const tc_entity_pool* pool, tc_entity_id id, tc_soa_type_id type);

// Get pointer to entity's SoA component data. Returns NULL if not present.
TC_POOL_API void* tc_entity_pool_get_soa(const tc_entity_pool* pool, tc_entity_id id, tc_soa_type_id type);

// Get SoA type mask for entity (bitmask of which SoA types are present).
TC_POOL_API uint64_t tc_entity_pool_soa_mask(const tc_entity_pool* pool, tc_entity_id id);

// ============================================================================
// Entity Handle API (unified access via tc_entity_handle)
// ============================================================================

// Create entity and return handle
static inline tc_entity_handle tc_entity_create(tc_entity_pool_handle pool_h, const char* name) {
    tc_entity_pool* pool = tc_entity_pool_registry_get(pool_h);
    if (!pool) return TC_ENTITY_HANDLE_INVALID;
    tc_entity_id id = tc_entity_pool_alloc(pool, name);
    return tc_entity_handle_make(pool_h, id);
}

static inline tc_entity_handle tc_entity_create_with_uuid(tc_entity_pool_handle pool_h, const char* name, const char* uuid) {
    tc_entity_pool* pool = tc_entity_pool_registry_get(pool_h);
    if (!pool) return TC_ENTITY_HANDLE_INVALID;
    tc_entity_id id = tc_entity_pool_alloc_with_uuid(pool, name, uuid);
    return tc_entity_handle_make(pool_h, id);
}

// Free entity
static inline void tc_entity_free(tc_entity_handle h) {
    tc_entity_pool* pool = tc_entity_pool_registry_get(h.pool);
    if (pool) tc_entity_pool_free(pool, h.id);
}

// Identity
static inline const char* tc_entity_name(tc_entity_handle h) {
    tc_entity_pool* pool = tc_entity_pool_registry_get(h.pool);
    return pool ? tc_entity_pool_name(pool, h.id) : "";
}

static inline void tc_entity_set_name(tc_entity_handle h, const char* name) {
    tc_entity_pool* pool = tc_entity_pool_registry_get(h.pool);
    if (pool) tc_entity_pool_set_name(pool, h.id, name);
}

static inline const char* tc_entity_uuid(tc_entity_handle h) {
    tc_entity_pool* pool = tc_entity_pool_registry_get(h.pool);
    return pool ? tc_entity_pool_uuid(pool, h.id) : "";
}

static inline void tc_entity_set_uuid(tc_entity_handle h, const char* uuid) {
    tc_entity_pool* pool = tc_entity_pool_registry_get(h.pool);
    if (pool) tc_entity_pool_set_uuid(pool, h.id, uuid);
}

// Flags
static inline bool tc_entity_visible(tc_entity_handle h) {
    tc_entity_pool* pool = tc_entity_pool_registry_get(h.pool);
    return pool ? tc_entity_pool_visible(pool, h.id) : false;
}

static inline void tc_entity_set_visible(tc_entity_handle h, bool v) {
    tc_entity_pool* pool = tc_entity_pool_registry_get(h.pool);
    if (pool) tc_entity_pool_set_visible(pool, h.id, v);
}

static inline bool tc_entity_enabled(tc_entity_handle h) {
    tc_entity_pool* pool = tc_entity_pool_registry_get(h.pool);
    return pool ? tc_entity_pool_enabled(pool, h.id) : false;
}

static inline void tc_entity_set_enabled(tc_entity_handle h, bool v) {
    tc_entity_pool* pool = tc_entity_pool_registry_get(h.pool);
    if (pool) tc_entity_pool_set_enabled(pool, h.id, v);
}

static inline bool tc_entity_pickable(tc_entity_handle h) {
    tc_entity_pool* pool = tc_entity_pool_registry_get(h.pool);
    return pool ? tc_entity_pool_pickable(pool, h.id) : false;
}

static inline void tc_entity_set_pickable(tc_entity_handle h, bool v) {
    tc_entity_pool* pool = tc_entity_pool_registry_get(h.pool);
    if (pool) tc_entity_pool_set_pickable(pool, h.id, v);
}

static inline bool tc_entity_selectable(tc_entity_handle h) {
    tc_entity_pool* pool = tc_entity_pool_registry_get(h.pool);
    return pool ? tc_entity_pool_selectable(pool, h.id) : false;
}

static inline void tc_entity_set_selectable(tc_entity_handle h, bool v) {
    tc_entity_pool* pool = tc_entity_pool_registry_get(h.pool);
    if (pool) tc_entity_pool_set_selectable(pool, h.id, v);
}

static inline bool tc_entity_serializable(tc_entity_handle h) {
    tc_entity_pool* pool = tc_entity_pool_registry_get(h.pool);
    return pool ? tc_entity_pool_serializable(pool, h.id) : false;
}

static inline void tc_entity_set_serializable(tc_entity_handle h, bool v) {
    tc_entity_pool* pool = tc_entity_pool_registry_get(h.pool);
    if (pool) tc_entity_pool_set_serializable(pool, h.id, v);
}

static inline int tc_entity_priority(tc_entity_handle h) {
    tc_entity_pool* pool = tc_entity_pool_registry_get(h.pool);
    return pool ? tc_entity_pool_priority(pool, h.id) : 0;
}

static inline void tc_entity_set_priority(tc_entity_handle h, int v) {
    tc_entity_pool* pool = tc_entity_pool_registry_get(h.pool);
    if (pool) tc_entity_pool_set_priority(pool, h.id, v);
}

static inline uint64_t tc_entity_layer(tc_entity_handle h) {
    tc_entity_pool* pool = tc_entity_pool_registry_get(h.pool);
    return pool ? tc_entity_pool_layer(pool, h.id) : 0;
}

static inline void tc_entity_set_layer(tc_entity_handle h, uint64_t v) {
    tc_entity_pool* pool = tc_entity_pool_registry_get(h.pool);
    if (pool) tc_entity_pool_set_layer(pool, h.id, v);
}

static inline uint64_t tc_entity_flags(tc_entity_handle h) {
    tc_entity_pool* pool = tc_entity_pool_registry_get(h.pool);
    return pool ? tc_entity_pool_flags(pool, h.id) : 0;
}

static inline void tc_entity_set_flags(tc_entity_handle h, uint64_t v) {
    tc_entity_pool* pool = tc_entity_pool_registry_get(h.pool);
    if (pool) tc_entity_pool_set_flags(pool, h.id, v);
}

// Transform
static inline void tc_entity_get_local_position(tc_entity_handle h, double* xyz) {
    tc_entity_pool* pool = tc_entity_pool_registry_get(h.pool);
    if (pool) tc_entity_pool_get_local_position(pool, h.id, xyz);
}

static inline void tc_entity_set_local_position(tc_entity_handle h, const double* xyz) {
    tc_entity_pool* pool = tc_entity_pool_registry_get(h.pool);
    if (pool) tc_entity_pool_set_local_position(pool, h.id, xyz);
}

static inline void tc_entity_get_local_rotation(tc_entity_handle h, double* xyzw) {
    tc_entity_pool* pool = tc_entity_pool_registry_get(h.pool);
    if (pool) tc_entity_pool_get_local_rotation(pool, h.id, xyzw);
}

static inline void tc_entity_set_local_rotation(tc_entity_handle h, const double* xyzw) {
    tc_entity_pool* pool = tc_entity_pool_registry_get(h.pool);
    if (pool) tc_entity_pool_set_local_rotation(pool, h.id, xyzw);
}

static inline void tc_entity_get_local_scale(tc_entity_handle h, double* xyz) {
    tc_entity_pool* pool = tc_entity_pool_registry_get(h.pool);
    if (pool) tc_entity_pool_get_local_scale(pool, h.id, xyz);
}

static inline void tc_entity_set_local_scale(tc_entity_handle h, const double* xyz) {
    tc_entity_pool* pool = tc_entity_pool_registry_get(h.pool);
    if (pool) tc_entity_pool_set_local_scale(pool, h.id, xyz);
}

static inline void tc_entity_get_world_matrix(tc_entity_handle h, double* m16) {
    tc_entity_pool* pool = tc_entity_pool_registry_get(h.pool);
    if (pool) tc_entity_pool_get_world_matrix(pool, h.id, m16);
}

static inline void tc_entity_mark_dirty(tc_entity_handle h) {
    tc_entity_pool* pool = tc_entity_pool_registry_get(h.pool);
    if (pool) tc_entity_pool_mark_dirty(pool, h.id);
}

// Hierarchy
static inline tc_entity_handle tc_entity_parent(tc_entity_handle h) {
    tc_entity_pool* pool = tc_entity_pool_registry_get(h.pool);
    if (!pool) return TC_ENTITY_HANDLE_INVALID;
    tc_entity_id parent_id = tc_entity_pool_parent(pool, h.id);
    if (!tc_entity_id_valid(parent_id)) return TC_ENTITY_HANDLE_INVALID;
    return tc_entity_handle_make(h.pool, parent_id);
}

static inline void tc_entity_set_parent(tc_entity_handle h, tc_entity_handle parent) {
    tc_entity_pool* pool = tc_entity_pool_registry_get(h.pool);
    if (pool) tc_entity_pool_set_parent(pool, h.id, parent.id);
}

static inline size_t tc_entity_children_count(tc_entity_handle h) {
    tc_entity_pool* pool = tc_entity_pool_registry_get(h.pool);
    return pool ? tc_entity_pool_children_count(pool, h.id) : 0;
}

static inline tc_entity_handle tc_entity_child_at(tc_entity_handle h, size_t index) {
    tc_entity_pool* pool = tc_entity_pool_registry_get(h.pool);
    if (!pool) return TC_ENTITY_HANDLE_INVALID;
    tc_entity_id child_id = tc_entity_pool_child_at(pool, h.id, index);
    if (!tc_entity_id_valid(child_id)) return TC_ENTITY_HANDLE_INVALID;
    return tc_entity_handle_make(h.pool, child_id);
}

// Components
static inline void tc_entity_add_component(tc_entity_handle h, tc_component* c) {
    tc_entity_pool* pool = tc_entity_pool_registry_get(h.pool);
    if (pool) tc_entity_pool_add_component(pool, h.id, c);
}

static inline void tc_entity_remove_component(tc_entity_handle h, tc_component* c) {
    tc_entity_pool* pool = tc_entity_pool_registry_get(h.pool);
    if (pool) tc_entity_pool_remove_component(pool, h.id, c);
}

static inline size_t tc_entity_component_count(tc_entity_handle h) {
    tc_entity_pool* pool = tc_entity_pool_registry_get(h.pool);
    return pool ? tc_entity_pool_component_count(pool, h.id) : 0;
}

static inline tc_component* tc_entity_component_at(tc_entity_handle h, size_t index) {
    tc_entity_pool* pool = tc_entity_pool_registry_get(h.pool);
    return pool ? tc_entity_pool_component_at(pool, h.id, index) : NULL;
}

// SoA Components (handle-based)
static inline void tc_entity_add_soa(tc_entity_handle h, tc_soa_type_id type) {
    tc_entity_pool* pool = tc_entity_pool_registry_get(h.pool);
    if (pool) tc_entity_pool_add_soa(pool, h.id, type);
}

static inline void tc_entity_remove_soa(tc_entity_handle h, tc_soa_type_id type) {
    tc_entity_pool* pool = tc_entity_pool_registry_get(h.pool);
    if (pool) tc_entity_pool_remove_soa(pool, h.id, type);
}

static inline bool tc_entity_has_soa(tc_entity_handle h, tc_soa_type_id type) {
    tc_entity_pool* pool = tc_entity_pool_registry_get(h.pool);
    return pool ? tc_entity_pool_has_soa(pool, h.id, type) : false;
}

static inline void* tc_entity_get_soa(tc_entity_handle h, tc_soa_type_id type) {
    tc_entity_pool* pool = tc_entity_pool_registry_get(h.pool);
    return pool ? tc_entity_pool_get_soa(pool, h.id, type) : NULL;
}

static inline uint64_t tc_entity_soa_mask(tc_entity_handle h) {
    tc_entity_pool* pool = tc_entity_pool_registry_get(h.pool);
    return pool ? tc_entity_pool_soa_mask(pool, h.id) : 0;
}

#ifdef __cplusplus
}
#endif
