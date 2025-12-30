#include <nanobind/nanobind.h>
#include <nanobind/stl/string.h>
#include <nanobind/stl/vector.h>

#include "inspect/inspect_registry.hpp"
#include "entity/component.hpp"
#include "render/material.hpp"
#include "../../core_c/include/tc_kind.hpp"
#include "inspect_bindings.hpp"

namespace nb = nanobind;

namespace termin {

// Helper to extract raw pointer from Python object
static void* get_raw_pointer(nb::object obj) {
    // Try Component first (covers C++ component types)
    try {
        return static_cast<void*>(nb::cast<Component*>(obj));
    } catch (const nb::cast_error&) {}

    // Material uses shared_ptr
    try {
        return static_cast<void*>(nb::cast<Material*>(obj));
    } catch (const nb::cast_error&) {}

    // For pure Python objects (PythonComponent etc), return PyObject*
    // The getter/setter lambdas in register_python_fields handle this case
    return static_cast<void*>(obj.ptr());
}

void register_builtin_kind_handlers() {
    // enum kind handler - serializes enum.value (int), deserializes as-is
    tc::KindRegistry::instance().register_python(
        "enum",
        // serialize
        nb::cpp_function([](nb::object obj) -> nb::object {
            if (nb::hasattr(obj, "value")) {
                return obj.attr("value");
            }
            return obj;
        }),
        // deserialize - return as-is, setter handles conversion
        nb::cpp_function([](nb::object data) -> nb::object {
            return data;
        }),
        // convert
        nb::none()
    );
}

void bind_inspect(nb::module_& m) {
    // Register builtin kind handlers
    register_builtin_kind_handlers();

    // TypeBackend enum
    nb::enum_<TypeBackend>(m, "TypeBackend")
        .value("Cpp", TypeBackend::Cpp)
        .value("Python", TypeBackend::Python)
        .value("Rust", TypeBackend::Rust);

    // EnumChoice - value/label pair for enum fields
    nb::class_<EnumChoice>(m, "EnumChoice")
        .def_ro("value", &EnumChoice::value)
        .def_ro("label", &EnumChoice::label);

    // InspectFieldInfo - read-only metadata
    nb::class_<InspectFieldInfo>(m, "InspectFieldInfo")
        .def_ro("type_name", &InspectFieldInfo::type_name)
        .def_ro("path", &InspectFieldInfo::path)
        .def_ro("label", &InspectFieldInfo::label)
        .def_ro("kind", &InspectFieldInfo::kind)
        .def_ro("min", &InspectFieldInfo::min)
        .def_ro("max", &InspectFieldInfo::max)
        .def_ro("step", &InspectFieldInfo::step)
        .def_ro("non_serializable", &InspectFieldInfo::non_serializable)
        .def_ro("choices", &InspectFieldInfo::choices)
        .def_prop_ro("action", [](const InspectFieldInfo& self) -> nb::object {
            if (self.action.ptr() == nullptr || self.action.is_none()) {
                return nb::none();
            }
            return self.action;
        });

    // InspectRegistry singleton
    nb::class_<InspectRegistry>(m, "InspectRegistry")
        .def_static("instance", &InspectRegistry::instance,
                    nb::rv_policy::reference)
        .def("fields", &InspectRegistry::fields,
             nb::arg("type_name"),
             nb::rv_policy::reference,
             "Get type's own fields only")
        .def("all_fields", &InspectRegistry::all_fields,
             nb::arg("type_name"),
             "Get all fields including inherited Component fields")
        .def("types", &InspectRegistry::types,
             "Get all registered type names")
        .def("register_python_fields", &InspectRegistry::register_python_fields,
             nb::arg("type_name"), nb::arg("fields_dict"),
             "Register fields from Python inspect_fields dict")
        .def("get_type_backend", &InspectRegistry::get_type_backend,
             nb::arg("type_name"),
             "Get the backend (Cpp/Python/Rust) for a type")
        .def("has_type", &InspectRegistry::has_type,
             nb::arg("type_name"),
             "Check if type is registered")
        .def("set_type_parent", &InspectRegistry::set_type_parent,
             nb::arg("type_name"), nb::arg("parent_name"),
             "Set parent type for field inheritance")
        .def("get_type_parent", &InspectRegistry::get_type_parent,
             nb::arg("type_name"),
             "Get parent type name")
        .def("get", [](InspectRegistry& self, nb::object obj, const std::string& field_path) {
            std::string type_name = nb::cast<std::string>(nb::str(nb::type_name(obj.type())));
            void* ptr = get_raw_pointer(obj);
            return self.get(ptr, type_name, field_path);
        }, nb::arg("obj"), nb::arg("field"),
           "Get field value from object")
        .def("set", [](InspectRegistry& self, nb::object obj, const std::string& field_path, nb::object value) {
            std::string type_name = nb::cast<std::string>(nb::str(nb::type_name(obj.type())));
            void* ptr = get_raw_pointer(obj);
            self.set(ptr, type_name, field_path, value);
        }, nb::arg("obj"), nb::arg("field"), nb::arg("value"),
           "Set field value on object")
        .def("serialize_all", [](InspectRegistry& self, nb::object obj) {
            std::string type_name = nb::cast<std::string>(nb::str(nb::type_name(obj.type())));
            void* ptr = get_raw_pointer(obj);
            nos::trent t = self.serialize_all(ptr, type_name);
            return InspectRegistry::trent_to_py(t);
        }, nb::arg("obj"),
           "Serialize all fields of object to dict")
        .def("deserialize_all", [](InspectRegistry& self, nb::object obj, nb::object data) {
            std::string type_name = nb::cast<std::string>(nb::str(nb::type_name(obj.type())));
            void* ptr = get_raw_pointer(obj);
            nb::dict py_data = nb::cast<nb::dict>(data);
            self.deserialize_component_fields_over_python(ptr, obj, type_name, py_data);
        }, nb::arg("obj"), nb::arg("data"),
           "Deserialize all fields from dict to object");
}

} // namespace termin
