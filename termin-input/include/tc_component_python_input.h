#ifndef TC_COMPONENT_PYTHON_INPUT_H
#define TC_COMPONENT_PYTHON_INPUT_H

#include "core/tc_component.h"
#include "core/tc_input_component.h"

#ifdef __cplusplus
extern "C" {
#endif

typedef void (*tc_py_input_on_mouse_button_fn)(void* py_self, tc_mouse_button_event* event);
typedef void (*tc_py_input_on_mouse_move_fn)(void* py_self, tc_mouse_move_event* event);
typedef void (*tc_py_input_on_scroll_fn)(void* py_self, tc_scroll_event* event);
typedef void (*tc_py_input_on_key_fn)(void* py_self, tc_key_event* event);

typedef struct {
    tc_py_input_on_mouse_button_fn on_mouse_button;
    tc_py_input_on_mouse_move_fn on_mouse_move;
    tc_py_input_on_scroll_fn on_scroll;
    tc_py_input_on_key_fn on_key;
} tc_python_input_callbacks;

TC_API void tc_component_set_python_input_callbacks(const tc_python_input_callbacks* callbacks);
TC_API void tc_component_install_python_input_vtable(tc_component* c);

#ifdef __cplusplus
}
#endif

#endif
