#include "common.hpp"
#include <nanobind/stl/unique_ptr.h>
#include "termin/render/render.hpp"
#include "tgfx/types.hpp"
#include "termin/render/shader_parser.hpp"
#include "termin/render/glsl_preprocessor.hpp"
#include "termin/lighting/shadow.hpp"
#include <termin/geom/mat44.hpp>
#include <tcbase/tc_log.hpp>

extern "C" {
#include <tgfx/tc_gpu_context.h>
}

namespace termin {

void bind_graphics_backend(nb::module_& m) {
    // --- Handles (abstract, exposed for type hints) ---

    nb::class_<ShaderHandle>(m, "ShaderHandle")
        .def("use", &ShaderHandle::use)
        .def("stop", &ShaderHandle::stop)
        .def("release", &ShaderHandle::release)
        .def("set_uniform_int", &ShaderHandle::set_uniform_int)
        .def("set_uniform_float", &ShaderHandle::set_uniform_float)
        .def("set_uniform_vec2", &ShaderHandle::set_uniform_vec2)
        .def("set_uniform_vec2", [](ShaderHandle& self, const char* name, nb::ndarray<nb::numpy, float, nb::shape<2>> v) {
            self.set_uniform_vec2(name, v(0), v(1));
        })
        .def("set_uniform_vec2", [](ShaderHandle& self, const char* name, nb::tuple t) {
            self.set_uniform_vec2(name, nb::cast<float>(t[0]), nb::cast<float>(t[1]));
        })
        .def("set_uniform_vec3", &ShaderHandle::set_uniform_vec3)
        .def("set_uniform_vec3", [](ShaderHandle& self, const char* name, nb::ndarray<nb::numpy, float, nb::shape<3>> v) {
            self.set_uniform_vec3(name, v(0), v(1), v(2));
        })
        .def("set_uniform_vec3", [](ShaderHandle& self, const char* name, nb::tuple t) {
            self.set_uniform_vec3(name, nb::cast<float>(t[0]), nb::cast<float>(t[1]), nb::cast<float>(t[2]));
        })
        .def("set_uniform_vec4", &ShaderHandle::set_uniform_vec4)
        .def("set_uniform_vec4", [](ShaderHandle& self, const char* name, nb::ndarray<nb::numpy, float, nb::shape<4>> v) {
            self.set_uniform_vec4(name, v(0), v(1), v(2), v(3));
        })
        .def("set_uniform_vec4", [](ShaderHandle& self, const char* name, nb::tuple t) {
            self.set_uniform_vec4(name, nb::cast<float>(t[0]), nb::cast<float>(t[1]), nb::cast<float>(t[2]), nb::cast<float>(t[3]));
        })
        .def("set_uniform_matrix4", [](ShaderHandle& self, const char* name, nb::ndarray<nb::numpy, float, nb::shape<4, 4>> matrix, bool transpose) {
            self.set_uniform_matrix4(name, matrix.data(), transpose);
        }, nb::arg("name"), nb::arg("matrix"), nb::arg("transpose") = true)
        .def("set_uniform_matrix4", [](ShaderHandle& self, const char* name, const Mat44& m, bool transpose) {
            self.set_uniform_matrix4(name, m.to_float().data, transpose);
        }, nb::arg("name"), nb::arg("matrix"), nb::arg("transpose") = false)  // Mat44 is already column-major
        .def("set_uniform_matrix4_array", [](ShaderHandle& self, const char* name, nb::ndarray<nb::numpy, float> matrices, int count, bool transpose) {
            self.set_uniform_matrix4_array(name, matrices.data(), count, transpose);
        }, nb::arg("name"), nb::arg("matrices"), nb::arg("count"), nb::arg("transpose") = true);

    nb::class_<GPUMeshHandle>(m, "GPUMeshHandle")
        .def("draw", &GPUMeshHandle::draw)
        .def("release", &GPUMeshHandle::release)
        .def("delete", &GPUMeshHandle::release);  // Alias for Python interface

    nb::class_<GPUTextureHandle>(m, "GPUTextureHandle")
        .def("bind", &GPUTextureHandle::bind, nb::arg("unit") = 0)
        .def("release", &GPUTextureHandle::release)
        .def("delete", &GPUTextureHandle::release)  // Alias for Python interface
        .def("get_id", &GPUTextureHandle::get_id)
        .def("get_width", &GPUTextureHandle::get_width)
        .def("get_height", &GPUTextureHandle::get_height);

    // init_opengl function
    m.def("init_opengl", &init_opengl, "Initialize OpenGL via glad. Call after context creation.");
}

} // namespace termin
