// tc_component_python_bindings.hpp - Python bindings for pure Python components
#pragma once

#include <nanobind/nanobind.h>

namespace termin {

void bind_tc_component_python(nanobind::module_& m);

} // namespace termin
