// kind_bindings.cpp - Python bindings for KindRegistry
#include <pybind11/pybind11.h>
#include <pybind11/stl.h>
#include <pybind11/functional.h>

#include "../../core_c/include/tc_kind.hpp"

namespace py = pybind11;

namespace termin {

void bind_kind(py::module_& m) {
    // TcKind class (read-only view)
    py::class_<tc::TcKind>(m, "TcKind")
        .def_readonly("name", &tc::TcKind::name)
        .def("has_cpp", &tc::TcKind::has_cpp)
        .def("has_python", &tc::TcKind::has_python);

    // KindRegistry singleton
    py::class_<tc::KindRegistry>(m, "KindRegistry")
        .def_static("instance", &tc::KindRegistry::instance,
                    py::return_value_policy::reference)
        .def("kinds", &tc::KindRegistry::kinds,
             "Get all registered kind names")
        .def("get", &tc::KindRegistry::get,
             py::arg("name"),
             py::return_value_policy::reference,
             "Get kind by name, returns None if not found")

        // Python registration
        .def("register_python", [](tc::KindRegistry& self,
                                   const std::string& name,
                                   py::object serialize,
                                   py::object deserialize,
                                   py::object convert) {
            self.register_python(name, serialize, deserialize, convert);
        },
        py::arg("name"),
        py::arg("serialize"),
        py::arg("deserialize"),
        py::arg("convert") = py::none(),
        "Register Python handlers for a kind")

        // Python serialization
        .def("serialize", [](tc::KindRegistry& self,
                             const std::string& kind_name,
                             py::object obj) {
            return self.serialize_python(kind_name, obj);
        },
        py::arg("kind"), py::arg("obj"),
        "Serialize object using Python handler")

        .def("deserialize", [](tc::KindRegistry& self,
                               const std::string& kind_name,
                               py::object data) {
            return self.deserialize_python(kind_name, data);
        },
        py::arg("kind"), py::arg("data"),
        "Deserialize data using Python handler")

        .def("convert", [](tc::KindRegistry& self,
                           const std::string& kind_name,
                           py::object value) {
            return self.convert_python(kind_name, value);
        },
        py::arg("kind"), py::arg("value"),
        "Convert value using Python handler");
}

} // namespace termin
