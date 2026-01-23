// tc_viewport.c - Viewport implementation
#include "tc_viewport.h"
#include <stdlib.h>
#include <string.h>

// ============================================================================
// Helper Functions
// ============================================================================

static char* tc_strdup(const char* s) {
    if (s == NULL) return NULL;
    size_t len = strlen(s) + 1;
    char* copy = (char*)malloc(len);
    if (copy) memcpy(copy, s, len);
    return copy;
}

static void tc_strset(char** dest, const char* src) {
    free(*dest);
    *dest = tc_strdup(src);
}

// ============================================================================
// Viewport Lifecycle
// ============================================================================

tc_viewport* tc_viewport_new(const char* name, tc_scene* scene, tc_component* camera) {
    tc_viewport* vp = (tc_viewport*)calloc(1, sizeof(tc_viewport));
    if (!vp) return NULL;

    vp->name = tc_strdup(name);
    vp->scene = scene;
    vp->camera = camera;

    // Default rect: full viewport
    vp->rect[0] = 0.0f;
    vp->rect[1] = 0.0f;
    vp->rect[2] = 1.0f;
    vp->rect[3] = 1.0f;

    // Default pixel rect
    vp->pixel_rect[0] = 0;
    vp->pixel_rect[1] = 0;
    vp->pixel_rect[2] = 1;
    vp->pixel_rect[3] = 1;

    vp->depth = 0;
    vp->pipeline = NULL;
    vp->layer_mask = 0xFFFFFFFFFFFFFFFFULL;
    vp->enabled = true;

    vp->input_mode = tc_strdup("simple");
    vp->block_input_in_editor = false;
    vp->managed_by_scene_pipeline = NULL;

    vp->internal_entities = NULL;
    vp->canvas = NULL;
    vp->py_wrapper = NULL;

    return vp;
}

void tc_viewport_free(tc_viewport* vp) {
    if (!vp) return;

    free(vp->name);
    free(vp->input_mode);
    free(vp->managed_by_scene_pipeline);
    free(vp);
}

// ============================================================================
// Viewport Properties
// ============================================================================

void tc_viewport_set_name(tc_viewport* vp, const char* name) {
    if (vp) tc_strset(&vp->name, name);
}

const char* tc_viewport_get_name(const tc_viewport* vp) {
    return vp ? vp->name : NULL;
}

void tc_viewport_set_rect(tc_viewport* vp, float x, float y, float w, float h) {
    if (!vp) return;
    vp->rect[0] = x;
    vp->rect[1] = y;
    vp->rect[2] = w;
    vp->rect[3] = h;
}

void tc_viewport_get_rect(const tc_viewport* vp, float* x, float* y, float* w, float* h) {
    if (!vp) return;
    if (x) *x = vp->rect[0];
    if (y) *y = vp->rect[1];
    if (w) *w = vp->rect[2];
    if (h) *h = vp->rect[3];
}

void tc_viewport_set_pixel_rect(tc_viewport* vp, int px, int py, int pw, int ph) {
    if (!vp) return;
    vp->pixel_rect[0] = px;
    vp->pixel_rect[1] = py;
    vp->pixel_rect[2] = pw;
    vp->pixel_rect[3] = ph;
}

void tc_viewport_get_pixel_rect(const tc_viewport* vp, int* px, int* py, int* pw, int* ph) {
    if (!vp) return;
    if (px) *px = vp->pixel_rect[0];
    if (py) *py = vp->pixel_rect[1];
    if (pw) *pw = vp->pixel_rect[2];
    if (ph) *ph = vp->pixel_rect[3];
}

void tc_viewport_set_depth(tc_viewport* vp, int depth) {
    if (vp) vp->depth = depth;
}

int tc_viewport_get_depth(const tc_viewport* vp) {
    return vp ? vp->depth : 0;
}

void tc_viewport_set_pipeline(tc_viewport* vp, tc_pipeline* pipeline) {
    if (vp) vp->pipeline = pipeline;
}

tc_pipeline* tc_viewport_get_pipeline(const tc_viewport* vp) {
    return vp ? vp->pipeline : NULL;
}

void tc_viewport_set_layer_mask(tc_viewport* vp, uint64_t mask) {
    if (vp) vp->layer_mask = mask;
}

uint64_t tc_viewport_get_layer_mask(const tc_viewport* vp) {
    return vp ? vp->layer_mask : 0xFFFFFFFFFFFFFFFFULL;
}

void tc_viewport_set_enabled(tc_viewport* vp, bool enabled) {
    if (vp) vp->enabled = enabled;
}

bool tc_viewport_get_enabled(const tc_viewport* vp) {
    return vp ? vp->enabled : false;
}

void tc_viewport_set_scene(tc_viewport* vp, tc_scene* scene) {
    if (vp) vp->scene = scene;
}

tc_scene* tc_viewport_get_scene(const tc_viewport* vp) {
    return vp ? vp->scene : NULL;
}

void tc_viewport_set_camera(tc_viewport* vp, tc_component* camera) {
    if (vp) vp->camera = camera;
}

tc_component* tc_viewport_get_camera(const tc_viewport* vp) {
    return vp ? vp->camera : NULL;
}

void tc_viewport_set_input_mode(tc_viewport* vp, const char* mode) {
    if (vp) tc_strset(&vp->input_mode, mode);
}

const char* tc_viewport_get_input_mode(const tc_viewport* vp) {
    return vp ? vp->input_mode : NULL;
}

void tc_viewport_set_managed_by(tc_viewport* vp, const char* pipeline_name) {
    if (vp) tc_strset(&vp->managed_by_scene_pipeline, pipeline_name);
}

const char* tc_viewport_get_managed_by(const tc_viewport* vp) {
    return vp ? vp->managed_by_scene_pipeline : NULL;
}

void tc_viewport_set_block_input_in_editor(tc_viewport* vp, bool block) {
    if (vp) vp->block_input_in_editor = block;
}

bool tc_viewport_get_block_input_in_editor(const tc_viewport* vp) {
    return vp ? vp->block_input_in_editor : false;
}

// ============================================================================
// Pixel Rect Calculation
// ============================================================================

void tc_viewport_update_pixel_rect(tc_viewport* vp, int display_width, int display_height) {
    if (!vp) return;

    int px = (int)(vp->rect[0] * display_width);
    int py = (int)(vp->rect[1] * display_height);
    int pw = (int)(vp->rect[2] * display_width);
    int ph = (int)(vp->rect[3] * display_height);

    // Ensure minimum size of 1
    if (pw < 1) pw = 1;
    if (ph < 1) ph = 1;

    vp->pixel_rect[0] = px;
    vp->pixel_rect[1] = py;
    vp->pixel_rect[2] = pw;
    vp->pixel_rect[3] = ph;
}

// ============================================================================
// Canvas
// ============================================================================

void tc_viewport_set_canvas(tc_viewport* vp, void* canvas) {
    if (vp) vp->canvas = canvas;
}

void* tc_viewport_get_canvas(const tc_viewport* vp) {
    return vp ? vp->canvas : NULL;
}

// ============================================================================
// Python Wrapper
// ============================================================================

void tc_viewport_set_py_wrapper(tc_viewport* vp, void* wrapper) {
    if (vp) vp->py_wrapper = wrapper;
}

void* tc_viewport_get_py_wrapper(const tc_viewport* vp) {
    return vp ? vp->py_wrapper : NULL;
}
