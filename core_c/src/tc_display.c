// tc_display.c - Display implementation
#include "render/tc_display.h"
#include "tc_gpu.h"
#include "tc_log.h"
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
// Display Lifecycle
// ============================================================================

tc_display* tc_display_new(const char* name, tc_render_surface* surface) {
    tc_display* display = (tc_display*)calloc(1, sizeof(tc_display));
    if (!display) {
        tc_log(TC_LOG_ERROR, "[tc_display_new] allocation failed");
        return NULL;
    }

    display->name = tc_strdup(name ? name : "Display");
    display->uuid = NULL;
    display->editor_only = false;
    display->enabled = true;
    display->surface = surface;
    display->first_viewport = TC_VIEWPORT_HANDLE_INVALID;
    display->last_viewport = TC_VIEWPORT_HANDLE_INVALID;
    display->viewport_count = 0;

    // Subscribe to surface resize
    if (surface) {
        tc_render_surface_set_on_resize(surface, tc_display_on_surface_resize, display);
    }

    return display;
}

void tc_display_free(tc_display* display) {
    if (!display) return;

    // Unsubscribe from surface resize
    if (display->surface) {
        tc_render_surface_set_on_resize(display->surface, NULL, NULL);
    }

    // Free all viewports in the linked list
    tc_viewport_handle vp = display->first_viewport;
    while (tc_viewport_handle_valid(vp)) {
        tc_viewport_handle next = tc_viewport_get_display_next(vp);
        tc_viewport_set_display_prev(vp, TC_VIEWPORT_HANDLE_INVALID);
        tc_viewport_set_display_next(vp, TC_VIEWPORT_HANDLE_INVALID);
        tc_viewport_free(vp);
        vp = next;
    }

    free(display->name);
    free(display->uuid);
    free(display);
}

// ============================================================================
// Display Properties
// ============================================================================

void tc_display_set_name(tc_display* display, const char* name) {
    if (display) tc_strset(&display->name, name);
}

const char* tc_display_get_name(const tc_display* display) {
    return display ? display->name : NULL;
}

void tc_display_set_uuid(tc_display* display, const char* uuid) {
    if (display) tc_strset(&display->uuid, uuid);
}

const char* tc_display_get_uuid(const tc_display* display) {
    return display ? display->uuid : NULL;
}

void tc_display_set_editor_only(tc_display* display, bool editor_only) {
    if (display) display->editor_only = editor_only;
}

bool tc_display_get_editor_only(const tc_display* display) {
    return display ? display->editor_only : false;
}

void tc_display_set_enabled(tc_display* display, bool enabled) {
    if (display) display->enabled = enabled;
}

bool tc_display_get_enabled(const tc_display* display) {
    return display ? display->enabled : false;
}

void tc_display_set_surface(tc_display* display, tc_render_surface* surface) {
    if (!display) return;

    // Unsubscribe from old surface
    if (display->surface) {
        tc_render_surface_set_on_resize(display->surface, NULL, NULL);
    }

    display->surface = surface;

    // Subscribe to new surface
    if (surface) {
        tc_render_surface_set_on_resize(surface, tc_display_on_surface_resize, display);
        // Update pixel rects with new surface size
        tc_display_update_all_pixel_rects(display);
    }
}

tc_render_surface* tc_display_get_surface(const tc_display* display) {
    return display ? display->surface : NULL;
}

// ============================================================================
// Surface Delegation
// ============================================================================

void tc_display_get_size(const tc_display* display, int* width, int* height) {
    if (display && display->surface) {
        tc_render_surface_get_size(display->surface, width, height);
    } else {
        if (width) *width = 0;
        if (height) *height = 0;
    }
}

void tc_display_get_window_size(const tc_display* display, int* width, int* height) {
    if (display && display->surface) {
        tc_render_surface_get_window_size(display->surface, width, height);
    } else {
        if (width) *width = 0;
        if (height) *height = 0;
    }
}

void tc_display_get_cursor_pos(const tc_display* display, double* x, double* y) {
    if (display && display->surface) {
        tc_render_surface_get_cursor_pos(display->surface, x, y);
    } else {
        if (x) *x = 0.0;
        if (y) *y = 0.0;
    }
}

void tc_display_make_current(tc_display* display) {
    if (display && display->surface) {
        tc_render_surface_make_current(display->surface);
        tc_gpu_set_context_key(tc_render_surface_context_key(display->surface));
    }
}

void tc_display_swap_buffers(tc_display* display) {
    if (display && display->surface) {
        tc_render_surface_swap_buffers(display->surface);
    }
}

bool tc_display_should_close(const tc_display* display) {
    if (display && display->surface) {
        return tc_render_surface_should_close(display->surface);
    }
    return false;
}

void tc_display_set_should_close(tc_display* display, bool value) {
    if (display && display->surface) {
        tc_render_surface_set_should_close(display->surface, value);
    }
}

// ============================================================================
// Viewport Management
// ============================================================================

void tc_display_add_viewport(tc_display* display, tc_viewport_handle viewport) {
    if (!display || !tc_viewport_handle_valid(viewport)) return;

    // Check if already in a display (has prev or next links)
    tc_viewport_handle prev = tc_viewport_get_display_prev(viewport);
    tc_viewport_handle next = tc_viewport_get_display_next(viewport);
    if (tc_viewport_handle_valid(prev) || tc_viewport_handle_valid(next)) {
        tc_log(TC_LOG_WARN, "[tc_display_add_viewport] viewport '%s' already in a display",
               tc_viewport_get_name(viewport) ? tc_viewport_get_name(viewport) : "(null)");
        return;
    }

    // Check if it's already the first viewport
    if (tc_viewport_handle_eq(display->first_viewport, viewport)) {
        return;
    }

    // Add to end of linked list
    tc_viewport_set_display_prev(viewport, display->last_viewport);
    tc_viewport_set_display_next(viewport, TC_VIEWPORT_HANDLE_INVALID);

    if (tc_viewport_handle_valid(display->last_viewport)) {
        tc_viewport_set_display_next(display->last_viewport, viewport);
    } else {
        display->first_viewport = viewport;
    }
    display->last_viewport = viewport;
    display->viewport_count++;

    // Update pixel rect
    int width, height;
    tc_display_get_size(display, &width, &height);
    tc_viewport_update_pixel_rect(viewport, width, height);
}

void tc_display_remove_viewport(tc_display* display, tc_viewport_handle viewport) {
    if (!display || !tc_viewport_handle_valid(viewport)) return;

    // Check if viewport is in this display
    bool found = false;
    tc_viewport_handle vp = display->first_viewport;
    while (tc_viewport_handle_valid(vp)) {
        if (tc_viewport_handle_eq(vp, viewport)) {
            found = true;
            break;
        }
        vp = tc_viewport_get_display_next(vp);
    }

    if (!found) {
        return;
    }

    // Unlink from list
    tc_viewport_handle prev = tc_viewport_get_display_prev(viewport);
    tc_viewport_handle next = tc_viewport_get_display_next(viewport);

    if (tc_viewport_handle_valid(prev)) {
        tc_viewport_set_display_next(prev, next);
    } else {
        display->first_viewport = next;
    }

    if (tc_viewport_handle_valid(next)) {
        tc_viewport_set_display_prev(next, prev);
    } else {
        display->last_viewport = prev;
    }

    tc_viewport_set_display_prev(viewport, TC_VIEWPORT_HANDLE_INVALID);
    tc_viewport_set_display_next(viewport, TC_VIEWPORT_HANDLE_INVALID);
    display->viewport_count--;
}

size_t tc_display_get_viewport_count(const tc_display* display) {
    return display ? display->viewport_count : 0;
}

tc_viewport_handle tc_display_get_first_viewport(const tc_display* display) {
    return display ? display->first_viewport : TC_VIEWPORT_HANDLE_INVALID;
}

tc_viewport_handle tc_display_get_viewport_at_index(const tc_display* display, size_t index) {
    if (!display || index >= display->viewport_count) return TC_VIEWPORT_HANDLE_INVALID;

    tc_viewport_handle vp = display->first_viewport;
    for (size_t i = 0; i < index && tc_viewport_handle_valid(vp); i++) {
        vp = tc_viewport_get_display_next(vp);
    }
    return vp;
}

// ============================================================================
// Viewport Lookup by Coordinates
// ============================================================================

tc_viewport_handle tc_display_viewport_at(const tc_display* display, float x, float y) {
    if (!display) return TC_VIEWPORT_HANDLE_INVALID;

    tc_viewport_handle best = TC_VIEWPORT_HANDLE_INVALID;
    int best_depth = -1;

    tc_viewport_handle vp = display->first_viewport;
    while (tc_viewport_handle_valid(vp)) {
        if (!tc_viewport_get_enabled(vp)) {
            vp = tc_viewport_get_display_next(vp);
            continue;
        }

        float vx, vy, vw, vh;
        tc_viewport_get_rect(vp, &vx, &vy, &vw, &vh);

        if (x >= vx && x <= vx + vw && y >= vy && y <= vy + vh) {
            int depth = tc_viewport_get_depth(vp);
            if (depth > best_depth) {
                best = vp;
                best_depth = depth;
            }
        }

        vp = tc_viewport_get_display_next(vp);
    }

    return best;
}

tc_viewport_handle tc_display_viewport_at_screen(const tc_display* display, float px, float py) {
    if (!display) return TC_VIEWPORT_HANDLE_INVALID;

    int width, height;
    tc_display_get_size(display, &width, &height);

    if (width <= 0 || height <= 0) return TC_VIEWPORT_HANDLE_INVALID;

    // Convert screen coordinates (origin top-left) to normalized (origin bottom-left)
    float nx = px / (float)width;
    float ny = 1.0f - (py / (float)height);

    return tc_display_viewport_at(display, nx, ny);
}

// ============================================================================
// Pixel Rect Updates
// ============================================================================

void tc_display_update_all_pixel_rects(tc_display* display) {
    if (!display) return;

    int width, height;
    tc_display_get_size(display, &width, &height);

    tc_viewport_handle vp = display->first_viewport;
    while (tc_viewport_handle_valid(vp)) {
        tc_viewport_update_pixel_rect(vp, width, height);
        vp = tc_viewport_get_display_next(vp);
    }
}

// ============================================================================
// Resize Handler
// ============================================================================

void tc_display_on_surface_resize(
    tc_render_surface* surface,
    int width,
    int height,
    void* userdata
) {
    (void)surface;
    (void)width;
    (void)height;

    tc_display* display = (tc_display*)userdata;
    if (display) {
        tc_display_update_all_pixel_rects(display);
    }
}
