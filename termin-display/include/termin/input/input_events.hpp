/**
 * @file input_events.hpp
 * @brief C++ wrappers for viewport-bound input event structures.
 *
 * Uses C structures from tc_input_event.h as base,
 * adds C++ constructors and methods.
 */

#pragma once

#include <cstdint>
#include <tcbase/input_enums.hpp>

extern "C" {
#include "tc_input_event.h"
#include "render/tc_viewport.h"
#include "render/tc_viewport_pool.h"
}

namespace termin {

/**
 * Mouse button press/release event.
 * C++ wrapper for tc_mouse_button_event.
 */
struct MouseButtonEvent : public tc_mouse_button_event {
    MouseButtonEvent() {
        viewport = TC_VIEWPORT_HANDLE_INVALID;
        x = 0; y = 0;
        button = 0; action = 0; mods = 0;
        handled = false;
    }

    MouseButtonEvent(tc_viewport_handle vp, double x_, double y_, int btn, int act, int m = 0) {
        viewport = vp;
        x = x_; y = y_;
        button = btn; action = act; mods = m;
        handled = false;
    }

    explicit MouseButtonEvent(const tc_mouse_button_event& e) {
        viewport = e.viewport;
        x = e.x; y = e.y;
        button = e.button; action = e.action; mods = e.mods;
        handled = e.handled;
    }
};

/**
 * Mouse movement event.
 * C++ wrapper for tc_mouse_move_event.
 */
struct MouseMoveEvent : public tc_mouse_move_event {
    MouseMoveEvent() {
        viewport = TC_VIEWPORT_HANDLE_INVALID;
        x = 0; y = 0;
        dx = 0; dy = 0;
        handled = false;
    }

    MouseMoveEvent(tc_viewport_handle vp, double x_, double y_, double dx_, double dy_) {
        viewport = vp;
        x = x_; y = y_;
        dx = dx_; dy = dy_;
        handled = false;
    }

    explicit MouseMoveEvent(const tc_mouse_move_event& e) {
        viewport = e.viewport;
        x = e.x; y = e.y;
        dx = e.dx; dy = e.dy;
        handled = e.handled;
    }
};

/**
 * Mouse scroll event.
 * C++ wrapper for tc_scroll_event.
 */
struct ScrollEvent : public tc_scroll_event {
    ScrollEvent() {
        viewport = TC_VIEWPORT_HANDLE_INVALID;
        x = 0; y = 0;
        xoffset = 0; yoffset = 0; mods = 0;
        handled = false;
    }

    ScrollEvent(tc_viewport_handle vp, double x_, double y_, double xoff, double yoff, int m = 0) {
        viewport = vp;
        x = x_; y = y_;
        xoffset = xoff; yoffset = yoff; mods = m;
        handled = false;
    }

    explicit ScrollEvent(const tc_scroll_event& e) {
        viewport = e.viewport;
        x = e.x; y = e.y;
        xoffset = e.xoffset; yoffset = e.yoffset; mods = e.mods;
        handled = e.handled;
    }
};

/**
 * Keyboard event.
 * C++ wrapper for tc_key_event.
 */
struct KeyEvent : public tc_key_event {
    KeyEvent() {
        viewport = TC_VIEWPORT_HANDLE_INVALID;
        key = 0; scancode = 0;
        action = 0; mods = 0;
        handled = false;
    }

    KeyEvent(tc_viewport_handle vp, int k, int sc, int act, int m = 0) {
        viewport = vp;
        key = k; scancode = sc;
        action = act; mods = m;
        handled = false;
    }

    explicit KeyEvent(const tc_key_event& e) {
        viewport = e.viewport;
        key = e.key; scancode = e.scancode;
        action = e.action; mods = e.mods;
        handled = e.handled;
    }
};

using tcbase::Action;
using tcbase::Mods;
using tcbase::MouseButton;

} // namespace termin
