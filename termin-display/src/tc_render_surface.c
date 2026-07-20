// tc_render_surface.c - Render surface implementation
#include "render/tc_render_surface.h"
#include <tcbase/tc_log.h>
#include <stdlib.h>

bool tc_render_surface_validate_output(
    tc_render_surface* surface,
    uintptr_t expected_graphics_domain_key,
    uint32_t* color_texture_id
) {
    if (color_texture_id) *color_texture_id = 0;
    if (!surface || !surface->vtable) {
        tc_log(TC_LOG_ERROR, "[tc_render_surface_validate_output] surface is invalid");
        return false;
    }
    uint32_t texture_id = tc_render_surface_get_color_texture_id(surface);
    if (texture_id == 0) {
        tc_log(TC_LOG_ERROR,
               "[tc_render_surface_validate_output] surface has no color texture");
        return false;
    }
    uintptr_t actual_domain = tc_render_surface_get_graphics_domain_key(surface);
    if (expected_graphics_domain_key == 0 || actual_domain == 0 ||
        actual_domain != expected_graphics_domain_key) {
        tc_log(TC_LOG_ERROR,
               "[tc_render_surface_validate_output] graphics domain mismatch: surface=%p expected=%p",
               (void*)actual_domain, (void*)expected_graphics_domain_key);
        return false;
    }
    if (color_texture_id) *color_texture_id = texture_id;
    return true;
}

// ============================================================================
// External Surface Lifecycle
// ============================================================================

tc_render_surface* tc_render_surface_new_external(
    void* body,
    const tc_render_surface_vtable* vtable,
    size_t vtable_size,
    uint32_t abi_version
) {
    if (!body) {
        tc_log(TC_LOG_ERROR, "[tc_render_surface_new_external] body is NULL");
        return NULL;
    }
    if (!vtable) {
        tc_log(TC_LOG_ERROR, "[tc_render_surface_new_external] vtable is NULL");
        return NULL;
    }
    if (abi_version != TC_RENDER_SURFACE_ABI_VERSION) {
        tc_log(TC_LOG_ERROR,
               "[tc_render_surface_new_external] ABI version mismatch: got %u, expected %u",
               abi_version, TC_RENDER_SURFACE_ABI_VERSION);
        return NULL;
    }
    if (vtable_size != sizeof(tc_render_surface_vtable)) {
        tc_log(TC_LOG_ERROR,
               "[tc_render_surface_new_external] vtable size mismatch: got %zu, expected %zu",
               vtable_size, sizeof(tc_render_surface_vtable));
        return NULL;
    }
    if (!vtable->get_size || !vtable->get_color_texture_id ||
        !vtable->get_graphics_domain_key || !vtable->destroy) {
        tc_log(TC_LOG_ERROR,
               "[tc_render_surface_new_external] vtable has missing mandatory callbacks");
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

bool tc_render_surface_free_external(tc_render_surface* s) {
    if (!s) return true;
    if (s->attached_display) {
        tc_log(TC_LOG_ERROR,
               "[tc_render_surface_free_external] surface is still attached to a display");
        return false;
    }
    if (s->vtable && s->vtable->destroy) {
        s->vtable->destroy(s);
    }
    // Free the copied vtable
    if (s->vtable) {
        free((void*)s->vtable);
    }
    free(s);
    return true;
}

bool tc_render_surface_attach(tc_render_surface* surface, tc_display* display) {
    if (!surface || !display) {
        tc_log(TC_LOG_ERROR, "[tc_render_surface_attach] surface and display are required");
        return false;
    }
    if (surface->attached_display && surface->attached_display != display) {
        tc_log(TC_LOG_ERROR,
               "[tc_render_surface_attach] surface is already attached to another display");
        return false;
    }
    surface->attached_display = display;
    return true;
}

bool tc_render_surface_detach(tc_render_surface* surface, tc_display* display) {
    if (!surface || !display) {
        tc_log(TC_LOG_ERROR, "[tc_render_surface_detach] surface and display are required");
        return false;
    }
    if (surface->attached_display != display) {
        tc_log(TC_LOG_ERROR,
               "[tc_render_surface_detach] display does not own this surface attachment");
        return false;
    }
    surface->attached_display = NULL;
    return true;
}
