// tc_entity_pool_registry.h - Registry for entity pools with generational handles
#pragma once

#include <stdint.h>
#include <stdbool.h>
#include <stddef.h>
#include "tc_types.h"

#ifdef __cplusplus
extern "C" {
#endif

// ============================================================================
// Entity Pool Handle - generational index for safe pool references
// ============================================================================

#ifndef TC_ENTITY_POOL_HANDLE_DEFINED
#define TC_ENTITY_POOL_HANDLE_DEFINED
typedef struct {
    uint32_t index;
    uint32_t generation;
} tc_entity_pool_handle;
#endif

#ifdef __cplusplus
    #define TC_ENTITY_POOL_HANDLE_INVALID (tc_entity_pool_handle{0xFFFFFFFF, 0})
#else
    #define TC_ENTITY_POOL_HANDLE_INVALID ((tc_entity_pool_handle){0xFFFFFFFF, 0})
#endif

static inline bool tc_entity_pool_handle_valid(tc_entity_pool_handle h) {
    return h.index != 0xFFFFFFFF;
}

static inline bool tc_entity_pool_handle_eq(tc_entity_pool_handle a, tc_entity_pool_handle b) {
    return a.index == b.index && a.generation == b.generation;
}

// ============================================================================
// Registry lifecycle
// ============================================================================

// Initialize the global pool registry (called automatically on first use)
TC_API void tc_entity_pool_registry_init(void);

// Shutdown the registry and free all pools
TC_API void tc_entity_pool_registry_shutdown(void);

// ============================================================================
// Pool allocation via registry
// ============================================================================

// Create a new pool and return its handle
TC_API tc_entity_pool_handle tc_entity_pool_registry_create(size_t initial_capacity);

// Destroy pool by handle (invalidates handle via generation bump)
TC_API void tc_entity_pool_registry_destroy(tc_entity_pool_handle h);

// Check if pool handle is still alive
TC_API bool tc_entity_pool_registry_alive(tc_entity_pool_handle h);

// Get raw pool pointer from handle (returns NULL if handle invalid)
// WARNING: Do NOT cache this pointer - it may become invalid!
TC_API struct tc_entity_pool* tc_entity_pool_registry_get(tc_entity_pool_handle h);

// Get handle for existing pool pointer (for migration, returns INVALID if not found)
TC_API tc_entity_pool_handle tc_entity_pool_registry_find(struct tc_entity_pool* pool);

// Register an existing pool in the registry (takes ownership - pool will be destroyed on handle destroy)
// Returns handle to the pool, or INVALID if registration failed
TC_API tc_entity_pool_handle tc_entity_pool_registry_register(struct tc_entity_pool* pool);

// ============================================================================
// Standalone pool (for entities created outside of scenes)
// ============================================================================

// Get handle to the global standalone pool (created on first call)
TC_API tc_entity_pool_handle tc_entity_pool_standalone_handle(void);

#ifdef __cplusplus
}
#endif
