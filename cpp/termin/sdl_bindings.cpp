#include "sdl_bindings.hpp"

#include <pybind11/pybind11.h>
#include <pybind11/stl.h>
#include <pybind11/functional.h>

#include "termin/platform/sdl_window.hpp"

namespace py = pybind11;

namespace termin {

void bind_sdl(py::module_& m) {
    // SDLWindow
    py::class_<SDLWindow, std::shared_ptr<SDLWindow>>(m, "SDLWindow")
        .def(py::init<int, int, const std::string&, SDLWindow*>(),
            py::arg("width"), py::arg("height"), py::arg("title"),
            py::arg("share") = nullptr)
        .def("close", &SDLWindow::close)
        .def("should_close", &SDLWindow::should_close)
        .def("set_should_close", &SDLWindow::set_should_close)
        .def("make_current", &SDLWindow::make_current)
        .def("swap_buffers", &SDLWindow::swap_buffers)
        .def("framebuffer_size", &SDLWindow::framebuffer_size)
        .def("window_size", &SDLWindow::window_size)
        .def("get_cursor_pos", &SDLWindow::get_cursor_pos)
        .def("get_window_id", &SDLWindow::get_window_id)
        .def("set_graphics", &SDLWindow::set_graphics, py::arg("graphics"))
        .def("get_window_framebuffer", &SDLWindow::get_window_framebuffer,
            py::return_value_policy::reference)
        // Callbacks - use lambdas to convert C++ callbacks to Python
        .def("set_framebuffer_size_callback", [](SDLWindow& self, py::object callback) {
            if (callback.is_none()) {
                self.set_framebuffer_size_callback(nullptr);
            } else {
                self.set_framebuffer_size_callback(
                    [callback](SDLWindow* win, int w, int h) {
                        py::gil_scoped_acquire gil;
                        callback(win, w, h);
                    }
                );
            }
        })
        .def("set_cursor_pos_callback", [](SDLWindow& self, py::object callback) {
            if (callback.is_none()) {
                self.set_cursor_pos_callback(nullptr);
            } else {
                self.set_cursor_pos_callback(
                    [callback](SDLWindow* win, double x, double y) {
                        py::gil_scoped_acquire gil;
                        callback(win, x, y);
                    }
                );
            }
        })
        .def("set_scroll_callback", [](SDLWindow& self, py::object callback) {
            if (callback.is_none()) {
                self.set_scroll_callback(nullptr);
            } else {
                self.set_scroll_callback(
                    [callback](SDLWindow* win, double x, double y) {
                        py::gil_scoped_acquire gil;
                        callback(win, x, y);
                    }
                );
            }
        })
        .def("set_mouse_button_callback", [](SDLWindow& self, py::object callback) {
            if (callback.is_none()) {
                self.set_mouse_button_callback(nullptr);
            } else {
                self.set_mouse_button_callback(
                    [callback](SDLWindow* win, int button, int action, int mods) {
                        py::gil_scoped_acquire gil;
                        callback(win, button, action, mods);
                    }
                );
            }
        })
        .def("set_key_callback", [](SDLWindow& self, py::object callback) {
            if (callback.is_none()) {
                self.set_key_callback(nullptr);
            } else {
                self.set_key_callback(
                    [callback](SDLWindow* win, int key, int scancode, int action, int mods) {
                        py::gil_scoped_acquire gil;
                        callback(win, key, scancode, action, mods);
                    }
                );
            }
        })
        // Constants
        .def_readonly_static("ACTION_RELEASE", &SDLWindow::ACTION_RELEASE)
        .def_readonly_static("ACTION_PRESS", &SDLWindow::ACTION_PRESS)
        .def_readonly_static("ACTION_REPEAT", &SDLWindow::ACTION_REPEAT)
        .def_readonly_static("MOUSE_BUTTON_LEFT", &SDLWindow::MOUSE_BUTTON_LEFT)
        .def_readonly_static("MOUSE_BUTTON_RIGHT", &SDLWindow::MOUSE_BUTTON_RIGHT)
        .def_readonly_static("MOUSE_BUTTON_MIDDLE", &SDLWindow::MOUSE_BUTTON_MIDDLE);

    // SDLWindowBackend
    py::class_<SDLWindowBackend, std::shared_ptr<SDLWindowBackend>>(m, "SDLWindowBackend")
        .def(py::init<>())
        .def("create_window", &SDLWindowBackend::create_window,
            py::arg("width"), py::arg("height"), py::arg("title"),
            py::arg("share") = nullptr)
        .def("poll_events", &SDLWindowBackend::poll_events)
        .def("terminate", &SDLWindowBackend::terminate);
}

} // namespace termin
