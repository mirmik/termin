// tc_display.c - Display implementation
#include "render/tc_display.h"
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
    display->surface = surface;
    display->first_viewport = NULL;
    display->last_viewport = NULL;
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

    // Release all viewports
    tc_viewport* vp = display->first_viewport;
    while (vp) {
        tc_viewport* next = vp->display_next;
        vp->display_prev = NULL;
        vp->display_next = NULL;
        tc_viewport_release(vp);
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

void tc_display_make_current(tc_display* display) {
    if (display && display->surface) {
        tc_render_surface_make_current(display->surface);
    }
}

void tc_display_swap_buffers(tc_display* display) {
    if (display && display->surface) {
        tc_render_surface_swap_buffers(display->surface);
    }
}

// ============================================================================
// Viewport Management
// ============================================================================

void tc_display_add_viewport(tc_display* display, tc_viewport* viewport) {
    if (!display || !viewport) return;

    // Check if already in this display
    if (viewport->display_prev || viewport->display_next || display->first_viewport == viewport) {
        tc_log(TC_LOG_WARN, "[tc_display_add_viewport] viewport '%s' already in a display",
               viewport->name ? viewport->name : "(null)");
        return;
    }

    // Add to end of linked list
    viewport->display_prev = display->last_viewport;
    viewport->display_next = NULL;

    if (display->last_viewport) {
        display->last_viewport->display_next = viewport;
    } else {
        display->first_viewport = viewport;
    }
    display->last_viewport = viewport;
    display->viewport_count++;

    // Increment refcount
    tc_viewport_add_ref(viewport);

    // Update pixel rect
    int width, height;
    tc_display_get_size(display, &width, &height);
    tc_viewport_update_pixel_rect(viewport, width, height);
}

void tc_display_remove_viewport(tc_display* display, tc_viewport* viewport) {
    if (!display || !viewport) return;

    // Check if viewport is in this display
    bool found = false;
    for (tc_viewport* vp = display->first_viewport; vp; vp = vp->display_next) {
        if (vp == viewport) {
            found = true;
            break;
        }
    }

    if (!found) {
        return;
    }

    // Unlink from list
    if (viewport->display_prev) {
        viewport->display_prev->display_next = viewport->display_next;
    } else {
        display->first_viewport = viewport->display_next;
    }

    if (viewport->display_next) {
        viewport->display_next->display_prev = viewport->display_prev;
    } else {
        display->last_viewport = viewport->display_prev;
    }

    viewport->display_prev = NULL;
    viewport->display_next = NULL;
    display->viewport_count--;

    // Decrement refcount
    tc_viewport_release(viewport);
}

size_t tc_display_get_viewport_count(const tc_display* display) {
    return display ? display->viewport_count : 0;
}

tc_viewport* tc_display_get_first_viewport(const tc_display* display) {
    return display ? display->first_viewport : NULL;
}

tc_viewport* tc_display_get_viewport_at_index(const tc_display* display, size_t index) {
    if (!display || index >= display->viewport_count) return NULL;

    tc_viewport* vp = display->first_viewport;
    for (size_t i = 0; i < index && vp; i++) {
        vp = vp->display_next;
    }
    return vp;
}

// ============================================================================
// Viewport Lookup by Coordinates
// ============================================================================

tc_viewport* tc_display_viewport_at(const tc_display* display, float x, float y) {
    if (!display) return NULL;

    tc_viewport* best = NULL;
    int best_depth = -1;

    for (tc_viewport* vp = display->first_viewport; vp; vp = vp->display_next) {
        if (!vp->enabled) continue;

        float vx = vp->rect[0];
        float vy = vp->rect[1];
        float vw = vp->rect[2];
        float vh = vp->rect[3];

        if (x >= vx && x <= vx + vw && y >= vy && y <= vy + vh) {
            if (vp->depth > best_depth) {
                best = vp;
                best_depth = vp->depth;
            }
        }
    }

    return best;
}

tc_viewport* tc_display_viewport_at_screen(const tc_display* display, float px, float py) {
    if (!display) return NULL;

    int width, height;
    tc_display_get_size(display, &width, &height);

    if (width <= 0 || height <= 0) return NULL;

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

    for (tc_viewport* vp = display->first_viewport; vp; vp = vp->display_next) {
        tc_viewport_update_pixel_rect(vp, width, height);
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
