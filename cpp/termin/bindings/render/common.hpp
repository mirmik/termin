#pragma once

#include <pybind11/pybind11.h>
#include <pybind11/stl.h>
#include <pybind11/numpy.h>

namespace py = pybind11;

namespace termin {

// Forward declarations for bind functions
void bind_render_types(py::module_& m);
void bind_graphics_backend(py::module_& m);
void bind_shader(py::module_& m);
void bind_shader_parser(py::module_& m);
void bind_camera(py::module_& m);
void bind_shadow(py::module_& m);
void bind_resource_spec(py::module_& m);
void bind_immediate(py::module_& m);
void bind_frame_pass(py::module_& m);
void bind_material(py::module_& m);
void bind_drawable(py::module_& m);
void bind_gpu(py::module_& m);
void bind_renderers(py::module_& m);

} // namespace termin
