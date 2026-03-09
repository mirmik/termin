#pragma once

// InputHandler - interface for components that handle input events
// Input event structs are forward-declared here. Consumers that need
// full definitions must include tc_input_event.h from core_c.

#include "core/tc_component.h"
#include "component.hpp"
#include <termin/export.hpp>

// Forward declarations for input event types (defined in core_c/tc_input_event.h)
struct tc_mouse_button_event;
struct tc_mouse_move_event;
struct tc_scroll_event;
struct tc_key_event;

namespace termin {

// InputHandler interface for components that handle input events.
// Protocol for input-receiving components like CameraController, etc.
//
// Methods (all optional - implement only what you need):
//   on_mouse_button: Mouse button press/release
//   on_mouse_move: Mouse movement
//   on_scroll: Scroll wheel
//   on_key: Keyboard input
class ENTITY_API InputHandler {
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
