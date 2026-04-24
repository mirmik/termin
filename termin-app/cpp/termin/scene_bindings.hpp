#pragma once

#include <nanobind/nanobind.h>

namespace termin {
void bind_tc_scene(nanobind::module_& m);
void bind_tc_scene_lighting(nanobind::module_& m);
}
