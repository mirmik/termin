// tc_viewport_input_manager.h - Per-viewport input manager
// Dispatches input events to the viewport's scene input handlers
// and internal entities. No viewport lookup — viewport is known at construction.
#ifndef TC_VIEWPORT_INPUT_MANAGER_H
#define TC_VIEWPORT_INPUT_MANAGER_H

#include "tc_types.h"
#include "render/tc_input_manager.h"
#include "render/tc_viewport_pool.h"
#include <stdbool.h>

#ifdef __cplusplus
extern "C" {
#endif

typedef struct tc_viewport_input_manager tc_viewport_input_manager;

struct tc_viewport_input_manager {
    // Embedded tc_input_manager (must be first for casting)
    tc_input_manager base;

    // The viewport this manager handles
    tc_viewport_handle viewport;

    // Cursor tracking (for delta computation and mouse_button position)
    double last_cursor_x;
    double last_cursor_y;
    bool has_cursor;
};

// Create viewport input manager and auto-attach to viewport
TC_API tc_viewport_input_manager* tc_viewport_input_manager_new(tc_viewport_handle viewport);

// Free viewport input manager (clears viewport's input_manager if still set)
TC_API void tc_viewport_input_manager_free(tc_viewport_input_manager* m);

#ifdef __cplusplus
}
#endif

#endif // TC_VIEWPORT_INPUT_MANAGER_H
