#pragma once

#include <nanobind/nanobind.h>

namespace nb = nanobind;

namespace termin {

void bind_collider_component(nb::module_& m);

} // namespace termin
