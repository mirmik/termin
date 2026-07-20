#include "termin/platform/sdl_window.hpp"

namespace termin {

void SDLWindowBackend::poll_events() {
    SDL_Event event;
    while (SDL_PollEvent(&event)) {
        if (event.type == SDL_QUIT) {
            for (auto& [id, weak_window] : windows_) {
                (void)id;
                if (auto window = weak_window.lock()) {
                    window->handle_event(event);
                }
            }
            continue;
        }

        uint32_t window_id = 0;
        switch (event.type) {
            case SDL_WINDOWEVENT: window_id = event.window.windowID; break;
            case SDL_MOUSEMOTION: window_id = event.motion.windowID; break;
            case SDL_MOUSEBUTTONDOWN:
            case SDL_MOUSEBUTTONUP: window_id = event.button.windowID; break;
            case SDL_MOUSEWHEEL: window_id = event.wheel.windowID; break;
            case SDL_KEYDOWN:
            case SDL_KEYUP: window_id = event.key.windowID; break;
            case SDL_TEXTINPUT: window_id = event.text.windowID; break;
            default: break;
        }

        auto found = windows_.find(window_id);
        if (found != windows_.end()) {
            if (auto window = found->second.lock()) {
                window->handle_event(event);
            }
        }
    }

    for (auto it = windows_.begin(); it != windows_.end();) {
        auto window = it->second.lock();
        if (!window || window->should_close()) {
            it = windows_.erase(it);
        } else {
            ++it;
        }
    }
}

} // namespace termin
