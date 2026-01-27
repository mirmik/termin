// tc_display.h - Display abstraction (render target with viewports)
#ifndef TC_DISPLAY_H
#define TC_DISPLAY_H

#include "tc_types.h"
#include "render/tc_render_surface.h"
#include "render/tc_viewport.h"
#include <stdbool.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

// ============================================================================
// Display Structure
// ============================================================================

typedef struct tc_display {
    char* name;
    char* uuid;
    bool editor_only;

    // Underlying render surface
    tc_render_surface* surface;

    // Linked list of viewports
    tc_viewport* first_viewport;
    tc_viewport* last_viewport;
    size_t viewport_count;
} tc_display;

// ============================================================================
// Display Lifecycle
// ============================================================================

TC_API tc_display* tc_display_new(const char* name, tc_render_surface* surface);
TC_API void tc_display_free(tc_display* display);

// ============================================================================
// Display Properties
// ============================================================================

TC_API void tc_display_set_name(tc_display* display, const char* name);
TC_API const char* tc_display_get_name(const tc_display* display);

TC_API void tc_display_set_uuid(tc_display* display, const char* uuid);
TC_API const char* tc_display_get_uuid(const tc_display* display);

TC_API void tc_display_set_editor_only(tc_display* display, bool editor_only);
TC_API bool tc_display_get_editor_only(const tc_display* display);

TC_API void tc_display_set_surface(tc_display* display, tc_render_surface* surface);
TC_API tc_render_surface* tc_display_get_surface(const tc_display* display);

// ============================================================================
// Surface Delegation
// ============================================================================

// Get display size in pixels (delegates to surface)
TC_API void tc_display_get_size(const tc_display* display, int* width, int* height);

// Make context current (delegates to surface)
TC_API void tc_display_make_current(tc_display* display);

// Swap buffers (delegates to surface)
TC_API void tc_display_swap_buffers(tc_display* display);

// ============================================================================
// Viewport Management
// ============================================================================

// Add viewport to display (increments viewport refcount)
TC_API void tc_display_add_viewport(tc_display* display, tc_viewport* viewport);

// Remove viewport from display (decrements viewport refcount)
TC_API void tc_display_remove_viewport(tc_display* display, tc_viewport* viewport);

// Get viewport count
TC_API size_t tc_display_get_viewport_count(const tc_display* display);

// Get first viewport (for iteration)
TC_API tc_viewport* tc_display_get_first_viewport(const tc_display* display);

// Get viewport by index (O(n) - use iteration for performance)
TC_API tc_viewport* tc_display_get_viewport_at_index(const tc_display* display, size_t index);

// ============================================================================
// Viewport Lookup by Coordinates
// ============================================================================

// Find viewport at normalized coordinates (0..1), origin bottom-left (OpenGL convention)
// For screen coordinates (origin top-left), use tc_display_viewport_at_screen
// Returns viewport with highest depth if multiple overlap, NULL if none
TC_API tc_viewport* tc_display_viewport_at(
    const tc_display* display,
    float x,
    float y
);

// Find viewport at screen coordinates (pixels, origin top-left)
TC_API tc_viewport* tc_display_viewport_at_screen(
    const tc_display* display,
    float px,
    float py
);

// ============================================================================
// Pixel Rect Updates
// ============================================================================

// Update pixel_rect for all viewports based on current display size
TC_API void tc_display_update_all_pixel_rects(tc_display* display);

// ============================================================================
// Internal: Resize Handler
// ============================================================================

// Called when surface resizes - updates all viewport pixel_rects
// This is set as the surface's on_resize callback automatically
void tc_display_on_surface_resize(
    tc_render_surface* surface,
    int width,
    int height,
    void* userdata
);

#ifdef __cplusplus
}
#endif

#endif // TC_DISPLAY_H
