#pragma once

// InputHandler - interface for components that handle input events
// Similar to Drawable, but for input instead of rendering.

extern "C" {
#include "termin_core.h"
#include "tc_input_event.h"
}

#include "component.hpp"

namespace termin {

// InputHandler interface for components that handle input events.
// Protocol for input-receiving components like CameraController, etc.
//
// Methods (all optional - implement only what you need):
//   on_mouse_button: Mouse button press/release
//   on_mouse_move: Mouse movement
//   on_scroll: Scroll wheel
//   on_key: Keyboard input
class InputHandler {
public:
    virtual ~InputHandler() = default;

    // Mouse button press/release.
    virtual void on_mouse_button(tc_mouse_button_event* event) {}

    // Mouse movement.
    virtual void on_mouse_move(tc_mouse_move_event* event) {}

    // Scroll wheel.
    virtual void on_scroll(tc_scroll_event* event) {}

    // Keyboard input.
    virtual void on_key(tc_key_event* event) {}

    // Static input vtable for C components
    static const tc_input_vtable cxx_input_vtable;

protected:
    // Set input_vtable on the C component (call from subclass constructor)
    void install_input_vtable(tc_component* c) {
        if (c) {
            c->input_vtable = &cxx_input_vtable;
        }
    }

private:
    // Static callbacks for input vtable
    static void _cb_on_mouse_button(tc_component* c, tc_mouse_button_event* event);
    static void _cb_on_mouse_move(tc_component* c, tc_mouse_move_event* event);
    static void _cb_on_scroll(tc_component* c, tc_scroll_event* event);
    static void _cb_on_key(tc_component* c, tc_key_event* event);
};

} // namespace termin
