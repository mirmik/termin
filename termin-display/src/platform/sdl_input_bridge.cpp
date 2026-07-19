#include "termin/input/sdl_input_bridge.hpp"

#include <SDL2/SDL.h>

#include "render/tc_input_manager.h"
#include "termin/platform/sdl_backend_window.hpp"

namespace termin {

namespace {

int translate_mouse_button(Uint8 button) {
    switch (button) {
        case SDL_BUTTON_LEFT: return 0;
        case SDL_BUTTON_RIGHT: return 1;
        case SDL_BUTTON_MIDDLE: return 2;
        default: return 0;
    }
}

int translate_modifiers(Uint16 modifiers) {
    int result = 0;
    if (modifiers & (KMOD_LSHIFT | KMOD_RSHIFT)) result |= 0x0001;
    if (modifiers & (KMOD_LCTRL | KMOD_RCTRL)) result |= 0x0002;
    if (modifiers & (KMOD_LALT | KMOD_RALT)) result |= 0x0004;
    return result;
}

void route_event(tc_input_manager* input_manager, const SDL_Event& event) {
    switch (event.type) {
        case SDL_MOUSEMOTION:
            tc_input_manager_on_mouse_move(input_manager, event.motion.x, event.motion.y);
            break;

        case SDL_MOUSEBUTTONDOWN:
        case SDL_MOUSEBUTTONUP:
            tc_input_manager_on_mouse_move(input_manager, event.button.x, event.button.y);
            tc_input_manager_on_mouse_button(
                input_manager,
                translate_mouse_button(event.button.button),
                event.type == SDL_MOUSEBUTTONDOWN ? TC_INPUT_PRESS : TC_INPUT_RELEASE,
                translate_modifiers(SDL_GetModState()),
                event.button.clicks);
            break;

        case SDL_MOUSEWHEEL: {
            int x = 0;
            int y = 0;
            SDL_GetMouseState(&x, &y);
            tc_input_manager_on_mouse_move(input_manager, x, y);
            tc_input_manager_on_scroll(
                input_manager,
                event.wheel.x,
                event.wheel.y,
                translate_modifiers(SDL_GetModState()));
            break;
        }

        case SDL_KEYDOWN:
        case SDL_KEYUP:
            tc_input_manager_on_key(
                input_manager,
                event.key.keysym.sym,
                event.key.keysym.scancode,
                event.type == SDL_KEYUP
                    ? TC_INPUT_RELEASE
                    : (event.key.repeat ? TC_INPUT_REPEAT : TC_INPUT_PRESS),
                translate_modifiers(event.key.keysym.mod));
            break;

        default:
            break;
    }
}

} // namespace

void attach_sdl_input_manager(
    SDLBackendWindow& window,
    tc_input_manager* input_manager) {
    if (!input_manager) {
        window.set_event_handler({});
        return;
    }
    window.set_event_handler(
        [input_manager](const SDL_Event& event) {
            route_event(input_manager, event);
        });
}

} // namespace termin
