#include "termin/input/window_input_bridge.hpp"

#include "render/tc_input_manager.h"
#include "termin/platform/backend_window.hpp"

namespace termin {

namespace {

void route_event(tc_input_manager* input_manager, const WindowEvent& event) {
    switch (event.type) {
        case WindowEventType::PointerMoved:
            tc_input_manager_on_mouse_move(
                input_manager,
                event.pointer.logical_position.x,
                event.pointer.logical_position.y);
            break;

        case WindowEventType::PointerButtonPressed:
        case WindowEventType::PointerButtonReleased:
            tc_input_manager_on_mouse_move(
                input_manager,
                event.pointer.logical_position.x,
                event.pointer.logical_position.y);
            tc_input_manager_on_mouse_button(
                input_manager,
                static_cast<int>(event.pointer.button),
                event.type == WindowEventType::PointerButtonPressed
                    ? TC_INPUT_PRESS : TC_INPUT_RELEASE,
                static_cast<int>(event.pointer.modifiers),
                static_cast<int>(event.pointer.clicks));
            break;

        case WindowEventType::PointerWheel:
            tc_input_manager_on_mouse_move(
                input_manager,
                event.pointer.logical_position.x,
                event.pointer.logical_position.y);
            tc_input_manager_on_scroll(
                input_manager,
                event.pointer.wheel_x,
                event.pointer.wheel_y,
                static_cast<int>(event.pointer.modifiers));
            break;

        case WindowEventType::KeyPressed:
        case WindowEventType::KeyReleased:
            tc_input_manager_on_key(
                input_manager,
                event.key.native_key,
                event.key.native_scancode,
                event.type == WindowEventType::KeyReleased
                    ? TC_INPUT_RELEASE
                    : (event.key.repeat ? TC_INPUT_REPEAT : TC_INPUT_PRESS),
                static_cast<int>(event.key.modifiers));
            break;

        default:
            break;
    }
}

} // namespace

void attach_window_input_manager(
    BackendWindow& window,
    tc_input_manager* input_manager) {
    if (!input_manager) {
        window.set_event_handler({});
        return;
    }
    window.set_event_handler(
        [input_manager](const WindowEvent& event) {
            route_event(input_manager, event);
        });
}

} // namespace termin
