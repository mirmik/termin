#pragma once

#include <nanobind/nanobind.h>
#include <nanobind/stl/string.h>
#include <nanobind/stl/vector.h>
#include <nanobind/stl/array.h>
#include <nanobind/ndarray.h>

namespace nb = nanobind;

namespace termin {

// Forward declarations for bind functions
void bind_render_types(nb::module_& m);
void bind_graphics_backend(nb::module_& m);
void bind_shader(nb::module_& m);
void bind_shader_parser(nb::module_& m);
void bind_camera(nb::module_& m);
void bind_shadow(nb::module_& m);
void bind_resource_spec(nb::module_& m);
void bind_immediate(nb::module_& m);
void bind_wireframe(nb::module_& m);
void bind_frame_pass(nb::module_& m);
void bind_material(nb::module_& m);
void bind_tc_material(nb::module_& m);
void register_material_kind_handlers();
void bind_drawable(nb::module_& m);
void bind_renderers(nb::module_& m);
void bind_solid_primitive(nb::module_& m);
void bind_tc_pass(nb::module_& m);
void bind_render_engine(nb::module_& m);

} // namespace termin
