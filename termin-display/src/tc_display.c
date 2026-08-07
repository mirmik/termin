// tc_display.c - Display implementation
#include "render/tc_display.h"
#include "tc_display_input_router_internal.h"
#include "tc_input_event.h"
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <tcbase/tc_log.h>
#include <tcbase/tc_pool.h>

#define MAX_DISPLAYS 256u
#define INITIAL_POOL_CAPACITY 16u

typedef struct tc_display {
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

static tc_pool g_display_pool;
static tc_pool_generation_epoch g_display_generation_epoch;
static bool g_display_pool_initialized = false;

// ============================================================================
// Helper Functions
// ============================================================================

static char* tc_strdup(const char* s) {
    if (s == NULL)
        return NULL;
    size_t len = strlen(s) + 1;
    char* copy = (char*)malloc(len);
    if (copy)
        memcpy(copy, s, len);
    return copy;
}

static void tc_display_strset(char** dest, const char* src) {
    free(*dest);
    *dest = tc_strdup(src);
}

static void tc_display_init_empty(tc_display* display) {
    memset(display, 0, sizeof(*display));
    display->first_viewport = TC_VIEWPORT_HANDLE_INVALID;
    display->last_viewport = TC_VIEWPORT_HANDLE_INVALID;
}

static bool tc_display_surface_can_be_adopted(tc_render_surface* surface, const char* operation) {
    if (!surface)
        return true;
    if (!surface->vtable || !surface->vtable->get_size || !surface->vtable->resize ||
        !surface->vtable->get_color_texture_id || !surface->vtable->get_graphics_domain_key ||
        !surface->vtable->destroy) {
        tc_log(TC_LOG_ERROR, "[%s] surface has an incomplete vtable", operation);
        return false;
    }
    if (!surface->deleter) {
        tc_log(TC_LOG_ERROR, "[%s] surface has no storage deleter", operation);
        return false;
    }
    return true;
}

static bool
tc_display_destroy_owned_surface(tc_display_handle handle, tc_render_surface* surface, const char* operation) {
    if (!surface)
        return true;
    surface->on_resize = NULL;
    surface->on_resize_userdata = NULL;
    if (!tc_render_surface_detach(surface, handle)) {
        tc_log(TC_LOG_ERROR, "[%s] owned surface attachment is inconsistent", operation);
        return false;
    }
    return tc_render_surface_delete_unowned(surface);
}

static tc_display* tc_display_get_alive(tc_display_handle handle, const char* operation) {
    if (!g_display_pool_initialized) {
        tc_log(TC_LOG_ERROR, "[%s] display pool is not initialized", operation);
        return NULL;
    }
    if (!tc_display_handle_valid(handle) || handle.index >= g_display_pool.capacity) {
        tc_log(TC_LOG_ERROR, "[%s] invalid display handle (%u, %u)", operation, handle.index, handle.generation);
        return NULL;
    }
    tc_handle pool_handle = {handle.index, handle.generation};
    if (!tc_pool_is_valid(&g_display_pool, pool_handle)) {
        tc_log(TC_LOG_ERROR, "[%s] stale display handle (%u, %u)", operation, handle.index, handle.generation);
        return NULL;
    }
    return (tc_display*)tc_pool_get_unchecked(&g_display_pool, handle.index);
}

// ============================================================================
// Display Lifecycle
// ============================================================================

void tc_display_pool_init(void) {
    if (g_display_pool_initialized) {
        tc_log(TC_LOG_WARN, "[tc_display_pool] already initialized");
        return;
    }
    const tc_pool_config config = {
        .max_capacity = MAX_DISPLAYS,
        .initial_generation = 0u,
        .allocate_low_indices_first = true,
        .name = "tc_display_pool",
        .generation_epoch = &g_display_generation_epoch,
    };
    if (!tc_pool_init_ex(&g_display_pool, sizeof(tc_display), INITIAL_POOL_CAPACITY, &config)) {
        tc_log(TC_LOG_ERROR, "[tc_display_pool] storage allocation failed");
        return;
    }
    for (uint32_t i = 0; i < g_display_pool.capacity; ++i) {
        tc_display_init_empty((tc_display*)tc_pool_get_unchecked(&g_display_pool, i));
    }
    g_display_pool_initialized = true;
}

static void tc_display_cleanup(tc_display_handle handle, tc_display* display) {
    if (display->surface) {
        tc_render_surface* surface = display->surface;
        display->surface = NULL;
        if (!tc_display_destroy_owned_surface(handle, surface, "tc_display_cleanup")) {
            tc_log(TC_LOG_ERROR, "[tc_display_cleanup] failed to destroy owned surface");
        }
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
    if (!g_display_pool_initialized)
        return;
    if (tc_pool_count(&g_display_pool) != 0u) {
        tc_log(TC_LOG_ERROR,
               "[tc_display_pool] shutdown with %zu live display(s)",
               (size_t)tc_pool_count(&g_display_pool));
    }
    for (uint32_t i = 0; i < g_display_pool.capacity; ++i) {
        if (g_display_pool.states[i] == TC_SLOT_OCCUPIED) {
            tc_display* display = (tc_display*)tc_pool_get_unchecked(&g_display_pool, i);
            tc_display_handle handle = {i, g_display_pool.generations[i]};
            tc_display_cleanup(handle, display);
        }
    }
    tc_pool_free(&g_display_pool);
    g_display_pool_initialized = false;
}

bool tc_display_alive(tc_display_handle handle) {
    const tc_handle pool_handle = {handle.index, handle.generation};
    return g_display_pool_initialized && tc_display_handle_valid(handle) &&
           tc_pool_is_valid(&g_display_pool, pool_handle);
}

size_t tc_display_pool_count(void) {
    return g_display_pool_initialized ? tc_pool_count(&g_display_pool) : 0u;
}

tc_display_handle tc_display_new(const char* name, tc_render_surface* surface) {
    if (!g_display_pool_initialized) {
        tc_log(TC_LOG_ERROR, "[tc_display_new] display pool is not initialized");
        return TC_DISPLAY_HANDLE_INVALID;
    }
    if (!tc_display_surface_can_be_adopted(surface, "tc_display_new")) {
        return TC_DISPLAY_HANDLE_INVALID;
    }
    tc_handle pool_handle = tc_pool_alloc(&g_display_pool);
    if (tc_handle_is_invalid(pool_handle)) {
        return TC_DISPLAY_HANDLE_INVALID;
    }
    tc_display* display = (tc_display*)tc_pool_get_unchecked(&g_display_pool, pool_handle.index);
    tc_display_init_empty(display);
    tc_display_handle handle = {pool_handle.index, pool_handle.generation};

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
        tc_display_init_empty(display);
        tc_pool_free_slot(&g_display_pool, pool_handle);
        return TC_DISPLAY_HANDLE_INVALID;
    }
    display->first_viewport = TC_VIEWPORT_HANDLE_INVALID;
    display->last_viewport = TC_VIEWPORT_HANDLE_INVALID;
    display->viewport_count = 0;

    if (surface && !tc_render_surface_attach(surface, handle)) {
        tc_log(TC_LOG_ERROR, "[tc_display_new] surface attachment failed");
        tc_display_input_router_destroy(display->input_endpoint);
        free(display->name);
        tc_display_init_empty(display);
        tc_pool_free_slot(&g_display_pool, pool_handle);
        return TC_DISPLAY_HANDLE_INVALID;
    }
    if (surface) {
        display->surface = surface;
        surface->on_resize = tc_display_on_surface_resize;
        surface->on_resize_userdata = surface;
    }

    return handle;
}

bool tc_display_free(tc_display_handle handle) {
    tc_display* display = tc_display_get_alive(handle, "tc_display_free");
    if (!display)
        return false;
    tc_display_cleanup(handle, display);
    tc_display_init_empty(display);
    const tc_handle pool_handle = {handle.index, handle.generation};
    return tc_pool_free_slot(&g_display_pool, pool_handle);
}

// ============================================================================
// Display Properties
// ============================================================================

void tc_display_set_name(tc_display_handle handle, const char* name) {
    tc_display* display = tc_display_get_alive(handle, "tc_display_set_name");
    if (display)
        tc_display_strset(&display->name, name);
}

const char* tc_display_get_name(tc_display_handle handle) {
    tc_display* display = tc_display_get_alive(handle, "tc_display_get_name");
    return display ? display->name : NULL;
}

void tc_display_set_uuid(tc_display_handle handle, const char* uuid) {
    tc_display* display = tc_display_get_alive(handle, "tc_display_set_uuid");
    if (display)
        tc_display_strset(&display->uuid, uuid);
}

const char* tc_display_get_uuid(tc_display_handle handle) {
    tc_display* display = tc_display_get_alive(handle, "tc_display_get_uuid");
    return display ? display->uuid : NULL;
}

void tc_display_set_editor_only(tc_display_handle handle, bool editor_only) {
    tc_display* display = tc_display_get_alive(handle, "tc_display_set_editor_only");
    if (display)
        display->editor_only = editor_only;
}

bool tc_display_get_editor_only(tc_display_handle handle) {
    tc_display* display = tc_display_get_alive(handle, "tc_display_get_editor_only");
    return display ? display->editor_only : false;
}

void tc_display_set_enabled(tc_display_handle handle, bool enabled) {
    tc_display* display = tc_display_get_alive(handle, "tc_display_set_enabled");
    if (display)
        display->enabled = enabled;
}

bool tc_display_get_enabled(tc_display_handle handle) {
    tc_display* display = tc_display_get_alive(handle, "tc_display_get_enabled");
    return display ? display->enabled : false;
}

void tc_display_set_auto_remove_when_empty(tc_display_handle handle, bool value) {
    tc_display* display = tc_display_get_alive(handle, "tc_display_set_auto_remove_when_empty");
    if (display)
        display->auto_remove_when_empty = value;
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
    if (surface == display->surface)
        return true;

    if (!tc_display_surface_can_be_adopted(surface, "tc_display_set_surface")) {
        return false;
    }
    if (display->surface && !tc_display_handle_eq(display->surface->attached_display, handle)) {
        tc_log(TC_LOG_ERROR, "[tc_display_set_surface] current owned surface attachment is inconsistent");
        return false;
    }

    // Claim the replacement before touching the current attachment. A failed
    // duplicate attach therefore leaves both displays unchanged.
    if (surface && !tc_render_surface_attach(surface, handle))
        return false;

    tc_render_surface* previous = display->surface;
    display->surface = surface;

    // Subscribe to new surface
    if (surface) {
        surface->on_resize = tc_display_on_surface_resize;
        surface->on_resize_userdata = surface;
        // Update pixel rects with new surface size
        tc_display_update_all_pixel_rects(handle);
    }
    if (previous && !tc_display_destroy_owned_surface(handle, previous, "tc_display_set_surface")) {
        tc_log(TC_LOG_ERROR, "[tc_display_set_surface] failed to destroy replaced owned surface");
    }
    return true;
}

tc_render_surface* tc_display_get_surface(tc_display_handle handle) {
    tc_display* display = tc_display_get_alive(handle, "tc_display_get_surface");
    return display ? display->surface : NULL;
}

bool tc_display_resize(tc_display_handle handle, int width, int height) {
    tc_display* display = tc_display_get_alive(handle, "tc_display_resize");
    if (!display || !display->surface) {
        tc_log(TC_LOG_ERROR, "[tc_display_resize] display has no render surface");
        return false;
    }
    if (width <= 0 || height <= 0) {
        tc_log(TC_LOG_ERROR, "[tc_display_resize] positive pixel dimensions are required");
        return false;
    }
    if (!tc_render_surface_resize(display->surface, width, height)) {
        tc_log(TC_LOG_ERROR, "[tc_display_resize] surface rejected resize to %dx%d", width, height);
        return false;
    }
    return true;
}

uint32_t tc_display_get_color_texture_id(tc_display_handle handle) {
    tc_display* display = tc_display_get_alive(handle, "tc_display_get_color_texture_id");
    return display && display->surface ? tc_render_surface_get_color_texture_id(display->surface) : 0u;
}

uintptr_t tc_display_get_graphics_domain_key(tc_display_handle handle) {
    tc_display* display = tc_display_get_alive(handle, "tc_display_get_graphics_domain_key");
    return display && display->surface ? tc_render_surface_get_graphics_domain_key(display->surface) : 0u;
}

bool tc_display_validate_output(tc_display_handle handle,
                                uintptr_t expected_graphics_domain_key,
                                uint32_t* color_texture_id) {
    tc_display* display = tc_display_get_alive(handle, "tc_display_validate_output");
    if (!display || !display->surface) {
        if (color_texture_id)
            *color_texture_id = 0u;
        tc_log(TC_LOG_ERROR, "[tc_display_validate_output] display has no render surface");
        return false;
    }
    return tc_render_surface_validate_output(display->surface, expected_graphics_domain_key, color_texture_id);
}

static bool tc_display_validate_pointer_event(tc_display* display, double x, double y, const char* operation) {
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

bool tc_display_dispatch_pointer(
    tc_display_handle handle, uint64_t pointer_id, int device, int phase, double x, double y, float pressure) {
    tc_display* display = tc_display_get_alive(handle, "tc_display_dispatch_pointer");
    if (!tc_display_validate_pointer_event(display, x, y, "tc_display_dispatch_pointer"))
        return false;
    if (device < TC_POINTER_DEVICE_MOUSE || device > TC_POINTER_DEVICE_PEN) {
        tc_log(TC_LOG_ERROR, "[tc_display_dispatch_pointer] invalid pointer device %d", device);
        return false;
    }
    if (phase < TC_POINTER_DOWN || phase > TC_POINTER_CANCEL) {
        tc_log(TC_LOG_ERROR, "[tc_display_dispatch_pointer] invalid pointer phase %d", phase);
        return false;
    }
    if (!isfinite(pressure)) {
        tc_log(TC_LOG_ERROR, "[tc_display_dispatch_pointer] non-finite pressure");
        return false;
    }
    tc_input_manager_on_pointer(display->input_endpoint, pointer_id, device, phase, x, y, pressure);
    return true;
}

bool tc_display_dispatch_pointer_move(tc_display_handle handle, double x, double y) {
    tc_display* display = tc_display_get_alive(handle, "tc_display_dispatch_pointer_move");
    if (!tc_display_validate_pointer_event(display, x, y, "tc_display_dispatch_pointer_move"))
        return false;
    tc_input_manager_on_mouse_move(display->input_endpoint, x, y);
    return true;
}

bool tc_display_dispatch_pointer_button(
    tc_display_handle handle, double x, double y, int button, int action, int mods, uint32_t click_count) {
    tc_display* display = tc_display_get_alive(handle, "tc_display_dispatch_pointer_button");
    if (!tc_display_validate_pointer_event(display, x, y, "tc_display_dispatch_pointer_button"))
        return false;
    tc_input_manager_on_mouse_move(display->input_endpoint, x, y);
    tc_input_manager_on_mouse_button(display->input_endpoint, button, action, mods, click_count);
    return true;
}

bool tc_display_dispatch_wheel(tc_display_handle handle, double x, double y, double wheel_x, double wheel_y, int mods) {
    tc_display* display = tc_display_get_alive(handle, "tc_display_dispatch_wheel");
    if (!tc_display_validate_pointer_event(display, x, y, "tc_display_dispatch_wheel"))
        return false;
    if (!isfinite(wheel_x) || !isfinite(wheel_y)) {
        tc_log(TC_LOG_ERROR, "[tc_display_dispatch_wheel] non-finite wheel delta");
        return false;
    }
    tc_input_manager_on_mouse_move(display->input_endpoint, x, y);
    tc_input_manager_on_scroll(display->input_endpoint, wheel_x, wheel_y, mods);
    return true;
}

bool tc_display_dispatch_key(tc_display_handle handle, int key, int scancode, int action, int mods) {
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

bool tc_display_dispatch_text_utf8(tc_display_handle handle, const char* text_utf8) {
    tc_display* display = tc_display_get_alive(handle, "tc_display_dispatch_text_utf8");
    if (!display || !display->input_endpoint || !text_utf8) {
        tc_log(TC_LOG_ERROR,
               "[tc_display_dispatch_text_utf8] display input endpoint or text "
               "is unavailable");
        return false;
    }
    tc_input_manager_on_text(display->input_endpoint, text_utf8);
    return true;
}

bool tc_display_dispatch_focus_lost(tc_display_handle handle) {
    tc_display* display = tc_display_get_alive(handle, "tc_display_dispatch_focus_lost");
    if (!display || !display->input_endpoint) {
        tc_log(TC_LOG_ERROR,
               "[tc_display_dispatch_focus_lost] display input endpoint is "
               "unavailable");
        return false;
    }
    tc_input_manager_on_focus_lost(display->input_endpoint);
    return true;
}

bool tc_display_set_input_platform_services(tc_display_handle handle, const tc_input_platform_services* services) {
    tc_display* display = tc_display_get_alive(handle, "tc_display_set_input_platform_services");
    if (!display || !display->input_endpoint) {
        tc_log(TC_LOG_ERROR,
               "[tc_display_set_input_platform_services] display input endpoint "
               "is unavailable");
        return false;
    }
    tc_input_manager_set_platform_services(display->input_endpoint, services);
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
        if (width)
            *width = 0;
        if (height)
            *height = 0;
    }
}

// ============================================================================
// Viewport Management
// ============================================================================

void tc_display_add_viewport(tc_display_handle handle, tc_viewport_handle viewport) {
    tc_display* display = tc_display_get_alive(handle, "tc_display_add_viewport");
    if (!display || !tc_viewport_handle_valid(viewport))
        return;

    // Check if already in a display (has prev or next links)
    tc_viewport_handle prev = tc_viewport_get_display_prev(viewport);
    tc_viewport_handle next = tc_viewport_get_display_next(viewport);
    if (tc_viewport_handle_valid(prev) || tc_viewport_handle_valid(next)) {
        tc_log(TC_LOG_WARN,
               "[tc_display_add_viewport] viewport '%s' already in a display",
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
    if (!display || !tc_viewport_handle_valid(viewport))
        return;

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
    if (!display || index >= display->viewport_count)
        return TC_VIEWPORT_HANDLE_INVALID;

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
    if (!display)
        return TC_VIEWPORT_HANDLE_INVALID;

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
    if (!display)
        return TC_VIEWPORT_HANDLE_INVALID;

    int width, height;
    tc_display_get_size(handle, &width, &height);

    if (width <= 0 || height <= 0)
        return TC_VIEWPORT_HANDLE_INVALID;

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
    if (!display)
        return;

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

void tc_display_on_surface_resize(tc_render_surface* surface, int width, int height, void* userdata) {
    (void)width;
    (void)height;
    tc_render_surface* callback_surface = (tc_render_surface*)userdata;
    if (callback_surface != surface)
        return;
    tc_display_update_all_pixel_rects(surface->attached_display);
}
