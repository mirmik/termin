#include <pybind11/pybind11.h>
#include <pybind11/stl.h>

#include "inspect/inspect_registry.hpp"

namespace py = pybind11;

namespace termin {

void bind_inspect(py::module_& m) {
    // InspectFieldInfo - read-only metadata
    py::class_<InspectFieldInfo>(m, "InspectFieldInfo")
        .def_readonly("type_name", &InspectFieldInfo::type_name)
        .def_readonly("path", &InspectFieldInfo::path)
        .def_readonly("label", &InspectFieldInfo::label)
        .def_readonly("kind", &InspectFieldInfo::kind)
        .def_readonly("min", &InspectFieldInfo::min)
        .def_readonly("max", &InspectFieldInfo::max)
        .def_readonly("step", &InspectFieldInfo::step);

    // InspectRegistry singleton
    py::class_<InspectRegistry>(m, "InspectRegistry")
        .def_static("instance", &InspectRegistry::instance,
                    py::return_value_policy::reference)
        .def("fields", &InspectRegistry::fields,
             py::arg("type_name"),
             py::return_value_policy::reference,
             "Get all fields for a type")
        .def("types", &InspectRegistry::types,
             "Get all registered type names")
        .def("get", [](InspectRegistry& self, py::object obj, const std::string& field_path) {
            // Get type name from Python object
            std::string type_name = py::str(py::type::of(obj).attr("__name__")).cast<std::string>();
            // Cast to void* - pybind11 knows the actual type
            void* ptr = py::cast<void*>(obj);
            return self.get(ptr, type_name, field_path);
        }, py::arg("obj"), py::arg("field"),
           "Get field value from object")
        .def("set", [](InspectRegistry& self, py::object obj, const std::string& field_path, py::object value) {
            std::string type_name = py::str(py::type::of(obj).attr("__name__")).cast<std::string>();
            void* ptr = py::cast<void*>(obj);
            self.set(ptr, type_name, field_path, value);
        }, py::arg("obj"), py::arg("field"), py::arg("value"),
           "Set field value on object");
}

} // namespace termin
