/**
 * @file input_events.hpp
 * @brief C++ wrappers for input event structures.
 *
 * Uses C structures from tc_input_event.h as base,
 * adds C++ constructors and methods.
 */

#pragma once

#include <cstdint>

extern "C" {
#include "tc_input_event.h"
#include "render/tc_viewport.h"
}

namespace termin {

/**
 * Mouse button press/release event.
 * C++ wrapper for tc_mouse_button_event.
 */
struct MouseButtonEvent : public tc_mouse_button_event {
    MouseButtonEvent() {
        viewport = nullptr;
        x = 0; y = 0;
        button = 0; action = 0; mods = 0;
    }

    MouseButtonEvent(tc_viewport* vp, double x_, double y_, int btn, int act, int m = 0) {
        viewport = vp;
        x = x_; y = y_;
        button = btn; action = act; mods = m;
    }

    // Construct from C struct
    explicit MouseButtonEvent(const tc_mouse_button_event& e) {
        viewport = e.viewport;
        x = e.x; y = e.y;
        button = e.button; action = e.action; mods = e.mods;
    }
};

/**
 * Mouse movement event.
 * C++ wrapper for tc_mouse_move_event.
 */
struct MouseMoveEvent : public tc_mouse_move_event {
    MouseMoveEvent() {
        viewport = nullptr;
        x = 0; y = 0;
        dx = 0; dy = 0;
    }

    MouseMoveEvent(tc_viewport* vp, double x_, double y_, double dx_, double dy_) {
        viewport = vp;
        x = x_; y = y_;
        dx = dx_; dy = dy_;
    }

    // Construct from C struct
    explicit MouseMoveEvent(const tc_mouse_move_event& e) {
        viewport = e.viewport;
        x = e.x; y = e.y;
        dx = e.dx; dy = e.dy;
    }
};

/**
 * Mouse scroll event.
 * C++ wrapper for tc_scroll_event.
 */
struct ScrollEvent : public tc_scroll_event {
    ScrollEvent() {
        viewport = nullptr;
        x = 0; y = 0;
        xoffset = 0; yoffset = 0; mods = 0;
    }

    ScrollEvent(tc_viewport* vp, double x_, double y_, double xoff, double yoff, int m = 0) {
        viewport = vp;
        x = x_; y = y_;
        xoffset = xoff; yoffset = yoff; mods = m;
    }

    // Construct from C struct
    explicit ScrollEvent(const tc_scroll_event& e) {
        viewport = e.viewport;
        x = e.x; y = e.y;
        xoffset = e.xoffset; yoffset = e.yoffset; mods = e.mods;
    }
};

/**
 * Keyboard event.
 * C++ wrapper for tc_key_event.
 */
struct KeyEvent : public tc_key_event {
    KeyEvent() {
        viewport = nullptr;
        key = 0; scancode = 0;
        action = 0; mods = 0;
    }

    KeyEvent(tc_viewport* vp, int k, int sc, int act, int m = 0) {
        viewport = vp;
        key = k; scancode = sc;
        action = act; mods = m;
    }

    // Construct from C struct
    explicit KeyEvent(const tc_key_event& e) {
        viewport = e.viewport;
        key = e.key; scancode = e.scancode;
        action = e.action; mods = e.mods;
    }
};

/**
 * Mouse button enum.
 */
enum class MouseButton : int {
    LEFT = 0,
    RIGHT = 1,
    MIDDLE = 2
};

/**
 * Action enum.
 */
enum class Action : int {
    RELEASE = 0,
    PRESS = 1,
    REPEAT = 2
};

/**
 * Modifier key flags enum.
 */
enum class Mods : int {
    SHIFT = 1,
    CTRL = 2,
    ALT = 4,
    SUPER = 8
};

} // namespace termin
