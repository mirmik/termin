#include "sdl_bindings.hpp"

#include <nanobind/nanobind.h>
#include <nanobind/stl/string.h>
#include <nanobind/stl/shared_ptr.h>

#include "termin/platform/sdl_window.hpp"
#include "termin/platform/sdl_render_surface.hpp"

namespace nb = nanobind;

namespace termin {

void bind_sdl(nb::module_& m) {
    // SDLWindow
    nb::class_<SDLWindow>(m, "SDLWindow")
        .def(nb::init<int, int, const std::string&, SDLWindow*>(),
            nb::arg("width"), nb::arg("height"), nb::arg("title"),
            nb::arg("share") = nullptr)
        .def("close", &SDLWindow::close)
        .def("should_close", &SDLWindow::should_close)
        .def("set_should_close", &SDLWindow::set_should_close)
        .def("make_current", &SDLWindow::make_current)
        .def("swap_buffers", &SDLWindow::swap_buffers)
        .def("framebuffer_size", &SDLWindow::framebuffer_size)
        .def("window_size", &SDLWindow::window_size)
        .def("get_cursor_pos", &SDLWindow::get_cursor_pos)
        .def("get_window_id", &SDLWindow::get_window_id)
        .def("set_graphics", &SDLWindow::set_graphics, nb::arg("graphics"))
        .def("get_window_framebuffer", &SDLWindow::get_window_framebuffer,
            nb::rv_policy::reference)
        // Callbacks - use lambdas to convert C++ callbacks to Python
        .def("set_framebuffer_size_callback", [](SDLWindow& self, nb::object callback) {
            if (callback.is_none()) {
                self.set_framebuffer_size_callback(nullptr);
            } else {
                self.set_framebuffer_size_callback(
                    [callback](SDLWindow* win, int w, int h) {
                        nb::gil_scoped_acquire gil;
                        callback(win, w, h);
                    }
                );
            }
        })
        .def("set_cursor_pos_callback", [](SDLWindow& self, nb::object callback) {
            if (callback.is_none()) {
                self.set_cursor_pos_callback(nullptr);
            } else {
                self.set_cursor_pos_callback(
                    [callback](SDLWindow* win, double x, double y) {
                        nb::gil_scoped_acquire gil;
                        callback(win, x, y);
                    }
                );
            }
        })
        .def("set_scroll_callback", [](SDLWindow& self, nb::object callback) {
            if (callback.is_none()) {
                self.set_scroll_callback(nullptr);
            } else {
                self.set_scroll_callback(
                    [callback](SDLWindow* win, double x, double y, int mods) {
                        nb::gil_scoped_acquire gil;
                        callback(win, x, y, mods);
                    }
                );
            }
        })
        .def("set_mouse_button_callback", [](SDLWindow& self, nb::object callback) {
            if (callback.is_none()) {
                self.set_mouse_button_callback(nullptr);
            } else {
                self.set_mouse_button_callback(
                    [callback](SDLWindow* win, int button, int action, int mods) {
                        nb::gil_scoped_acquire gil;
                        callback(win, button, action, mods);
                    }
                );
            }
        })
        .def("set_key_callback", [](SDLWindow& self, nb::object callback) {
            if (callback.is_none()) {
                self.set_key_callback(nullptr);
            } else {
                self.set_key_callback(
                    [callback](SDLWindow* win, int key, int scancode, int action, int mods) {
                        nb::gil_scoped_acquire gil;
                        callback(win, key, scancode, action, mods);
                    }
                );
            }
        })
        // Constants - using def_ro_static for nanobind
        .def_ro_static("ACTION_RELEASE", &SDLWindow::ACTION_RELEASE)
        .def_ro_static("ACTION_PRESS", &SDLWindow::ACTION_PRESS)
        .def_ro_static("ACTION_REPEAT", &SDLWindow::ACTION_REPEAT)
        .def_ro_static("MOUSE_BUTTON_LEFT", &SDLWindow::MOUSE_BUTTON_LEFT)
        .def_ro_static("MOUSE_BUTTON_RIGHT", &SDLWindow::MOUSE_BUTTON_RIGHT)
        .def_ro_static("MOUSE_BUTTON_MIDDLE", &SDLWindow::MOUSE_BUTTON_MIDDLE);

    // SDLWindowBackend
    nb::class_<SDLWindowBackend>(m, "SDLWindowBackend")
        .def(nb::init<>())
        .def("create_window", &SDLWindowBackend::create_window,
            nb::arg("width"), nb::arg("height"), nb::arg("title"),
            nb::arg("share") = nullptr)
        .def("poll_events", &SDLWindowBackend::poll_events)
        .def("terminate", &SDLWindowBackend::terminate);

    // SDLWindowRenderSurface - C++ render surface wrapping SDLWindow and tc_render_surface
    nb::class_<SDLWindowRenderSurface>(m, "SDLWindowRenderSurface")
        .def(nb::init<int, int, const std::string&, SDLWindowBackend*, SDLWindowRenderSurface*>(),
            nb::arg("width"), nb::arg("height"), nb::arg("title"),
            nb::arg("backend"), nb::arg("share") = nullptr,
            nb::keep_alive<1, 5>())  // keep backend alive
        .def("tc_surface", [](SDLWindowRenderSurface& self) {
            return self.tc_surface();
        }, nb::rv_policy::reference)
        .def("set_input_manager", &SDLWindowRenderSurface::set_input_manager,
            nb::arg("manager"), nb::keep_alive<1, 2>())
        .def("input_manager", &SDLWindowRenderSurface::input_manager,
            nb::rv_policy::reference)
        .def("window", [](SDLWindowRenderSurface& self) {
            return self.window();
        }, nb::rv_policy::reference)
        .def("window_id", &SDLWindowRenderSurface::window_id)
        .def("make_current", &SDLWindowRenderSurface::make_current)
        .def("swap_buffers", &SDLWindowRenderSurface::swap_buffers)
        .def("get_size", &SDLWindowRenderSurface::get_size)
        .def("window_size", &SDLWindowRenderSurface::window_size)
        .def("should_close", &SDLWindowRenderSurface::should_close)
        .def("set_should_close", &SDLWindowRenderSurface::set_should_close, nb::arg("value"))
        .def("get_cursor_pos", &SDLWindowRenderSurface::get_cursor_pos)
        .def("set_graphics", &SDLWindowRenderSurface::set_graphics, nb::arg("graphics"))
        .def("get_window_framebuffer", &SDLWindowRenderSurface::get_window_framebuffer,
            nb::rv_policy::reference)
        .def("get_native_handle", &SDLWindowRenderSurface::get_native_handle)
        .def("request_update", &SDLWindowRenderSurface::request_update)
        .def("needs_render", &SDLWindowRenderSurface::needs_render)
        .def("clear_render_flag", &SDLWindowRenderSurface::clear_render_flag)
        .def("check_resize", &SDLWindowRenderSurface::check_resize);
}

} // namespace termin
