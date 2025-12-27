#pragma once

#include <pybind11/pybind11.h>

namespace termin {
void bind_profiler(pybind11::module_& m);
}
