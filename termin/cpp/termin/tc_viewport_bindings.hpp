#pragma once

#include <nanobind/nanobind.h>
#include "viewport/tc_viewport_handle.hpp"

namespace termin {
void bind_tc_viewport(nanobind::module_& m);
}
