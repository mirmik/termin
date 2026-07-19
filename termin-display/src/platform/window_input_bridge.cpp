#include "termin/input/window_input_bridge.hpp"

#include "render/tc_display.h"
#include "termin/platform/backend_window.hpp"
#include <tcbase/tc_log.h>

#include <string_view>

namespace termin {

namespace {

bool decode_utf8(std::string_view text, size_t& offset, uint32_t& codepoint) {
    if (offset >= text.size()) return false;
    const auto lead = static_cast<unsigned char>(text[offset++]);
    if (lead < 0x80) {
        codepoint = lead;
        return true;
    }
    int continuation_count = 0;
    uint32_t value = 0;
    if ((lead & 0xe0) == 0xc0) { continuation_count = 1; value = lead & 0x1f; }
    else if ((lead & 0xf0) == 0xe0) { continuation_count = 2; value = lead & 0x0f; }
    else if ((lead & 0xf8) == 0xf0) { continuation_count = 3; value = lead & 0x07; }
    else return false;
    if (offset + static_cast<size_t>(continuation_count) > text.size()) return false;
    for (int index = 0; index < continuation_count; ++index) {
        const auto byte = static_cast<unsigned char>(text[offset++]);
        if ((byte & 0xc0) != 0x80) return false;
        value = (value << 6) | (byte & 0x3f);
    }
    if ((continuation_count == 1 && value < 0x80) ||
        (continuation_count == 2 && value < 0x800) ||
        (continuation_count == 3 && value < 0x10000) ||
        value > 0x10ffff || (value >= 0xd800 && value <= 0xdfff)) return false;
    codepoint = value;
    return true;
}

} // namespace

void dispatch_window_input_event(tc_display* display, const WindowEvent& event) {
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
                static_cast<int>(event.pointer.button),
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
                event.key.native_key,
                event.key.native_scancode,
                event.type == WindowEventType::KeyReleased
                    ? TC_INPUT_RELEASE
                    : (event.key.repeat ? TC_INPUT_REPEAT : TC_INPUT_PRESS),
                static_cast<int>(event.key.modifiers));
            break;

        case WindowEventType::TextInput: {
            size_t length = 0;
            while (length < event.text.utf8.size() && event.text.utf8[length] != '\0') ++length;
            const std::string_view text(event.text.utf8.data(), length);
            size_t offset = 0;
            while (offset < text.size()) {
                uint32_t codepoint = 0;
                if (!decode_utf8(text, offset, codepoint)) {
                    tc_log_error("[window_input_bridge] invalid UTF-8 text event");
                    return;
                }
                tc_display_dispatch_text(display, codepoint);
            }
            break;
        }

        default:
            break;
    }
}

void attach_window_input_display(
    BackendWindow& window,
    tc_display* display) {
    if (!display) {
        window.set_event_handler({});
        return;
    }
    window.set_event_handler(
        [display](const WindowEvent& event) {
            dispatch_window_input_event(display, event);
        });
}

} // namespace termin
