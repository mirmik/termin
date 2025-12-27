// tc_component_python_bindings.hpp - Python bindings for pure Python components
#pragma once

#include <pybind11/pybind11.h>

namespace termin {

void bind_tc_component_python(pybind11::module_& m);

} // namespace termin
