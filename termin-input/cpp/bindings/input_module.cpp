// input_module.cpp - Python bindings for termin-input
#include <nanobind/nanobind.h>
#include <nanobind/stl/string.h>

#include <termin/input/xr_input.hpp>

extern "C" {
#include "core/tc_input_capability.h"
#include "core/tc_input_component.h"
#include "tc_component_python_input.h"
#include "core/tc_component.h"
}

namespace nb = nanobind;

NB_MODULE(_input_native, m) {
    nb::enum_<termin::xr::XrHand>(m, "XrHand")
        .value("Left", termin::xr::XrHand::Left)
        .value("Right", termin::xr::XrHand::Right);

    nb::class_<termin::xr::XrRigInputState>(m, "XrRigInputState")
        .def_prop_ro("id", [](const termin::xr::XrRigInputState& state) {
            return state.id;
        })
        .def_prop_ro("frame_index", [](const termin::xr::XrRigInputState& state) {
            return state.frame_index;
        })
        .def_prop_ro("head_axes_active", [](const termin::xr::XrRigInputState& state) {
            return state.head_axes_active;
        })
        .def("thumbstick", [](const termin::xr::XrRigInputState& state, termin::xr::XrHand hand) {
            const termin::xr::XrAxis2State& axis = state.hand(hand).thumbstick;
            return nb::make_tuple(axis.value.x, axis.value.y, axis.active);
        }, nb::arg("hand"))
        .def("head_forward_in_origin", [](const termin::xr::XrRigInputState& state) {
            return nb::make_tuple(
                state.head_forward_in_origin.x,
                state.head_forward_in_origin.y,
                state.head_forward_in_origin.z
            );
        })
        .def("head_right_in_origin", [](const termin::xr::XrRigInputState& state) {
            return nb::make_tuple(
                state.head_right_in_origin.x,
                state.head_right_in_origin.y,
                state.head_right_in_origin.z
            );
        });

    nb::class_<termin::xr::XrInput>(m, "XrInput")
        .def_static("get_state", [](const std::string& id) -> nb::object {
            termin::xr::XrRigInputState* state = termin::xr::XrInput::get_state(id);
            if (!state) {
                return nb::none();
            }
            return nb::cast(state, nb::rv_policy::reference);
        }, nb::arg("id"))
        .def_static("current", []() -> nb::object {
            termin::xr::XrRigInputState* state = termin::xr::XrInput::current();
            if (!state) {
                return nb::none();
            }
            return nb::cast(state, nb::rv_policy::reference);
        });

    m.def("xr_hand_to_string", &termin::xr::xr_hand_to_string, nb::arg("hand"));
    m.def("xr_hand_from_string", &termin::xr::xr_hand_from_string, nb::arg("value"));

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

    m.def("get_input_priority", [](uintptr_t c_ptr) -> int {
        auto* c = reinterpret_cast<tc_component*>(c_ptr);
        return c ? tc_component_get_input_priority(c) : 0;
    }, nb::arg("c_ptr"),
       "Get an input component dispatch priority");

    m.def("set_input_priority", [](uintptr_t c_ptr, int priority) -> bool {
        auto* c = reinterpret_cast<tc_component*>(c_ptr);
        return c && tc_component_set_input_priority(c, priority);
    }, nb::arg("c_ptr"), nb::arg("priority"),
       "Set an input component dispatch priority");
}
