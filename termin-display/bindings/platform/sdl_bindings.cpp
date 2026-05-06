#include "sdl_bindings.hpp"

#include <nanobind/nanobind.h>
#include <nanobind/stl/string.h>
#include <nanobind/stl/shared_ptr.h>
#include <nanobind/stl/pair.h>

#include "termin/platform/sdl_window.hpp"
#include "termin/platform/sdl_render_surface.hpp"
#include "termin/platform/backend_window.hpp"

#include "tgfx2/handles.hpp"
#include "tgfx2/i_render_device.hpp"
#include "tgfx2/render_context.hpp"

namespace nb = nanobind;

namespace termin {

void bind_sdl(nb::module_& m) {
    m.def("get_clipboard_text", []() -> std::string {
        char* raw = SDL_GetClipboardText();
        if (!raw) {
            return "";
        }
        std::string text(raw);
        SDL_free(raw);
        return text;
    });
    m.def("set_clipboard_text", [](const std::string& text) {
        SDL_SetClipboardText(text.c_str());
    }, nb::arg("text"));

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
        .def("tc_surface_ptr", [](SDLWindowRenderSurface& self) -> uintptr_t {
            return reinterpret_cast<uintptr_t>(self.tc_surface());
        })
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
        .def("get_native_handle", &SDLWindowRenderSurface::get_native_handle)
        .def("request_update", &SDLWindowRenderSurface::request_update)
        .def("needs_render", &SDLWindowRenderSurface::needs_render)
        .def("clear_render_flag", &SDLWindowRenderSurface::clear_render_flag)
        .def("check_resize", &SDLWindowRenderSurface::check_resize);

    // --- BackendWindow: the backend-neutral SDL wrapper. ---
    //
    // Apps write the same Python code under TERMIN_BACKEND=opengl and
    // TERMIN_BACKEND=vulkan. The ctor reads the env-var and spins up
    // the right SDL window flags + IRenderDevice internally.
    //
    //   from tgfx import _tgfx_native   # ensures Tgfx2* types registered
    //   from termin.display._platform_native import BackendWindow
    //   win = BackendWindow("Editor", 1280, 720)
    //   dev = win.device()
    //   while not win.should_close():
    //       win.poll_events()
    //       # render into my_color_tex via dev
    //       win.present(my_color_tex)
    nb::class_<BackendWindow>(m, "BackendWindow")
        .def(nb::init<const std::string&, int, int>(),
             nb::arg("title"), nb::arg("width"), nb::arg("height"))
        .def(nb::init<const std::string&, int, int, BackendWindow&>(),
             nb::arg("title"), nb::arg("width"), nb::arg("height"),
             nb::arg("share_with"),
             "Secondary-window ctor: reuses `share_with`'s IRenderDevice "
             "and RenderContext2. Creates its own SDL window + GL context "
             "(OpenGL) or Vulkan surface + swapchain.")
        .def("device", &BackendWindow::device, nb::rv_policy::reference_internal,
             "tgfx::IRenderDevice bound to this window. Outlives the window.")
        .def("context", &BackendWindow::context, nb::rv_policy::reference_internal,
             "tgfx::RenderContext2 bound to this window's device. Lazy-built.")
        // Opaque pointers for cross-module (nanobind) handshakes. Python
        // code in tgfx._tgfx_native calls `Tgfx2Context.borrow(dev_ptr,
        // ctx_ptr)` with these to produce a non-owning holder — we cannot
        // return the C++ objects directly because IRenderDevice /
        // RenderContext2 are registered in another .so's nanobind type
        // table.
        .def("device_ptr", [](BackendWindow& self) -> uintptr_t {
                return reinterpret_cast<uintptr_t>(self.device());
            },
            "uintptr_t to the bound IRenderDevice. Pass to "
            "tgfx._tgfx_native.Tgfx2Context.borrow.")
        .def("context_ptr", [](BackendWindow& self) -> uintptr_t {
                return reinterpret_cast<uintptr_t>(self.context());
            },
            "uintptr_t to the bound RenderContext2 (lazy-built on first "
            "call). Pass to tgfx._tgfx_native.Tgfx2Context.borrow.")
        .def("should_close", &BackendWindow::should_close)
        .def("set_should_close", &BackendWindow::set_should_close, nb::arg("value"))
        .def("set_title", [](BackendWindow& self, const std::string& title) {
                SDL_Window* w = self.sdl_window();
                if (w) {
                    SDL_SetWindowTitle(w, title.c_str());
                }
            },
            nb::arg("title"),
            "Set the OS window title.")
        .def("maximize", &BackendWindow::maximize,
             "Maximize the OS window via SDL_MaximizeWindow.")
        .def("close", &BackendWindow::close,
             "Release OS-level resources (SDL window, GL context, "
             "Vulkan surface+swapchain). Idempotent.")
        .def("window_id", [](BackendWindow& self) -> uint32_t {
                SDL_Window* w = self.sdl_window();
                return w ? SDL_GetWindowID(w) : 0;
            },
            "SDL_GetWindowID of the underlying SDL_Window. Used to "
            "route incoming SDL events to the right UI.")
        .def("poll_events", &BackendWindow::poll_events,
             "Drain SDL events, flip should_close on SDL_QUIT / window-close "
             "/ ESC. For finer control use the SDL module directly.")
        .def("framebuffer_size", &BackendWindow::framebuffer_size,
             "Drawable size (width, height). Updates after host resize; "
             "the next present() will recreate the Vulkan swapchain.")
        .def("present", &BackendWindow::present, nb::arg("color_tex"),
             "Publish color_tex to the window surface. GL: blit + SwapWindow. "
             "Vulkan: acquire + compose + present.");
}

} // namespace termin
