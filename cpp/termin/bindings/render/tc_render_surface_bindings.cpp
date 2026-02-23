// tc_render_surface_bindings.cpp - Python bindings for tc_render_surface
#include <nanobind/nanobind.h>
#include <nanobind/stl/string.h>
#include <nanobind/stl/tuple.h>

#include "render/tc_render_surface.h"
#include <tcbase/tc_log.hpp>

namespace nb = nanobind;

namespace termin {

// ============================================================================
// Generic VTable for Python render surface objects.
// Works with any Python object that implements the required methods:
//   framebuffer_size(), make_current(), swap_buffers(), window_size(),
//   should_close(), get_cursor_pos(), get_framebuffer() (optional).
// Used by SDLEmbeddedWindowHandle, QtGLWindowHandle, etc.
// ============================================================================

static uint32_t pysurface_get_framebuffer(tc_render_surface* s) {
    if (!s->body) return 0;
    nb::gil_scoped_acquire gil;
    try {
        nb::object py_obj = nb::borrow<nb::object>(reinterpret_cast<PyObject*>(s->body));
        // get_framebuffer_id() returns raw OpenGL FBO id (uint32_t).
        // Separate from get_framebuffer() which returns FramebufferHandle for Python.
        return nb::cast<uint32_t>(py_obj.attr("get_framebuffer_id")());
    } catch (const std::exception& e) {
        tc::Log::error("pysurface_get_framebuffer failed: %s", e.what());
    }
    return 0;
}

static void pysurface_get_size(tc_render_surface* s, int* width, int* height) {
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

static void pysurface_make_current(tc_render_surface* s) {
    if (!s->body) return;
    nb::gil_scoped_acquire gil;
    try {
        nb::object py_obj = nb::borrow<nb::object>(reinterpret_cast<PyObject*>(s->body));
        py_obj.attr("make_current")();
    } catch (const std::exception& e) {
        // Ignore
    }
}

static void pysurface_swap_buffers(tc_render_surface* s) {
    if (!s->body) return;
    nb::gil_scoped_acquire gil;
    try {
        nb::object py_obj = nb::borrow<nb::object>(reinterpret_cast<PyObject*>(s->body));
        py_obj.attr("swap_buffers")();
    } catch (const std::exception& e) {
        // Ignore
    }
}

static uintptr_t pysurface_context_key(tc_render_surface* s) {
    // Use body pointer as context key
    return reinterpret_cast<uintptr_t>(s->body);
}

static void pysurface_poll_events(tc_render_surface* s) {
    // No-op - events are polled by the backend
}

static void pysurface_get_window_size(tc_render_surface* s, int* width, int* height) {
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

static bool pysurface_should_close(tc_render_surface* s) {
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

static void pysurface_set_should_close(tc_render_surface* s, bool value) {
    if (!s->body) return;
    nb::gil_scoped_acquire gil;
    try {
        nb::object py_obj = nb::borrow<nb::object>(reinterpret_cast<PyObject*>(s->body));
        py_obj.attr("set_should_close")(value);
    } catch (const std::exception& e) {
        // Ignore
    }
}

static void pysurface_get_cursor_pos(tc_render_surface* s, double* x, double* y) {
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

static void pysurface_destroy(tc_render_surface* s) {
    // No-op: Python owns the surface and will free it
}

static uintptr_t pysurface_share_group_key(tc_render_surface* s) {
    if (!s->body) return reinterpret_cast<uintptr_t>(s->body);
    nb::gil_scoped_acquire gil;
    try {
        nb::object py_obj = nb::borrow<nb::object>(reinterpret_cast<PyObject*>(s->body));
        if (nb::hasattr(py_obj, "share_group_key")) {
            return nb::cast<uintptr_t>(py_obj.attr("share_group_key")());
        }
    } catch (const std::exception& e) {
        tc::Log::error("pysurface_share_group_key failed: %s", e.what());
    }
    // Fallback: same as context_key (no sharing)
    return pysurface_context_key(s);
}

// Generic vtable for Python render surface objects
static const tc_render_surface_vtable g_python_surface_vtable = {
    .get_framebuffer = pysurface_get_framebuffer,
    .get_size = pysurface_get_size,
    .make_current = pysurface_make_current,
    .swap_buffers = pysurface_swap_buffers,
    .context_key = pysurface_context_key,
    .poll_events = pysurface_poll_events,
    .get_window_size = pysurface_get_window_size,
    .should_close = pysurface_should_close,
    .set_should_close = pysurface_set_should_close,
    .get_cursor_pos = pysurface_get_cursor_pos,
    .destroy = pysurface_destroy,
    .share_group_key = pysurface_share_group_key,
};

// ============================================================================
// Python Bindings
// ============================================================================

void bind_tc_render_surface(nb::module_& m) {
    // Create tc_render_surface from any Python object with the required methods
    m.def("_render_surface_new_from_python", [](nb::object py_surface) -> uintptr_t {
        PyObject* ptr = py_surface.ptr();
        tc_render_surface* surface = tc_render_surface_new_external(ptr, &g_python_surface_vtable);
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
