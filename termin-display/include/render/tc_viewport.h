// tc_viewport.h - Viewport (what to render and where)
#ifndef TC_VIEWPORT_H
#define TC_VIEWPORT_H

#include "tc_types.h"
#include "render/termin_display_api.h"
#include "core/tc_entity_pool.h"
#include "core/tc_scene_pool.h"
#include "render/tc_viewport_pool.h"
#include "render/tc_pipeline_pool.h"
#include "render/tc_render_target_pool.h"

#ifdef __cplusplus
extern "C" {
#endif

typedef struct tc_input_manager tc_input_manager;

TERMIN_DISPLAY_API tc_viewport_handle tc_viewport_new(const char* name, tc_scene_handle scene, tc_component* camera);
TERMIN_DISPLAY_API void tc_viewport_free(tc_viewport_handle h);
TERMIN_DISPLAY_API bool tc_viewport_alive(tc_viewport_handle h);

TERMIN_DISPLAY_API void tc_viewport_set_name(tc_viewport_handle h, const char* name);
TERMIN_DISPLAY_API const char* tc_viewport_get_name(tc_viewport_handle h);

TERMIN_DISPLAY_API void tc_viewport_set_rect(tc_viewport_handle h, float x, float y, float w, float height);
TERMIN_DISPLAY_API void tc_viewport_get_rect(tc_viewport_handle h, float* x, float* y, float* w, float* height);

TERMIN_DISPLAY_API void tc_viewport_set_pixel_rect(tc_viewport_handle h, int px, int py, int pw, int ph);
TERMIN_DISPLAY_API void tc_viewport_get_pixel_rect(tc_viewport_handle h, int* px, int* py, int* pw, int* ph);

TERMIN_DISPLAY_API void tc_viewport_set_depth(tc_viewport_handle h, int depth);
TERMIN_DISPLAY_API int tc_viewport_get_depth(tc_viewport_handle h);

TERMIN_DISPLAY_API void tc_viewport_set_pipeline(tc_viewport_handle h, tc_pipeline_handle pipeline);
TERMIN_DISPLAY_API tc_pipeline_handle tc_viewport_get_pipeline(tc_viewport_handle h);

TERMIN_DISPLAY_API void tc_viewport_set_layer_mask(tc_viewport_handle h, uint64_t mask);
TERMIN_DISPLAY_API uint64_t tc_viewport_get_layer_mask(tc_viewport_handle h);

TERMIN_DISPLAY_API void tc_viewport_set_enabled(tc_viewport_handle h, bool enabled);
TERMIN_DISPLAY_API bool tc_viewport_get_enabled(tc_viewport_handle h);

TERMIN_DISPLAY_API void tc_viewport_set_scene(tc_viewport_handle h, tc_scene_handle scene);
TERMIN_DISPLAY_API tc_scene_handle tc_viewport_get_scene(tc_viewport_handle h);

TERMIN_DISPLAY_API void tc_viewport_set_camera(tc_viewport_handle h, tc_component* camera);
TERMIN_DISPLAY_API tc_component* tc_viewport_get_camera(tc_viewport_handle h);
TERMIN_DISPLAY_API tc_entity_handle tc_viewport_get_camera_entity(tc_viewport_handle h);

TERMIN_DISPLAY_API void tc_viewport_set_render_target(tc_viewport_handle h, tc_render_target_handle rt);
TERMIN_DISPLAY_API tc_render_target_handle tc_viewport_get_render_target(tc_viewport_handle h);

TERMIN_DISPLAY_API void tc_viewport_set_override_resolution(tc_viewport_handle h, bool override_resolution);
TERMIN_DISPLAY_API bool tc_viewport_get_override_resolution(tc_viewport_handle h);

TERMIN_DISPLAY_API void tc_viewport_set_input_mode(tc_viewport_handle h, const char* mode);
TERMIN_DISPLAY_API const char* tc_viewport_get_input_mode(tc_viewport_handle h);

TERMIN_DISPLAY_API void tc_viewport_set_managed_by(tc_viewport_handle h, const char* pipeline_name);
TERMIN_DISPLAY_API const char* tc_viewport_get_managed_by(tc_viewport_handle h);

TERMIN_DISPLAY_API void tc_viewport_set_block_input_in_editor(tc_viewport_handle h, bool block);
TERMIN_DISPLAY_API bool tc_viewport_get_block_input_in_editor(tc_viewport_handle h);

TERMIN_DISPLAY_API void tc_viewport_set_input_manager(tc_viewport_handle h, tc_input_manager* manager);
TERMIN_DISPLAY_API tc_input_manager* tc_viewport_get_input_manager(tc_viewport_handle h);

TERMIN_DISPLAY_API void tc_viewport_update_pixel_rect(tc_viewport_handle h, int display_width, int display_height);

TERMIN_DISPLAY_API void tc_viewport_set_internal_entities(tc_viewport_handle h, tc_entity_handle ent);
TERMIN_DISPLAY_API tc_entity_handle tc_viewport_get_internal_entities(tc_viewport_handle h);
TERMIN_DISPLAY_API bool tc_viewport_has_internal_entities(tc_viewport_handle h);

TERMIN_DISPLAY_API tc_viewport_handle tc_viewport_get_display_next(tc_viewport_handle h);
TERMIN_DISPLAY_API tc_viewport_handle tc_viewport_get_display_prev(tc_viewport_handle h);
TERMIN_DISPLAY_API void tc_viewport_set_display_next(tc_viewport_handle h, tc_viewport_handle next);
TERMIN_DISPLAY_API void tc_viewport_set_display_prev(tc_viewport_handle h, tc_viewport_handle prev);

#ifdef __cplusplus
}
#endif

#endif // TC_VIEWPORT_H
