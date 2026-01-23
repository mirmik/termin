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
    tc_pass* first_pass;         // Linked list head
    tc_pass* last_pass;          // Linked list tail
    size_t pass_count;

    // Pipeline-level resource specs (additional to pass specs)
    tc_resource_spec* specs;
    size_t spec_count;
    size_t spec_capacity;
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
// Iteration
// ============================================================================

static inline tc_pass* tc_pipeline_first(tc_pipeline* p) {
    return p ? p->first_pass : NULL;
}

static inline tc_pass* tc_pipeline_last(tc_pipeline* p) {
    return p ? p->last_pass : NULL;
}

static inline tc_pass* tc_pass_next(tc_pass* pass) {
    return pass ? pass->next : NULL;
}

static inline tc_pass* tc_pass_prev(tc_pass* pass) {
    return pass ? pass->prev : NULL;
}

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
