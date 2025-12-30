#include "common.hpp"
#include <fstream>
#include <sstream>
#include <nanobind/stl/shared_ptr.h>
#include <nanobind/stl/unique_ptr.h>
#include "termin/render/shader_program.hpp"
#include "termin/render/render.hpp"
#include "termin/geom/mat44.hpp"
#include "termin/geom/vec3.hpp"

namespace termin {

void bind_shader(nb::module_& m) {
    nb::class_<ShaderProgram>(m, "ShaderProgram")
        .def(nb::init<>())
        .def(nb::init<std::string, std::string, std::string, std::string>(),
            nb::arg("vertex_source"),
            nb::arg("fragment_source"),
            nb::arg("geometry_source") = "",
            nb::arg("source_path") = "")
        .def_prop_ro("vertex_source", &ShaderProgram::vertex_source)
        .def_prop_ro("fragment_source", &ShaderProgram::fragment_source)
        .def_prop_ro("geometry_source", &ShaderProgram::geometry_source)
        .def_prop_ro("source_path", &ShaderProgram::source_path)
        .def_prop_ro("is_compiled", &ShaderProgram::is_compiled)
        .def("ensure_ready", [](ShaderProgram& self, OpenGLGraphicsBackend& backend) {
            self.ensure_ready([&backend](const char* v, const char* f, const char* g) {
                return backend.create_shader(v, f, g);
            });
        }, nb::arg("graphics"), "Compile shader using graphics backend")
        .def("set_handle", [](ShaderProgram& self, std::unique_ptr<ShaderHandle> handle) {
            self.set_handle(std::move(handle));
        })
        .def("use", &ShaderProgram::use)
        .def("stop", &ShaderProgram::stop)
        .def("release", &ShaderProgram::release)
        .def("set_uniform_int", &ShaderProgram::set_uniform_int)
        .def("set_uniform_float", &ShaderProgram::set_uniform_float)
        .def("set_uniform_vec2", nb::overload_cast<const char*, float, float>(&ShaderProgram::set_uniform_vec2))
        .def("set_uniform_vec2", [](ShaderProgram& self, const char* name, nb::ndarray<nb::numpy, float, nb::shape<2>> v) {
            self.set_uniform_vec2(name, v(0), v(1));
        })
        .def("set_uniform_vec2", [](ShaderProgram& self, const char* name, nb::tuple t) {
            self.set_uniform_vec2(name, nb::cast<float>(t[0]), nb::cast<float>(t[1]));
        })
        .def("set_uniform_vec3", nb::overload_cast<const char*, float, float, float>(&ShaderProgram::set_uniform_vec3))
        .def("set_uniform_vec3", nb::overload_cast<const char*, const Vec3&>(&ShaderProgram::set_uniform_vec3))
        .def("set_uniform_vec3", [](ShaderProgram& self, const char* name, nb::ndarray<nb::numpy, float, nb::shape<3>> v) {
            self.set_uniform_vec3(name, v(0), v(1), v(2));
        })
        .def("set_uniform_vec3", [](ShaderProgram& self, const char* name, nb::tuple t) {
            self.set_uniform_vec3(name, nb::cast<float>(t[0]), nb::cast<float>(t[1]), nb::cast<float>(t[2]));
        })
        .def("set_uniform_vec4", nb::overload_cast<const char*, float, float, float, float>(&ShaderProgram::set_uniform_vec4))
        .def("set_uniform_vec4", [](ShaderProgram& self, const char* name, nb::ndarray<nb::numpy, float, nb::shape<4>> v) {
            self.set_uniform_vec4(name, v(0), v(1), v(2), v(3));
        })
        .def("set_uniform_vec4", [](ShaderProgram& self, const char* name, nb::tuple t) {
            self.set_uniform_vec4(name, nb::cast<float>(t[0]), nb::cast<float>(t[1]), nb::cast<float>(t[2]), nb::cast<float>(t[3]));
        })
        .def("set_uniform_matrix4", [](ShaderProgram& self, const char* name, nb::ndarray<nb::numpy, float, nb::shape<4, 4>> matrix, bool transpose) {
            self.set_uniform_matrix4(name, matrix.data(), transpose);
        }, nb::arg("name"), nb::arg("matrix"), nb::arg("transpose") = true)
        .def("set_uniform_matrix4", [](ShaderProgram& self, const char* name, const Mat44& m, bool transpose) {
            self.set_uniform_matrix4(name, m, transpose);
        }, nb::arg("name"), nb::arg("matrix"), nb::arg("transpose") = true)
        .def("set_uniform_matrix4_array", [](ShaderProgram& self, const char* name, nb::ndarray<nb::numpy, float> matrices, int count, bool transpose) {
            self.set_uniform_matrix4_array(name, matrices.data(), count, transpose);
        }, nb::arg("name"), nb::arg("matrices"), nb::arg("count"), nb::arg("transpose") = true)
        .def("set_uniform_auto", [](ShaderProgram& self, const char* name, nb::object value) {
            // Check for ndarray first
            if (nb::ndarray_check(value)) {
                nb::ndarray<nb::numpy, float> arr = nb::cast<nb::ndarray<nb::numpy, float>>(value);
                if (arr.ndim() == 2 && arr.shape(0) == 4 && arr.shape(1) == 4) {
                    self.set_uniform_matrix4(name, arr.data(), true);
                } else if (arr.ndim() == 1) {
                    auto data = arr.data();
                    size_t size = arr.shape(0);
                    if (size == 2) {
                        self.set_uniform_vec2(name, data[0], data[1]);
                    } else if (size == 3) {
                        self.set_uniform_vec3(name, data[0], data[1], data[2]);
                    } else if (size == 4) {
                        self.set_uniform_vec4(name, data[0], data[1], data[2], data[3]);
                    } else {
                        throw std::runtime_error("Unsupported uniform array size: " + std::to_string(size));
                    }
                } else {
                    throw std::runtime_error("Unsupported uniform array shape");
                }
            } else if (nb::isinstance<nb::list>(value) || nb::isinstance<nb::tuple>(value)) {
                nb::list lst = nb::isinstance<nb::list>(value) ? nb::cast<nb::list>(value) : nb::list(value);
                size_t size = nb::len(lst);
                if (size == 2) {
                    self.set_uniform_vec2(name, nb::cast<float>(lst[0]), nb::cast<float>(lst[1]));
                } else if (size == 3) {
                    self.set_uniform_vec3(name, nb::cast<float>(lst[0]), nb::cast<float>(lst[1]), nb::cast<float>(lst[2]));
                } else if (size == 4) {
                    self.set_uniform_vec4(name, nb::cast<float>(lst[0]), nb::cast<float>(lst[1]), nb::cast<float>(lst[2]), nb::cast<float>(lst[3]));
                } else {
                    throw std::runtime_error("Unsupported uniform list size: " + std::to_string(size));
                }
            } else if (nb::isinstance<nb::bool_>(value)) {
                self.set_uniform_int(name, nb::cast<bool>(value) ? 1 : 0);
            } else if (nb::isinstance<nb::int_>(value)) {
                self.set_uniform_int(name, nb::cast<int>(value));
            } else {
                self.set_uniform_float(name, nb::cast<float>(value));
            }
        }, nb::arg("name"), nb::arg("value"), "Set uniform with automatic type inference")
        .def("delete", &ShaderProgram::release)
        .def("direct_serialize", [](const ShaderProgram& prog) -> nb::dict {
            nb::dict result;
            if (!prog.source_path().empty()) {
                result["type"] = "path";
                result["path"] = prog.source_path();
            } else {
                result["type"] = "inline";
                result["vertex"] = prog.vertex_source();
                result["fragment"] = prog.fragment_source();
                if (!prog.geometry_source().empty()) {
                    result["geometry"] = prog.geometry_source();
                }
            }
            return result;
        })
        .def_static("direct_deserialize", [](nb::dict data) {
            std::string source_path;
            if (data.contains("type") && nb::cast<std::string>(data["type"]) == "path") {
                source_path = nb::cast<std::string>(data["path"]);
            }
            return ShaderProgram(
                nb::cast<std::string>(data["vertex"]),
                nb::cast<std::string>(data["fragment"]),
                data.contains("geometry") ? nb::cast<std::string>(data["geometry"]) : "",
                source_path
            );
        })
        .def_static("from_files", [](const std::string& vertex_path, const std::string& fragment_path) {
            auto read_file = [](const std::string& path) -> std::string {
                std::ifstream file(path);
                if (!file) {
                    throw std::runtime_error("Cannot open file: " + path);
                }
                std::stringstream buffer;
                buffer << file.rdbuf();
                return buffer.str();
            };
            return ShaderProgram(
                read_file(vertex_path),
                read_file(fragment_path),
                "",
                vertex_path
            );
        }, nb::arg("vertex_path"), nb::arg("fragment_path"), "Load shader from files")
        .def("__repr__", [](const ShaderProgram& prog) -> std::string {
            std::string path = prog.source_path().empty() ? "<inline>" : prog.source_path();
            return "<ShaderProgram " + path + (prog.is_compiled() ? " compiled>" : " not compiled>");
        });
}

} // namespace termin
