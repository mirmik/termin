// kind_bindings.hpp - Python bindings for KindRegistry
#pragma once

#include <pybind11/pybind11.h>

namespace termin {

void bind_kind(pybind11::module_& m);

} // namespace termin
