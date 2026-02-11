#include "sdl_render_surface.hpp"
#include "render/tc_input_manager.h"
#include "tc_log.h"
#include <SDL2/SDL_syswm.h>

namespace termin {

// ============================================================================
// SDLWindowBackend Implementation
// ============================================================================

void SDLWindowBackend::register_surface(SDLWindowRenderSurface* surface) {
    if (surface) {
        surfaces_[surface->window_id()] = surface;
    }
}

void SDLWindowBackend::unregister_surface(SDLWindowRenderSurface* surface) {
    if (surface) {
        surfaces_.erase(surface->window_id());
    }
}

void SDLWindowBackend::poll_events() {
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
                // Quit event - mark all surfaces as should_close
                for (auto& [id, surface] : surfaces_) {
                    surface->set_should_close(true);
                }
                // Also handle legacy windows
                for (auto& [id, win] : windows_) {
                    if (auto w = win.lock()) {
                        w->handle_event(event);
                    }
                }
                continue;
        }

        // Try render surface first
        auto sit = surfaces_.find(window_id);
        if (sit != surfaces_.end()) {
            dispatch_event_to_surface(sit->second, event);
        }

        // Also dispatch to legacy SDLWindow (for callbacks)
        auto wit = windows_.find(window_id);
        if (wit != windows_.end()) {
            if (auto win = wit->second.lock()) {
                win->handle_event(event);
            }
        }
    }

    // Clean up closed legacy windows
    for (auto it = windows_.begin(); it != windows_.end();) {
        auto win = it->second.lock();
        if (!win || win->should_close()) {
            it = windows_.erase(it);
        } else {
            ++it;
        }
    }
}

void SDLWindowBackend::dispatch_event_to_surface(SDLWindowRenderSurface* surface, const SDL_Event& event) {
    tc_input_manager* input = surface->input_manager();
    if (!input) return;

    switch (event.type) {
        case SDL_WINDOWEVENT:
            if (event.window.event == SDL_WINDOWEVENT_CLOSE) {
                surface->set_should_close(true);
            } else if (event.window.event == SDL_WINDOWEVENT_RESIZED) {
                auto [w, h] = surface->get_size();
                tc_render_surface_notify_resize(surface->tc_surface(), w, h);
            }
            break;

        case SDL_MOUSEMOTION:
            tc_input_manager_on_mouse_move(input, event.motion.x, event.motion.y);
            break;

        case SDL_MOUSEBUTTONDOWN:
            tc_input_manager_on_mouse_button(
                input,
                SDLWindow::translate_mouse_button(event.button.button),
                TC_INPUT_PRESS,
                SDLWindow::translate_sdl_mods(SDL_GetModState())
            );
            break;

        case SDL_MOUSEBUTTONUP:
            tc_input_manager_on_mouse_button(
                input,
                SDLWindow::translate_mouse_button(event.button.button),
                TC_INPUT_RELEASE,
                SDLWindow::translate_sdl_mods(SDL_GetModState())
            );
            break;

        case SDL_MOUSEWHEEL:
            tc_input_manager_on_scroll(
                input,
                event.wheel.x,
                event.wheel.y,
                SDLWindow::translate_sdl_mods(SDL_GetModState())
            );
            break;

        case SDL_KEYDOWN:
            tc_input_manager_on_key(
                input,
                event.key.keysym.sym,
                event.key.keysym.scancode,
                event.key.repeat ? TC_INPUT_REPEAT : TC_INPUT_PRESS,
                SDLWindow::translate_sdl_mods(event.key.keysym.mod)
            );
            break;

        case SDL_KEYUP:
            tc_input_manager_on_key(
                input,
                event.key.keysym.sym,
                event.key.keysym.scancode,
                TC_INPUT_RELEASE,
                SDLWindow::translate_sdl_mods(event.key.keysym.mod)
            );
            break;
    }
}

// ============================================================================
// SDLWindowRenderSurface Implementation
// ============================================================================

// Static vtable
const tc_render_surface_vtable SDLWindowRenderSurface::s_vtable = {
    .get_framebuffer = &SDLWindowRenderSurface::vtable_get_framebuffer,
    .get_size = &SDLWindowRenderSurface::vtable_get_size,
    .make_current = &SDLWindowRenderSurface::vtable_make_current,
    .swap_buffers = &SDLWindowRenderSurface::vtable_swap_buffers,
    .context_key = &SDLWindowRenderSurface::vtable_context_key,
    .poll_events = &SDLWindowRenderSurface::vtable_poll_events,
    .get_window_size = &SDLWindowRenderSurface::vtable_get_window_size,
    .should_close = &SDLWindowRenderSurface::vtable_should_close,
    .set_should_close = &SDLWindowRenderSurface::vtable_set_should_close,
    .get_cursor_pos = &SDLWindowRenderSurface::vtable_get_cursor_pos,
    .destroy = &SDLWindowRenderSurface::vtable_destroy,
};

SDLWindowRenderSurface::SDLWindowRenderSurface(
    int width,
    int height,
    const std::string& title,
    SDLWindowBackend* backend,
    SDLWindowRenderSurface* share
)
    : window_(nullptr)
    , backend_(backend)
    , needs_render_(true)
    , last_width_(width)
    , last_height_(height)
{
    // Create SDL window
    SDLWindow* share_window = share ? share->window_ : nullptr;
    window_ = new SDLWindow(width, height, title, share_window);

    // Initialize tc_render_surface
    tc_render_surface_init(&surface_, &s_vtable);
    surface_.body = this;

    // Register in backend for event routing
    if (backend_) {
        backend_->register_surface(this);
    }
}

SDLWindowRenderSurface::~SDLWindowRenderSurface() {
    // Unregister from backend
    if (backend_) {
        backend_->unregister_surface(this);
    }

    if (window_) {
        delete window_;
        window_ = nullptr;
    }
}

void SDLWindowRenderSurface::set_input_manager(tc_input_manager* manager) {
    tc_render_surface_set_input_manager(&surface_, manager);
}

bool SDLWindowRenderSurface::check_resize() {
    auto [w, h] = get_size();
    if (w != last_width_ || h != last_height_) {
        last_width_ = w;
        last_height_ = h;
        needs_render_ = true;
        tc_render_surface_notify_resize(&surface_, w, h);
        return true;
    }
    return false;
}

uintptr_t SDLWindowRenderSurface::get_native_handle() const {
    if (!window_) return 0;

    // Get raw SDL_Window* from our wrapper
    SDL_Window* sdl_win = SDL_GetWindowFromID(window_->get_window_id());
    if (!sdl_win) return 0;

    SDL_SysWMinfo info;
    SDL_VERSION(&info.version);
    if (!SDL_GetWindowWMInfo(sdl_win, &info)) {
        return 0;
    }

#ifdef _WIN32
    return reinterpret_cast<uintptr_t>(info.info.win.window);
#elif defined(__APPLE__)
    return reinterpret_cast<uintptr_t>(info.info.cocoa.window);
#else
    return static_cast<uintptr_t>(info.info.x11.window);
#endif
}

// ============================================================================
// VTable Implementation
// ============================================================================

uint32_t SDLWindowRenderSurface::vtable_get_framebuffer(tc_render_surface* self) {
    auto* surface = from_tc_surface(self);
    // Window framebuffer is always 0
    return 0;
}

void SDLWindowRenderSurface::vtable_get_size(tc_render_surface* self, int* width, int* height) {
    auto* surface = from_tc_surface(self);
    auto [w, h] = surface->get_size();
    if (width) *width = w;
    if (height) *height = h;
}

void SDLWindowRenderSurface::vtable_make_current(tc_render_surface* self) {
    auto* surface = from_tc_surface(self);
    surface->make_current();
}

void SDLWindowRenderSurface::vtable_swap_buffers(tc_render_surface* self) {
    auto* surface = from_tc_surface(self);
    surface->swap_buffers();
}

uintptr_t SDLWindowRenderSurface::vtable_context_key(tc_render_surface* self) {
    auto* surface = from_tc_surface(self);
    return reinterpret_cast<uintptr_t>(surface->window_);
}

void SDLWindowRenderSurface::vtable_poll_events(tc_render_surface* self) {
    // poll_events вызывается через backend, не через отдельный surface
}

void SDLWindowRenderSurface::vtable_get_window_size(tc_render_surface* self, int* width, int* height) {
    auto* surface = from_tc_surface(self);
    auto [w, h] = surface->window_size();
    if (width) *width = w;
    if (height) *height = h;
}

bool SDLWindowRenderSurface::vtable_should_close(tc_render_surface* self) {
    auto* surface = from_tc_surface(self);
    return surface->should_close();
}

void SDLWindowRenderSurface::vtable_set_should_close(tc_render_surface* self, bool value) {
    auto* surface = from_tc_surface(self);
    surface->set_should_close(value);
}

void SDLWindowRenderSurface::vtable_get_cursor_pos(tc_render_surface* self, double* x, double* y) {
    auto* surface = from_tc_surface(self);
    auto [cx, cy] = surface->get_cursor_pos();
    if (x) *x = cx;
    if (y) *y = cy;
}

void SDLWindowRenderSurface::vtable_destroy(tc_render_surface* self) {
    // Деструктор вызывается через C++ delete, не через vtable
}

} // namespace termin
