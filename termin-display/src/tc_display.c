// tc_display.c - Display implementation
#include "render/tc_display.h"
#include "tc_display_input_router_internal.h"
#include <tcbase/tc_log.h>
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define MAX_DISPLAYS 256u
#define INITIAL_POOL_CAPACITY 16u

typedef struct tc_display {
    uint32_t generation;
    bool alive;
    char* name;
    char* uuid;
    bool editor_only;
    bool enabled;
    bool auto_remove_when_empty;
    tc_render_surface* surface;
    tc_input_manager* input_endpoint;
    tc_viewport_handle first_viewport;
    tc_viewport_handle last_viewport;
    size_t viewport_count;
} tc_display;

typedef struct {
    tc_display* items;
    uint32_t* free_stack;
    size_t free_count;
    size_t capacity;
    size_t count;
} tc_display_pool;

static tc_display_pool* g_display_pool = NULL;

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

static void tc_display_strset(char** dest, const char* src) {
    free(*dest);
    *dest = tc_strdup(src);
}

static void tc_display_init_empty(tc_display* display, uint32_t generation) {
    memset(display, 0, sizeof(*display));
    display->generation = generation;
    display->first_viewport = TC_VIEWPORT_HANDLE_INVALID;
    display->last_viewport = TC_VIEWPORT_HANDLE_INVALID;
}

static tc_display* tc_display_get_alive(tc_display_handle handle, const char* operation) {
    if (!g_display_pool) {
        tc_log(TC_LOG_ERROR, "[%s] display pool is not initialized", operation);
        return NULL;
    }
    if (!tc_display_handle_valid(handle) || handle.index >= g_display_pool->capacity) {
        tc_log(TC_LOG_ERROR, "[%s] invalid display handle (%u, %u)", operation,
               handle.index, handle.generation);
        return NULL;
    }
    tc_display* display = &g_display_pool->items[handle.index];
    if (!display->alive || display->generation != handle.generation) {
        tc_log(TC_LOG_ERROR, "[%s] stale display handle (%u, %u)", operation,
               handle.index, handle.generation);
        return NULL;
    }
    return display;
}

static bool tc_display_pool_grow(void) {
    size_t old_capacity = g_display_pool->capacity;
    size_t new_capacity = old_capacity * 2u;
    if (new_capacity > MAX_DISPLAYS) new_capacity = MAX_DISPLAYS;
    if (new_capacity <= old_capacity) {
        tc_log(TC_LOG_ERROR, "[tc_display_pool] max capacity reached");
        return false;
    }

    tc_display* items = (tc_display*)malloc(new_capacity * sizeof(tc_display));
    uint32_t* free_stack = (uint32_t*)malloc(new_capacity * sizeof(uint32_t));
    if (!items || !free_stack) {
        tc_log(TC_LOG_ERROR, "[tc_display_pool] grow allocation failed");
        free(items);
        free(free_stack);
        return false;
    }

    memcpy(items, g_display_pool->items, old_capacity * sizeof(tc_display));
    memcpy(free_stack, g_display_pool->free_stack,
           g_display_pool->free_count * sizeof(uint32_t));
    free(g_display_pool->items);
    free(g_display_pool->free_stack);
    g_display_pool->items = items;
    g_display_pool->free_stack = free_stack;
    for (size_t i = old_capacity; i < new_capacity; ++i) {
        tc_display_init_empty(&g_display_pool->items[i], 0u);
        g_display_pool->free_stack[g_display_pool->free_count++] =
            (uint32_t)(new_capacity - 1u - (i - old_capacity));
    }
    g_display_pool->capacity = new_capacity;
    return true;
}

// ============================================================================
// Display Lifecycle
// ============================================================================

void tc_display_pool_init(void) {
    if (g_display_pool) {
        tc_log(TC_LOG_WARN, "[tc_display_pool] already initialized");
        return;
    }
    g_display_pool = (tc_display_pool*)calloc(1, sizeof(tc_display_pool));
    if (!g_display_pool) {
        tc_log(TC_LOG_ERROR, "[tc_display_pool] allocation failed");
        return;
    }
    g_display_pool->capacity = INITIAL_POOL_CAPACITY;
    g_display_pool->items = (tc_display*)calloc(
        g_display_pool->capacity, sizeof(tc_display));
    g_display_pool->free_stack = (uint32_t*)malloc(
        g_display_pool->capacity * sizeof(uint32_t));
    if (!g_display_pool->items || !g_display_pool->free_stack) {
        tc_log(TC_LOG_ERROR, "[tc_display_pool] storage allocation failed");
        free(g_display_pool->items);
        free(g_display_pool->free_stack);
        free(g_display_pool);
        g_display_pool = NULL;
        return;
    }
    for (size_t i = 0; i < g_display_pool->capacity; ++i) {
        tc_display_init_empty(&g_display_pool->items[i], 0u);
        g_display_pool->free_stack[i] =
            (uint32_t)(g_display_pool->capacity - 1u - i);
    }
    g_display_pool->free_count = g_display_pool->capacity;
}

static void tc_display_cleanup(tc_display_handle handle, tc_display* display) {
    if (display->surface) {
        display->surface->on_resize = NULL;
        display->surface->on_resize_userdata = NULL;
        tc_render_surface_detach(display->surface, handle);
        display->surface = NULL;
    }

    tc_display_input_router_destroy(display->input_endpoint);
    display->input_endpoint = NULL;

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
}

void tc_display_pool_shutdown(void) {
    if (!g_display_pool) return;
    if (g_display_pool->count != 0u) {
        tc_log(TC_LOG_ERROR, "[tc_display_pool] shutdown with %zu live display(s)",
               g_display_pool->count);
    }
    for (uint32_t i = 0; i < g_display_pool->capacity; ++i) {
        tc_display* display = &g_display_pool->items[i];
        if (display->alive) {
            tc_display_handle handle = {i, display->generation};
            tc_display_cleanup(handle, display);
        }
    }
    free(g_display_pool->items);
    free(g_display_pool->free_stack);
    free(g_display_pool);
    g_display_pool = NULL;
}

bool tc_display_alive(tc_display_handle handle) {
    if (!g_display_pool || !tc_display_handle_valid(handle) ||
        handle.index >= g_display_pool->capacity) return false;
    tc_display* display = &g_display_pool->items[handle.index];
    return display->alive && display->generation == handle.generation;
}

size_t tc_display_pool_count(void) {
    return g_display_pool ? g_display_pool->count : 0u;
}

tc_display_handle tc_display_new(const char* name, tc_render_surface* surface) {
    if (!g_display_pool) {
        tc_log(TC_LOG_ERROR, "[tc_display_new] display pool is not initialized");
        return TC_DISPLAY_HANDLE_INVALID;
    }
    if (g_display_pool->free_count == 0u && !tc_display_pool_grow()) {
        return TC_DISPLAY_HANDLE_INVALID;
    }
    uint32_t index = g_display_pool->free_stack[--g_display_pool->free_count];
    tc_display* display = &g_display_pool->items[index];
    uint32_t generation = display->generation;
    tc_display_init_empty(display, generation);
    display->alive = true;
    tc_display_handle handle = {index, generation};

    display->name = tc_strdup(name ? name : "Display");
    display->uuid = NULL;
    display->editor_only = false;
    display->enabled = true;
    display->auto_remove_when_empty = false;
    display->surface = NULL;
    display->input_endpoint = tc_display_input_router_create(handle);
    if (!display->input_endpoint) {
        tc_log(TC_LOG_ERROR, "[tc_display_new] input endpoint allocation failed");
        free(display->name);
        tc_display_init_empty(display, generation + 1u);
        g_display_pool->free_stack[g_display_pool->free_count++] = index;
        return TC_DISPLAY_HANDLE_INVALID;
    }
    display->first_viewport = TC_VIEWPORT_HANDLE_INVALID;
    display->last_viewport = TC_VIEWPORT_HANDLE_INVALID;
    display->viewport_count = 0;

    if (surface && !tc_render_surface_attach(surface, handle)) {
        tc_log(TC_LOG_ERROR, "[tc_display_new] surface attachment failed");
        tc_display_input_router_destroy(display->input_endpoint);
        free(display->name);
        tc_display_init_empty(display, generation + 1u);
        g_display_pool->free_stack[g_display_pool->free_count++] = index;
        return TC_DISPLAY_HANDLE_INVALID;
    }
    if (surface) {
        display->surface = surface;
        surface->on_resize = tc_display_on_surface_resize;
        surface->on_resize_userdata = surface;
    }

    g_display_pool->count++;
    return handle;
}

bool tc_display_free(tc_display_handle handle) {
    tc_display* display = tc_display_get_alive(handle, "tc_display_free");
    if (!display) return false;
    uint32_t generation = display->generation;
    tc_display_cleanup(handle, display);
    tc_display_init_empty(display, generation + 1u);
    g_display_pool->free_stack[g_display_pool->free_count++] = handle.index;
    g_display_pool->count--;
    return true;
}

// ============================================================================
// Display Properties
// ============================================================================

void tc_display_set_name(tc_display_handle handle, const char* name) {
    tc_display* display = tc_display_get_alive(handle, "tc_display_set_name");
    if (display) tc_display_strset(&display->name, name);
}

const char* tc_display_get_name(tc_display_handle handle) {
    tc_display* display = tc_display_get_alive(handle, "tc_display_get_name");
    return display ? display->name : NULL;
}

void tc_display_set_uuid(tc_display_handle handle, const char* uuid) {
    tc_display* display = tc_display_get_alive(handle, "tc_display_set_uuid");
    if (display) tc_display_strset(&display->uuid, uuid);
}

const char* tc_display_get_uuid(tc_display_handle handle) {
    tc_display* display = tc_display_get_alive(handle, "tc_display_get_uuid");
    return display ? display->uuid : NULL;
}

void tc_display_set_editor_only(tc_display_handle handle, bool editor_only) {
    tc_display* display = tc_display_get_alive(handle, "tc_display_set_editor_only");
    if (display) display->editor_only = editor_only;
}

bool tc_display_get_editor_only(tc_display_handle handle) {
    tc_display* display = tc_display_get_alive(handle, "tc_display_get_editor_only");
    return display ? display->editor_only : false;
}

void tc_display_set_enabled(tc_display_handle handle, bool enabled) {
    tc_display* display = tc_display_get_alive(handle, "tc_display_set_enabled");
    if (display) display->enabled = enabled;
}

bool tc_display_get_enabled(tc_display_handle handle) {
    tc_display* display = tc_display_get_alive(handle, "tc_display_get_enabled");
    return display ? display->enabled : false;
}

void tc_display_set_auto_remove_when_empty(tc_display_handle handle, bool value) {
    tc_display* display = tc_display_get_alive(handle, "tc_display_set_auto_remove_when_empty");
    if (display) display->auto_remove_when_empty = value;
}

bool tc_display_get_auto_remove_when_empty(tc_display_handle handle) {
    tc_display* display = tc_display_get_alive(handle, "tc_display_get_auto_remove_when_empty");
    return display ? display->auto_remove_when_empty : false;
}

bool tc_display_set_surface(tc_display_handle handle, tc_render_surface* surface) {
    tc_display* display = tc_display_get_alive(handle, "tc_display_set_surface");
    if (!display) {
        return false;
    }
    if (surface == display->surface) return true;

    // Claim the replacement before touching the current attachment. A failed
    // duplicate attach therefore leaves both displays unchanged.
    if (surface && !tc_render_surface_attach(surface, handle)) return false;

    if (display->surface) {
        display->surface->on_resize = NULL;
        display->surface->on_resize_userdata = NULL;
        tc_render_surface_detach(display->surface, handle);
    }

    display->surface = surface;

    // Subscribe to new surface
    if (surface) {
        surface->on_resize = tc_display_on_surface_resize;
        surface->on_resize_userdata = surface;
        // Update pixel rects with new surface size
        tc_display_update_all_pixel_rects(handle);
    }
    return true;
}

tc_render_surface* tc_display_get_surface(tc_display_handle handle) {
    tc_display* display = tc_display_get_alive(handle, "tc_display_get_surface");
    return display ? display->surface : NULL;
}

static bool tc_display_validate_pointer_event(tc_display* display, double x, double y,
                                              const char* operation) {
    if (!display || !display->input_endpoint) {
        tc_log(TC_LOG_ERROR, "[%s] display input endpoint is unavailable", operation);
        return false;
    }
    if (!isfinite(x) || !isfinite(y)) {
        tc_log(TC_LOG_ERROR, "[%s] non-finite display pixel coordinates", operation);
        return false;
    }
    return true;
}

tc_input_manager* tc_display_get_input_manager(tc_display_handle handle) {
    tc_display* display = tc_display_get_alive(handle, "tc_display_get_input_manager");
    if (!display) {
        return NULL;
    }
    return display->input_endpoint;
}

bool tc_display_dispatch_pointer_move(tc_display_handle handle, double x, double y) {
    tc_display* display = tc_display_get_alive(handle, "tc_display_dispatch_pointer_move");
    if (!tc_display_validate_pointer_event(display, x, y,
                                           "tc_display_dispatch_pointer_move")) return false;
    tc_input_manager_on_mouse_move(display->input_endpoint, x, y);
    return true;
}

bool tc_display_dispatch_pointer_button(tc_display_handle handle, double x, double y,
                                        int button, int action, int mods,
                                        uint32_t click_count) {
    tc_display* display = tc_display_get_alive(handle, "tc_display_dispatch_pointer_button");
    if (!tc_display_validate_pointer_event(display, x, y,
                                           "tc_display_dispatch_pointer_button")) return false;
    tc_input_manager_on_mouse_move(display->input_endpoint, x, y);
    tc_input_manager_on_mouse_button(display->input_endpoint, button, action, mods, click_count);
    return true;
}

bool tc_display_dispatch_wheel(tc_display_handle handle, double x, double y,
                               double wheel_x, double wheel_y, int mods) {
    tc_display* display = tc_display_get_alive(handle, "tc_display_dispatch_wheel");
    if (!tc_display_validate_pointer_event(display, x, y,
                                           "tc_display_dispatch_wheel")) return false;
    if (!isfinite(wheel_x) || !isfinite(wheel_y)) {
        tc_log(TC_LOG_ERROR, "[tc_display_dispatch_wheel] non-finite wheel delta");
        return false;
    }
    tc_input_manager_on_mouse_move(display->input_endpoint, x, y);
    tc_input_manager_on_scroll(display->input_endpoint, wheel_x, wheel_y, mods);
    return true;
}

bool tc_display_dispatch_key(tc_display_handle handle, int key, int scancode,
                             int action, int mods) {
    tc_display* display = tc_display_get_alive(handle, "tc_display_dispatch_key");
    if (!display || !display->input_endpoint) {
        tc_log(TC_LOG_ERROR, "[tc_display_dispatch_key] display input endpoint is unavailable");
        return false;
    }
    tc_input_manager_on_key(display->input_endpoint, key, scancode, action, mods);
    return true;
}

bool tc_display_dispatch_text(tc_display_handle handle, uint32_t codepoint) {
    tc_display* display = tc_display_get_alive(handle, "tc_display_dispatch_text");
    if (!display || !display->input_endpoint) {
        tc_log(TC_LOG_ERROR, "[tc_display_dispatch_text] display input endpoint is unavailable");
        return false;
    }
    tc_input_manager_on_char(display->input_endpoint, codepoint);
    return true;
}

// ============================================================================
// Surface Delegation
// ============================================================================

void tc_display_get_size(tc_display_handle handle, int* width, int* height) {
    tc_display* display = tc_display_get_alive(handle, "tc_display_get_size");
    if (display && display->surface) {
        tc_render_surface_get_size(display->surface, width, height);
    } else {
        if (width) *width = 0;
        if (height) *height = 0;
    }
}

// ============================================================================
// Viewport Management
// ============================================================================

void tc_display_add_viewport(tc_display_handle handle, tc_viewport_handle viewport) {
    tc_display* display = tc_display_get_alive(handle, "tc_display_add_viewport");
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
    tc_display_get_size(handle, &width, &height);
    tc_viewport_update_pixel_rect(viewport, width, height);
}

void tc_display_remove_viewport(tc_display_handle handle, tc_viewport_handle viewport) {
    tc_display* display = tc_display_get_alive(handle, "tc_display_remove_viewport");
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

size_t tc_display_get_viewport_count(tc_display_handle handle) {
    tc_display* display = tc_display_get_alive(handle, "tc_display_get_viewport_count");
    return display ? display->viewport_count : 0;
}

tc_viewport_handle tc_display_get_first_viewport(tc_display_handle handle) {
    tc_display* display = tc_display_get_alive(handle, "tc_display_get_first_viewport");
    return display ? display->first_viewport : TC_VIEWPORT_HANDLE_INVALID;
}

tc_viewport_handle tc_display_get_viewport_at_index(tc_display_handle handle, size_t index) {
    tc_display* display = tc_display_get_alive(handle, "tc_display_get_viewport_at_index");
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

tc_viewport_handle tc_display_viewport_at(tc_display_handle handle, float x, float y) {
    tc_display* display = tc_display_get_alive(handle, "tc_display_viewport_at");
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

tc_viewport_handle tc_display_viewport_at_screen(tc_display_handle handle, float px, float py) {
    tc_display* display = tc_display_get_alive(handle, "tc_display_viewport_at_screen");
    if (!display) return TC_VIEWPORT_HANDLE_INVALID;

    int width, height;
    tc_display_get_size(handle, &width, &height);

    if (width <= 0 || height <= 0) return TC_VIEWPORT_HANDLE_INVALID;

    // Convert screen coordinates (origin top-left) to normalized (origin bottom-left)
    float nx = px / (float)width;
    float ny = 1.0f - (py / (float)height);

    return tc_display_viewport_at(handle, nx, ny);
}

// ============================================================================
// Pixel Rect Updates
// ============================================================================

void tc_display_update_all_pixel_rects(tc_display_handle handle) {
    tc_display* display = tc_display_get_alive(handle, "tc_display_update_all_pixel_rects");
    if (!display) return;

    int width, height;
    tc_display_get_size(handle, &width, &height);

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
    (void)width;
    (void)height;
    tc_render_surface* callback_surface = (tc_render_surface*)userdata;
    if (callback_surface != surface) return;
    tc_display_update_all_pixel_rects(surface->attached_display);
}
