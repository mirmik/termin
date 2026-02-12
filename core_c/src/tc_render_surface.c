// tc_render_surface.c - Render surface implementation
#include "render/tc_render_surface.h"
#include "tc_log.h"
#include <stdlib.h>

// ============================================================================
// External Surface Lifecycle
// ============================================================================

tc_render_surface* tc_render_surface_new_external(
    void* body,
    const tc_render_surface_vtable* vtable
) {
    if (!body) {
        tc_log(TC_LOG_ERROR, "[tc_render_surface_new_external] body is NULL");
        return NULL;
    }
    if (!vtable) {
        tc_log(TC_LOG_ERROR, "[tc_render_surface_new_external] vtable is NULL");
        return NULL;
    }

    tc_render_surface* s = (tc_render_surface*)calloc(1, sizeof(tc_render_surface));
    if (!s) {
        tc_log(TC_LOG_ERROR, "[tc_render_surface_new_external] allocation failed");
        return NULL;
    }

    // Copy vtable to owned memory (caller's vtable may be in managed memory that can move)
    tc_render_surface_vtable* vtable_copy = (tc_render_surface_vtable*)malloc(sizeof(tc_render_surface_vtable));
    if (!vtable_copy) {
        tc_log(TC_LOG_ERROR, "[tc_render_surface_new_external] vtable allocation failed");
        free(s);
        return NULL;
    }
    *vtable_copy = *vtable;

    tc_render_surface_init(s, vtable_copy);
    s->body = body;

    return s;
}

void tc_render_surface_free_external(tc_render_surface* s) {
    if (!s) return;
    // Free GPU context if it was created
    if (s->gpu_context) {
        tc_gpu_context_free(s->gpu_context);
        s->gpu_context = NULL;
    }
    // Free the copied vtable
    if (s->vtable) {
        free((void*)s->vtable);
    }
    free(s);
}
