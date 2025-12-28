#include <pybind11/pybind11.h>
#include <pybind11/stl.h>

#include "inspect/inspect_registry.hpp"
#include "entity/component.hpp"
#include "render/material.hpp"
#include "../../core_c/include/tc_kind.hpp"

namespace py = pybind11;

namespace termin {

// Helper to extract raw pointer from Python object
static void* get_raw_pointer(py::object obj) {
    // Try Component first (covers C++ component types)
    try {
        return static_cast<void*>(obj.cast<Component*>());
    } catch (const py::cast_error&) {}

    // Material uses shared_ptr
    try {
        return static_cast<void*>(obj.cast<Material*>());
    } catch (const py::cast_error&) {}

    // For pure Python objects (PythonComponent etc), return PyObject*
    // The getter/setter lambdas in register_python_fields handle this case
    return static_cast<void*>(obj.ptr());
}

void register_builtin_kind_handlers() {
    // enum kind handler - serializes enum.value (int), deserializes as-is
    tc::KindRegistry::instance().register_python(
        "enum",
        // serialize
        py::cpp_function([](py::object obj) -> py::object {
            if (py::hasattr(obj, "value")) {
                return obj.attr("value");
            }
            return obj;
        }),
        // deserialize - return as-is, setter handles conversion
        py::cpp_function([](py::object data) -> py::object {
            return data;
        }),
        // convert
        py::none()
    );
}

void bind_inspect(py::module_& m) {
    // Register builtin kind handlers
    register_builtin_kind_handlers();

    // TypeBackend enum
    py::enum_<TypeBackend>(m, "TypeBackend")
        .value("Cpp", TypeBackend::Cpp)
        .value("Python", TypeBackend::Python)
        .value("Rust", TypeBackend::Rust);

    // EnumChoice - value/label pair for enum fields
    py::class_<EnumChoice>(m, "EnumChoice")
        .def_readonly("value", &EnumChoice::value)
        .def_readonly("label", &EnumChoice::label);

    // InspectFieldInfo - read-only metadata
    py::class_<InspectFieldInfo>(m, "InspectFieldInfo")
        .def_readonly("type_name", &InspectFieldInfo::type_name)
        .def_readonly("path", &InspectFieldInfo::path)
        .def_readonly("label", &InspectFieldInfo::label)
        .def_readonly("kind", &InspectFieldInfo::kind)
        .def_readonly("min", &InspectFieldInfo::min)
        .def_readonly("max", &InspectFieldInfo::max)
        .def_readonly("step", &InspectFieldInfo::step)
        .def_readonly("non_serializable", &InspectFieldInfo::non_serializable)
        .def_readonly("choices", &InspectFieldInfo::choices)
        .def_property_readonly("action", [](const InspectFieldInfo& self) -> py::object {
            if (self.action.ptr() == nullptr || self.action.is_none()) {
                return py::none();
            }
            return self.action;
        });

    // InspectRegistry singleton
    py::class_<InspectRegistry>(m, "InspectRegistry")
        .def_static("instance", &InspectRegistry::instance,
                    py::return_value_policy::reference)
        .def("fields", &InspectRegistry::fields,
             py::arg("type_name"),
             py::return_value_policy::reference,
             "Get type's own fields only")
        .def("all_fields", &InspectRegistry::all_fields,
             py::arg("type_name"),
             "Get all fields including inherited Component fields")
        .def("types", &InspectRegistry::types,
             "Get all registered type names")
        .def("register_python_fields", &InspectRegistry::register_python_fields,
             py::arg("type_name"), py::arg("fields_dict"),
             "Register fields from Python inspect_fields dict")
        .def("get_type_backend", &InspectRegistry::get_type_backend,
             py::arg("type_name"),
             "Get the backend (Cpp/Python/Rust) for a type")
        .def("has_type", &InspectRegistry::has_type,
             py::arg("type_name"),
             "Check if type is registered")
        .def("set_type_parent", &InspectRegistry::set_type_parent,
             py::arg("type_name"), py::arg("parent_name"),
             "Set parent type for field inheritance")
        .def("get_type_parent", &InspectRegistry::get_type_parent,
             py::arg("type_name"),
             "Get parent type name")
        .def("get", [](InspectRegistry& self, py::object obj, const std::string& field_path) {
            std::string type_name = py::str(py::type::of(obj).attr("__name__")).cast<std::string>();
            void* ptr = get_raw_pointer(obj);
            return self.get(ptr, type_name, field_path);
        }, py::arg("obj"), py::arg("field"),
           "Get field value from object")
        .def("set", [](InspectRegistry& self, py::object obj, const std::string& field_path, py::object value) {
            std::string type_name = py::str(py::type::of(obj).attr("__name__")).cast<std::string>();
            void* ptr = get_raw_pointer(obj);
            self.set(ptr, type_name, field_path, value);
        }, py::arg("obj"), py::arg("field"), py::arg("value"),
           "Set field value on object")
        .def("serialize_all", [](InspectRegistry& self, py::object obj) {
            std::string type_name = py::str(py::type::of(obj).attr("__name__")).cast<std::string>();
            void* ptr = get_raw_pointer(obj);
            nos::trent t = self.serialize_all(ptr, type_name);
            return InspectRegistry::trent_to_py(t);
        }, py::arg("obj"),
           "Serialize all fields of object to dict")
        .def("deserialize_all", [](InspectRegistry& self, py::object obj, py::object data) {
            std::string type_name = py::str(py::type::of(obj).attr("__name__")).cast<std::string>();
            void* ptr = get_raw_pointer(obj);
            py::dict py_data = data.cast<py::dict>();
            self.deserialize_component_fields_over_python(ptr, obj, type_name, py_data);
        }, py::arg("obj"), py::arg("data"),
           "Deserialize all fields from dict to object");
}

} // namespace termin
