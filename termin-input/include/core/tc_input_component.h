#ifndef TC_INPUT_COMPONENT_H
#define TC_INPUT_COMPONENT_H

#include "core/tc_component.h"
#include "core/tc_input_capability.h"

#ifdef __cplusplus
extern "C" {
#endif

typedef struct tc_mouse_button_event tc_mouse_button_event;
typedef struct tc_mouse_move_event tc_mouse_move_event;
typedef struct tc_scroll_event tc_scroll_event;
typedef struct tc_key_event tc_key_event;

typedef struct tc_input_vtable {
    void (*on_mouse_button)(tc_component* self, tc_mouse_button_event* event);
    void (*on_mouse_move)(tc_component* self, tc_mouse_move_event* event);
    void (*on_scroll)(tc_component* self, tc_scroll_event* event);
    void (*on_key)(tc_component* self, tc_key_event* event);
} tc_input_vtable;

static inline bool tc_component_is_input_handler(const tc_component* c) {
    return c && tc_input_capability_get(c) != NULL;
}

static inline const tc_input_vtable* tc_component_get_input_vtable(const tc_component* c) {
    if (!c) return NULL;
    return tc_input_capability_get(c);
}

static inline void tc_component_on_mouse_button(tc_component* c, tc_mouse_button_event* event) {
    const tc_input_vtable* vt = tc_component_get_input_vtable(c);
    if (c && c->enabled && vt && vt->on_mouse_button) {
        vt->on_mouse_button(c, event);
    }
}

static inline void tc_component_on_mouse_move(tc_component* c, tc_mouse_move_event* event) {
    const tc_input_vtable* vt = tc_component_get_input_vtable(c);
    if (c && c->enabled && vt && vt->on_mouse_move) {
        vt->on_mouse_move(c, event);
    }
}

static inline void tc_component_on_scroll(tc_component* c, tc_scroll_event* event) {
    const tc_input_vtable* vt = tc_component_get_input_vtable(c);
    if (c && c->enabled && vt && vt->on_scroll) {
        vt->on_scroll(c, event);
    }
}

static inline void tc_component_on_key(tc_component* c, tc_key_event* event) {
    const tc_input_vtable* vt = tc_component_get_input_vtable(c);
    if (c && c->enabled && vt && vt->on_key) {
        vt->on_key(c, event);
    }
}

TC_API bool tc_component_get_is_input_handler(const tc_component* c);

#ifdef __cplusplus
}
#endif

#endif
