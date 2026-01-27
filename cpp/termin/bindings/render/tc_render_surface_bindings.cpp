// tc_render_surface_bindings.cpp - Python bindings for tc_render_surface
#include <nanobind/nanobind.h>
#include <nanobind/stl/string.h>
#include <nanobind/stl/tuple.h>

#include "render/tc_render_surface.h"

namespace nb = nanobind;

namespace termin {

// ============================================================================
// VTable for SDLEmbeddedWindowHandle (Python class)
// One vtable shared by all instances of this type.
// Each function calls the corresponding method on the Python object (body).
// ============================================================================

static uint32_t sdl_window_get_framebuffer(tc_render_surface* s) {
    // Window framebuffer is always 0
    return 0;
}

static void sdl_window_get_size(tc_render_surface* s, int* width, int* height) {
    if (!s->body) {
        if (width) *width = 0;
        if (height) *height = 0;
        return;
    }
    nb::gil_scoped_acquire gil;
    try {
        nb::object py_obj = nb::borrow<nb::object>(reinterpret_cast<PyObject*>(s->body));
        nb::object result = py_obj.attr("framebuffer_size")();
        auto tup = nb::cast<std::tuple<int, int>>(result);
        if (width) *width = std::get<0>(tup);
        if (height) *height = std::get<1>(tup);
    } catch (const std::exception& e) {
        if (width) *width = 0;
        if (height) *height = 0;
    }
}

static void sdl_window_make_current(tc_render_surface* s) {
    if (!s->body) return;
    nb::gil_scoped_acquire gil;
    try {
        nb::object py_obj = nb::borrow<nb::object>(reinterpret_cast<PyObject*>(s->body));
        py_obj.attr("make_current")();
    } catch (const std::exception& e) {
        // Ignore
    }
}

static void sdl_window_swap_buffers(tc_render_surface* s) {
    if (!s->body) return;
    nb::gil_scoped_acquire gil;
    try {
        nb::object py_obj = nb::borrow<nb::object>(reinterpret_cast<PyObject*>(s->body));
        py_obj.attr("swap_buffers")();
    } catch (const std::exception& e) {
        // Ignore
    }
}

static uintptr_t sdl_window_context_key(tc_render_surface* s) {
    // Use body pointer as context key
    return reinterpret_cast<uintptr_t>(s->body);
}

static void sdl_window_poll_events(tc_render_surface* s) {
    // No-op - events are polled via SDLEmbeddedWindowBackend
}

static void sdl_window_get_window_size(tc_render_surface* s, int* width, int* height) {
    if (!s->body) {
        if (width) *width = 0;
        if (height) *height = 0;
        return;
    }
    nb::gil_scoped_acquire gil;
    try {
        nb::object py_obj = nb::borrow<nb::object>(reinterpret_cast<PyObject*>(s->body));
        nb::object result = py_obj.attr("window_size")();
        auto tup = nb::cast<std::tuple<int, int>>(result);
        if (width) *width = std::get<0>(tup);
        if (height) *height = std::get<1>(tup);
    } catch (const std::exception& e) {
        if (width) *width = 0;
        if (height) *height = 0;
    }
}

static bool sdl_window_should_close(tc_render_surface* s) {
    if (!s->body) return true;
    nb::gil_scoped_acquire gil;
    try {
        nb::object py_obj = nb::borrow<nb::object>(reinterpret_cast<PyObject*>(s->body));
        nb::object result = py_obj.attr("should_close")();
        return nb::cast<bool>(result);
    } catch (const std::exception& e) {
        return true;
    }
}

static void sdl_window_set_should_close(tc_render_surface* s, bool value) {
    if (!s->body) return;
    nb::gil_scoped_acquire gil;
    try {
        nb::object py_obj = nb::borrow<nb::object>(reinterpret_cast<PyObject*>(s->body));
        py_obj.attr("_should_close") = value;
    } catch (const std::exception& e) {
        // Ignore
    }
}

static void sdl_window_get_cursor_pos(tc_render_surface* s, double* x, double* y) {
    if (!s->body) {
        if (x) *x = 0.0;
        if (y) *y = 0.0;
        return;
    }
    nb::gil_scoped_acquire gil;
    try {
        nb::object py_obj = nb::borrow<nb::object>(reinterpret_cast<PyObject*>(s->body));
        nb::object result = py_obj.attr("get_cursor_pos")();
        auto tup = nb::cast<std::tuple<double, double>>(result);
        if (x) *x = std::get<0>(tup);
        if (y) *y = std::get<1>(tup);
    } catch (const std::exception& e) {
        if (x) *x = 0.0;
        if (y) *y = 0.0;
    }
}

static void sdl_window_destroy(tc_render_surface* s) {
    // No-op: Python owns the surface and will free it
}

// Static vtable for SDLEmbeddedWindowHandle
static const tc_render_surface_vtable g_sdl_window_vtable = {
    .get_framebuffer = sdl_window_get_framebuffer,
    .get_size = sdl_window_get_size,
    .make_current = sdl_window_make_current,
    .swap_buffers = sdl_window_swap_buffers,
    .context_key = sdl_window_context_key,
    .poll_events = sdl_window_poll_events,
    .get_window_size = sdl_window_get_window_size,
    .should_close = sdl_window_should_close,
    .set_should_close = sdl_window_set_should_close,
    .get_cursor_pos = sdl_window_get_cursor_pos,
    .destroy = sdl_window_destroy,
};

// ============================================================================
// Python Bindings
// ============================================================================

void bind_tc_render_surface(nb::module_& m) {
    // Create tc_render_surface for SDLEmbeddedWindowHandle
    m.def("_render_surface_new_sdl_window", [](nb::object py_surface) -> uintptr_t {
        PyObject* ptr = py_surface.ptr();
        tc_render_surface* surface = tc_render_surface_new_external(ptr, &g_sdl_window_vtable);
        return reinterpret_cast<uintptr_t>(surface);
    });

    // Free external render surface
    m.def("_render_surface_free_external", [](uintptr_t ptr) {
        tc_render_surface* surface = reinterpret_cast<tc_render_surface*>(ptr);
        tc_render_surface_free_external(surface);
    });

    // Get pointer from tc_render_surface (for passing to C code)
    m.def("_render_surface_get_ptr", [](uintptr_t ptr) -> uintptr_t {
        return ptr;
    });

    // Set input manager for render surface
    m.def("_render_surface_set_input_manager", [](uintptr_t surface_ptr, uintptr_t input_manager_ptr) {
        tc_render_surface* surface = reinterpret_cast<tc_render_surface*>(surface_ptr);
        tc_input_manager* input_manager = reinterpret_cast<tc_input_manager*>(input_manager_ptr);
        tc_render_surface_set_input_manager(surface, input_manager);
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
                    } catch (const std::exception& e) {
                        // Ignore
                    }
                },
                cb_ptr
            );
        }
    });

    // Notify resize (call from Python when window resizes)
    m.def("_render_surface_notify_resize", [](uintptr_t ptr, int width, int height) {
        tc_render_surface* surface = reinterpret_cast<tc_render_surface*>(ptr);
        tc_render_surface_notify_resize(surface, width, height);
    });
}

} // namespace termin
