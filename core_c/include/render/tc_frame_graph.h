// tc_frame_graph.h - Frame graph for dependency resolution and scheduling
#ifndef TC_FRAME_GRAPH_H
#define TC_FRAME_GRAPH_H

#include "render/tc_pass.h"
#include "render/tc_pipeline.h"

#ifdef __cplusplus
extern "C" {
#endif

typedef struct tc_frame_graph tc_frame_graph;

// ============================================================================
// Error Types
// ============================================================================

typedef enum tc_frame_graph_error {
    TC_FG_OK = 0,
    TC_FG_ERROR_MULTI_WRITER,    // Same resource written by multiple passes
    TC_FG_ERROR_CYCLE,           // Dependency cycle detected
    TC_FG_ERROR_INVALID_INPLACE  // Invalid inplace alias configuration
} tc_frame_graph_error;

// ============================================================================
// Frame Graph Lifecycle
// ============================================================================

// Build frame graph from pipeline passes
// Analyzes dependencies and prepares execution schedule
TC_API tc_frame_graph* tc_frame_graph_build(tc_pipeline* pipeline);

// Destroy frame graph (does not destroy passes)
TC_API void tc_frame_graph_destroy(tc_frame_graph* fg);

// ============================================================================
// Error Handling
// ============================================================================

// Get error code from last build
TC_API tc_frame_graph_error tc_frame_graph_get_error(tc_frame_graph* fg);

// Get error message (NULL if no error)
TC_API const char* tc_frame_graph_get_error_message(tc_frame_graph* fg);

// ============================================================================
// Execution Schedule
// ============================================================================

// Get topologically sorted execution schedule
// Returns count, fills out_passes array with pointers
TC_API size_t tc_frame_graph_get_schedule(
    tc_frame_graph* fg,
    tc_pass** out_passes,
    size_t max_count
);

// Get schedule count without copying
TC_API size_t tc_frame_graph_schedule_count(tc_frame_graph* fg);

// Get pass at schedule index
TC_API tc_pass* tc_frame_graph_schedule_at(tc_frame_graph* fg, size_t index);

// ============================================================================
// Resource Aliasing
// ============================================================================

// Get canonical resource name (resolves inplace aliases)
// Returns the canonical name (may be same as input)
TC_API const char* tc_frame_graph_canonical_resource(
    tc_frame_graph* fg,
    const char* name
);

// Get all resources in the same alias group
// Returns count, fills out_names array
TC_API size_t tc_frame_graph_get_alias_group(
    tc_frame_graph* fg,
    const char* resource,
    const char** out_names,
    size_t max_count
);

// Get all canonical resource names (unique physical resources)
TC_API size_t tc_frame_graph_get_canonical_resources(
    tc_frame_graph* fg,
    const char** out_names,
    size_t max_count
);

// ============================================================================
// Debugging
// ============================================================================

// Print frame graph to log (for debugging)
TC_API void tc_frame_graph_dump(tc_frame_graph* fg);

#ifdef __cplusplus
}
#endif

#endif // TC_FRAME_GRAPH_H
