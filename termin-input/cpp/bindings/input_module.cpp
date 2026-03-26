// input_module.cpp - Python bindings for termin-input
#include <nanobind/nanobind.h>

extern "C" {
#include "core/tc_input_capability.h"
#include "core/tc_input_component.h"
#include "tc_component_python_input.h"
#include "core/tc_component.h"
}

namespace nb = nanobind;

NB_MODULE(_input_native, m) {
    m.def("input_capability_id", []() {
        return tc_input_capability_id();
    }, "Get the input capability ID");

    m.def("install_input_vtable", [](uintptr_t c_ptr) {
        auto* c = reinterpret_cast<tc_component*>(c_ptr);
        if (c) {
            tc_component_install_python_input_vtable(c);
        }
    }, nb::arg("c_ptr"),
       "Install input vtable on a component (by raw pointer)");

    m.def("is_input_handler", [](uintptr_t c_ptr) -> bool {
        auto* c = reinterpret_cast<tc_component*>(c_ptr);
        return c && tc_component_is_input_handler(c);
    }, nb::arg("c_ptr"),
       "Check if component is an input handler");
}
