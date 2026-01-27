/**
 * @file input_events.hpp
 * @brief Input event structures for mouse, keyboard, and scroll events.
 *
 * These structures are used to pass input events between the platform layer
 * (Python/C#/WPF) and C++ components like OrbitCameraController.
 *
 * Поля событий:
 * - viewport: указатель на tc_viewport
 * - x, y: позиция курсора в координатах viewport
 * - dx, dy: дельта перемещения (для MouseMoveEvent)
 * - button: кнопка мыши (0=left, 1=right, 2=middle)
 * - action: действие (0=release, 1=press, 2=repeat)
 * - mods: модификаторы (Shift=1, Ctrl=2, Alt=4, Super=8)
 */

#pragma once

#include <cstdint>

extern "C" {
#include "render/tc_viewport.h"
}

namespace termin {

/**
 * Mouse button press/release event.
 *
 * Генерируется при нажатии/отпускании кнопки мыши.
 */
struct MouseButtonEvent {
    tc_viewport* viewport;  ///< Viewport where event occurred
    double x;               ///< Cursor X position in viewport coordinates
    double y;               ///< Cursor Y position in viewport coordinates
    int button;             ///< Button: 0=left, 1=right, 2=middle
    int action;             ///< Action: 0=release, 1=press, 2=repeat
    int mods;               ///< Modifier flags: Shift=1, Ctrl=2, Alt=4, Super=8

    MouseButtonEvent() : viewport(nullptr), x(0), y(0), button(0), action(0), mods(0) {}

    MouseButtonEvent(tc_viewport* viewport, double x, double y, int button, int action, int mods = 0)
        : viewport(viewport), x(x), y(y), button(button), action(action), mods(mods) {}
};

/**
 * Mouse movement event.
 *
 * Генерируется при перемещении курсора мыши.
 * dx, dy — дельта относительно предыдущей позиции.
 */
struct MouseMoveEvent {
    tc_viewport* viewport;  ///< Viewport where event occurred
    double x;               ///< Current cursor X position
    double y;               ///< Current cursor Y position
    double dx;              ///< Delta X since last event
    double dy;              ///< Delta Y since last event

    MouseMoveEvent() : viewport(nullptr), x(0), y(0), dx(0), dy(0) {}

    MouseMoveEvent(tc_viewport* viewport, double x, double y, double dx, double dy)
        : viewport(viewport), x(x), y(y), dx(dx), dy(dy) {}
};

/**
 * Mouse scroll event.
 *
 * Генерируется при прокрутке колеса мыши.
 * yoffset > 0 — прокрутка вверх (zoom in), yoffset < 0 — вниз (zoom out).
 */
struct ScrollEvent {
    tc_viewport* viewport;  ///< Viewport where event occurred
    double x;               ///< Cursor X position
    double y;               ///< Cursor Y position
    double xoffset;         ///< Horizontal scroll offset
    double yoffset;         ///< Vertical scroll offset (positive = up/zoom in)
    int mods;               ///< Modifier flags

    ScrollEvent() : viewport(nullptr), x(0), y(0), xoffset(0), yoffset(0), mods(0) {}

    ScrollEvent(tc_viewport* viewport, double x, double y, double xoffset, double yoffset, int mods = 0)
        : viewport(viewport), x(x), y(y), xoffset(xoffset), yoffset(yoffset), mods(mods) {}
};

/**
 * Keyboard event.
 *
 * Генерируется при нажатии/отпускании клавиши.
 * key — виртуальный код клавиши (GLFW/platform-specific).
 */
struct KeyEvent {
    tc_viewport* viewport;  ///< Viewport where event occurred
    int key;                ///< Virtual key code
    int scancode;           ///< Platform-specific scancode
    int action;             ///< Action: 0=release, 1=press, 2=repeat
    int mods;               ///< Modifier flags

    KeyEvent() : viewport(nullptr), key(0), scancode(0), action(0), mods(0) {}

    KeyEvent(tc_viewport* viewport, int key, int scancode, int action, int mods = 0)
        : viewport(viewport), key(key), scancode(scancode), action(action), mods(mods) {}
};

/**
 * Mouse button enum.
 */
enum class MouseButton : int {
    Left = 0,
    Right = 1,
    Middle = 2
};

/**
 * Action enum.
 */
enum class Action : int {
    Release = 0,
    Press = 1,
    Repeat = 2
};

/**
 * Modifier key flags enum.
 */
enum class Mods : int {
    Shift = 1,
    Ctrl = 2,
    Alt = 4,
    Super = 8
};

} // namespace termin
