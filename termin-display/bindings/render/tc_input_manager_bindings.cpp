// tc_input_manager_bindings.cpp - Python bindings for tc_input_manager
#include <nanobind/nanobind.h>
#include <nanobind/stl/string.h>

#include "render/tc_input_manager.h"
#include "render/tc_display_input_router.h"
#include "render/tc_viewport_input_manager.h"
#include "render/tc_render_surface.h"
#include "render/tc_display.h"
#include "render/tc_viewport.h"

namespace nb = nanobind;

namespace termin {

// ============================================================================
// Per-class VTable Support
// ============================================================================

// VTable stored per Python class. When Python class creates an input manager,
// it passes its class-specific vtable pointer.

struct PyInputManagerVTable {
    nb::object on_mouse_button;
    nb::object on_mouse_move;
    nb::object on_scroll;
    nb::object on_key;
    nb::object on_char;
    nb::object destroy;
    tc_input_manager_vtable c_vtable;
};

// C callbacks that dispatch to Python methods via stored vtable
static void py_on_mouse_button(tc_input_manager* m, int button, int action, int mods) {
    if (!m || !m->body || !m->userdata) return;
    PyInputManagerVTable* vt = static_cast<PyInputManagerVTable*>(m->userdata);
    if (vt->on_mouse_button.is_none()) return;

    nb::gil_scoped_acquire gil;
    try {
        nb::object py_obj = nb::borrow<nb::object>(reinterpret_cast<PyObject*>(m->body));
        vt->on_mouse_button(py_obj, button, action, mods);
    } catch (const std::exception& e) {
        fprintf(stderr, "[py_on_mouse_button] exception: %s\n", e.what());
    }
}

static void py_on_mouse_move(tc_input_manager* m, double x, double y) {
    if (!m || !m->body || !m->userdata) return;
    PyInputManagerVTable* vt = static_cast<PyInputManagerVTable*>(m->userdata);
    if (vt->on_mouse_move.is_none()) return;

    nb::gil_scoped_acquire gil;
    try {
        nb::object py_obj = nb::borrow<nb::object>(reinterpret_cast<PyObject*>(m->body));
        vt->on_mouse_move(py_obj, x, y);
    } catch (const std::exception& e) {
        fprintf(stderr, "[py_on_mouse_move] exception: %s\n", e.what());
    }
}

static void py_on_scroll(tc_input_manager* m, double x, double y, int mods) {
    if (!m || !m->body || !m->userdata) return;
    PyInputManagerVTable* vt = static_cast<PyInputManagerVTable*>(m->userdata);
    if (vt->on_scroll.is_none()) return;

    nb::gil_scoped_acquire gil;
    try {
        nb::object py_obj = nb::borrow<nb::object>(reinterpret_cast<PyObject*>(m->body));
        vt->on_scroll(py_obj, x, y, mods);
    } catch (const std::exception& e) {
        fprintf(stderr, "[py_on_scroll] exception: %s\n", e.what());
    }
}

static void py_on_key(tc_input_manager* m, int key, int scancode, int action, int mods) {
    if (!m || !m->body || !m->userdata) return;
    PyInputManagerVTable* vt = static_cast<PyInputManagerVTable*>(m->userdata);
    if (vt->on_key.is_none()) return;

    nb::gil_scoped_acquire gil;
    try {
        nb::object py_obj = nb::borrow<nb::object>(reinterpret_cast<PyObject*>(m->body));
        vt->on_key(py_obj, key, scancode, action, mods);
    } catch (const std::exception& e) {
        fprintf(stderr, "[py_on_key] exception: %s\n", e.what());
    }
}

static void py_on_char(tc_input_manager* m, uint32_t codepoint) {
    if (!m || !m->body || !m->userdata) return;
    PyInputManagerVTable* vt = static_cast<PyInputManagerVTable*>(m->userdata);
    if (vt->on_char.is_none()) return;

    nb::gil_scoped_acquire gil;
    try {
        nb::object py_obj = nb::borrow<nb::object>(reinterpret_cast<PyObject*>(m->body));
        vt->on_char(py_obj, codepoint);
    } catch (const std::exception& e) {
        fprintf(stderr, "[py_on_char] exception: %s\n", e.what());
    }
}

static void py_destroy(tc_input_manager* m) {
    if (!m || !m->body) return;

    nb::gil_scoped_acquire gil;
    Py_DECREF(reinterpret_cast<PyObject*>(m->body));
    m->body = nullptr;
}

// ============================================================================
// Bindings
// ============================================================================

void bind_tc_input_manager(nb::module_& m) {
    // Create vtable for a Python class
    // Returns opaque pointer to PyInputManagerVTable
    m.def("_input_manager_create_vtable", [](
        nb::object on_mouse_button,
        nb::object on_mouse_move,
        nb::object on_scroll,
        nb::object on_key,
        nb::object on_char
    ) -> uintptr_t {
        auto* vt = new PyInputManagerVTable();
        vt->on_mouse_button = on_mouse_button;
        vt->on_mouse_move = on_mouse_move;
        vt->on_scroll = on_scroll;
        vt->on_key = on_key;
        vt->on_char = on_char;

        vt->c_vtable = {
            .on_mouse_button = py_on_mouse_button,
            .on_mouse_move = py_on_mouse_move,
            .on_scroll = py_on_scroll,
            .on_key = py_on_key,
            .on_char = py_on_char,
            .destroy = py_destroy,
        };

        return reinterpret_cast<uintptr_t>(vt);
    });

    // Create input manager with class vtable
    m.def("_input_manager_new", [](uintptr_t vtable_ptr, nb::object py_manager) -> uintptr_t {
        if (!vtable_ptr) {
            fprintf(stderr, "[_input_manager_new] vtable_ptr is NULL\n");
            return 0;
        }

        PyInputManagerVTable* vt = reinterpret_cast<PyInputManagerVTable*>(vtable_ptr);
        PyObject* body = py_manager.ptr();
        Py_INCREF(body);

        tc_input_manager* manager = tc_input_manager_new(&vt->c_vtable, body);
        if (manager) {
            manager->userdata = vt;  // Store vtable pointer for callbacks
        }
        return reinterpret_cast<uintptr_t>(manager);
    });

    // Free input manager
    m.def("_input_manager_free", [](uintptr_t ptr) {
        tc_input_manager* manager = reinterpret_cast<tc_input_manager*>(ptr);
        tc_input_manager_free(manager);
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

    // ========================================================================
    // tc_display_input_router - routes events from display to viewports
    // ========================================================================

    m.def("_display_input_router_new", [](uintptr_t display_ptr) -> uintptr_t {
        tc_display* display = reinterpret_cast<tc_display*>(display_ptr);
        tc_display_input_router* r = tc_display_input_router_new(display);
        return reinterpret_cast<uintptr_t>(r);
    }, nb::arg("display_ptr"),
       "Create display input router.\n"
       "Auto-attaches to display's surface.");

    m.def("_display_input_router_free", [](uintptr_t ptr) {
        tc_display_input_router* r = reinterpret_cast<tc_display_input_router*>(ptr);
        tc_display_input_router_free(r);
    });

    m.def("_display_input_router_base", [](uintptr_t ptr) -> uintptr_t {
        tc_display_input_router* r = reinterpret_cast<tc_display_input_router*>(ptr);
        return reinterpret_cast<uintptr_t>(tc_display_input_router_base(r));
    });

    // ========================================================================
    // tc_viewport_input_manager - per-viewport scene dispatch
    // ========================================================================

    m.def("_viewport_input_manager_new", [](uint32_t vp_index, uint32_t vp_generation) -> uintptr_t {
        tc_viewport_handle vh;
        vh.index = vp_index;
        vh.generation = vp_generation;
        tc_viewport_input_manager* m = tc_viewport_input_manager_new(vh);
        return reinterpret_cast<uintptr_t>(m);
    }, nb::arg("vp_index"), nb::arg("vp_generation"),
       "Create viewport input manager.\n"
       "Auto-attaches to viewport.");

    m.def("_viewport_input_manager_free", [](uintptr_t ptr) {
        tc_viewport_input_manager* m = reinterpret_cast<tc_viewport_input_manager*>(ptr);
        tc_viewport_input_manager_free(m);
    });

    // ========================================================================
    // Debug: query input manager state
    // ========================================================================

    // Get input_manager pointer from render surface
    m.def("_render_surface_get_input_manager", [](uintptr_t surface_ptr) -> uintptr_t {
        tc_render_surface* s = reinterpret_cast<tc_render_surface*>(surface_ptr);
        return reinterpret_cast<uintptr_t>(tc_render_surface_get_input_manager(s));
    });

    // Get input_manager pointer from viewport
    m.def("_viewport_get_input_manager", [](uint32_t vp_index, uint32_t vp_generation) -> uintptr_t {
        tc_viewport_handle vh;
        vh.index = vp_index;
        vh.generation = vp_generation;
        return reinterpret_cast<uintptr_t>(tc_viewport_get_input_manager(vh));
    });

    // Get surface pointer from display
    m.def("_display_get_surface_ptr", [](uintptr_t display_ptr) -> uintptr_t {
        tc_display* d = reinterpret_cast<tc_display*>(display_ptr);
        return reinterpret_cast<uintptr_t>(tc_display_get_surface(d));
    });
}

} // namespace termin
