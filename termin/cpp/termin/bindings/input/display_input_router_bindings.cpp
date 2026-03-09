// display_input_router_bindings.cpp - Python bindings for DisplayInputRouter
#include "display_input_router_bindings.hpp"
#include "../../input/display_input_router.hpp"
#include "render/tc_display.h"
#include "render/tc_render_surface.h"

#include <nanobind/nanobind.h>

namespace nb = nanobind;

namespace termin {

void bind_display_input_router(nb::module_& m) {
    nb::class_<DisplayInputRouter>(m, "DisplayInputRouter",
        "Display-level input router.\n\n"
        "Routes mouse and keyboard events from display surface\n"
        "to the appropriate viewport's input manager.")
        .def("__init__", [](DisplayInputRouter* self, uintptr_t display_ptr) {
            tc_display* display = reinterpret_cast<tc_display*>(display_ptr);
            new (self) DisplayInputRouter(display);
        }, nb::arg("display_ptr"),
            "Create DisplayInputRouter.\n\n"
            "Args:\n"
            "    display_ptr: Pointer to tc_display (from Display.tc_display_ptr)")

        .def_prop_ro("tc_input_manager_ptr", [](DisplayInputRouter& self) -> uintptr_t {
            return reinterpret_cast<uintptr_t>(self.input_manager_ptr());
        }, "Raw pointer to tc_input_manager (for C interop)")
        ;
}

} // namespace termin
