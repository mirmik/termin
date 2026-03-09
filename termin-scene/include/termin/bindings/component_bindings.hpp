// component_bindings.hpp - CxxComponent + ComponentRegistry binding declarations
#pragma once

#include <nanobind/nanobind.h>

namespace termin {
void bind_cxx_component(nanobind::module_& m);
void bind_component_registry(nanobind::module_& m);
}
