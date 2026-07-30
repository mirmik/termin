#include "termin/input/window_input_bridge.hpp"

#include "render/tc_display.h"
#include "termin/platform/backend_window.hpp"
#include <tcbase/tc_log.h>

#include <algorithm>
#include <cstring>
#include <string>

namespace termin {

namespace {

BackendWindow* platform_window(void* userdata) {
    return static_cast<BackendWindow*>(userdata);
}

size_t platform_clipboard_text(
    void* userdata,
    char* buffer,
    size_t capacity
) {
    BackendWindow* window = platform_window(userdata);
    if (!window) return 0;
    const std::string text = window->clipboard_text();
    if (buffer && capacity > 0) {
        const size_t copied = std::min(text.size(), capacity - 1);
        std::memcpy(buffer, text.data(), copied);
        buffer[copied] = '\0';
    }
    return text.size();
}

bool platform_set_clipboard_text(
    void* userdata,
    const char* text_utf8,
    size_t byte_length
) {
    BackendWindow* window = platform_window(userdata);
    if (!window || (!text_utf8 && byte_length != 0)) return false;
    return window->set_clipboard_text(
        std::string(text_utf8 ? text_utf8 : "", byte_length));
}

WindowCursor platform_cursor(tc_input_cursor cursor) {
    switch (cursor) {
        case TC_INPUT_CURSOR_TEXT: return WindowCursor::Text;
        case TC_INPUT_CURSOR_HAND: return WindowCursor::Hand;
        case TC_INPUT_CURSOR_CROSSHAIR: return WindowCursor::Crosshair;
        case TC_INPUT_CURSOR_MOVE: return WindowCursor::Move;
        case TC_INPUT_CURSOR_RESIZE_HORIZONTAL:
            return WindowCursor::ResizeHorizontal;
        case TC_INPUT_CURSOR_RESIZE_VERTICAL:
            return WindowCursor::ResizeVertical;
        case TC_INPUT_CURSOR_RESIZE_NWSE: return WindowCursor::ResizeNWSE;
        case TC_INPUT_CURSOR_RESIZE_NESW: return WindowCursor::ResizeNESW;
        case TC_INPUT_CURSOR_DEFAULT:
        default:
            return WindowCursor::Default;
    }
}

void platform_set_cursor(void* userdata, tc_input_cursor cursor) {
    BackendWindow* window = platform_window(userdata);
    if (window) window->set_cursor(platform_cursor(cursor));
}

void platform_set_text_input_enabled(void* userdata, bool enabled) {
    BackendWindow* window = platform_window(userdata);
    if (window) window->set_text_input_enabled(enabled);
}

} // namespace

void dispatch_window_input_event(tc_display_handle display, const WindowEvent& event) {
    switch (event.type) {
        case WindowEventType::PointerMoved:
            tc_display_dispatch_pointer_move(
                display,
                event.pointer.framebuffer_position.x,
                event.pointer.framebuffer_position.y);
            break;

        case WindowEventType::PointerButtonPressed:
        case WindowEventType::PointerButtonReleased:
            tc_display_dispatch_pointer_button(
                display,
                event.pointer.framebuffer_position.x,
                event.pointer.framebuffer_position.y,
                tcbase::mouse_button_value(event.pointer.button),
                event.type == WindowEventType::PointerButtonPressed
                    ? TC_INPUT_PRESS : TC_INPUT_RELEASE,
                static_cast<int>(event.pointer.modifiers),
                static_cast<int>(event.pointer.clicks));
            break;

        case WindowEventType::PointerWheel:
            tc_display_dispatch_wheel(
                display,
                event.pointer.framebuffer_position.x,
                event.pointer.framebuffer_position.y,
                event.pointer.wheel_x,
                event.pointer.wheel_y,
                static_cast<int>(event.pointer.modifiers));
            break;

        case WindowEventType::KeyPressed:
        case WindowEventType::KeyReleased:
            tc_display_dispatch_key(
                display,
                window_key_code(event.key.key),
                event.key.native_scancode,
                event.type == WindowEventType::KeyReleased
                    ? TC_INPUT_RELEASE
                    : (event.key.repeat ? TC_INPUT_REPEAT : TC_INPUT_PRESS),
                static_cast<int>(event.key.modifiers));
            break;

        case WindowEventType::TextInput: {
            size_t length = 0;
            while (length < event.text.utf8.size() && event.text.utf8[length] != '\0') ++length;
            const std::string text(event.text.utf8.data(), length);
            tc_display_dispatch_text_utf8(display, text.c_str());
            break;
        }

        case WindowEventType::PointerCaptureLost:
        case WindowEventType::FocusLost: {
            tc_display_dispatch_focus_lost(display);
            break;
        }

        default:
            break;
    }
}

void attach_window_input_display(
    BackendWindow& window,
    tc_display_handle display) {
    if (!tc_display_handle_valid(display)) {
        window.set_event_handler({});
        return;
    }
    const tc_input_platform_services services = {
        .userdata = &window,
        .clipboard_text = platform_clipboard_text,
        .set_clipboard_text = platform_set_clipboard_text,
        .set_cursor = platform_set_cursor,
        .set_text_input_enabled = platform_set_text_input_enabled,
    };
    if (!tc_display_set_input_platform_services(display, &services)) {
        tc_log_error(
            "[window_input_bridge] failed to install input platform services");
    }
    window.set_event_handler(
        [display](const WindowEvent& event) {
            dispatch_window_input_event(display, event);
        });
}

} // namespace termin
