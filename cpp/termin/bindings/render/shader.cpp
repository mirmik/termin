#include "common.hpp"
#include <fstream>
#include <sstream>
#include "termin/render/shader_program.hpp"
#include "termin/render/render.hpp"
#include "termin/geom/mat44.hpp"
#include "termin/geom/vec3.hpp"

namespace termin {

void bind_shader(py::module_& m) {
    py::class_<ShaderProgram, std::shared_ptr<ShaderProgram>>(m, "ShaderProgram")
        .def(py::init<>())
        .def(py::init<std::string, std::string, std::string, std::string>(),
            py::arg("vertex_source"),
            py::arg("fragment_source"),
            py::arg("geometry_source") = "",
            py::arg("source_path") = "")
        .def_property_readonly("vertex_source", &ShaderProgram::vertex_source)
        .def_property_readonly("fragment_source", &ShaderProgram::fragment_source)
        .def_property_readonly("geometry_source", &ShaderProgram::geometry_source)
        .def_property_readonly("source_path", &ShaderProgram::source_path)
        .def_property_readonly("is_compiled", &ShaderProgram::is_compiled)
        .def("ensure_ready", [](ShaderProgram& self, OpenGLGraphicsBackend& backend) {
            self.ensure_ready([&backend](const char* v, const char* f, const char* g) {
                return backend.create_shader(v, f, g);
            });
        }, py::arg("graphics"), "Compile shader using graphics backend")
        .def("set_handle", &ShaderProgram::set_handle)
        .def("use", &ShaderProgram::use)
        .def("stop", &ShaderProgram::stop)
        .def("release", &ShaderProgram::release)
        .def("set_uniform_int", &ShaderProgram::set_uniform_int)
        .def("set_uniform_float", &ShaderProgram::set_uniform_float)
        .def("set_uniform_vec2", py::overload_cast<const char*, float, float>(&ShaderProgram::set_uniform_vec2))
        .def("set_uniform_vec2", [](ShaderProgram& self, const char* name, py::array_t<float> v) {
            auto buf = v.unchecked<1>();
            self.set_uniform_vec2(name, buf(0), buf(1));
        })
        .def("set_uniform_vec3", py::overload_cast<const char*, float, float, float>(&ShaderProgram::set_uniform_vec3))
        .def("set_uniform_vec3", py::overload_cast<const char*, const Vec3&>(&ShaderProgram::set_uniform_vec3))
        .def("set_uniform_vec3", [](ShaderProgram& self, const char* name, py::array_t<float> v) {
            auto buf = v.unchecked<1>();
            self.set_uniform_vec3(name, buf(0), buf(1), buf(2));
        })
        .def("set_uniform_vec4", py::overload_cast<const char*, float, float, float, float>(&ShaderProgram::set_uniform_vec4))
        .def("set_uniform_vec4", [](ShaderProgram& self, const char* name, py::array_t<float> v) {
            auto buf = v.unchecked<1>();
            self.set_uniform_vec4(name, buf(0), buf(1), buf(2), buf(3));
        })
        .def("set_uniform_matrix4", [](ShaderProgram& self, const char* name, py::array matrix, bool transpose) {
            auto buf = matrix.request();
            if (buf.ndim != 2 || buf.shape[0] != 4 || buf.shape[1] != 4) {
                throw std::runtime_error("Matrix must be 4x4");
            }
            auto float_matrix = py::array_t<float>::ensure(matrix);
            self.set_uniform_matrix4(name, static_cast<float*>(float_matrix.request().ptr), transpose);
        }, py::arg("name"), py::arg("matrix"), py::arg("transpose") = true)
        .def("set_uniform_matrix4", [](ShaderProgram& self, const char* name, const Mat44& m, bool transpose) {
            self.set_uniform_matrix4(name, m, transpose);
        }, py::arg("name"), py::arg("matrix"), py::arg("transpose") = true)
        .def("set_uniform_matrix4_array", [](ShaderProgram& self, const char* name, py::array matrices, int count, bool transpose) {
            auto buf = matrices.request();
            auto float_matrices = py::array_t<float>::ensure(matrices);
            self.set_uniform_matrix4_array(name, static_cast<float*>(float_matrices.request().ptr), count, transpose);
        }, py::arg("name"), py::arg("matrices"), py::arg("count"), py::arg("transpose") = true)
        .def("set_uniform_auto", [](ShaderProgram& self, const char* name, py::object value) {
            if (py::isinstance<py::array>(value) || py::isinstance<py::list>(value) || py::isinstance<py::tuple>(value)) {
                auto arr = py::array_t<float>::ensure(value);
                auto buf = arr.request();

                if (buf.ndim == 2 && buf.shape[0] == 4 && buf.shape[1] == 4) {
                    self.set_uniform_matrix4(name, static_cast<float*>(buf.ptr), true);
                } else if (buf.ndim == 1) {
                    auto data = static_cast<float*>(buf.ptr);
                    if (buf.size == 2) {
                        self.set_uniform_vec2(name, data[0], data[1]);
                    } else if (buf.size == 3) {
                        self.set_uniform_vec3(name, data[0], data[1], data[2]);
                    } else if (buf.size == 4) {
                        self.set_uniform_vec4(name, data[0], data[1], data[2], data[3]);
                    } else {
                        throw std::runtime_error("Unsupported uniform array size: " + std::to_string(buf.size));
                    }
                } else {
                    throw std::runtime_error("Unsupported uniform array shape");
                }
            } else if (py::isinstance<py::bool_>(value)) {
                self.set_uniform_int(name, value.cast<bool>() ? 1 : 0);
            } else if (py::isinstance<py::int_>(value)) {
                self.set_uniform_int(name, value.cast<int>());
            } else {
                self.set_uniform_float(name, value.cast<float>());
            }
        }, py::arg("name"), py::arg("value"), "Set uniform with automatic type inference")
        .def("delete", &ShaderProgram::release)
        .def("direct_serialize", [](const ShaderProgram& prog) -> py::dict {
            py::dict result;
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
        .def_static("direct_deserialize", [](py::dict data) {
            std::string source_path;
            if (data.contains("type") && data["type"].cast<std::string>() == "path") {
                source_path = data["path"].cast<std::string>();
            }
            return ShaderProgram(
                data["vertex"].cast<std::string>(),
                data["fragment"].cast<std::string>(),
                data.contains("geometry") ? data["geometry"].cast<std::string>() : "",
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
        }, py::arg("vertex_path"), py::arg("fragment_path"), "Load shader from files")
        .def("__repr__", [](const ShaderProgram& prog) -> std::string {
            std::string path = prog.source_path().empty() ? "<inline>" : prog.source_path();
            return "<ShaderProgram " + path + (prog.is_compiled() ? " compiled>" : " not compiled>");
        });
}

} // namespace termin
