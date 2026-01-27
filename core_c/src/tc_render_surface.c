// tc_render_surface.c - Render surface implementation
#include "render/tc_render_surface.h"
#include "tc_log.h"
#include <stdlib.h>
#include <string.h>

// ============================================================================
// External Callbacks (set by Python/Rust/etc binding layer)
// ============================================================================

static tc_external_render_surface_callbacks g_external_callbacks = {0};

void tc_render_surface_set_external_callbacks(
    const tc_external_render_surface_callbacks* callbacks
) {
    if (callbacks) {
        g_external_callbacks = *callbacks;
    } else {
        memset(&g_external_callbacks, 0, sizeof(g_external_callbacks));
    }
}

// ============================================================================
// External Surface VTable Implementation
// ============================================================================

static uint32_t external_get_framebuffer(tc_render_surface* s) {
    if (s->body && g_external_callbacks.get_framebuffer) {
        return g_external_callbacks.get_framebuffer(s->body);
    }
    return 0;
}

static void external_get_size(tc_render_surface* s, int* width, int* height) {
    if (s->body && g_external_callbacks.get_size) {
        g_external_callbacks.get_size(s->body, width, height);
    } else {
        if (width) *width = 0;
        if (height) *height = 0;
    }
}

static void external_make_current(tc_render_surface* s) {
    if (s->body && g_external_callbacks.make_current) {
        g_external_callbacks.make_current(s->body);
    }
}

static void external_swap_buffers(tc_render_surface* s) {
    if (s->body && g_external_callbacks.swap_buffers) {
        g_external_callbacks.swap_buffers(s->body);
    }
}

static uintptr_t external_context_key(tc_render_surface* s) {
    if (s->body && g_external_callbacks.context_key) {
        return g_external_callbacks.context_key(s->body);
    }
    return (uintptr_t)s->body;
}

static void external_poll_events(tc_render_surface* s) {
    if (s->body && g_external_callbacks.poll_events) {
        g_external_callbacks.poll_events(s->body);
    }
}

static void external_get_window_size(tc_render_surface* s, int* width, int* height) {
    if (s->body && g_external_callbacks.get_window_size) {
        g_external_callbacks.get_window_size(s->body, width, height);
    } else {
        // Fallback to framebuffer size
        external_get_size(s, width, height);
    }
}

static bool external_should_close(tc_render_surface* s) {
    if (s->body && g_external_callbacks.should_close) {
        return g_external_callbacks.should_close(s->body);
    }
    return false;
}

static void external_set_should_close(tc_render_surface* s, bool value) {
    if (s->body && g_external_callbacks.set_should_close) {
        g_external_callbacks.set_should_close(s->body, value);
    }
}

static void external_get_cursor_pos(tc_render_surface* s, double* x, double* y) {
    if (s->body && g_external_callbacks.get_cursor_pos) {
        g_external_callbacks.get_cursor_pos(s->body, x, y);
    } else {
        if (x) *x = 0.0;
        if (y) *y = 0.0;
    }
}

static void external_destroy(tc_render_surface* s) {
    if (s->body && g_external_callbacks.destroy) {
        g_external_callbacks.destroy(s->body);
    }
}

static const tc_render_surface_vtable g_external_vtable = {
    .get_framebuffer = external_get_framebuffer,
    .get_size = external_get_size,
    .make_current = external_make_current,
    .swap_buffers = external_swap_buffers,
    .context_key = external_context_key,
    .poll_events = external_poll_events,
    .get_window_size = external_get_window_size,
    .should_close = external_should_close,
    .set_should_close = external_set_should_close,
    .get_cursor_pos = external_get_cursor_pos,
    .destroy = external_destroy,
};

// ============================================================================
// External Surface Lifecycle
// ============================================================================

tc_render_surface* tc_render_surface_new_external(void* body) {
    if (!body) {
        tc_log(TC_LOG_ERROR, "[tc_render_surface_new_external] body is NULL");
        return NULL;
    }

    tc_render_surface* s = (tc_render_surface*)calloc(1, sizeof(tc_render_surface));
    if (!s) {
        tc_log(TC_LOG_ERROR, "[tc_render_surface_new_external] allocation failed");
        return NULL;
    }

    tc_render_surface_init(s, &g_external_vtable);
    s->body = body;

    // Increment refcount on body
    if (g_external_callbacks.incref) {
        g_external_callbacks.incref(body);
    }

    return s;
}

void tc_render_surface_free_external(tc_render_surface* s) {
    if (!s) return;

    // Decrement refcount on body
    if (s->body && g_external_callbacks.decref) {
        g_external_callbacks.decref(s->body);
    }

    free(s);
}

void tc_render_surface_body_incref(void* body) {
    if (body && g_external_callbacks.incref) {
        g_external_callbacks.incref(body);
    }
}

void tc_render_surface_body_decref(void* body) {
    if (body && g_external_callbacks.decref) {
        g_external_callbacks.decref(body);
    }
}
