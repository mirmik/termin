#pragma once

#include <SDL2/SDL.h>
#include <glad/glad.h>

#include <functional>
#include <memory>
#include <string>
#include <unordered_map>

#include "termin/render/opengl/opengl_backend.hpp"

namespace termin {

/**
 * SDL2 window with OpenGL context.
 */
class SDLWindow {
public:
    // Callback types
    using FramebufferSizeCallback = std::function<void(SDLWindow*, int, int)>;
    using CursorPosCallback = std::function<void(SDLWindow*, double, double)>;
    using ScrollCallback = std::function<void(SDLWindow*, double, double, int)>;  // x, y, mods
    using MouseButtonCallback = std::function<void(SDLWindow*, int, int, int)>;  // button, action, mods
    using KeyCallback = std::function<void(SDLWindow*, int, int, int, int)>;  // key, scancode, action, mods

    // Actions
    static constexpr int ACTION_RELEASE = 0;
    static constexpr int ACTION_PRESS = 1;
    static constexpr int ACTION_REPEAT = 2;

    // Mouse buttons
    static constexpr int MOUSE_BUTTON_LEFT = 0;
    static constexpr int MOUSE_BUTTON_RIGHT = 1;
    static constexpr int MOUSE_BUTTON_MIDDLE = 2;

    SDLWindow(int width, int height, const std::string& title, SDLWindow* share = nullptr)
        : window_(nullptr), gl_context_(nullptr), should_close_(false),
          last_width_(width), last_height_(height), graphics_(nullptr) {

        // OpenGL attributes
        SDL_GL_SetAttribute(SDL_GL_CONTEXT_MAJOR_VERSION, 3);
        SDL_GL_SetAttribute(SDL_GL_CONTEXT_MINOR_VERSION, 3);
        SDL_GL_SetAttribute(SDL_GL_CONTEXT_PROFILE_MASK, SDL_GL_CONTEXT_PROFILE_CORE);
        SDL_GL_SetAttribute(SDL_GL_DOUBLEBUFFER, 1);
        SDL_GL_SetAttribute(SDL_GL_DEPTH_SIZE, 24);

        Uint32 flags = SDL_WINDOW_OPENGL | SDL_WINDOW_RESIZABLE | SDL_WINDOW_SHOWN;

        window_ = SDL_CreateWindow(
            title.c_str(),
            SDL_WINDOWPOS_CENTERED, SDL_WINDOWPOS_CENTERED,
            width, height,
            flags
        );

        if (!window_) {
            throw std::runtime_error(std::string("Failed to create SDL window: ") + SDL_GetError());
        }

        // Share context if provided
        if (share != nullptr) {
            SDL_GL_SetAttribute(SDL_GL_SHARE_WITH_CURRENT_CONTEXT, 1);
            share->make_current();
        }

        gl_context_ = SDL_GL_CreateContext(window_);
        if (!gl_context_) {
            SDL_DestroyWindow(window_);
            throw std::runtime_error(std::string("Failed to create GL context: ") + SDL_GetError());
        }

        SDL_GL_MakeCurrent(window_, gl_context_);
    }

    ~SDLWindow() {
        close();
    }

    void close() {
        if (window_fb_handle_) {
            window_fb_handle_.reset();
        }
        if (gl_context_) {
            SDL_GL_DeleteContext(gl_context_);
            gl_context_ = nullptr;
        }
        if (window_) {
            SDL_DestroyWindow(window_);
            window_ = nullptr;
        }
    }

    bool should_close() const { return should_close_ || window_ == nullptr; }
    void set_should_close(bool flag) { should_close_ = flag; }

    void make_current() {
        if (window_ && gl_context_) {
            SDL_GL_MakeCurrent(window_, gl_context_);
        }
    }

    void swap_buffers() {
        if (window_) {
            SDL_GL_SwapWindow(window_);
        }
    }

    std::pair<int, int> framebuffer_size() const {
        if (!window_) return {0, 0};
        int w, h;
        SDL_GL_GetDrawableSize(window_, &w, &h);
        return {w, h};
    }

    std::pair<int, int> window_size() const {
        if (!window_) return {0, 0};
        int w, h;
        SDL_GetWindowSize(window_, &w, &h);
        return {w, h};
    }

    std::pair<double, double> get_cursor_pos() const {
        int x, y;
        SDL_GetMouseState(&x, &y);
        return {static_cast<double>(x), static_cast<double>(y)};
    }

    uint32_t get_window_id() const {
        return window_ ? SDL_GetWindowID(window_) : 0;
    }

    // Set graphics backend for framebuffer creation
    void set_graphics(OpenGLGraphicsBackend* graphics) {
        graphics_ = graphics;
    }

    // Get window framebuffer (creates external FBO wrapper)
    FramebufferHandle* get_window_framebuffer() {
        auto [width, height] = framebuffer_size();

        if (!window_fb_handle_ && graphics_) {
            window_fb_handle_ = graphics_->create_external_framebuffer(0, width, height);
        } else if (window_fb_handle_) {
            window_fb_handle_->set_external_target(0, width, height);
        }

        return window_fb_handle_.get();
    }

    // Callbacks
    void set_framebuffer_size_callback(FramebufferSizeCallback cb) { framebuffer_size_callback_ = std::move(cb); }
    void set_cursor_pos_callback(CursorPosCallback cb) { cursor_pos_callback_ = std::move(cb); }
    void set_scroll_callback(ScrollCallback cb) { scroll_callback_ = std::move(cb); }
    void set_mouse_button_callback(MouseButtonCallback cb) { mouse_button_callback_ = std::move(cb); }
    void set_key_callback(KeyCallback cb) { key_callback_ = std::move(cb); }

    // Handle SDL event
    void handle_event(const SDL_Event& event) {
        switch (event.type) {
            case SDL_QUIT:
                should_close_ = true;
                break;

            case SDL_WINDOWEVENT:
                if (event.window.event == SDL_WINDOWEVENT_CLOSE) {
                    should_close_ = true;
                } else if (event.window.event == SDL_WINDOWEVENT_RESIZED) {
                    auto [w, h] = framebuffer_size();
                    if (w != last_width_ || h != last_height_) {
                        last_width_ = w;
                        last_height_ = h;
                        if (framebuffer_size_callback_) {
                            framebuffer_size_callback_(this, w, h);
                        }
                    }
                }
                break;

            case SDL_MOUSEMOTION:
                if (cursor_pos_callback_) {
                    cursor_pos_callback_(this, event.motion.x, event.motion.y);
                }
                break;

            case SDL_MOUSEWHEEL:
                if (scroll_callback_) {
                    int mods = translate_sdl_mods(SDL_GetModState());
                    scroll_callback_(this, event.wheel.x, event.wheel.y, mods);
                }
                break;

            case SDL_MOUSEBUTTONDOWN:
                if (mouse_button_callback_) {
                    int button = translate_mouse_button(event.button.button);
                    int mods = translate_sdl_mods(SDL_GetModState());
                    mouse_button_callback_(this, button, ACTION_PRESS, mods);
                }
                break;

            case SDL_MOUSEBUTTONUP:
                if (mouse_button_callback_) {
                    int button = translate_mouse_button(event.button.button);
                    int mods = translate_sdl_mods(SDL_GetModState());
                    mouse_button_callback_(this, button, ACTION_RELEASE, mods);
                }
                break;

            case SDL_KEYDOWN:
                if (key_callback_) {
                    int action = event.key.repeat ? ACTION_REPEAT : ACTION_PRESS;
                    int mods = translate_sdl_mods(event.key.keysym.mod);
                    key_callback_(this, event.key.keysym.sym, event.key.keysym.scancode, action, mods);
                }
                break;

            case SDL_KEYUP:
                if (key_callback_) {
                    int mods = translate_sdl_mods(event.key.keysym.mod);
                    key_callback_(this, event.key.keysym.sym, event.key.keysym.scancode, ACTION_RELEASE, mods);
                }
                break;
        }
    }

private:
    static int translate_mouse_button(Uint8 button) {
        switch (button) {
            case SDL_BUTTON_LEFT: return MOUSE_BUTTON_LEFT;
            case SDL_BUTTON_RIGHT: return MOUSE_BUTTON_RIGHT;
            case SDL_BUTTON_MIDDLE: return MOUSE_BUTTON_MIDDLE;
            default: return MOUSE_BUTTON_LEFT;
        }
    }

    static int translate_sdl_mods(Uint16 sdl_mods) {
        // SDL: KMOD_LSHIFT=0x0001, KMOD_RSHIFT=0x0002
        // SDL: KMOD_LCTRL=0x0040, KMOD_RCTRL=0x0080
        // SDL: KMOD_LALT=0x0100, KMOD_RALT=0x0200
        // GLFW: SHIFT=0x0001, CTRL=0x0002, ALT=0x0004, SUPER=0x0008
        int result = 0;
        if (sdl_mods & (KMOD_LSHIFT | KMOD_RSHIFT)) result |= 0x0001;
        if (sdl_mods & (KMOD_LCTRL | KMOD_RCTRL)) result |= 0x0002;
        if (sdl_mods & (KMOD_LALT | KMOD_RALT)) result |= 0x0004;
        return result;
    }

    SDL_Window* window_;
    SDL_GLContext gl_context_;
    bool should_close_;
    int last_width_;
    int last_height_;

    OpenGLGraphicsBackend* graphics_;
    FramebufferHandlePtr window_fb_handle_;

    FramebufferSizeCallback framebuffer_size_callback_;
    CursorPosCallback cursor_pos_callback_;
    ScrollCallback scroll_callback_;
    MouseButtonCallback mouse_button_callback_;
    KeyCallback key_callback_;
};

/**
 * SDL2 window backend - manages SDL initialization and windows.
 */
class SDLWindowBackend {
public:
    SDLWindowBackend() {
        if (SDL_Init(SDL_INIT_VIDEO) != 0) {
            throw std::runtime_error(std::string("Failed to initialize SDL: ") + SDL_GetError());
        }
    }

    ~SDLWindowBackend() {
        terminate();
    }

    std::shared_ptr<SDLWindow> create_window(
        int width, int height,
        const std::string& title,
        SDLWindow* share = nullptr
    ) {
        auto window = std::make_shared<SDLWindow>(width, height, title, share);
        windows_[window->get_window_id()] = window;
        return window;
    }

    void poll_events() {
        SDL_Event event;
        while (SDL_PollEvent(&event)) {
            uint32_t window_id = 0;

            switch (event.type) {
                case SDL_WINDOWEVENT:
                    window_id = event.window.windowID;
                    break;
                case SDL_MOUSEMOTION:
                case SDL_MOUSEBUTTONDOWN:
                case SDL_MOUSEBUTTONUP:
                case SDL_MOUSEWHEEL:
                    window_id = event.motion.windowID;
                    break;
                case SDL_KEYDOWN:
                case SDL_KEYUP:
                    window_id = event.key.windowID;
                    break;
                case SDL_QUIT:
                    // Quit event goes to all windows
                    for (auto& [id, win] : windows_) {
                        if (auto w = win.lock()) {
                            w->handle_event(event);
                        }
                    }
                    continue;
            }

            auto it = windows_.find(window_id);
            if (it != windows_.end()) {
                if (auto win = it->second.lock()) {
                    win->handle_event(event);
                }
            }
        }

        // Clean up closed windows
        for (auto it = windows_.begin(); it != windows_.end();) {
            auto win = it->second.lock();
            if (!win || win->should_close()) {
                it = windows_.erase(it);
            } else {
                ++it;
            }
        }
    }

    void terminate() {
        windows_.clear();
        SDL_Quit();
    }

private:
    std::unordered_map<uint32_t, std::weak_ptr<SDLWindow>> windows_;
};

} // namespace termin
