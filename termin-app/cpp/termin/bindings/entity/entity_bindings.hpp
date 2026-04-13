// entity_bindings.hpp - Entity class binding declaration
#pragma once

#include <nanobind/nanobind.h>

namespace termin {

// Bind Entity class to Python module
void bind_entity_class(nanobind::module_& m);

} // namespace termin
