/**
 * @file input_events_bindings.hpp
 * @brief nanobind bindings for input event structures.
 */

#pragma once

#include <nanobind/nanobind.h>

namespace nb = nanobind;

namespace termin {

void bind_input_events(nb::module_& m);

} // namespace termin
