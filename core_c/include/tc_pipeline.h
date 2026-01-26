// tc_pipeline.h - Render pipeline container
#ifndef TC_PIPELINE_H
#define TC_PIPELINE_H

#include "tc_pass.h"

#ifdef __cplusplus
extern "C" {
#endif

typedef struct tc_pipeline tc_pipeline;

struct tc_pipeline {
    char* name;

    // Pass storage (dynamic array)
    tc_pass** passes;
    size_t pass_count;
    size_t pass_capacity;

    // Pipeline-level resource specs (additional to pass specs)
    tc_resource_spec* specs;
    size_t spec_count;
    size_t spec_capacity;

    // Python wrapper
    void* py_wrapper;
};

// ============================================================================
// Pipeline Lifecycle
// ============================================================================

TC_API tc_pipeline* tc_pipeline_create(const char* name);
TC_API void tc_pipeline_destroy(tc_pipeline* p);

// ============================================================================
// Pass Management
// ============================================================================

// Add pass to end of pipeline (takes ownership)
TC_API void tc_pipeline_add_pass(tc_pipeline* p, tc_pass* pass);

// Insert pass before another pass
TC_API void tc_pipeline_insert_pass_before(tc_pipeline* p, tc_pass* pass, tc_pass* before);

// Remove pass from pipeline (does not destroy pass)
TC_API void tc_pipeline_remove_pass(tc_pipeline* p, tc_pass* pass);

// Find pass by name (returns NULL if not found)
TC_API tc_pass* tc_pipeline_get_pass(tc_pipeline* p, const char* name);

// Find pass by index
TC_API tc_pass* tc_pipeline_get_pass_at(tc_pipeline* p, size_t index);

// Get pass count
TC_API size_t tc_pipeline_pass_count(tc_pipeline* p);

// ============================================================================
// Iteration (index-based)
// ============================================================================

// Iterator callback: return true to continue, false to stop
typedef bool (*tc_pipeline_pass_iter_fn)(tc_pipeline* p, tc_pass* pass, size_t index, void* user_data);

// Iterate over all passes in order
TC_API void tc_pipeline_foreach(tc_pipeline* p, tc_pipeline_pass_iter_fn callback, void* user_data);

// ============================================================================
// Resource Specs
// ============================================================================

TC_API void tc_pipeline_add_spec(tc_pipeline* p, const tc_resource_spec* spec);
TC_API void tc_pipeline_clear_specs(tc_pipeline* p);

// Get all specs (from pipeline + all passes)
// Returns count, fills out_specs array
TC_API size_t tc_pipeline_collect_specs(
    tc_pipeline* p,
    tc_resource_spec* out_specs,
    size_t max_count
);

#ifdef __cplusplus
}
#endif

#endif // TC_PIPELINE_H
