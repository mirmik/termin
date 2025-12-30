// kind_bindings.cpp - Python bindings for KindRegistry
#include <nanobind/nanobind.h>
#include <nanobind/stl/string.h>
#include <nanobind/stl/vector.h>

#include "../../core_c/include/tc_kind.hpp"
#include "kind_bindings.hpp"

namespace nb = nanobind;

namespace termin {

void bind_kind(nb::module_& m) {
    // TcKind class (read-only view)
    nb::class_<tc::TcKind>(m, "TcKind")
        .def_ro("name", &tc::TcKind::name)
        .def("has_cpp", &tc::TcKind::has_cpp)
        .def("has_python", &tc::TcKind::has_python);

    // KindRegistry singleton
    nb::class_<tc::KindRegistry>(m, "KindRegistry")
        .def_static("instance", &tc::KindRegistry::instance,
                    nb::rv_policy::reference)
        .def("kinds", &tc::KindRegistry::kinds,
             "Get all registered kind names")
        .def("get", &tc::KindRegistry::get,
             nb::arg("name"),
             nb::rv_policy::reference,
             "Get kind by name, returns None if not found")

        // Python registration
        .def("register_python", [](tc::KindRegistry& self,
                                   const std::string& name,
                                   nb::object serialize,
                                   nb::object deserialize,
                                   nb::object convert) {
            self.register_python(name, serialize, deserialize, convert);
        },
        nb::arg("name"),
        nb::arg("serialize"),
        nb::arg("deserialize"),
        nb::arg("convert") = nb::none(),
        "Register Python handlers for a kind")

        // Python serialization
        .def("serialize", [](tc::KindRegistry& self,
                             const std::string& kind_name,
                             nb::object obj) {
            return self.serialize_python(kind_name, obj);
        },
        nb::arg("kind"), nb::arg("obj"),
        "Serialize object using Python handler")

        .def("deserialize", [](tc::KindRegistry& self,
                               const std::string& kind_name,
                               nb::object data) {
            return self.deserialize_python(kind_name, data);
        },
        nb::arg("kind"), nb::arg("data"),
        "Deserialize data using Python handler")

        .def("convert", [](tc::KindRegistry& self,
                           const std::string& kind_name,
                           nb::object value) {
            return self.convert_python(kind_name, value);
        },
        nb::arg("kind"), nb::arg("value"),
        "Convert value using Python handler");
}

} // namespace termin
