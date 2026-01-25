// tc_scene_skybox.h - Scene skybox properties
#ifndef TC_SCENE_SKYBOX_H
#define TC_SCENE_SKYBOX_H

#include "tc_types.h"

#ifdef __cplusplus
extern "C" {
#endif

struct tc_mesh;
struct tc_material;

// Skybox type
typedef enum tc_skybox_type {
    TC_SKYBOX_NONE = 0,
    TC_SKYBOX_GRADIENT = 1,
    TC_SKYBOX_SOLID = 2
} tc_skybox_type;

// Scene skybox properties
typedef struct tc_scene_skybox {
    int type;                    // tc_skybox_type
    float color[3];              // Solid color RGB
    float top_color[3];          // Gradient top RGB
    float bottom_color[3];       // Gradient bottom RGB
    struct tc_mesh* mesh;        // Skybox cube mesh (refcounted)
    struct tc_material* material; // Skybox material (refcounted)
} tc_scene_skybox;

// Initialize with defaults
TC_API void tc_scene_skybox_init(tc_scene_skybox* skybox);

// Free resources (release mesh/material refs)
TC_API void tc_scene_skybox_free(tc_scene_skybox* skybox);

// ============================================================================
// Scene Skybox API
// ============================================================================

// Get skybox properties from scene (returns internal pointer, do not free)
TC_API tc_scene_skybox* tc_scene_get_skybox(tc_scene* s);

// Type
TC_API void tc_scene_set_skybox_type(tc_scene* s, int type);
TC_API int tc_scene_get_skybox_type(tc_scene* s);

// Colors
TC_API void tc_scene_set_skybox_color(tc_scene* s, float r, float g, float b);
TC_API void tc_scene_get_skybox_color(tc_scene* s, float* r, float* g, float* b);

TC_API void tc_scene_set_skybox_top_color(tc_scene* s, float r, float g, float b);
TC_API void tc_scene_get_skybox_top_color(tc_scene* s, float* r, float* g, float* b);

TC_API void tc_scene_set_skybox_bottom_color(tc_scene* s, float r, float g, float b);
TC_API void tc_scene_get_skybox_bottom_color(tc_scene* s, float* r, float* g, float* b);

// Mesh and material (with refcounting)
TC_API void tc_scene_set_skybox_mesh(tc_scene* s, struct tc_mesh* mesh);
TC_API struct tc_mesh* tc_scene_get_skybox_mesh(tc_scene* s);

TC_API void tc_scene_set_skybox_material(tc_scene* s, struct tc_material* material);
TC_API struct tc_material* tc_scene_get_skybox_material(tc_scene* s);

#ifdef __cplusplus
}
#endif

#endif // TC_SCENE_SKYBOX_H
