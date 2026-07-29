// tc_display_input_router.c - Display-level input event router
#include "tc_display_input_router_internal.h"
#include "render/tc_display.h"
#include "render/tc_viewport.h"
#include "tc_input_event.h"
#include <tcbase/tc_log.h>
#include <stdlib.h>

// ============================================================================
// Forward declarations for vtable
// ============================================================================

static void router_on_pointer(tc_input_manager* self, uint64_t pointer_id, int device, int phase,
                              double x, double y, float pressure);
static void router_on_mouse_button(tc_input_manager* self, int button, int action, int mods,
                                   uint32_t click_count);
static void router_on_mouse_move(tc_input_manager* self, double x, double y);
static void router_on_scroll(tc_input_manager* self, double x, double y, int mods);
static void router_on_key(tc_input_manager* self, int key, int scancode, int action, int mods);
static void router_on_char(tc_input_manager* self, uint32_t codepoint);
static void router_destroy(tc_input_manager* self);

static const tc_input_manager_vtable g_router_vtable = {
    .on_pointer = router_on_pointer,
    .on_mouse_button = router_on_mouse_button,
    .on_mouse_move = router_on_mouse_move,
    .on_scroll = router_on_scroll,
    .on_key = router_on_key,
    .on_char = router_on_char,
    .destroy = router_destroy,
};

// ============================================================================
// Lifecycle
// ============================================================================

typedef struct tc_pointer_capture {
    uint64_t pointer_id;
    int device;
    tc_viewport_handle viewport;
    struct tc_pointer_capture* next;
} tc_pointer_capture;

typedef struct tc_display_input_router {
    tc_input_manager base;
    tc_display_handle display;
    tc_viewport_handle active_viewport;
    tc_viewport_handle focused_viewport;
    double last_cursor_x;
    double last_cursor_y;
    bool has_cursor;
    tc_pointer_capture* pointer_captures;
} tc_display_input_router;

tc_input_manager* tc_display_input_router_create(tc_display_handle display) {
    if (!tc_display_handle_valid(display)) return NULL;

    tc_display_input_router* r = (tc_display_input_router*)calloc(1, sizeof(tc_display_input_router));
    if (!r) {
        tc_log(TC_LOG_ERROR, "[tc_display_input_router_create] allocation failed");
        return NULL;
    }

    tc_input_manager_init(&r->base, &g_router_vtable);
    r->base.userdata = r;
    r->display = display;
    r->active_viewport = TC_VIEWPORT_HANDLE_INVALID;
    r->focused_viewport = TC_VIEWPORT_HANDLE_INVALID;
    r->last_cursor_x = 0.0;
    r->last_cursor_y = 0.0;
    r->has_cursor = false;
    r->pointer_captures = NULL;

    return &r->base;
}

void tc_display_input_router_destroy(tc_input_manager* endpoint) {
    if (!endpoint) return;
    tc_display_input_router* r = (tc_display_input_router*)endpoint->userdata;
    if (!r || &r->base != endpoint) {
        tc_log(TC_LOG_ERROR, "[tc_display_input_router_destroy] invalid endpoint");
        return;
    }
    tc_pointer_capture* capture = r->pointer_captures;
    while (capture) {
        tc_pointer_capture* next = capture->next;
        free(capture);
        capture = next;
    }
    r->display = TC_DISPLAY_HANDLE_INVALID;
    free(r);
}

// ============================================================================
// Helpers
// ============================================================================

static inline tc_display_input_router* router_from(tc_input_manager* self) {
    return self ? (tc_display_input_router*)self->userdata : NULL;
}

static tc_viewport_handle router_viewport_at_cursor(tc_display_input_router* r) {
    if (!tc_display_alive(r->display)) return TC_VIEWPORT_HANDLE_INVALID;
    return tc_display_viewport_at_screen(r->display, (float)r->last_cursor_x, (float)r->last_cursor_y);
}

static tc_pointer_capture* router_find_capture(
    tc_display_input_router* r,
    uint64_t pointer_id,
    int device,
    tc_pointer_capture** previous
) {
    tc_pointer_capture* prev = NULL;
    tc_pointer_capture* current = r ? r->pointer_captures : NULL;
    while (current) {
        if (current->pointer_id == pointer_id && current->device == device) {
            if (previous) *previous = prev;
            return current;
        }
        prev = current;
        current = current->next;
    }
    if (previous) *previous = NULL;
    return NULL;
}

static bool router_capture_pointer(
    tc_display_input_router* r,
    uint64_t pointer_id,
    int device,
    tc_viewport_handle viewport
) {
    tc_pointer_capture* existing = router_find_capture(r, pointer_id, device, NULL);
    if (existing) {
        existing->viewport = viewport;
        return true;
    }
    tc_pointer_capture* capture = (tc_pointer_capture*)calloc(1, sizeof(tc_pointer_capture));
    if (!capture) {
        tc_log(TC_LOG_ERROR, "[tc_display_input_router] pointer capture allocation failed");
        return false;
    }
    capture->pointer_id = pointer_id;
    capture->device = device;
    capture->viewport = viewport;
    capture->next = r->pointer_captures;
    r->pointer_captures = capture;
    return true;
}

static void router_release_pointer(
    tc_display_input_router* r,
    uint64_t pointer_id,
    int device
) {
    tc_pointer_capture* previous = NULL;
    tc_pointer_capture* capture = router_find_capture(r, pointer_id, device, &previous);
    if (!capture) return;
    if (previous) {
        previous->next = capture->next;
    } else {
        r->pointer_captures = capture->next;
    }
    free(capture);
}

// ============================================================================
// Event handlers
// ============================================================================

static void router_on_pointer(tc_input_manager* self, uint64_t pointer_id, int device, int phase,
                              double x, double y, float pressure) {
    tc_display_input_router* r = router_from(self);
    if (!r || !tc_display_alive(r->display)) return;

    tc_pointer_capture* capture = router_find_capture(r, pointer_id, device, NULL);
    tc_viewport_handle viewport = capture
        ? capture->viewport
        : tc_display_viewport_at_screen(r->display, (float)x, (float)y);

    if (phase == TC_POINTER_DOWN) {
        if (!tc_viewport_handle_valid(viewport)) return;
        if (!router_capture_pointer(r, pointer_id, device, viewport)) return;
        r->focused_viewport = viewport;
    }

    if (tc_viewport_handle_valid(viewport) && tc_viewport_alive(viewport)) {
        tc_input_manager* vm = tc_viewport_get_input_manager(viewport);
        if (vm) {
            tc_input_manager_on_pointer(
                vm, pointer_id, device, phase, x, y, pressure);
        }
    }

    if (phase == TC_POINTER_UP || phase == TC_POINTER_CANCEL) {
        router_release_pointer(r, pointer_id, device);
    }
}

static void router_on_mouse_button(tc_input_manager* self, int button, int action, int mods,
                                   uint32_t click_count) {
    tc_display_input_router* r = router_from(self);
    if (!r) return;

    tc_viewport_handle viewport = router_viewport_at_cursor(r);

    // Track active/focused viewport
    if (action == TC_INPUT_PRESS) {
        r->active_viewport = viewport;
        r->focused_viewport = viewport;
    }
    if (action == TC_INPUT_RELEASE) {
        if (tc_viewport_handle_valid(r->active_viewport)) {
            viewport = r->active_viewport;
        }
        r->active_viewport = TC_VIEWPORT_HANDLE_INVALID;
    }

    // Forward to viewport's input manager
    if (tc_viewport_handle_valid(viewport) && tc_viewport_alive(viewport)) {
        tc_input_manager* vm = tc_viewport_get_input_manager(viewport);
        if (vm) {
            tc_input_manager_on_mouse_button(vm, button, action, mods, click_count);
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
    if (!tc_viewport_handle_valid(viewport) && tc_display_alive(r->display)) {
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
    if (!tc_viewport_handle_valid(viewport) && tc_display_alive(r->display)) {
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
