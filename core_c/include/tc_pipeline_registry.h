// tc_pipeline_registry.h - Global registry for tc_pipeline instances
#ifndef TC_PIPELINE_REGISTRY_H
#define TC_PIPELINE_REGISTRY_H

#include "render/tc_pipeline.h"

#ifdef __cplusplus
extern "C" {
#endif

// ============================================================================
// Lifecycle
// ============================================================================

TC_API void tc_pipeline_registry_init(void);
TC_API void tc_pipeline_registry_shutdown(void);

// ============================================================================
// Query
// ============================================================================

TC_API size_t tc_pipeline_registry_count(void);
TC_API tc_pipeline_handle tc_pipeline_registry_get_at(size_t index);
TC_API tc_pipeline_handle tc_pipeline_registry_find_by_name(const char* name);

// ============================================================================
// Info for debugging/inspection
// ============================================================================

typedef struct tc_pipeline_info {
    tc_pipeline_handle handle;
    const char* name;
    size_t pass_count;
} tc_pipeline_info;

// Get info for all pipelines (caller must free() returned array)
// Returns NULL if no pipelines, sets *count to number of entries
TC_API tc_pipeline_info* tc_pipeline_registry_get_all_info(size_t* count);

// ============================================================================
// Pass instance info (for all passes across all pipelines)
// ============================================================================

typedef struct tc_pass_info {
    tc_pass* ptr;
    const char* pass_name;
    const char* type_name;
    tc_pipeline_handle pipeline_handle;
    const char* pipeline_name;
    bool enabled;
    bool passthrough;
    bool is_inplace;
    int kind;  // TC_NATIVE_PASS or TC_EXTERNAL_PASS
} tc_pass_info;

// Get info for all passes in all pipelines (caller must free() returned array)
TC_API tc_pass_info* tc_pass_registry_get_all_instance_info(size_t* count);

#ifdef __cplusplus
}
#endif

#endif // TC_PIPELINE_REGISTRY_H
