// tc_input_manager.c - Input manager implementation
#include "render/tc_input_manager.h"
#include <tcbase/tc_log.h>
#include <stdlib.h>

// ============================================================================
// Input Manager Lifecycle
// ============================================================================

tc_input_manager* tc_input_manager_new(
    const tc_input_manager_vtable* vtable,
    void* body
) {
    if (!vtable) {
        tc_log(TC_LOG_ERROR, "[tc_input_manager_new] vtable is NULL");
        return NULL;
    }

    tc_input_manager* m = (tc_input_manager*)calloc(1, sizeof(tc_input_manager));
    if (!m) {
        tc_log(TC_LOG_ERROR, "[tc_input_manager_new] allocation failed");
        return NULL;
    }

    tc_input_manager_init(m, vtable);
    m->body = body;

    return m;
}

void tc_input_manager_free(tc_input_manager* m) {
    if (!m) return;
    tc_input_manager_destroy(m);
    free(m);
}

// ============================================================================
// Exported Dispatch Functions (for C#/FFI - inline versions not exported)
// ============================================================================

TC_API void tc_input_manager_dispatch_mouse_button(
    tc_input_manager* m, int button, int action, int mods
) {
    tc_input_manager_on_mouse_button(m, button, action, mods);
}

TC_API void tc_input_manager_dispatch_mouse_move(
    tc_input_manager* m, double x, double y
) {
    tc_input_manager_on_mouse_move(m, x, y);
}

TC_API void tc_input_manager_dispatch_scroll(
    tc_input_manager* m, double x, double y, int mods
) {
    tc_input_manager_on_scroll(m, x, y, mods);
}

TC_API void tc_input_manager_dispatch_key(
    tc_input_manager* m, int key, int scancode, int action, int mods
) {
    tc_input_manager_on_key(m, key, scancode, action, mods);
}

TC_API void tc_input_manager_dispatch_char(tc_input_manager* m, uint32_t codepoint) {
    tc_input_manager_on_char(m, codepoint);
}
