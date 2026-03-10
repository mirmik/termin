#include "tc_component_python_input.h"
#include "core/tc_input_capability.h"

static tc_python_input_callbacks g_py_input_callbacks = {0};

static void py_input_on_mouse_button(tc_component* c, tc_mouse_button_event* event) {
    if (g_py_input_callbacks.on_mouse_button && c->body) {
        g_py_input_callbacks.on_mouse_button(c->body, event);
    }
}

static void py_input_on_mouse_move(tc_component* c, tc_mouse_move_event* event) {
    if (g_py_input_callbacks.on_mouse_move && c->body) {
        g_py_input_callbacks.on_mouse_move(c->body, event);
    }
}

static void py_input_on_scroll(tc_component* c, tc_scroll_event* event) {
    if (g_py_input_callbacks.on_scroll && c->body) {
        g_py_input_callbacks.on_scroll(c->body, event);
    }
}

static void py_input_on_key(tc_component* c, tc_key_event* event) {
    if (g_py_input_callbacks.on_key && c->body) {
        g_py_input_callbacks.on_key(c->body, event);
    }
}

static const tc_input_vtable g_python_input_vtable = {
    .on_mouse_button = py_input_on_mouse_button,
    .on_mouse_move = py_input_on_mouse_move,
    .on_scroll = py_input_on_scroll,
    .on_key = py_input_on_key,
};

void tc_component_set_python_input_callbacks(const tc_python_input_callbacks* callbacks) {
    if (callbacks) {
        g_py_input_callbacks = *callbacks;
    }
}

void tc_component_install_python_input_vtable(tc_component* c) {
    if (c) {
        tc_input_capability_attach(c, &g_python_input_vtable);
    }
}
