/**
 * @file input_events_bindings.cpp
 * @brief nanobind bindings for input event structures.
 */

#include "input_events_bindings.hpp"
#include "../../input/input_events.hpp"
#include "termin/viewport/tc_viewport_handle.hpp"

namespace nb = nanobind;

namespace termin {

void bind_input_events(nb::module_& m) {
    // MouseButtonEvent
    nb::class_<MouseButtonEvent>(m, "MouseButtonEvent",
        "Mouse button press/release event.\n\n"
        "Attributes:\n"
        "    viewport: TcViewport where event occurred\n"
        "    x, y: Cursor position in viewport coordinates\n"
        "    button: 0=left, 1=right, 2=middle\n"
        "    action: 0=release, 1=press, 2=repeat\n"
        "    mods: Modifier flags (Shift=1, Ctrl=2, Alt=4, Super=8)")
        .def(nb::init<>())
        .def("__init__", [](MouseButtonEvent* self, const TcViewport& viewport, double x, double y,
                           int button, int action, int mods) {
            new (self) MouseButtonEvent(viewport.handle(), x, y, button, action, mods);
        }, nb::arg("viewport"), nb::arg("x"), nb::arg("y"),
           nb::arg("button"), nb::arg("action"), nb::arg("mods") = 0)
        .def("__init__", [](MouseButtonEvent* self, const TcViewport& viewport, double x, double y,
                           MouseButton button_enum, Action action_enum, int mods) {
            new (self) MouseButtonEvent(viewport.handle(), x, y,
                static_cast<int>(button_enum), static_cast<int>(action_enum), mods);
        }, nb::arg("viewport"), nb::arg("x"), nb::arg("y"),
           nb::arg("button"), nb::arg("action"), nb::arg("mods") = 0)
        .def_prop_rw("viewport",
            [](const MouseButtonEvent& self) {
                return TcViewport::from_handle(self.viewport);
            },
            [](MouseButtonEvent& self, const TcViewport& vp) {
                self.viewport = vp.handle();
            })
        .def_rw("x", &MouseButtonEvent::x)
        .def_rw("y", &MouseButtonEvent::y)
        .def_prop_rw("button",
            [](const MouseButtonEvent& self) {
                return static_cast<MouseButton>(self.button);
            },
            [](MouseButtonEvent& self, MouseButton b) {
                self.button = static_cast<int>(b);
            })
        .def_prop_rw("action",
            [](const MouseButtonEvent& self) {
                return static_cast<Action>(self.action);
            },
            [](MouseButtonEvent& self, Action a) {
                self.action = static_cast<int>(a);
            })
        .def_rw("mods", &MouseButtonEvent::mods)
        .def("__repr__", [](const MouseButtonEvent& e) {
            const char* name = tc_viewport_handle_valid(e.viewport) ? tc_viewport_get_name(e.viewport) : nullptr;
            return "MouseButtonEvent(viewport=" +
                   (name ? std::string(name) : "None") +
                   ", x=" + std::to_string(e.x) + ", y=" + std::to_string(e.y) +
                   ", button=" + std::to_string(e.button) +
                   ", action=" + std::to_string(e.action) +
                   ", mods=" + std::to_string(e.mods) + ")";
        });

    // MouseMoveEvent
    nb::class_<MouseMoveEvent>(m, "MouseMoveEvent",
        "Mouse movement event.\n\n"
        "Attributes:\n"
        "    viewport: TcViewport where event occurred\n"
        "    x, y: Current cursor position\n"
        "    dx, dy: Delta since last event")
        .def(nb::init<>())
        .def("__init__", [](MouseMoveEvent* self, const TcViewport& viewport, double x, double y,
                           double dx, double dy) {
            new (self) MouseMoveEvent(viewport.handle(), x, y, dx, dy);
        }, nb::arg("viewport"), nb::arg("x"), nb::arg("y"),
           nb::arg("dx"), nb::arg("dy"))
        .def_prop_rw("viewport",
            [](const MouseMoveEvent& self) {
                return TcViewport::from_handle(self.viewport);
            },
            [](MouseMoveEvent& self, const TcViewport& vp) {
                self.viewport = vp.handle();
            })
        .def_rw("x", &MouseMoveEvent::x)
        .def_rw("y", &MouseMoveEvent::y)
        .def_rw("dx", &MouseMoveEvent::dx)
        .def_rw("dy", &MouseMoveEvent::dy)
        .def("__repr__", [](const MouseMoveEvent& e) {
            const char* name = tc_viewport_handle_valid(e.viewport) ? tc_viewport_get_name(e.viewport) : nullptr;
            return "MouseMoveEvent(viewport=" +
                   (name ? std::string(name) : "None") +
                   ", x=" + std::to_string(e.x) + ", y=" + std::to_string(e.y) +
                   ", dx=" + std::to_string(e.dx) + ", dy=" + std::to_string(e.dy) + ")";
        });

    // ScrollEvent
    nb::class_<ScrollEvent>(m, "ScrollEvent",
        "Mouse scroll event.\n\n"
        "Attributes:\n"
        "    viewport: TcViewport where event occurred\n"
        "    x, y: Cursor position\n"
        "    xoffset, yoffset: Scroll offsets (positive yoffset = up/zoom in)\n"
        "    mods: Modifier flags")
        .def(nb::init<>())
        .def("__init__", [](ScrollEvent* self, const TcViewport& viewport, double x, double y,
                           double xoffset, double yoffset, int mods) {
            new (self) ScrollEvent(viewport.handle(), x, y, xoffset, yoffset, mods);
        }, nb::arg("viewport"), nb::arg("x"), nb::arg("y"),
           nb::arg("xoffset"), nb::arg("yoffset"), nb::arg("mods") = 0)
        .def_prop_rw("viewport",
            [](const ScrollEvent& self) {
                return TcViewport::from_handle(self.viewport);
            },
            [](ScrollEvent& self, const TcViewport& vp) {
                self.viewport = vp.handle();
            })
        .def_rw("x", &ScrollEvent::x)
        .def_rw("y", &ScrollEvent::y)
        .def_rw("xoffset", &ScrollEvent::xoffset)
        .def_rw("yoffset", &ScrollEvent::yoffset)
        .def_rw("mods", &ScrollEvent::mods)
        .def("__repr__", [](const ScrollEvent& e) {
            const char* name = tc_viewport_handle_valid(e.viewport) ? tc_viewport_get_name(e.viewport) : nullptr;
            return "ScrollEvent(viewport=" +
                   (name ? std::string(name) : "None") +
                   ", x=" + std::to_string(e.x) + ", y=" + std::to_string(e.y) +
                   ", xoffset=" + std::to_string(e.xoffset) +
                   ", yoffset=" + std::to_string(e.yoffset) +
                   ", mods=" + std::to_string(e.mods) + ")";
        });

    // KeyEvent
    nb::class_<KeyEvent>(m, "KeyEvent",
        "Keyboard event.\n\n"
        "Attributes:\n"
        "    viewport: TcViewport where event occurred\n"
        "    key: Virtual key code\n"
        "    scancode: Platform-specific scancode\n"
        "    action: 0=release, 1=press, 2=repeat\n"
        "    mods: Modifier flags")
        .def(nb::init<>())
        .def("__init__", [](KeyEvent* self, const TcViewport& viewport, int key, int scancode,
                           int action, int mods) {
            new (self) KeyEvent(viewport.handle(), key, scancode, action, mods);
        }, nb::arg("viewport"), nb::arg("key"), nb::arg("scancode"),
           nb::arg("action"), nb::arg("mods") = 0)
        .def("__init__", [](KeyEvent* self, const TcViewport& viewport, int key, int scancode,
                           Action action, int mods) {
            new (self) KeyEvent(viewport.handle(), key, scancode, static_cast<int>(action), mods);
        }, nb::arg("viewport"), nb::arg("key"), nb::arg("scancode"),
           nb::arg("action"), nb::arg("mods") = 0)
        .def_prop_rw("viewport",
            [](const KeyEvent& self) {
                return TcViewport::from_handle(self.viewport);
            },
            [](KeyEvent& self, const TcViewport& vp) {
                self.viewport = vp.handle();
            })
        .def_rw("key", &KeyEvent::key)
        .def_rw("scancode", &KeyEvent::scancode)
        .def_prop_rw("action",
            [](const KeyEvent& self) {
                return static_cast<Action>(self.action);
            },
            [](KeyEvent& self, Action a) {
                self.action = static_cast<int>(a);
            })
        .def_rw("mods", &KeyEvent::mods)
        .def("__repr__", [](const KeyEvent& e) {
            const char* name = tc_viewport_handle_valid(e.viewport) ? tc_viewport_get_name(e.viewport) : nullptr;
            return "KeyEvent(viewport=" +
                   (name ? std::string(name) : "None") +
                   ", key=" + std::to_string(e.key) +
                   ", scancode=" + std::to_string(e.scancode) +
                   ", action=" + std::to_string(e.action) +
                   ", mods=" + std::to_string(e.mods) + ")";
        });

    // Enums
    nb::enum_<MouseButton>(m, "MouseButton", "Mouse button constants")
        .value("LEFT", MouseButton::LEFT)
        .value("RIGHT", MouseButton::RIGHT)
        .value("MIDDLE", MouseButton::MIDDLE)
        .export_values();

    nb::enum_<Action>(m, "Action", "Action constants")
        .value("RELEASE", Action::RELEASE)
        .value("PRESS", Action::PRESS)
        .value("REPEAT", Action::REPEAT)
        .export_values();

    nb::enum_<Mods>(m, "Mods", "Modifier key flags")
        .value("SHIFT", Mods::SHIFT)
        .value("CTRL", Mods::CTRL)
        .value("ALT", Mods::ALT)
        .value("SUPER", Mods::SUPER)
        .export_values();
}

} // namespace termin
