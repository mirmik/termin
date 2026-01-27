// tc_render_surface_bindings.cpp - Python bindings for tc_render_surface
#include <nanobind/nanobind.h>
#include <nanobind/stl/string.h>
#include <nanobind/stl/tuple.h>

#include "render/tc_render_surface.h"

namespace nb = nanobind;

namespace termin {

// Global Python callbacks for external surfaces
static nb::object g_py_get_framebuffer;
static nb::object g_py_get_size;
static nb::object g_py_make_current;
static nb::object g_py_swap_buffers;
static nb::object g_py_context_key;
static nb::object g_py_poll_events;
static nb::object g_py_get_window_size;
static nb::object g_py_should_close;
static nb::object g_py_set_should_close;
static nb::object g_py_get_cursor_pos;

// C callback implementations that call Python
static uint32_t py_get_framebuffer(void* body) {
    if (!body || g_py_get_framebuffer.is_none()) return 0;
    nb::gil_scoped_acquire gil;
    try {
        nb::object py_obj = nb::borrow<nb::object>(reinterpret_cast<PyObject*>(body));
        nb::object result = g_py_get_framebuffer(py_obj);
        return nb::cast<uint32_t>(result);
    } catch (const std::exception& e) {
        return 0;
    }
}

static void py_get_size(void* body, int* width, int* height) {
    if (!body || g_py_get_size.is_none()) {
        if (width) *width = 0;
        if (height) *height = 0;
        return;
    }
    nb::gil_scoped_acquire gil;
    try {
        nb::object py_obj = nb::borrow<nb::object>(reinterpret_cast<PyObject*>(body));
        nb::object result = g_py_get_size(py_obj);
        auto tup = nb::cast<std::tuple<int, int>>(result);
        if (width) *width = std::get<0>(tup);
        if (height) *height = std::get<1>(tup);
    } catch (const std::exception& e) {
        if (width) *width = 0;
        if (height) *height = 0;
    }
}

static void py_make_current(void* body) {
    if (!body || g_py_make_current.is_none()) return;
    nb::gil_scoped_acquire gil;
    try {
        nb::object py_obj = nb::borrow<nb::object>(reinterpret_cast<PyObject*>(body));
        g_py_make_current(py_obj);
    } catch (const std::exception& e) {
        // Ignore
    }
}

static void py_swap_buffers(void* body) {
    if (!body || g_py_swap_buffers.is_none()) return;
    nb::gil_scoped_acquire gil;
    try {
        nb::object py_obj = nb::borrow<nb::object>(reinterpret_cast<PyObject*>(body));
        g_py_swap_buffers(py_obj);
    } catch (const std::exception& e) {
        // Ignore
    }
}

static uintptr_t py_context_key(void* body) {
    if (!body) return 0;
    if (g_py_context_key.is_none()) {
        return reinterpret_cast<uintptr_t>(body);
    }
    nb::gil_scoped_acquire gil;
    try {
        nb::object py_obj = nb::borrow<nb::object>(reinterpret_cast<PyObject*>(body));
        nb::object result = g_py_context_key(py_obj);
        return nb::cast<uintptr_t>(result);
    } catch (const std::exception& e) {
        return reinterpret_cast<uintptr_t>(body);
    }
}

static void py_poll_events(void* body) {
    if (!body || g_py_poll_events.is_none()) return;
    nb::gil_scoped_acquire gil;
    try {
        nb::object py_obj = nb::borrow<nb::object>(reinterpret_cast<PyObject*>(body));
        g_py_poll_events(py_obj);
    } catch (const std::exception& e) {
        // Ignore
    }
}

static void py_get_window_size(void* body, int* width, int* height) {
    if (!body || g_py_get_window_size.is_none()) {
        // Fallback to get_size
        py_get_size(body, width, height);
        return;
    }
    nb::gil_scoped_acquire gil;
    try {
        nb::object py_obj = nb::borrow<nb::object>(reinterpret_cast<PyObject*>(body));
        nb::object result = g_py_get_window_size(py_obj);
        auto tup = nb::cast<std::tuple<int, int>>(result);
        if (width) *width = std::get<0>(tup);
        if (height) *height = std::get<1>(tup);
    } catch (const std::exception& e) {
        if (width) *width = 0;
        if (height) *height = 0;
    }
}

static bool py_should_close(void* body) {
    if (!body || g_py_should_close.is_none()) return false;
    nb::gil_scoped_acquire gil;
    try {
        nb::object py_obj = nb::borrow<nb::object>(reinterpret_cast<PyObject*>(body));
        nb::object result = g_py_should_close(py_obj);
        return nb::cast<bool>(result);
    } catch (const std::exception& e) {
        return false;
    }
}

static void py_set_should_close(void* body, bool value) {
    if (!body || g_py_set_should_close.is_none()) return;
    nb::gil_scoped_acquire gil;
    try {
        nb::object py_obj = nb::borrow<nb::object>(reinterpret_cast<PyObject*>(body));
        g_py_set_should_close(py_obj, value);
    } catch (const std::exception& e) {
        // Ignore
    }
}

static void py_get_cursor_pos(void* body, double* x, double* y) {
    if (!body || g_py_get_cursor_pos.is_none()) {
        if (x) *x = 0.0;
        if (y) *y = 0.0;
        return;
    }
    nb::gil_scoped_acquire gil;
    try {
        nb::object py_obj = nb::borrow<nb::object>(reinterpret_cast<PyObject*>(body));
        nb::object result = g_py_get_cursor_pos(py_obj);
        auto tup = nb::cast<std::tuple<double, double>>(result);
        if (x) *x = std::get<0>(tup);
        if (y) *y = std::get<1>(tup);
    } catch (const std::exception& e) {
        if (x) *x = 0.0;
        if (y) *y = 0.0;
    }
}

static void py_destroy(void* body) {
    // No-op: Python GC handles the object
}

static void py_incref(void* body) {
    if (body) {
        nb::gil_scoped_acquire gil;
        Py_INCREF(reinterpret_cast<PyObject*>(body));
    }
}

static void py_decref(void* body) {
    if (body) {
        nb::gil_scoped_acquire gil;
        Py_DECREF(reinterpret_cast<PyObject*>(body));
    }
}

// Initialize external callbacks
static void init_external_callbacks() {
    static bool initialized = false;
    if (initialized) return;
    initialized = true;

    tc_external_render_surface_callbacks cbs = {
        .get_framebuffer = py_get_framebuffer,
        .get_size = py_get_size,
        .make_current = py_make_current,
        .swap_buffers = py_swap_buffers,
        .context_key = py_context_key,
        .poll_events = py_poll_events,
        .get_window_size = py_get_window_size,
        .should_close = py_should_close,
        .set_should_close = py_set_should_close,
        .get_cursor_pos = py_get_cursor_pos,
        .destroy = py_destroy,
        .incref = py_incref,
        .decref = py_decref,
    };
    tc_render_surface_set_external_callbacks(&cbs);
}

void bind_tc_render_surface(nb::module_& m) {
    // Initialize callbacks on module load
    init_external_callbacks();

    // Set Python callback functions
    m.def("_set_render_surface_get_framebuffer_callback", [](nb::object cb) {
        g_py_get_framebuffer = cb;
    });
    m.def("_set_render_surface_get_size_callback", [](nb::object cb) {
        g_py_get_size = cb;
    });
    m.def("_set_render_surface_make_current_callback", [](nb::object cb) {
        g_py_make_current = cb;
    });
    m.def("_set_render_surface_swap_buffers_callback", [](nb::object cb) {
        g_py_swap_buffers = cb;
    });
    m.def("_set_render_surface_context_key_callback", [](nb::object cb) {
        g_py_context_key = cb;
    });
    m.def("_set_render_surface_poll_events_callback", [](nb::object cb) {
        g_py_poll_events = cb;
    });
    m.def("_set_render_surface_get_window_size_callback", [](nb::object cb) {
        g_py_get_window_size = cb;
    });
    m.def("_set_render_surface_should_close_callback", [](nb::object cb) {
        g_py_should_close = cb;
    });
    m.def("_set_render_surface_set_should_close_callback", [](nb::object cb) {
        g_py_set_should_close = cb;
    });
    m.def("_set_render_surface_get_cursor_pos_callback", [](nb::object cb) {
        g_py_get_cursor_pos = cb;
    });

    // Create external render surface from Python object
    m.def("_render_surface_new_external", [](nb::object py_surface) -> uintptr_t {
        PyObject* ptr = py_surface.ptr();
        tc_render_surface* surface = tc_render_surface_new_external(ptr);
        return reinterpret_cast<uintptr_t>(surface);
    });

    // Free external render surface
    m.def("_render_surface_free_external", [](uintptr_t ptr) {
        tc_render_surface* surface = reinterpret_cast<tc_render_surface*>(ptr);
        tc_render_surface_free_external(surface);
    });

    // Get size from tc_render_surface
    m.def("_render_surface_get_size", [](uintptr_t ptr) -> std::tuple<int, int> {
        tc_render_surface* surface = reinterpret_cast<tc_render_surface*>(ptr);
        int w = 0, h = 0;
        tc_render_surface_get_size(surface, &w, &h);
        return std::make_tuple(w, h);
    });

    // Make current
    m.def("_render_surface_make_current", [](uintptr_t ptr) {
        tc_render_surface* surface = reinterpret_cast<tc_render_surface*>(ptr);
        tc_render_surface_make_current(surface);
    });

    // Swap buffers
    m.def("_render_surface_swap_buffers", [](uintptr_t ptr) {
        tc_render_surface* surface = reinterpret_cast<tc_render_surface*>(ptr);
        tc_render_surface_swap_buffers(surface);
    });

    // Get framebuffer
    m.def("_render_surface_get_framebuffer", [](uintptr_t ptr) -> uint32_t {
        tc_render_surface* surface = reinterpret_cast<tc_render_surface*>(ptr);
        return tc_render_surface_get_framebuffer(surface);
    });

    // Context key
    m.def("_render_surface_context_key", [](uintptr_t ptr) -> uintptr_t {
        tc_render_surface* surface = reinterpret_cast<tc_render_surface*>(ptr);
        return tc_render_surface_context_key(surface);
    });

    // Set resize callback
    m.def("_render_surface_set_on_resize", [](uintptr_t ptr, nb::object callback) {
        tc_render_surface* surface = reinterpret_cast<tc_render_surface*>(ptr);
        if (callback.is_none()) {
            tc_render_surface_set_on_resize(surface, nullptr, nullptr);
        } else {
            // Store callback as userdata (prevent GC)
            PyObject* cb_ptr = callback.ptr();
            Py_INCREF(cb_ptr);
            tc_render_surface_set_on_resize(
                surface,
                [](tc_render_surface* s, int w, int h, void* userdata) {
                    nb::gil_scoped_acquire gil;
                    try {
                        nb::object cb = nb::borrow<nb::object>(reinterpret_cast<PyObject*>(userdata));
                        cb(w, h);
                    } catch (...) {
                        // Ignore
                    }
                },
                cb_ptr
            );
        }
    });

    // Notify resize (for Python surfaces to call)
    m.def("_render_surface_notify_resize", [](uintptr_t ptr, int width, int height) {
        tc_render_surface* surface = reinterpret_cast<tc_render_surface*>(ptr);
        tc_render_surface_notify_resize(surface, width, height);
    });
}

} // namespace termin
