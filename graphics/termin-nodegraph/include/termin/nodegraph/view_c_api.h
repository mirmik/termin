#pragma once

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#include <termin/gui_native/tc_ui_document.h>
#include <termin/nodegraph/c_api.h>

#ifdef __cplusplus
extern "C" {
#endif

TC_DEFINE_HANDLE(tc_nodegraph_view_handle)

typedef enum tc_nodegraph_parameter_editor_kind {
    TC_NODEGRAPH_PARAMETER_AUTOMATIC = 0,
    TC_NODEGRAPH_PARAMETER_BOOLEAN,
    TC_NODEGRAPH_PARAMETER_ENUMERATION,
    TC_NODEGRAPH_PARAMETER_INTEGER,
    TC_NODEGRAPH_PARAMETER_FLOATING_POINT,
    TC_NODEGRAPH_PARAMETER_TEXT,
} tc_nodegraph_parameter_editor_kind;

typedef struct tc_nodegraph_parameter_choice {
    const char* value;
    const char* label;
} tc_nodegraph_parameter_choice;

typedef struct tc_nodegraph_parameter_editor_desc {
    size_t struct_size;
    const char* name;
    const char* label;
    tc_nodegraph_parameter_editor_kind kind;
    double minimum;
    double maximum;
    double step;
    int32_t decimals;
    const tc_nodegraph_parameter_choice* choices;
    size_t choice_count;
    const tc_ui_style_override* style;
} tc_nodegraph_parameter_editor_desc;

typedef struct tc_nodegraph_body_layout {
    size_t struct_size;
    float height;
    float inset_left;
    float inset_right;
    float inset_top;
    float inset_bottom;
    float gap_before;
} tc_nodegraph_body_layout;

typedef enum tc_nodegraph_semantic_kind {
    TC_NODEGRAPH_SEMANTIC_NONE = 0,
    TC_NODEGRAPH_SEMANTIC_NODE,
    TC_NODEGRAPH_SEMANTIC_GROUP,
    TC_NODEGRAPH_SEMANTIC_EDGE,
    TC_NODEGRAPH_SEMANTIC_SOCKET,
} tc_nodegraph_semantic_kind;

typedef struct tc_nodegraph_semantic_ref {
    size_t struct_size;
    tc_nodegraph_semantic_kind kind;
    tc_nodegraph_node_handle node;
    tc_nodegraph_group_handle group;
    tc_nodegraph_edge_handle edge;
    const char* socket_name;
    bool socket_is_output;
} tc_nodegraph_semantic_ref;

// All pointers passed to callbacks are borrowed for the duration of the call.
// Descriptor strings, choice arrays and style returned by the presentation
// callback are copied before the callback returns.
typedef bool (*tc_nodegraph_view_present_parameter_fn)(void* userdata,
                                                       tc_nodegraph_node_handle node,
                                                       const char* name,
                                                       const tc_value* value,
                                                       tc_nodegraph_parameter_editor_desc* out_descriptor);
typedef bool (*tc_nodegraph_view_create_body_fn)(void* userdata,
                                                 tc_ui_document_handle document,
                                                 tc_nodegraph_node_handle node,
                                                 tc_widget_handle* out_widget,
                                                 tc_nodegraph_body_layout* out_layout);
typedef void (*tc_nodegraph_view_update_body_fn)(void* userdata,
                                                 tc_nodegraph_node_handle node,
                                                 tc_widget_handle widget);
typedef void (*tc_nodegraph_view_request_render_fn)(void* userdata);
typedef void (*tc_nodegraph_view_graph_changed_fn)(void* userdata, uint64_t revision);
typedef void (*tc_nodegraph_view_parameter_changed_fn)(void* userdata,
                                                       tc_nodegraph_node_handle node,
                                                       const char* name,
                                                       const tc_value* value);
typedef void (*tc_nodegraph_view_context_requested_fn)(void* userdata,
                                                       float world_x,
                                                       float world_y,
                                                       const tc_nodegraph_semantic_ref* semantic);

typedef struct tc_nodegraph_view_config {
    size_t struct_size;
    void* userdata;
    tc_nodegraph_userdata_deleter destroy_userdata;
    tc_nodegraph_view_present_parameter_fn present_parameter;
    tc_nodegraph_view_create_body_fn create_body;
    tc_nodegraph_view_update_body_fn update_body;
    tc_nodegraph_view_request_render_fn request_render;
    tc_nodegraph_view_graph_changed_fn graph_changed;
    tc_nodegraph_view_parameter_changed_fn parameter_changed;
    tc_nodegraph_view_context_requested_fn context_requested;
} tc_nodegraph_view_config;

TERMIN_NODEGRAPH_UI_API tc_nodegraph_view_handle tc_nodegraph_view_create(tc_ui_document_handle document,
                                                                          tc_nodegraph_handle graph,
                                                                          const tc_nodegraph_view_config* config);
TERMIN_NODEGRAPH_UI_API void tc_nodegraph_view_destroy(tc_nodegraph_view_handle view);
TERMIN_NODEGRAPH_UI_API bool tc_nodegraph_view_is_valid(tc_nodegraph_view_handle view);
TERMIN_NODEGRAPH_UI_API tc_widget_handle tc_nodegraph_view_root_widget(tc_nodegraph_view_handle view);
TERMIN_NODEGRAPH_UI_API bool tc_nodegraph_view_rebuild(tc_nodegraph_view_handle view);
TERMIN_NODEGRAPH_UI_API bool tc_nodegraph_view_sync(tc_nodegraph_view_handle view);
TERMIN_NODEGRAPH_UI_API tc_widget_handle tc_nodegraph_view_parameter_widget(tc_nodegraph_view_handle view,
                                                                            tc_nodegraph_node_handle node,
                                                                            const char* name);
// The returned size includes the trailing NUL. Passing NULL/0 is a size query.
TERMIN_NODEGRAPH_UI_API size_t tc_nodegraph_view_copy_last_error(tc_nodegraph_view_handle view,
                                                                 char* buffer,
                                                                 size_t capacity);

#ifdef __cplusplus
}
#endif
