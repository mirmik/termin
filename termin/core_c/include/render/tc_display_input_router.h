// tc_display_input_router.h - Display-level input event router
// Routes OS events from tc_render_surface to per-viewport input managers.
// Finds viewport at cursor position, forwards events to viewport's tc_input_manager.
#ifndef TC_DISPLAY_INPUT_ROUTER_H
#define TC_DISPLAY_INPUT_ROUTER_H

#include "tc_types.h"
#include "render/tc_input_manager.h"
#include "render/tc_display.h"
#include "render/tc_viewport_pool.h"
#include <stdbool.h>

#ifdef __cplusplus
extern "C" {
#endif

typedef struct tc_display_input_router tc_display_input_router;

struct tc_display_input_router {
    // Embedded tc_input_manager (must be first for casting)
    tc_input_manager base;

    // Display to route events through
    tc_display* display;

    // Active viewport for drag operations (set on press, cleared on release)
    tc_viewport_handle active_viewport;

    // Focused viewport for key events (last viewport that received mouse press)
    tc_viewport_handle focused_viewport;

    // Cursor tracking
    double last_cursor_x;
    double last_cursor_y;
    bool has_cursor;
};

// Create display input router
// Automatically attaches to display's surface as input_manager
TC_API tc_display_input_router* tc_display_input_router_new(tc_display* display);

// Free display input router
TC_API void tc_display_input_router_free(tc_display_input_router* r);

// Get base tc_input_manager pointer
TC_API tc_input_manager* tc_display_input_router_base(tc_display_input_router* r);

#ifdef __cplusplus
}
#endif

#endif // TC_DISPLAY_INPUT_ROUTER_H
