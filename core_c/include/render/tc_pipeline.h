// tc_pipeline.h - Render pipeline container
#ifndef TC_PIPELINE_H
#define TC_PIPELINE_H

#include "render/tc_pass.h"
#include "render/tc_pipeline_pool.h"

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

    // Pointer to C++ RenderPipeline owner (for casting back)
    void* cpp_owner;

    // Python object wrapper (for Python bindings)
    void* py_wrapper;

    // Frame graph cache (tc_frame_graph*)
    void* cached_frame_graph;

    // Dirty flag - set when passes change, cleared when frame graph is rebuilt
    bool dirty;
};

// ============================================================================
// Pipeline Lifecycle
// ============================================================================

TC_API tc_pipeline_handle tc_pipeline_create(const char* name);
TC_API void tc_pipeline_destroy(tc_pipeline_handle h);

// ============================================================================
// Pipeline Access (for internal use / backwards compatibility during migration)
// ============================================================================

// Get raw pointer from handle (returns NULL if handle is invalid)
TC_API tc_pipeline* tc_pipeline_get_ptr(tc_pipeline_handle h);

// ============================================================================
// Pass Management
// ============================================================================

// Add pass to end of pipeline (takes ownership)
TC_API void tc_pipeline_add_pass(tc_pipeline_handle h, tc_pass* pass);

// Insert pass before another pass
TC_API void tc_pipeline_insert_pass_before(tc_pipeline_handle h, tc_pass* pass, tc_pass* before);

// Remove pass from pipeline (does not destroy pass)
TC_API void tc_pipeline_remove_pass(tc_pipeline_handle h, tc_pass* pass);

// Remove all passes with given name, returns count of removed passes
TC_API size_t tc_pipeline_remove_passes_by_name(tc_pipeline_handle h, const char* name);

// Find pass by name (returns NULL if not found)
TC_API tc_pass* tc_pipeline_get_pass(tc_pipeline_handle h, const char* name);

// Find pass by index
TC_API tc_pass* tc_pipeline_get_pass_at(tc_pipeline_handle h, size_t index);

// Get pass count
TC_API size_t tc_pipeline_pass_count(tc_pipeline_handle h);

// ============================================================================
// Pipeline Properties
// ============================================================================

TC_API const char* tc_pipeline_get_name(tc_pipeline_handle h);
TC_API void tc_pipeline_set_name(tc_pipeline_handle h, const char* name);

// Get/set cpp_owner (for C++ interop)
TC_API void* tc_pipeline_get_cpp_owner(tc_pipeline_handle h);
TC_API void tc_pipeline_set_cpp_owner(tc_pipeline_handle h, void* owner);

// Get/set py_wrapper (for Python interop)
TC_API void* tc_pipeline_get_py_wrapper(tc_pipeline_handle h);
TC_API void tc_pipeline_set_py_wrapper(tc_pipeline_handle h, void* wrapper);

// Dirty flag management
TC_API bool tc_pipeline_is_dirty(tc_pipeline_handle h);
TC_API void tc_pipeline_mark_dirty(tc_pipeline_handle h);
TC_API void tc_pipeline_clear_dirty(tc_pipeline_handle h);

// Frame graph cache (returns cached or builds new if dirty)
// Caller must NOT destroy the returned frame graph - it's owned by pipeline
TC_API struct tc_frame_graph* tc_pipeline_get_frame_graph(tc_pipeline_handle h);

// ============================================================================
// Iteration (index-based)
// ============================================================================

// Iterator callback: return true to continue, false to stop
typedef bool (*tc_pipeline_pass_iter_fn)(tc_pipeline_handle h, tc_pass* pass, size_t index, void* user_data);

// Iterate over all passes in order
TC_API void tc_pipeline_foreach(tc_pipeline_handle h, tc_pipeline_pass_iter_fn callback, void* user_data);

// ============================================================================
// Resource Specs
// ============================================================================

// Note: Pipeline-level specs are stored in C++ RenderPipeline class.
// Use RenderPipeline::collect_specs() to get all specs (pipeline + pass).
// tc_pipeline_collect_specs is available for C code but only returns pass specs.

// Get all specs from passes only (for C code compatibility)
// Returns count, fills out_specs array (out_specs is ResourceSpec* from C++)
TC_API size_t tc_pipeline_collect_specs(
    tc_pipeline_handle h,
    void* out_specs,
    size_t max_count
);

#ifdef __cplusplus
}
#endif

#endif // TC_PIPELINE_H
