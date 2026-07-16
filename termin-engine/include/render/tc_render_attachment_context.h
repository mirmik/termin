#ifndef TC_RENDER_ATTACHMENT_CONTEXT_H
#define TC_RENDER_ATTACHMENT_CONTEXT_H

#include <stdbool.h>
#include <stddef.h>

#include "tc_types.h"
#include "core/tc_component.h"
#include "core/tc_scene_pool.h"
#include "render/tc_pipeline_pool.h"
#include "render/tc_render_target_pool.h"

#ifdef __cplusplus
extern "C" {
#endif

TC_API bool tc_render_attachment_context_valid(
    const tc_render_attachment_context* context
);
TC_API tc_scene_handle tc_render_attachment_context_scene(
    const tc_render_attachment_context* context
);
TC_API size_t tc_render_attachment_context_render_target_count(
    const tc_render_attachment_context* context
);
TC_API tc_render_target_handle tc_render_attachment_context_render_target_at(
    const tc_render_attachment_context* context,
    size_t index
);
TC_API tc_render_target_handle tc_render_attachment_context_find_render_target(
    const tc_render_attachment_context* context,
    const char* name
);
TC_API tc_render_target_handle tc_render_attachment_context_find_camera_target(
    const tc_render_attachment_context* context,
    const tc_component* camera
);
TC_API tc_pipeline_handle tc_render_attachment_context_get_pipeline(
    const tc_render_attachment_context* context,
    const char* name
);

#ifdef __cplusplus
}
#endif

#endif
