#pragma once

#include <nanobind/nanobind.h>
#include <nanobind/stl/string.h>
#include <nanobind/stl/vector.h>
#include <nanobind/ndarray.h>
#include <tc_log.hpp>

namespace nb = nanobind;

namespace termin {

void bind_recast_navmesh_builder(nb::module_& m);

} // namespace termin
