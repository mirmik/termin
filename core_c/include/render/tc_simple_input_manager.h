// tc_simple_input_manager.h - Simple input manager for display
// Routes input events to scene InputComponents via vtable
#ifndef TC_SIMPLE_INPUT_MANAGER_H
#define TC_SIMPLE_INPUT_MANAGER_H

#include "tc_types.h"
#include "render/tc_input_manager.h"
#include "render/tc_display.h"
#include "render/tc_viewport_pool.h"
#include <stdbool.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

// Forward declarations
typedef struct tc_simple_input_manager tc_simple_input_manager;

// ============================================================================
// Simple Input Manager Structure
// ============================================================================

struct tc_simple_input_manager {
    // Embedded tc_input_manager (must be first for casting)
    tc_input_manager base;

    // Display to route events to
    tc_display* display;

    // Active viewport for drag operations
    tc_viewport_handle active_viewport;

    // Cursor tracking
    double last_cursor_x;
    double last_cursor_y;
    bool has_cursor;
};

// ============================================================================
// Lifecycle
// ============================================================================

// Create simple input manager for display
// Automatically attaches to display's surface
TC_API tc_simple_input_manager* tc_simple_input_manager_new(tc_display* display);

// Free simple input manager
TC_API void tc_simple_input_manager_free(tc_simple_input_manager* m);

// Get base tc_input_manager pointer (exported for FFI)
TC_API tc_input_manager* tc_simple_input_manager_base(tc_simple_input_manager* m);

// ============================================================================
// Accessors (inline for C/C++ internal use)
// ============================================================================

// Get base tc_input_manager pointer (for attaching to surface)
static inline tc_input_manager* tc_simple_input_manager_get_input_manager(
    tc_simple_input_manager* m
) {
    return m ? &m->base : NULL;
}

// Get display
static inline tc_display* tc_simple_input_manager_get_display(
    tc_simple_input_manager* m
) {
    return m ? m->display : NULL;
}

#ifdef __cplusplus
}
#endif

#endif // TC_SIMPLE_INPUT_MANAGER_H
