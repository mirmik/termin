// tc_scene_pool.h - Scene pool with generational indices
#pragma once

#include "tc_types.h"
#include <stdint.h>
#include <stdbool.h>
#include <stddef.h>

#ifdef __cplusplus
extern "C" {
#endif

// ============================================================================
// tc_scene_handle - generational index for scene references
// ============================================================================

typedef struct {
    uint32_t index;
    uint32_t generation;
} tc_scene_handle;

#ifdef __cplusplus
    #define TC_SCENE_HANDLE_INVALID (tc_scene_handle{0xFFFFFFFF, 0})
#else
    #define TC_SCENE_HANDLE_INVALID ((tc_scene_handle){0xFFFFFFFF, 0})
#endif

static inline bool tc_scene_handle_valid(tc_scene_handle h) {
    return h.index != 0xFFFFFFFF;
}

static inline bool tc_scene_handle_eq(tc_scene_handle a, tc_scene_handle b) {
    return a.index == b.index && a.generation == b.generation;
}

// ============================================================================
// Scene Pool Lifecycle (called from tc_init/tc_shutdown)
// ============================================================================

TC_API void tc_scene_pool_init(void);
TC_API void tc_scene_pool_shutdown(void);

// ============================================================================
// Scene Allocation
// ============================================================================

// Allocate a new scene, returns handle
TC_API tc_scene_handle tc_scene_pool_alloc(const char* name);

// Free a scene by handle
TC_API void tc_scene_pool_free(tc_scene_handle h);

// Check if scene handle is alive (valid and not freed)
TC_API bool tc_scene_pool_alive(tc_scene_handle h);

// ============================================================================
// Scene Count
// ============================================================================

TC_API size_t tc_scene_pool_count(void);

// ============================================================================
// Scene Name
// ============================================================================

TC_API const char* tc_scene_pool_get_name(tc_scene_handle h);
TC_API void tc_scene_pool_set_name(tc_scene_handle h, const char* name);

// ============================================================================
// Iteration
// ============================================================================

// Iterator callback: return true to continue, false to stop
typedef bool (*tc_scene_pool_iter_fn)(tc_scene_handle h, void* user_data);

// Iterate over all alive scenes
TC_API void tc_scene_pool_foreach(tc_scene_pool_iter_fn callback, void* user_data);

// ============================================================================
// Debug Info
// ============================================================================

typedef struct tc_scene_info {
    tc_scene_handle handle;
    const char* name;
    size_t entity_count;
    size_t pending_count;
    size_t update_count;
    size_t fixed_update_count;
} tc_scene_info;

// Get info for all scenes (caller must free() returned array)
TC_API tc_scene_info* tc_scene_pool_get_all_info(size_t* count);

#ifdef __cplusplus
}
#endif
