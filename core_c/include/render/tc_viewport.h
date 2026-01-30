// tc_viewport.h - Viewport (what to render and where)
#ifndef TC_VIEWPORT_H
#define TC_VIEWPORT_H

#include "tc_types.h"
#include "tc_entity_pool.h"
#include "tc_scene_pool.h"

#ifdef __cplusplus
extern "C" {
#endif

// ============================================================================
// Viewport Structure
// ============================================================================

// Destructor callback type (for Python bindings to clean up py_wrapper)
typedef void (*tc_viewport_destructor_fn)(struct tc_viewport* vp, void* user_data);

struct tc_viewport {
    // Reference counting
    uint32_t ref_count;

    char* name;
    tc_scene_handle scene;          // Scene handle
    tc_component* camera;           // CameraComponent

    // Normalized rect (0.0 - 1.0)
    float rect[4];                  // x, y, width, height

    // Pixel rect (updated by display on resize)
    int pixel_rect[4];              // px, py, pw, ph

    int depth;                      // Render priority (lower = earlier)
    tc_pipeline* pipeline;
    uint64_t layer_mask;
    bool enabled;

    char* input_mode;               // "none", "simple", "editor"
    bool block_input_in_editor;
    char* managed_by_scene_pipeline;

    // Internal entities root (for viewport-specific objects)
    tc_entity_pool* internal_entities_pool;
    tc_entity_id internal_entities_id;

    // Destructor callback (called before free, for Python bindings cleanup)
    tc_viewport_destructor_fn destructor_fn;
    void* destructor_user_data;

    // Linked list for display's viewport list
    struct tc_viewport* display_prev;
    struct tc_viewport* display_next;
};

// ============================================================================
// Viewport Lifecycle
// ============================================================================

TC_API tc_viewport* tc_viewport_new(const char* name, tc_scene_handle scene, tc_component* camera);
TC_API void tc_viewport_free(tc_viewport* vp);

// ============================================================================
// Reference Counting
// ============================================================================

// Increment reference count
TC_API void tc_viewport_add_ref(tc_viewport* vp);

// Decrement reference count. Returns true if viewport was destroyed (ref_count reached 0)
TC_API bool tc_viewport_release(tc_viewport* vp);

// Get current reference count
TC_API uint32_t tc_viewport_get_ref_count(const tc_viewport* vp);

// ============================================================================
// Viewport Properties
// ============================================================================

TC_API void tc_viewport_set_name(tc_viewport* vp, const char* name);
TC_API const char* tc_viewport_get_name(const tc_viewport* vp);

TC_API void tc_viewport_set_rect(tc_viewport* vp, float x, float y, float w, float h);
TC_API void tc_viewport_get_rect(const tc_viewport* vp, float* x, float* y, float* w, float* h);

TC_API void tc_viewport_set_pixel_rect(tc_viewport* vp, int px, int py, int pw, int ph);
TC_API void tc_viewport_get_pixel_rect(const tc_viewport* vp, int* px, int* py, int* pw, int* ph);

TC_API void tc_viewport_set_depth(tc_viewport* vp, int depth);
TC_API int tc_viewport_get_depth(const tc_viewport* vp);

TC_API void tc_viewport_set_pipeline(tc_viewport* vp, tc_pipeline* pipeline);
TC_API tc_pipeline* tc_viewport_get_pipeline(const tc_viewport* vp);

TC_API void tc_viewport_set_layer_mask(tc_viewport* vp, uint64_t mask);
TC_API uint64_t tc_viewport_get_layer_mask(const tc_viewport* vp);

TC_API void tc_viewport_set_enabled(tc_viewport* vp, bool enabled);
TC_API bool tc_viewport_get_enabled(const tc_viewport* vp);

TC_API void tc_viewport_set_scene(tc_viewport* vp, tc_scene_handle scene);
TC_API tc_scene_handle tc_viewport_get_scene(const tc_viewport* vp);

TC_API void tc_viewport_set_camera(tc_viewport* vp, tc_component* camera);
TC_API tc_component* tc_viewport_get_camera(const tc_viewport* vp);

TC_API void tc_viewport_set_input_mode(tc_viewport* vp, const char* mode);
TC_API const char* tc_viewport_get_input_mode(const tc_viewport* vp);

TC_API void tc_viewport_set_managed_by(tc_viewport* vp, const char* pipeline_name);
TC_API const char* tc_viewport_get_managed_by(const tc_viewport* vp);

TC_API void tc_viewport_set_block_input_in_editor(tc_viewport* vp, bool block);
TC_API bool tc_viewport_get_block_input_in_editor(const tc_viewport* vp);

// ============================================================================
// Pixel Rect Calculation
// ============================================================================

// Update pixel_rect from normalized rect and display size
TC_API void tc_viewport_update_pixel_rect(tc_viewport* vp, int display_width, int display_height);

// ============================================================================
// Internal Entities
// ============================================================================

TC_API void tc_viewport_set_internal_entities(tc_viewport* vp, tc_entity_pool* pool, tc_entity_id id);
TC_API tc_entity_pool* tc_viewport_get_internal_entities_pool(const tc_viewport* vp);
TC_API tc_entity_id tc_viewport_get_internal_entities_id(const tc_viewport* vp);
TC_API bool tc_viewport_has_internal_entities(const tc_viewport* vp);

#ifdef __cplusplus
}
#endif

#endif // TC_VIEWPORT_H
