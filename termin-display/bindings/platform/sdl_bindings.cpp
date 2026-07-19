#include "sdl_bindings.hpp"

#include "tgfx2/device_factory.hpp"

#include <nanobind/nanobind.h>
#include <nanobind/stl/string.h>
#include <nanobind/stl/shared_ptr.h>
#include <nanobind/stl/pair.h>

#include <cstdint>
#include <array>
#include <stdexcept>
#include <string>

#include <tcbase/tc_log.h>

#include "termin/platform/sdl_window.hpp"
#include "termin/platform/sdl_render_surface.hpp"
#include "termin/platform/sdl_backend_window.hpp"
#include "termin/input/window_input_bridge.hpp"

#include "tgfx2/handles.hpp"
#include "tgfx2/i_render_device.hpp"
#include "tgfx2/render_context.hpp"

namespace nb = nanobind;

namespace termin {

namespace {

enum class SystemCursorShape : int {
    Default = 0,
    Text = 1,
    Hand = 2,
    Crosshair = 3,
    Move = 4,
    ResizeHorizontal = 5,
    ResizeVertical = 6,
    ResizeNwse = 7,
    ResizeNesw = 8,
    Count = 9,
};

std::array<SDL_Cursor*, static_cast<size_t>(SystemCursorShape::Count)> system_cursors{};
std::array<bool, static_cast<size_t>(SystemCursorShape::Count)> unavailable_system_cursors{};

SDL_SystemCursor to_sdl_cursor(SystemCursorShape shape) {
    switch (shape) {
        case SystemCursorShape::Default: return SDL_SYSTEM_CURSOR_ARROW;
        case SystemCursorShape::Text: return SDL_SYSTEM_CURSOR_IBEAM;
        case SystemCursorShape::Hand: return SDL_SYSTEM_CURSOR_HAND;
        case SystemCursorShape::Crosshair: return SDL_SYSTEM_CURSOR_CROSSHAIR;
        case SystemCursorShape::Move: return SDL_SYSTEM_CURSOR_SIZEALL;
        case SystemCursorShape::ResizeHorizontal: return SDL_SYSTEM_CURSOR_SIZEWE;
        case SystemCursorShape::ResizeVertical: return SDL_SYSTEM_CURSOR_SIZENS;
        case SystemCursorShape::ResizeNwse: return SDL_SYSTEM_CURSOR_SIZENWSE;
        case SystemCursorShape::ResizeNesw: return SDL_SYSTEM_CURSOR_SIZENESW;
        case SystemCursorShape::Count: break;
    }
    throw std::invalid_argument("invalid system cursor shape");
}

void set_system_cursor(SystemCursorShape shape) {
    SDL_Cursor* cursor = nullptr;
    if (shape == SystemCursorShape::Default) {
        cursor = SDL_GetDefaultCursor();
    }
    const size_t index = static_cast<size_t>(shape);
    if (!cursor) {
        if (unavailable_system_cursors[index]) {
            return;
        }
        cursor = system_cursors[index];
        if (!cursor) {
            cursor = SDL_CreateSystemCursor(to_sdl_cursor(shape));
            if (cursor) {
                system_cursors[index] = cursor;
            } else {
                const char* error = SDL_GetError();
                tc_log_warn(
                    "[termin-display] system cursor %d is unavailable: %s",
                    static_cast<int>(shape),
                    error && error[0] ? error : "SDL returned no error detail"
                );
                unavailable_system_cursors[index] = true;
                SDL_ClearError();
                return;
            }
        }
    }
    SDL_SetCursor(cursor);
}

void release_system_cursors() {
    SDL_Cursor* default_cursor = SDL_GetDefaultCursor();
    bool default_is_owned = false;
    for (SDL_Cursor* cursor : system_cursors) {
        default_is_owned = default_is_owned || cursor == default_cursor;
    }
    if (default_cursor && !default_is_owned) {
        SDL_SetCursor(default_cursor);
    } else {
        SDL_SetCursor(nullptr);
    }
    for (size_t index = 0; index < system_cursors.size(); ++index) {
        if (system_cursors[index]) {
            SDL_FreeCursor(system_cursors[index]);
            system_cursors[index] = nullptr;
        }
        unavailable_system_cursors[index] = false;
    }
}

constexpr int TC_KEY_UNKNOWN = -1;
constexpr int TC_KEY_TAB = 9;
constexpr int TC_KEY_ENTER = 13;
constexpr int TC_KEY_SPACE = 32;
constexpr int TC_KEY_ESCAPE = 256;
constexpr int TC_KEY_BACKSPACE = 259;
constexpr int TC_KEY_DELETE = 261;
constexpr int TC_KEY_RIGHT = 262;
constexpr int TC_KEY_LEFT = 263;
constexpr int TC_KEY_DOWN = 264;
constexpr int TC_KEY_UP = 265;
constexpr int TC_KEY_HOME = 268;
constexpr int TC_KEY_END = 269;

uint32_t sdl_event_window_id(const SDL_Event& event) {
    switch (event.type) {
        case SDL_WINDOWEVENT:
            return event.window.windowID;
        case SDL_MOUSEMOTION:
            return event.motion.windowID;
        case SDL_MOUSEBUTTONDOWN:
        case SDL_MOUSEBUTTONUP:
            return event.button.windowID;
        case SDL_MOUSEWHEEL:
            return event.wheel.windowID;
        case SDL_KEYDOWN:
        case SDL_KEYUP:
            return event.key.windowID;
        case SDL_TEXTINPUT:
            return event.text.windowID;
        case SDL_DROPFILE:
            return event.drop.windowID;
        default:
            return 0;
    }
}

int translate_sdl_key(SDL_Scancode scancode) {
    // Commands and shortcuts must not depend on the active keyboard layout.
    // Text entry is delivered separately through SDL_TEXTINPUT, so map the
    // physical alphanumeric keys to their stable editor key codes here.
    if (scancode >= SDL_SCANCODE_A && scancode <= SDL_SCANCODE_Z) {
        return 'A' + (scancode - SDL_SCANCODE_A);
    }
    if (scancode >= SDL_SCANCODE_1 && scancode <= SDL_SCANCODE_9) {
        return '1' + (scancode - SDL_SCANCODE_1);
    }
    if (scancode == SDL_SCANCODE_0) {
        return '0';
    }

    switch (scancode) {
        case SDL_SCANCODE_BACKSPACE:
            return TC_KEY_BACKSPACE;
        case SDL_SCANCODE_DELETE:
            return TC_KEY_DELETE;
        case SDL_SCANCODE_LEFT:
            return TC_KEY_LEFT;
        case SDL_SCANCODE_RIGHT:
            return TC_KEY_RIGHT;
        case SDL_SCANCODE_UP:
            return TC_KEY_UP;
        case SDL_SCANCODE_DOWN:
            return TC_KEY_DOWN;
        case SDL_SCANCODE_HOME:
            return TC_KEY_HOME;
        case SDL_SCANCODE_END:
            return TC_KEY_END;
        case SDL_SCANCODE_RETURN:
            return TC_KEY_ENTER;
        case SDL_SCANCODE_ESCAPE:
            return TC_KEY_ESCAPE;
        case SDL_SCANCODE_TAB:
            return TC_KEY_TAB;
        case SDL_SCANCODE_SPACE:
            return TC_KEY_SPACE;
        default:
            break;
    }

    int keycode = SDL_GetKeyFromScancode(scancode);
    if (keycode >= 'a' && keycode <= 'z') {
        keycode -= ('a' - 'A');
    }
    if (keycode >= 0 && keycode < 128) {
        return keycode;
    }
    return TC_KEY_UNKNOWN;
}

nb::dict make_base_event(const char* type, const SDL_Event& event) {
    nb::dict result;
    result["type"] = type;
    result["window_id"] = sdl_event_window_id(event);
    return result;
}

nb::object translate_sdl_event(const SDL_Event& event) {
    switch (event.type) {
        case SDL_QUIT:
            return make_base_event("quit", event);

        case SDL_WINDOWEVENT:
            if (event.window.event == SDL_WINDOWEVENT_CLOSE) {
                return make_base_event("window_close", event);
            }
            switch (event.window.event) {
                case SDL_WINDOWEVENT_SHOWN:
                case SDL_WINDOWEVENT_EXPOSED:
                case SDL_WINDOWEVENT_RESIZED:
                case SDL_WINDOWEVENT_SIZE_CHANGED:
                case SDL_WINDOWEVENT_RESTORED:
                case SDL_WINDOWEVENT_MAXIMIZED:
                case SDL_WINDOWEVENT_FOCUS_GAINED:
                    return make_base_event("window_refresh", event);
                case SDL_WINDOWEVENT_LEAVE:
                    return make_base_event("mouse_leave", event);
                default:
                    break;
            }
            return nb::none();

        case SDL_MOUSEMOTION: {
            nb::dict result = make_base_event("mouse_move", event);
            result["x"] = static_cast<double>(event.motion.x);
            result["y"] = static_cast<double>(event.motion.y);
            result["mods"] = SDLWindow::translate_sdl_mods(SDL_GetModState());
            return result;
        }

        case SDL_MOUSEBUTTONDOWN:
        case SDL_MOUSEBUTTONUP: {
            nb::dict result = make_base_event(
                event.type == SDL_MOUSEBUTTONDOWN ? "mouse_down" : "mouse_up",
                event
            );
            result["x"] = static_cast<double>(event.button.x);
            result["y"] = static_cast<double>(event.button.y);
            result["button"] = SDLWindow::translate_mouse_button(event.button.button);
            result["click_count"] = static_cast<int>(event.button.clicks);
            result["mods"] = SDLWindow::translate_sdl_mods(SDL_GetModState());
            return result;
        }

        case SDL_MOUSEWHEEL: {
            int x = 0;
            int y = 0;
            SDL_GetMouseState(&x, &y);

            nb::dict result = make_base_event("mouse_wheel", event);
            result["dx"] = static_cast<double>(event.wheel.x);
            result["dy"] = static_cast<double>(event.wheel.y);
            result["x"] = static_cast<double>(x);
            result["y"] = static_cast<double>(y);
            result["mods"] = SDLWindow::translate_sdl_mods(SDL_GetModState());
            return result;
        }

        case SDL_KEYDOWN:
        case SDL_KEYUP: {
            nb::dict result = make_base_event(
                event.type == SDL_KEYDOWN ? "key_down" : "key_up",
                event
            );
            result["key"] = translate_sdl_key(event.key.keysym.scancode);
            result["scancode"] = static_cast<int>(event.key.keysym.scancode);
            result["mods"] = SDLWindow::translate_sdl_mods(event.key.keysym.mod);
            result["repeat"] = event.key.repeat != 0;
            return result;
        }

        case SDL_TEXTINPUT: {
            nb::dict result = make_base_event("text_input", event);
            result["text"] = std::string(event.text.text);
            return result;
        }

        case SDL_DROPFILE: {
            nb::dict result = make_base_event("file_drop", event);
            result["path"] = event.drop.file ? std::string(event.drop.file) : std::string();

            int x = 0;
            int y = 0;
            SDL_GetMouseState(&x, &y);
            result["x"] = static_cast<double>(x);
            result["y"] = static_cast<double>(y);
            result["mods"] = SDLWindow::translate_sdl_mods(SDL_GetModState());

            if (event.drop.file) {
                SDL_free(event.drop.file);
            }
            return result;
        }

        default:
            return nb::none();
    }
}

void append_translated_event(nb::list& events, const SDL_Event& event) {
    nb::object translated = translate_sdl_event(event);
    if (!translated.is_none()) {
        events.append(translated);
    }
}

nb::list poll_sdl_events() {
    nb::list events;
    SDL_Event event;
    while (SDL_PollEvent(&event) != 0) {
        append_translated_event(events, event);
    }
    return events;
}

nb::list wait_sdl_events_timeout(int timeout_ms) {
    nb::list events;
    SDL_Event event;
    if (SDL_WaitEventTimeout(&event, timeout_ms) == 0) {
        return events;
    }

    append_translated_event(events, event);
    while (SDL_PollEvent(&event) != 0) {
        append_translated_event(events, event);
    }
    return events;
}

} // namespace

void bind_sdl(nb::module_& m) {
    nb::enum_<SystemCursorShape>(m, "SystemCursorShape")
        .value("Default", SystemCursorShape::Default)
        .value("Text", SystemCursorShape::Text)
        .value("Hand", SystemCursorShape::Hand)
        .value("Crosshair", SystemCursorShape::Crosshair)
        .value("Move", SystemCursorShape::Move)
        .value("ResizeHorizontal", SystemCursorShape::ResizeHorizontal)
        .value("ResizeVertical", SystemCursorShape::ResizeVertical)
        .value("ResizeNwse", SystemCursorShape::ResizeNwse)
        .value("ResizeNesw", SystemCursorShape::ResizeNesw);
    m.def("set_system_cursor", &set_system_cursor, nb::arg("shape"));
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
    m.def("start_text_input", []() {
        SDL_StartTextInput();
    });
    m.def("stop_text_input", []() {
        SDL_StopTextInput();
    });
    m.def("quit_sdl", []() {
        release_system_cursors();
        SDL_Quit();
    });
    m.def("poll_sdl_events", &poll_sdl_events,
        "Drain SDL events and return Termin event dictionaries without exposing SDL_Event.");
    m.def("wait_sdl_events_timeout", &wait_sdl_events_timeout, nb::arg("timeout_ms"),
        "Wait for one SDL event, drain pending events, and return Termin event dictionaries.");

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
                    [callback](SDLWindow* win, int button, int action, int mods,
                               uint32_t click_count) {
                        nb::gil_scoped_acquire gil;
                        callback(win, button, action, mods, click_count);
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
    nb::enum_<tgfx::PresentationMode>(m, "PresentationMode")
        .value("VSYNC", tgfx::PresentationMode::VSync)
        .value("IMMEDIATE", tgfx::PresentationMode::Immediate);

    nb::class_<SDLBackendWindow, BackendWindow>(m, "SDLBackendWindow")
        .def(nb::init<const std::string&, int, int, tgfx::PresentationMode>(),
             nb::arg("title"), nb::arg("width"), nb::arg("height"),
             nb::arg("presentation_mode") = tgfx::PresentationMode::VSync)
        .def(nb::init<const std::string&, int, int, SDLBackendWindow&>(),
             nb::arg("title"), nb::arg("width"), nb::arg("height"),
             nb::arg("share_with"),
             "Secondary-window ctor: reuses `share_with`'s IRenderDevice "
             "and RenderContext2. Creates its own SDL window + GL context "
             "(OpenGL) or Vulkan surface + swapchain.")
        .def("device", &SDLBackendWindow::device, nb::rv_policy::reference_internal,
             "tgfx::IRenderDevice bound to this window. Outlives the window.")
        .def("context", &SDLBackendWindow::context, nb::rv_policy::reference_internal,
             "tgfx::RenderContext2 bound to this window's device. Lazy-built.")
        .def_prop_ro("backend", [](const SDLBackendWindow& self) {
                return std::string(tgfx::backend_name(self.backend_type()));
            },
            "Name of the backend actually created for this window.")
        .def_prop_ro("presentation_mode", &SDLBackendWindow::presentation_mode,
            "Presentation mode actually applied to this window group.")
        .def_prop_ro("requested_presentation_mode", &SDLBackendWindow::requested_presentation_mode,
            "Presentation mode requested when the primary window was created.")
        // Opaque pointers for cross-module (nanobind) handshakes. Python
        // code in tgfx._tgfx_native calls `Tgfx2Context.borrow(dev_ptr,
        // ctx_ptr)` with these to produce a non-owning holder — we cannot
        // return the C++ objects directly because IRenderDevice /
        // RenderContext2 are registered in another .so's nanobind type
        // table.
        .def("device_ptr", [](SDLBackendWindow& self) -> uintptr_t {
                return reinterpret_cast<uintptr_t>(self.device());
            },
            "uintptr_t to the bound IRenderDevice. Pass to "
            "tgfx._tgfx_native.Tgfx2Context.borrow.")
        .def("context_ptr", [](SDLBackendWindow& self) -> uintptr_t {
                return reinterpret_cast<uintptr_t>(self.context());
            },
            "uintptr_t to the bound RenderContext2 (lazy-built on first "
            "call). Pass to tgfx._tgfx_native.Tgfx2Context.borrow.")
        .def("should_close", &SDLBackendWindow::should_close)
        .def("set_should_close", &SDLBackendWindow::set_should_close, nb::arg("value"))
        .def("set_input_manager", [](SDLBackendWindow& self, uintptr_t input_manager_ptr) {
                attach_window_input_manager(
                    self,
                    reinterpret_cast<tc_input_manager*>(input_manager_ptr));
            },
            nb::arg("input_manager_ptr"),
            "Route SDL input events from this window to a tc_input_manager.")
        .def("set_title", &SDLBackendWindow::set_title,
            nb::arg("title"),
            "Set the OS window title.")
        .def("maximize", &SDLBackendWindow::maximize,
             "Maximize the OS window via SDL_MaximizeWindow.")
        .def("set_icon_bmp", &SDLBackendWindow::set_icon_bmp,
             nb::arg("path"),
             "Load a BMP file and use it as the OS window icon. Raises on load failure.")
        .def("set_fullscreen", &SDLBackendWindow::set_fullscreen,
             nb::arg("enabled"),
             "Toggle borderless desktop fullscreen via SDL_SetWindowFullscreen.")
        .def("set_always_on_top", &SDLBackendWindow::set_always_on_top,
             nb::arg("enabled"),
             "Set whether the OS window should stay above normal windows.")
        .def("close", &SDLBackendWindow::close,
             "Release OS-level resources (SDL window, GL context, "
             "Vulkan surface+swapchain). Idempotent.")
        .def("window_id", [](SDLBackendWindow& self) -> uint32_t {
                SDL_Window* w = self.sdl_window();
                return w ? SDL_GetWindowID(w) : 0;
            },
            "SDL_GetWindowID of the underlying SDL_Window. Used to "
            "route incoming SDL events to the right UI.")
        .def("poll_events", &SDLBackendWindow::poll_events,
             "Drain SDL events, flip should_close on SDL_QUIT / window-close "
             "/ ESC. For finer control use the SDL module directly.")
        .def("framebuffer_size", &SDLBackendWindow::framebuffer_size,
             "Drawable size (width, height). Updates after host resize; "
             "the next present() will recreate the Vulkan swapchain.")
        .def("present", &SDLBackendWindow::present, nb::arg("color_tex"),
             "Publish color_tex to the window surface. GL: blit + SwapWindow. "
             "Vulkan: acquire + compose + present.");
}

} // namespace termin
