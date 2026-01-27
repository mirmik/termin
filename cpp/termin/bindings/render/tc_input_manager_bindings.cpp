// tc_input_manager_bindings.cpp - Python bindings for tc_input_manager
#include <nanobind/nanobind.h>
#include <nanobind/stl/string.h>
#include <nanobind/stl/tuple.h>

#include "render/tc_input_manager.h"
#include "render/tc_render_surface.h"

namespace nb = nanobind;

namespace termin {

// Global Python callbacks for external input managers
static nb::object g_py_on_mouse_button;
static nb::object g_py_on_mouse_move;
static nb::object g_py_on_scroll;
static nb::object g_py_on_key;
static nb::object g_py_on_char;

// C callback implementations that call Python
static void py_on_mouse_button(void* body, int button, int action, int mods) {
    if (!body || g_py_on_mouse_button.is_none()) return;
    nb::gil_scoped_acquire gil;
    try {
        nb::object py_obj = nb::borrow<nb::object>(reinterpret_cast<PyObject*>(body));
        g_py_on_mouse_button(py_obj, button, action, mods);
    } catch (const std::exception& e) {
        // Ignore
    }
}

static void py_on_mouse_move(void* body, double x, double y) {
    if (!body || g_py_on_mouse_move.is_none()) return;
    nb::gil_scoped_acquire gil;
    try {
        nb::object py_obj = nb::borrow<nb::object>(reinterpret_cast<PyObject*>(body));
        g_py_on_mouse_move(py_obj, x, y);
    } catch (const std::exception& e) {
        // Ignore
    }
}

static void py_on_scroll(void* body, double x, double y, int mods) {
    if (!body || g_py_on_scroll.is_none()) return;
    nb::gil_scoped_acquire gil;
    try {
        nb::object py_obj = nb::borrow<nb::object>(reinterpret_cast<PyObject*>(body));
        g_py_on_scroll(py_obj, x, y, mods);
    } catch (const std::exception& e) {
        // Ignore
    }
}

static void py_on_key(void* body, int key, int scancode, int action, int mods) {
    if (!body || g_py_on_key.is_none()) return;
    nb::gil_scoped_acquire gil;
    try {
        nb::object py_obj = nb::borrow<nb::object>(reinterpret_cast<PyObject*>(body));
        g_py_on_key(py_obj, key, scancode, action, mods);
    } catch (const std::exception& e) {
        // Ignore
    }
}

static void py_on_char(void* body, uint32_t codepoint) {
    if (!body || g_py_on_char.is_none()) return;
    nb::gil_scoped_acquire gil;
    try {
        nb::object py_obj = nb::borrow<nb::object>(reinterpret_cast<PyObject*>(body));
        g_py_on_char(py_obj, codepoint);
    } catch (const std::exception& e) {
        // Ignore
    }
}

static void py_input_destroy(void* body) {
    // No-op: Python GC handles the object
}

static void py_input_incref(void* body) {
    if (body) {
        nb::gil_scoped_acquire gil;
        Py_INCREF(reinterpret_cast<PyObject*>(body));
    }
}

static void py_input_decref(void* body) {
    if (body) {
        nb::gil_scoped_acquire gil;
        Py_DECREF(reinterpret_cast<PyObject*>(body));
    }
}

// Initialize external callbacks
static void init_input_external_callbacks() {
    static bool initialized = false;
    if (initialized) return;
    initialized = true;

    tc_external_input_manager_callbacks cbs = {
        .on_mouse_button = py_on_mouse_button,
        .on_mouse_move = py_on_mouse_move,
        .on_scroll = py_on_scroll,
        .on_key = py_on_key,
        .on_char = py_on_char,
        .destroy = py_input_destroy,
        .incref = py_input_incref,
        .decref = py_input_decref,
    };
    tc_input_manager_set_external_callbacks(&cbs);
}

void bind_tc_input_manager(nb::module_& m) {
    // Initialize callbacks on module load
    init_input_external_callbacks();

    // Set Python callback functions for external input managers
    m.def("_set_input_manager_on_mouse_button_callback", [](nb::object cb) {
        g_py_on_mouse_button = cb;
    });
    m.def("_set_input_manager_on_mouse_move_callback", [](nb::object cb) {
        g_py_on_mouse_move = cb;
    });
    m.def("_set_input_manager_on_scroll_callback", [](nb::object cb) {
        g_py_on_scroll = cb;
    });
    m.def("_set_input_manager_on_key_callback", [](nb::object cb) {
        g_py_on_key = cb;
    });
    m.def("_set_input_manager_on_char_callback", [](nb::object cb) {
        g_py_on_char = cb;
    });

    // Create external input manager from Python object
    m.def("_input_manager_new_external", [](nb::object py_manager) -> uintptr_t {
        PyObject* ptr = py_manager.ptr();
        tc_input_manager* manager = tc_input_manager_new_external(ptr);
        return reinterpret_cast<uintptr_t>(manager);
    });

    // Free external input manager
    m.def("_input_manager_free_external", [](uintptr_t ptr) {
        tc_input_manager* manager = reinterpret_cast<tc_input_manager*>(ptr);
        tc_input_manager_free_external(manager);
    });

    // Direct event dispatch (for forwarding from window)
    m.def("_input_manager_on_mouse_button", [](uintptr_t ptr, int button, int action, int mods) {
        tc_input_manager* m = reinterpret_cast<tc_input_manager*>(ptr);
        tc_input_manager_on_mouse_button(m, button, action, mods);
    });

    m.def("_input_manager_on_mouse_move", [](uintptr_t ptr, double x, double y) {
        tc_input_manager* m = reinterpret_cast<tc_input_manager*>(ptr);
        tc_input_manager_on_mouse_move(m, x, y);
    });

    m.def("_input_manager_on_scroll", [](uintptr_t ptr, double x, double y, int mods) {
        tc_input_manager* m = reinterpret_cast<tc_input_manager*>(ptr);
        tc_input_manager_on_scroll(m, x, y, mods);
    });

    m.def("_input_manager_on_key", [](uintptr_t ptr, int key, int scancode, int action, int mods) {
        tc_input_manager* m = reinterpret_cast<tc_input_manager*>(ptr);
        tc_input_manager_on_key(m, key, scancode, action, mods);
    });

    m.def("_input_manager_on_char", [](uintptr_t ptr, uint32_t codepoint) {
        tc_input_manager* m = reinterpret_cast<tc_input_manager*>(ptr);
        tc_input_manager_on_char(m, codepoint);
    });

    // Set input manager on render surface
    m.def("_render_surface_set_input_manager", [](uintptr_t surface_ptr, uintptr_t manager_ptr) {
        tc_render_surface* surface = reinterpret_cast<tc_render_surface*>(surface_ptr);
        tc_input_manager* manager = reinterpret_cast<tc_input_manager*>(manager_ptr);
        tc_render_surface_set_input_manager(surface, manager);
    });

    // Input constants
    m.attr("TC_INPUT_RELEASE") = TC_INPUT_RELEASE;
    m.attr("TC_INPUT_PRESS") = TC_INPUT_PRESS;
    m.attr("TC_INPUT_REPEAT") = TC_INPUT_REPEAT;
    m.attr("TC_MOUSE_BUTTON_LEFT") = TC_MOUSE_BUTTON_LEFT;
    m.attr("TC_MOUSE_BUTTON_RIGHT") = TC_MOUSE_BUTTON_RIGHT;
    m.attr("TC_MOUSE_BUTTON_MIDDLE") = TC_MOUSE_BUTTON_MIDDLE;
    m.attr("TC_MOD_SHIFT") = TC_MOD_SHIFT;
    m.attr("TC_MOD_CONTROL") = TC_MOD_CONTROL;
    m.attr("TC_MOD_ALT") = TC_MOD_ALT;
    m.attr("TC_MOD_SUPER") = TC_MOD_SUPER;
}

} // namespace termin
