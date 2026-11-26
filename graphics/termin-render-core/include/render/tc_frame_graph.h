#ifndef TC_FRAME_GRAPH_H
#define TC_FRAME_GRAPH_H

#include <render/tc_pass.h>
#include <render/tc_pipeline.h>

#ifdef __cplusplus
extern "C" {
#endif

typedef struct tc_frame_graph tc_frame_graph;

enum { TC_FRAME_GRAPH_MAX_PASSES = 128 };

typedef struct tc_frame_graph_pass_resources {
    const char* const* reads;
    size_t read_count;
    const char* const* writes;
    size_t write_count;
    const char* const* aliases;
    size_t alias_count;
} tc_frame_graph_pass_resources;

typedef enum tc_frame_graph_error {
    TC_FG_OK = 0,
    TC_FG_ERROR_MULTI_WRITER,
    TC_FG_ERROR_CYCLE,
    TC_FG_ERROR_INVALID_INPLACE,
    TC_FG_ERROR_ALLOCATION,
    TC_FG_ERROR_LIMIT
} tc_frame_graph_error;

TC_API tc_frame_graph* tc_frame_graph_build(tc_pipeline_handle pipeline);
TC_API void tc_frame_graph_destroy(tc_frame_graph* fg);
TC_API tc_frame_graph_error tc_frame_graph_get_error(tc_frame_graph* fg);
TC_API const char* tc_frame_graph_get_error_message(tc_frame_graph* fg);
TC_API size_t tc_frame_graph_get_schedule(tc_frame_graph* fg, tc_pass** out_passes, size_t max_count);
TC_API size_t tc_frame_graph_schedule_count(tc_frame_graph* fg);
TC_API tc_pass* tc_frame_graph_schedule_at(tc_frame_graph* fg, size_t index);
TC_API tc_frame_graph_pass_resources tc_frame_graph_resources_at(tc_frame_graph* fg, size_t index);
// Returns the index of the writer of this logical version, or SIZE_MAX.
TC_API size_t tc_frame_graph_writer_index(tc_frame_graph* fg, const char* resource);
TC_API bool tc_frame_graph_has_resource(tc_frame_graph* fg, const char* resource);
// Includes ordering-only edges, for example a reader before an in-place write.
TC_API size_t tc_frame_graph_get_dependents(tc_frame_graph* fg, size_t index, size_t* out, size_t capacity);
TC_API const char* tc_frame_graph_canonical_resource(tc_frame_graph* fg, const char* name);
// Count/fill enumeration: both functions return the complete count. Passing
// out_names == NULL queries the required capacity.
TC_API size_t tc_frame_graph_get_alias_group(tc_frame_graph* fg,
                                             const char* resource,
                                             const char** out_names,
                                             size_t max_count);
TC_API size_t tc_frame_graph_get_canonical_resources(tc_frame_graph* fg, const char** out_names, size_t max_count);
TC_API void tc_frame_graph_dump(tc_frame_graph* fg);

#ifdef __cplusplus
}
#endif

#endif
