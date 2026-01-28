// simple_display_input_manager_bindings.cpp - Python bindings for SimpleDisplayInputManager
#include "simple_display_input_manager_bindings.hpp"
#include "../../input/simple_display_input_manager.hpp"
#include "render/tc_display.h"
#include "render/tc_render_surface.h"

#include <nanobind/nanobind.h>

namespace nb = nanobind;

namespace termin {

void bind_simple_display_input_manager(nb::module_& m) {
    nb::class_<SimpleDisplayInputManager>(m, "SimpleDisplayInputManager",
        "Simple input handler for Display.\n\n"
        "Routes mouse and keyboard events to scene via InputComponents.\n"
        "ESC closes the window.")
        .def("__init__", [](SimpleDisplayInputManager* self, uintptr_t display_ptr) {
            tc_display* display = reinterpret_cast<tc_display*>(display_ptr);
            new (self) SimpleDisplayInputManager(display);
        }, nb::arg("display_ptr"),
            "Create SimpleDisplayInputManager.\n\n"
            "Args:\n"
            "    display_ptr: Pointer to tc_display (from Display.tc_display_ptr)")

        .def_prop_ro("tc_input_manager_ptr", [](SimpleDisplayInputManager& self) -> uintptr_t {
            return reinterpret_cast<uintptr_t>(self.tc_input_manager_ptr());
        }, "Raw pointer to tc_input_manager (for C interop)")

        .def_prop_ro("display_ptr", [](SimpleDisplayInputManager& self) -> uintptr_t {
            return reinterpret_cast<uintptr_t>(self.display());
        }, "Raw pointer to tc_display")
        ;
}

} // namespace termin
