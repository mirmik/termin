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

    tc_render_surface_init(s, vtable);
    s->body = body;

    return s;
}

void tc_render_surface_free_external(tc_render_surface* s) {
    if (!s) return;
    free(s);
}
