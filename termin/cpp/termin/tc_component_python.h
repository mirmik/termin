// tc_component_python.h - External component functions
// These functions are used when components are created from external
// scripting languages (e.g. Python) and need callback support.
#ifndef TC_COMPONENT_PYTHON_H
#define TC_COMPONENT_PYTHON_H

#include "core/tc_component.h"

#ifdef __cplusplus
extern "C" {
#endif

// Create a new component that will call Python methods.
// py_self is a borrowed reference to the Python object (PyObject*).
// The caller must ensure py_self stays alive for the component's lifetime.
// type_name should be an interned string that stays valid.
TC_API tc_component* tc_component_new_python(void* py_self, const char* type_name);

// Free a Python component created with tc_component_new_python.
// Does NOT decref py_self - caller is responsible for Python object lifetime.
TC_API void tc_component_free_python(tc_component* c);

// Set Python callbacks.
// These are function pointers that will be called from C.
// Each callback receives (PyObject* self, ...) as arguments.
typedef void (*tc_py_start_fn)(void* py_self);
typedef void (*tc_py_update_fn)(void* py_self, float dt);
typedef void (*tc_py_fixed_update_fn)(void* py_self, float dt);
typedef void (*tc_py_before_render_fn)(void* py_self);
typedef void (*tc_py_on_destroy_fn)(void* py_self);
typedef void (*tc_py_on_added_to_entity_fn)(void* py_self);
typedef void (*tc_py_on_removed_from_entity_fn)(void* py_self);
typedef void (*tc_py_on_added_fn)(void* py_self);
typedef void (*tc_py_on_removed_fn)(void* py_self);
typedef void (*tc_py_on_scene_inactive_fn)(void* py_self);
typedef void (*tc_py_on_scene_active_fn)(void* py_self);
typedef void (*tc_py_on_editor_start_fn)(void* py_self);

// Reference counting callbacks for Python objects
typedef void (*tc_py_incref_fn)(void* py_obj);
typedef void (*tc_py_decref_fn)(void* py_obj);

// Global Python callback table.
// Set once at module initialization.
typedef struct {
    tc_py_start_fn start;
    tc_py_update_fn update;
    tc_py_fixed_update_fn fixed_update;
    tc_py_before_render_fn before_render;
    tc_py_on_destroy_fn on_destroy;
    tc_py_on_added_to_entity_fn on_added_to_entity;
    tc_py_on_removed_from_entity_fn on_removed_from_entity;
    tc_py_on_added_fn on_added;
    tc_py_on_removed_fn on_removed;
    tc_py_on_scene_inactive_fn on_scene_inactive;
    tc_py_on_scene_active_fn on_scene_active;
    tc_py_on_editor_start_fn on_editor_start;
    // Reference counting
    tc_py_incref_fn incref;
    tc_py_decref_fn decref;
} tc_python_callbacks;

// Set the global Python callbacks.
// Must be called once from Python bindings before any Python components are created.
TC_API void tc_component_set_python_callbacks(const tc_python_callbacks* callbacks);

// ============================================================================
// Python Drawable callbacks
// ============================================================================

typedef bool (*tc_py_drawable_has_phase_fn)(void* py_self, const char* phase_mark);
typedef void (*tc_py_drawable_draw_geometry_fn)(void* py_self, void* render_context, int geometry_id);
typedef void* (*tc_py_drawable_get_geometry_draws_fn)(void* py_self, const char* phase_mark);

typedef struct {
    tc_py_drawable_has_phase_fn has_phase;
    tc_py_drawable_draw_geometry_fn draw_geometry;
    tc_py_drawable_get_geometry_draws_fn get_geometry_draws;
} tc_python_drawable_callbacks;

// Set the global Python drawable callbacks.
TC_API void tc_component_set_python_drawable_callbacks(const tc_python_drawable_callbacks* callbacks);

// Install drawable vtable on a Python component.
// Call this when the Python component implements Drawable protocol.
TC_API void tc_component_install_python_drawable_vtable(tc_component* c);

// ============================================================================
// Python Input Handler callbacks
// ============================================================================

#include "tc_input_event.h"

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

// Set the global Python input callbacks.
TC_API void tc_component_set_python_input_callbacks(const tc_python_input_callbacks* callbacks);

// Install input vtable on a Python component.
// Call this when the Python component implements InputHandler protocol.
TC_API void tc_component_install_python_input_vtable(tc_component* c);

#ifdef __cplusplus
}
#endif

#endif // TC_COMPONENT_PYTHON_H
