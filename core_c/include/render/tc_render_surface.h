// tc_render_surface.h - Abstract render surface (window, offscreen FBO, etc.)
// Language-agnostic interface for render targets
#ifndef TC_RENDER_SURFACE_H
#define TC_RENDER_SURFACE_H

#include "tc_types.h"
#include <tgfx/tc_gpu_context.h>
#include "render/tc_input_manager.h"
#include <stdbool.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

// Forward declarations
typedef struct tc_render_surface tc_render_surface;
typedef struct tc_render_surface_vtable tc_render_surface_vtable;

// ============================================================================
// Resize Callback
// ============================================================================

typedef void (*tc_render_surface_resize_fn)(
    tc_render_surface* surface,
    int width,
    int height,
    void* userdata
);

// ============================================================================
// Render Surface VTable
// ============================================================================

struct tc_render_surface_vtable {
    // Get framebuffer handle (0 for default/window, custom for offscreen)
    uint32_t (*get_framebuffer)(tc_render_surface* self);

    // Get surface size in pixels (framebuffer size)
    void (*get_size)(tc_render_surface* self, int* width, int* height);

    // Make OpenGL context current
    void (*make_current)(tc_render_surface* self);

    // Swap buffers (present result). No-op for offscreen surfaces.
    void (*swap_buffers)(tc_render_surface* self);

    // Unique key for caching VAO/shaders per context
    uintptr_t (*context_key)(tc_render_surface* self);

    // Poll events (for window surfaces). No-op for offscreen.
    void (*poll_events)(tc_render_surface* self);

    // Window-specific methods (NULL for offscreen surfaces)
    // Get logical window size (may differ from framebuffer on HiDPI)
    void (*get_window_size)(tc_render_surface* self, int* width, int* height);

    // Check if window should close
    bool (*should_close)(tc_render_surface* self);

    // Set should close flag
    void (*set_should_close)(tc_render_surface* self, bool value);

    // Get cursor position in window pixels
    void (*get_cursor_pos)(tc_render_surface* self, double* x, double* y);

    // Cleanup
    void (*destroy)(tc_render_surface* self);

    // Share group key — surfaces with the same key share GL resources
    // (textures, shaders, VBO/EBO). NULL = fallback to context_key (no sharing).
    uintptr_t (*share_group_key)(tc_render_surface* self);
};

// ============================================================================
// Render Surface Structure
// ============================================================================

struct tc_render_surface {
    // Virtual method table
    const tc_render_surface_vtable* vtable;

    // External object (PyObject*, etc.) for external surfaces
    void* body;

    // Resize callback
    tc_render_surface_resize_fn on_resize;
    void* on_resize_userdata;

    // Input manager (optional, for window surfaces)
    tc_input_manager* input_manager;

    // Per-context GPU resource state (lazy-created on first make_current)
    tc_gpu_context* gpu_context;
};

// ============================================================================
// Initialization
// ============================================================================

static inline void tc_render_surface_init(
    tc_render_surface* s,
    const tc_render_surface_vtable* vtable
) {
    s->vtable = vtable;
    s->body = NULL;
    s->on_resize = NULL;
    s->on_resize_userdata = NULL;
    s->input_manager = NULL;
    s->gpu_context = NULL;
}

// Set input manager for surface
static inline void tc_render_surface_set_input_manager(
    tc_render_surface* s,
    tc_input_manager* input_manager
) {
    if (s) {
        s->input_manager = input_manager;
    }
}

// Get input manager from surface
static inline tc_input_manager* tc_render_surface_get_input_manager(tc_render_surface* s) {
    return s ? s->input_manager : NULL;
}

// ============================================================================
// VTable Dispatch (null-safe)
// ============================================================================

static inline uint32_t tc_render_surface_get_framebuffer(tc_render_surface* s) {
    if (s && s->vtable && s->vtable->get_framebuffer) {
        return s->vtable->get_framebuffer(s);
    }
    return 0;
}

static inline void tc_render_surface_get_size(tc_render_surface* s, int* width, int* height) {
    if (s && s->vtable && s->vtable->get_size) {
        s->vtable->get_size(s, width, height);
    } else {
        if (width) *width = 0;
        if (height) *height = 0;
    }
}

static inline void tc_render_surface_make_current(tc_render_surface* s) {
    if (s && s->vtable && s->vtable->make_current) {
        s->vtable->make_current(s);
    }
}

static inline void tc_render_surface_swap_buffers(tc_render_surface* s) {
    if (s && s->vtable && s->vtable->swap_buffers) {
        s->vtable->swap_buffers(s);
    }
}

static inline uintptr_t tc_render_surface_context_key(tc_render_surface* s) {
    if (s && s->vtable && s->vtable->context_key) {
        return s->vtable->context_key(s);
    }
    return (uintptr_t)s;
}

static inline void tc_render_surface_destroy(tc_render_surface* s) {
    if (s && s->vtable && s->vtable->destroy) {
        s->vtable->destroy(s);
    }
}

static inline uintptr_t tc_render_surface_share_group_key(tc_render_surface* s) {
    if (s && s->vtable && s->vtable->share_group_key) {
        return s->vtable->share_group_key(s);
    }
    // Fallback: same as context_key (no sharing, each surface = own group)
    return tc_render_surface_context_key(s);
}

static inline void tc_render_surface_poll_events(tc_render_surface* s) {
    if (s && s->vtable && s->vtable->poll_events) {
        s->vtable->poll_events(s);
    }
}

static inline void tc_render_surface_get_window_size(tc_render_surface* s, int* width, int* height) {
    if (s && s->vtable && s->vtable->get_window_size) {
        s->vtable->get_window_size(s, width, height);
    } else {
        // Fallback to framebuffer size
        tc_render_surface_get_size(s, width, height);
    }
}

static inline bool tc_render_surface_should_close(tc_render_surface* s) {
    if (s && s->vtable && s->vtable->should_close) {
        return s->vtable->should_close(s);
    }
    return false;
}

static inline void tc_render_surface_set_should_close(tc_render_surface* s, bool value) {
    if (s && s->vtable && s->vtable->set_should_close) {
        s->vtable->set_should_close(s, value);
    }
}

static inline void tc_render_surface_get_cursor_pos(tc_render_surface* s, double* x, double* y) {
    if (s && s->vtable && s->vtable->get_cursor_pos) {
        s->vtable->get_cursor_pos(s, x, y);
    } else {
        if (x) *x = 0.0;
        if (y) *y = 0.0;
    }
}

// ============================================================================
// Resize Callback Management
// ============================================================================

static inline void tc_render_surface_set_on_resize(
    tc_render_surface* s,
    tc_render_surface_resize_fn callback,
    void* userdata
) {
    if (s) {
        s->on_resize = callback;
        s->on_resize_userdata = userdata;
    }
}

// Call this from surface implementations when size changes
static inline void tc_render_surface_notify_resize(
    tc_render_surface* s,
    int width,
    int height
) {
    if (s && s->on_resize) {
        s->on_resize(s, width, height, s->on_resize_userdata);
    }
}

// ============================================================================
// External Surface Support (for Python/Rust/C#)
// ============================================================================

// Create external surface with custom vtable
// - body: pointer to external object (e.g., PyObject*)
// - vtable: vtable for this surface type (one per type, shared by all instances)
// Python side owns the tc_render_surface and frees it when done.
TC_API tc_render_surface* tc_render_surface_new_external(
    void* body,
    const tc_render_surface_vtable* vtable
);

// Free external surface
TC_API void tc_render_surface_free_external(tc_render_surface* s);

#ifdef __cplusplus
}
#endif

#endif // TC_RENDER_SURFACE_H
