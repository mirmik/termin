// tc_input_event.h - Input event structures
#ifndef TC_INPUT_EVENT_H
#define TC_INPUT_EVENT_H

#include "tc_types.h"
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

// Forward declarations
typedef struct tc_viewport tc_viewport;

// ============================================================================
// Input Event Structures
// ============================================================================

// Mouse button event
typedef struct tc_mouse_button_event {
    tc_viewport* viewport;
    double x;
    double y;
    int button;     // 0=left, 1=right, 2=middle
    int action;     // 0=release, 1=press, 2=repeat
    int mods;       // Shift=1, Ctrl=2, Alt=4, Super=8
} tc_mouse_button_event;

// Mouse move event
typedef struct tc_mouse_move_event {
    tc_viewport* viewport;
    double x;
    double y;
    double dx;
    double dy;
} tc_mouse_move_event;

// Scroll event
typedef struct tc_scroll_event {
    tc_viewport* viewport;
    double x;
    double y;
    double xoffset;
    double yoffset;
    int mods;
} tc_scroll_event;

// Key event
typedef struct tc_key_event {
    tc_viewport* viewport;
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
    tc_viewport* viewport,
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
    tc_viewport* viewport,
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
    tc_viewport* viewport,
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
    tc_viewport* viewport,
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
