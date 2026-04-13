// tc_viewport_pool.h - Viewport pool with generational indices
#ifndef TC_VIEWPORT_POOL_H
#define TC_VIEWPORT_POOL_H

#include "tc_types.h"
#include <stdint.h>
#include <stdbool.h>
#include <stddef.h>

#ifdef __cplusplus
extern "C" {
#endif

// ============================================================================
// tc_viewport_handle - generational index for viewport references
// ============================================================================

typedef struct {
    uint32_t index;
    uint32_t generation;
} tc_viewport_handle;

#ifdef __cplusplus
    #define TC_VIEWPORT_HANDLE_INVALID (tc_viewport_handle{0xFFFFFFFF, 0})
#else
    #define TC_VIEWPORT_HANDLE_INVALID ((tc_viewport_handle){0xFFFFFFFF, 0})
#endif

static inline bool tc_viewport_handle_valid(tc_viewport_handle h) {
    return h.index != 0xFFFFFFFF;
}

static inline bool tc_viewport_handle_eq(tc_viewport_handle a, tc_viewport_handle b) {
    return a.index == b.index && a.generation == b.generation;
}

// ============================================================================
// Viewport Pool Lifecycle (called from tc_init/tc_shutdown)
// ============================================================================

TC_API void tc_viewport_pool_init(void);
TC_API void tc_viewport_pool_shutdown(void);

// ============================================================================
// Viewport Allocation
// ============================================================================

// Allocate a new viewport, returns handle
TC_API tc_viewport_handle tc_viewport_pool_alloc(const char* name);

// Free a viewport by handle
TC_API void tc_viewport_pool_free(tc_viewport_handle h);

// Check if viewport handle is alive (valid and not freed)
TC_API bool tc_viewport_pool_alive(tc_viewport_handle h);

// ============================================================================
// Viewport Count
// ============================================================================

TC_API size_t tc_viewport_pool_count(void);

// ============================================================================
// Iteration
// ============================================================================

// Iterator callback: return true to continue, false to stop
typedef bool (*tc_viewport_pool_iter_fn)(tc_viewport_handle h, void* user_data);

// Iterate over all alive viewports
TC_API void tc_viewport_pool_foreach(tc_viewport_pool_iter_fn callback, void* user_data);

#ifdef __cplusplus
}
#endif

#endif // TC_VIEWPORT_POOL_H
