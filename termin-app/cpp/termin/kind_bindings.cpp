// kind_bindings.cpp - Python bindings for KindRegistry
#include <nanobind/nanobind.h>
#include <nanobind/stl/string.h>
#include <nanobind/stl/vector.h>

#include "inspect/tc_kind.hpp"
#include "kind_bindings.hpp"

namespace nb = nanobind;

namespace termin {

void bind_kind(nb::module_& m) {
    // Use the bind function from tc_kind_python.hpp
    tc::bind_kind_registry(m);
}

} // namespace termin
