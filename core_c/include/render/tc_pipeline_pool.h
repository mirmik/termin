// tc_pipeline_pool.h - Pipeline pool with generational indices
#ifndef TC_PIPELINE_POOL_H
#define TC_PIPELINE_POOL_H

#include "tc_types.h"
#include <stdint.h>
#include <stdbool.h>
#include <stddef.h>

#ifdef __cplusplus
extern "C" {
#endif

// ============================================================================
// tc_pipeline_handle - generational index for pipeline references
// ============================================================================

typedef struct {
    uint32_t index;
    uint32_t generation;
} tc_pipeline_handle;

#ifdef __cplusplus
    #define TC_PIPELINE_HANDLE_INVALID (tc_pipeline_handle{0xFFFFFFFF, 0})
#else
    #define TC_PIPELINE_HANDLE_INVALID ((tc_pipeline_handle){0xFFFFFFFF, 0})
#endif

static inline bool tc_pipeline_handle_valid(tc_pipeline_handle h) {
    return h.index != 0xFFFFFFFF;
}

static inline bool tc_pipeline_handle_eq(tc_pipeline_handle a, tc_pipeline_handle b) {
    return a.index == b.index && a.generation == b.generation;
}

// ============================================================================
// Pipeline Pool Lifecycle (called from tc_init/tc_shutdown)
// ============================================================================

TC_API void tc_pipeline_pool_init(void);
TC_API void tc_pipeline_pool_shutdown(void);

// ============================================================================
// Pipeline Allocation
// ============================================================================

// Allocate a new pipeline, returns handle
TC_API tc_pipeline_handle tc_pipeline_pool_alloc(const char* name);

// Free a pipeline by handle
TC_API void tc_pipeline_pool_free(tc_pipeline_handle h);

// Check if pipeline handle is alive (valid and not freed)
TC_API bool tc_pipeline_pool_alive(tc_pipeline_handle h);

// ============================================================================
// Pipeline Count
// ============================================================================

TC_API size_t tc_pipeline_pool_count(void);

// ============================================================================
// Iteration
// ============================================================================

// Iterator callback: return true to continue, false to stop
typedef bool (*tc_pipeline_pool_iter_fn)(tc_pipeline_handle h, void* user_data);

// Iterate over all alive pipelines
TC_API void tc_pipeline_pool_foreach(tc_pipeline_pool_iter_fn callback, void* user_data);

#ifdef __cplusplus
}
#endif

#endif // TC_PIPELINE_POOL_H
