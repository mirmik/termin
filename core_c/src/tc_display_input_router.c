// tc_display_input_router.c - Display-level input event router
#include "render/tc_display_input_router.h"
#include "render/tc_viewport.h"
#include "render/tc_render_surface.h"
#include "tc_log.h"
#include <stdlib.h>

// ============================================================================
// Forward declarations for vtable
// ============================================================================

static void router_on_mouse_button(tc_input_manager* self, int button, int action, int mods);
static void router_on_mouse_move(tc_input_manager* self, double x, double y);
static void router_on_scroll(tc_input_manager* self, double x, double y, int mods);
static void router_on_key(tc_input_manager* self, int key, int scancode, int action, int mods);
static void router_on_char(tc_input_manager* self, uint32_t codepoint);
static void router_destroy(tc_input_manager* self);

static const tc_input_manager_vtable g_router_vtable = {
    router_on_mouse_button,
    router_on_mouse_move,
    router_on_scroll,
    router_on_key,
    router_on_char,
    router_destroy
};

// ============================================================================
// Lifecycle
// ============================================================================

tc_display_input_router* tc_display_input_router_new(tc_display* display) {
    if (!display) return NULL;

    tc_display_input_router* r = (tc_display_input_router*)calloc(1, sizeof(tc_display_input_router));
    if (!r) return NULL;

    tc_input_manager_init(&r->base, &g_router_vtable);
    r->base.userdata = r;
    r->display = display;
    r->active_viewport = TC_VIEWPORT_HANDLE_INVALID;
    r->focused_viewport = TC_VIEWPORT_HANDLE_INVALID;
    r->last_cursor_x = 0.0;
    r->last_cursor_y = 0.0;
    r->has_cursor = false;

    // Auto-attach to display's surface
    if (display->surface) {
        tc_render_surface_set_input_manager(display->surface, &r->base);
    }

    return r;
}

void tc_display_input_router_free(tc_display_input_router* r) {
    if (!r) return;

    // Detach from surface
    if (r->display && r->display->surface) {
        if (r->display->surface->input_manager == &r->base) {
            tc_render_surface_set_input_manager(r->display->surface, NULL);
        }
    }

    free(r);
}

tc_input_manager* tc_display_input_router_base(tc_display_input_router* r) {
    return r ? &r->base : NULL;
}

// ============================================================================
// Helpers
// ============================================================================

static inline tc_display_input_router* router_from(tc_input_manager* self) {
    return self ? (tc_display_input_router*)self->userdata : NULL;
}

static tc_viewport_handle router_viewport_at_cursor(tc_display_input_router* r) {
    if (!r->display) return TC_VIEWPORT_HANDLE_INVALID;
    return tc_display_viewport_at_screen(r->display, (float)r->last_cursor_x, (float)r->last_cursor_y);
}

// ============================================================================
// Event handlers
// ============================================================================

static void router_on_mouse_button(tc_input_manager* self, int button, int action, int mods) {
    tc_display_input_router* r = router_from(self);
    if (!r) return;

    tc_viewport_handle viewport = router_viewport_at_cursor(r);

    // Track active/focused viewport
    if (action == TC_INPUT_PRESS) {
        r->active_viewport = viewport;
        r->focused_viewport = viewport;
    }
    if (action == TC_INPUT_RELEASE) {
        if (!tc_viewport_handle_valid(viewport)) {
            viewport = r->active_viewport;
        }
        r->active_viewport = TC_VIEWPORT_HANDLE_INVALID;
    }

    // Forward to viewport's input manager
    if (tc_viewport_handle_valid(viewport) && tc_viewport_alive(viewport)) {
        tc_input_manager* vm = tc_viewport_get_input_manager(viewport);
        if (vm) {
            tc_input_manager_on_mouse_button(vm, button, action, mods);
        }
    }
}

static void router_on_mouse_move(tc_input_manager* self, double x, double y) {
    tc_display_input_router* r = router_from(self);
    if (!r) return;

    r->last_cursor_x = x;
    r->last_cursor_y = y;
    r->has_cursor = true;

    // Use active viewport during drag, otherwise find viewport at cursor
    tc_viewport_handle viewport = r->active_viewport;
    if (!tc_viewport_handle_valid(viewport)) {
        viewport = router_viewport_at_cursor(r);
    }

    // Forward to viewport's input manager
    if (tc_viewport_handle_valid(viewport) && tc_viewport_alive(viewport)) {
        tc_input_manager* vm = tc_viewport_get_input_manager(viewport);
        if (vm) {
            tc_input_manager_on_mouse_move(vm, x, y);
        }
    }
}

static void router_on_scroll(tc_input_manager* self, double x, double y, int mods) {
    tc_display_input_router* r = router_from(self);
    if (!r) return;

    tc_viewport_handle viewport = router_viewport_at_cursor(r);
    if (!tc_viewport_handle_valid(viewport)) {
        viewport = r->active_viewport;
    }

    // Forward to viewport's input manager
    if (tc_viewport_handle_valid(viewport) && tc_viewport_alive(viewport)) {
        tc_input_manager* vm = tc_viewport_get_input_manager(viewport);
        if (vm) {
            tc_input_manager_on_scroll(vm, x, y, mods);
        }
    }
}

static void router_on_key(tc_input_manager* self, int key, int scancode, int action, int mods) {
    tc_display_input_router* r = router_from(self);
    if (!r) return;

    // Priority: active viewport > focused viewport > first viewport
    tc_viewport_handle viewport = r->active_viewport;
    if (!tc_viewport_handle_valid(viewport)) {
        viewport = r->focused_viewport;
    }
    if (!tc_viewport_handle_valid(viewport) && r->display) {
        viewport = tc_display_get_first_viewport(r->display);
    }

    // Forward to viewport's input manager
    if (tc_viewport_handle_valid(viewport) && tc_viewport_alive(viewport)) {
        tc_input_manager* vm = tc_viewport_get_input_manager(viewport);
        if (vm) {
            tc_input_manager_on_key(vm, key, scancode, action, mods);
        }
    }
}

static void router_on_char(tc_input_manager* self, uint32_t codepoint) {
    tc_display_input_router* r = router_from(self);
    if (!r) return;

    // Same priority as key events
    tc_viewport_handle viewport = r->active_viewport;
    if (!tc_viewport_handle_valid(viewport)) {
        viewport = r->focused_viewport;
    }
    if (!tc_viewport_handle_valid(viewport) && r->display) {
        viewport = tc_display_get_first_viewport(r->display);
    }

    if (tc_viewport_handle_valid(viewport) && tc_viewport_alive(viewport)) {
        tc_input_manager* vm = tc_viewport_get_input_manager(viewport);
        if (vm) {
            tc_input_manager_on_char(vm, codepoint);
        }
    }
}

static void router_destroy(tc_input_manager* self) {
    (void)self;
}
