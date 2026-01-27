// tc_input_manager.h - Input event handling
#ifndef TC_INPUT_MANAGER_H
#define TC_INPUT_MANAGER_H

#include "tc_types.h"
#include <stdbool.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

// Forward declarations
typedef struct tc_input_manager tc_input_manager;
typedef struct tc_input_manager_vtable tc_input_manager_vtable;

// ============================================================================
// Input Constants
// ============================================================================

// Actions (compatible with GLFW/SDL)
#define TC_INPUT_RELEASE 0
#define TC_INPUT_PRESS   1
#define TC_INPUT_REPEAT  2

// Mouse buttons
#define TC_MOUSE_BUTTON_LEFT   0
#define TC_MOUSE_BUTTON_RIGHT  1
#define TC_MOUSE_BUTTON_MIDDLE 2

// Modifier keys (bitmask)
#define TC_MOD_SHIFT   0x0001
#define TC_MOD_CONTROL 0x0002
#define TC_MOD_ALT     0x0004
#define TC_MOD_SUPER   0x0008

// ============================================================================
// Input Manager VTable
// ============================================================================

struct tc_input_manager_vtable {
    // Mouse button event (button, action, mods)
    void (*on_mouse_button)(tc_input_manager* self, int button, int action, int mods);

    // Mouse move event (x, y in window pixels)
    void (*on_mouse_move)(tc_input_manager* self, double x, double y);

    // Scroll event (x, y offsets, mods)
    void (*on_scroll)(tc_input_manager* self, double x, double y, int mods);

    // Key event (key code, scancode, action, mods)
    void (*on_key)(tc_input_manager* self, int key, int scancode, int action, int mods);

    // Character input (unicode codepoint)
    void (*on_char)(tc_input_manager* self, uint32_t codepoint);

    // Cleanup
    void (*destroy)(tc_input_manager* self);
};

// ============================================================================
// Input Manager Structure
// ============================================================================

struct tc_input_manager {
    const tc_input_manager_vtable* vtable;

    // External object (PyObject*, etc.) for external managers
    void* body;

    // User data for callbacks
    void* userdata;
};

// ============================================================================
// Initialization
// ============================================================================

static inline void tc_input_manager_init(
    tc_input_manager* m,
    const tc_input_manager_vtable* vtable
) {
    m->vtable = vtable;
    m->body = NULL;
    m->userdata = NULL;
}

// ============================================================================
// VTable Dispatch (null-safe)
// ============================================================================

static inline void tc_input_manager_on_mouse_button(
    tc_input_manager* m, int button, int action, int mods
) {
    if (m && m->vtable && m->vtable->on_mouse_button) {
        m->vtable->on_mouse_button(m, button, action, mods);
    }
}

static inline void tc_input_manager_on_mouse_move(
    tc_input_manager* m, double x, double y
) {
    if (m && m->vtable && m->vtable->on_mouse_move) {
        m->vtable->on_mouse_move(m, x, y);
    }
}

static inline void tc_input_manager_on_scroll(
    tc_input_manager* m, double x, double y, int mods
) {
    if (m && m->vtable && m->vtable->on_scroll) {
        m->vtable->on_scroll(m, x, y, mods);
    }
}

static inline void tc_input_manager_on_key(
    tc_input_manager* m, int key, int scancode, int action, int mods
) {
    if (m && m->vtable && m->vtable->on_key) {
        m->vtable->on_key(m, key, scancode, action, mods);
    }
}

static inline void tc_input_manager_on_char(tc_input_manager* m, uint32_t codepoint) {
    if (m && m->vtable && m->vtable->on_char) {
        m->vtable->on_char(m, codepoint);
    }
}

static inline void tc_input_manager_destroy(tc_input_manager* m) {
    if (m && m->vtable && m->vtable->destroy) {
        m->vtable->destroy(m);
    }
}

// ============================================================================
// External Input Manager Support (for Python/Rust/C#)
// ============================================================================

typedef struct {
    void (*on_mouse_button)(void* body, int button, int action, int mods);
    void (*on_mouse_move)(void* body, double x, double y);
    void (*on_scroll)(void* body, double x, double y, int mods);
    void (*on_key)(void* body, int key, int scancode, int action, int mods);
    void (*on_char)(void* body, uint32_t codepoint);
    void (*destroy)(void* body);
    void (*incref)(void* body);
    void (*decref)(void* body);
} tc_external_input_manager_callbacks;

// Set global callbacks for external input managers
TC_API void tc_input_manager_set_external_callbacks(
    const tc_external_input_manager_callbacks* callbacks
);

// Create external input manager wrapping a body object
TC_API tc_input_manager* tc_input_manager_new_external(void* body);

// Free external input manager
TC_API void tc_input_manager_free_external(tc_input_manager* m);

#ifdef __cplusplus
}
#endif

#endif // TC_INPUT_MANAGER_H
