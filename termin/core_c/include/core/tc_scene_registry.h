// tc_scene_registry.h - Legacy API, now delegates to tc_scene_pool
// This header is deprecated, use tc_scene_pool.h directly
#pragma once

#include "tc_types.h"
#include "core/tc_scene_pool.h"

#ifdef __cplusplus
extern "C" {
#endif

// ============================================================================
// Lifecycle (called from tc_init/tc_shutdown)
// Now delegates to tc_scene_pool
// ============================================================================

static inline void tc_scene_registry_init(void) {
    tc_scene_pool_init();
}

static inline void tc_scene_registry_shutdown(void) {
    tc_scene_pool_shutdown();
}

// ============================================================================
// Queries - delegate to pool
// ============================================================================

static inline size_t tc_scene_registry_count(void) {
    return tc_scene_pool_count();
}

// ============================================================================
// Scene info - uses tc_scene_info from tc_scene_pool.h
// ============================================================================

static inline tc_scene_info* tc_scene_registry_get_all_info(size_t* count) {
    return tc_scene_pool_get_all_info(count);
}

// ============================================================================
// Iteration - delegate to pool
// ============================================================================

static inline void tc_scene_registry_foreach(tc_scene_pool_iter_fn callback, void* user_data) {
    tc_scene_pool_foreach(callback, user_data);
}

#ifdef __cplusplus
}
#endif
