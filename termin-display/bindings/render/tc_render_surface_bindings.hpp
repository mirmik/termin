#pragma once

#include <nanobind/nanobind.h>

extern "C" {
#include "render/tc_render_surface.h"
}

namespace termin {

tc_render_surface* create_python_render_surface(nanobind::object python_surface);

} // namespace termin
