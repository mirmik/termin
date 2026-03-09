// tc_input_event.h - Input event structures
#ifndef TC_INPUT_EVENT_H
#define TC_INPUT_EVENT_H

#include "tc_types.h"
#include "render/tc_viewport_pool.h"
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

// ============================================================================
// Input Constants
// ============================================================================

// Action types
#define TC_ACTION_RELEASE 0
#define TC_ACTION_PRESS   1
#define TC_ACTION_REPEAT  2

// Mouse buttons
#define TC_MOUSE_BUTTON_LEFT   0
#define TC_MOUSE_BUTTON_RIGHT  1
#define TC_MOUSE_BUTTON_MIDDLE 2

// Modifier keys
#define TC_MOD_SHIFT   0x0001
#define TC_MOD_CONTROL 0x0002
#define TC_MOD_ALT     0x0004
#define TC_MOD_SUPER   0x0008

// Key codes (matching GLFW values)
#define TC_KEY_SPACE         32
#define TC_KEY_ESCAPE        256
#define TC_KEY_ENTER         257
#define TC_KEY_TAB           258
#define TC_KEY_BACKSPACE     259
#define TC_KEY_INSERT        260
#define TC_KEY_DELETE        261
#define TC_KEY_RIGHT         262
#define TC_KEY_LEFT          263
#define TC_KEY_DOWN          264
#define TC_KEY_UP            265
#define TC_KEY_PAGE_UP       266
#define TC_KEY_PAGE_DOWN     267
#define TC_KEY_HOME          268
#define TC_KEY_END           269
#define TC_KEY_A             65
#define TC_KEY_B             66
#define TC_KEY_C             67
#define TC_KEY_D             68
#define TC_KEY_E             69
#define TC_KEY_F             70
#define TC_KEY_G             71
#define TC_KEY_H             72
#define TC_KEY_I             73
#define TC_KEY_J             74
#define TC_KEY_K             75
#define TC_KEY_L             76
#define TC_KEY_M             77
#define TC_KEY_N             78
#define TC_KEY_O             79
#define TC_KEY_P             80
#define TC_KEY_Q             81
#define TC_KEY_R             82
#define TC_KEY_S             83
#define TC_KEY_T             84
#define TC_KEY_U             85
#define TC_KEY_V             86
#define TC_KEY_W             87
#define TC_KEY_X             88
#define TC_KEY_Y             89
#define TC_KEY_Z             90

// ============================================================================
// Input Event Structures
// ============================================================================

// Mouse button event
typedef struct tc_mouse_button_event {
    tc_viewport_handle viewport;
    double x;
    double y;
    int button;     // 0=left, 1=right, 2=middle
    int action;     // 0=release, 1=press, 2=repeat
    int mods;       // Shift=1, Ctrl=2, Alt=4, Super=8
} tc_mouse_button_event;

// Mouse move event
typedef struct tc_mouse_move_event {
    tc_viewport_handle viewport;
    double x;
    double y;
    double dx;
    double dy;
} tc_mouse_move_event;

// Scroll event
typedef struct tc_scroll_event {
    tc_viewport_handle viewport;
    double x;
    double y;
    double xoffset;
    double yoffset;
    int mods;
} tc_scroll_event;

// Key event
typedef struct tc_key_event {
    tc_viewport_handle viewport;
    int key;
    int scancode;
    int action;     // 0=release, 1=press, 2=repeat
    int mods;
} tc_key_event;

// ============================================================================
// Initialization helpers
// ============================================================================

static inline void tc_mouse_button_event_init(
    tc_mouse_button_event* e,
    tc_viewport_handle viewport,
    double x, double y,
    int button, int action, int mods
) {
    e->viewport = viewport;
    e->x = x;
    e->y = y;
    e->button = button;
    e->action = action;
    e->mods = mods;
}

static inline void tc_mouse_move_event_init(
    tc_mouse_move_event* e,
    tc_viewport_handle viewport,
    double x, double y,
    double dx, double dy
) {
    e->viewport = viewport;
    e->x = x;
    e->y = y;
    e->dx = dx;
    e->dy = dy;
}

static inline void tc_scroll_event_init(
    tc_scroll_event* e,
    tc_viewport_handle viewport,
    double x, double y,
    double xoffset, double yoffset,
    int mods
) {
    e->viewport = viewport;
    e->x = x;
    e->y = y;
    e->xoffset = xoffset;
    e->yoffset = yoffset;
    e->mods = mods;
}

static inline void tc_key_event_init(
    tc_key_event* e,
    tc_viewport_handle viewport,
    int key, int scancode,
    int action, int mods
) {
    e->viewport = viewport;
    e->key = key;
    e->scancode = scancode;
    e->action = action;
    e->mods = mods;
}

#ifdef __cplusplus
}
#endif

#endif // TC_INPUT_EVENT_H
