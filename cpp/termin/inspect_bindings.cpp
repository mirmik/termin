#include <nanobind/nanobind.h>
#include <nanobind/stl/string.h>
#include <nanobind/stl/vector.h>

#include "../../core_c/include/tc_inspect.hpp"
#include "entity/component.hpp"
#include "material/tc_material_handle.hpp"
#include "render/frame_pass.hpp"
#include "inspect/tc_kind.hpp"
#include "inspect_bindings.hpp"
#include "bindings/tc_value_helpers.hpp"

namespace nb = nanobind;

namespace termin {

// Import tc:: types for bindings
using tc::TypeBackend;
using tc::EnumChoice;
using tc::InspectFieldInfo;
using tc::InspectRegistry;

// Helper to extract short type name from full qualified name
// "termin._native.render.MeshRenderer" -> "MeshRenderer"
static std::string get_short_type_name(const std::string& full_name) {
    size_t pos = full_name.rfind('.');
    if (pos != std::string::npos) {
        return full_name.substr(pos + 1);
    }
    return full_name;
}

// Helper to extract raw pointer from Python object
static void* get_raw_pointer(nb::object obj) {
    // Try Component first (covers C++ component types)
    try {
        return static_cast<void*>(nb::cast<Component*>(obj));
    } catch (const nb::cast_error&) {}

    // TcMaterial (handle-based)
    try {
        TcMaterial mat = nb::cast<TcMaterial>(obj);
        return static_cast<void*>(mat.get());
    } catch (const nb::cast_error&) {}

    // FramePass (ColorPass, ShadowPass, etc.)
    try {
        return static_cast<void*>(nb::cast<FramePass*>(obj));
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
        })
    );
}

// Ensure list[X] kind has a Python handler
// Returns true if handler exists or was created
static bool ensure_list_handler_impl(const std::string& kind) {
    auto& py_reg = tc::KindRegistryPython::instance();

    // Already registered?
    if (py_reg.has(kind)) {
        return true;
    }

    // Parse list[element] format
    char container[64], element[64];
    if (!tc_kind_parse(kind.c_str(), container, sizeof(container),
                      element, sizeof(element))) {
        return false;
    }

    if (std::string(container) != "list") {
        return false;
    }

    // Check element handler exists
    std::string elem_kind = element;
    if (!py_reg.has(elem_kind) && !tc::KindRegistryCpp::instance().has(elem_kind)) {
        return false;
    }

    // Create serialize function
    nb::object serialize_fn = nb::cpp_function([elem_kind](nb::object obj) -> nb::object {
        nb::list result;
        if (obj.is_none()) {
            return result;
        }
        auto& py_reg = tc::KindRegistryPython::instance();
        for (auto item : obj) {
            nb::object nb_item = nb::borrow<nb::object>(item);
            if (py_reg.has(elem_kind)) {
                result.append(py_reg.serialize(elem_kind, nb_item));
            } else {
                result.append(nb_item);
            }
        }
        return result;
    });

    // Create deserialize function
    nb::object deserialize_fn = nb::cpp_function([elem_kind](nb::object data) -> nb::object {
        nb::list result;
        if (!nb::isinstance<nb::list>(data)) return result;
        auto& py_reg = tc::KindRegistryPython::instance();
        for (auto item : data) {
            nb::object nb_item = nb::borrow<nb::object>(item);
            if (py_reg.has(elem_kind)) {
                result.append(py_reg.deserialize(elem_kind, nb_item));
            } else {
                result.append(nb_item);
            }
        }
        return result;
    });

    // Prevent Python GC from collecting these
    serialize_fn.inc_ref();
    deserialize_fn.inc_ref();

    // Register in Python registry
    py_reg.register_kind(kind, serialize_fn, deserialize_fn);

    return true;
}

void bind_inspect(nb::module_& m) {
    // Register C++ builtin kinds (bool, int, float, string, etc.)
    tc::register_builtin_kinds();

    // Register C++ inspect vtable in C dispatcher
    tc::init_cpp_inspect_vtable();

    // Register Python language vtable in C kind dispatcher
    tc::init_python_lang_vtable();

    // Register Python-specific kind handlers (enum)
    register_builtin_kind_handlers();

    // Set callback for lazy list handler creation
    tc::set_ensure_list_handler(ensure_list_handler_impl);

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
        .def_ro("is_serializable", &InspectFieldInfo::is_serializable)
        .def_ro("is_inspectable", &InspectFieldInfo::is_inspectable)
        .def_ro("choices", &InspectFieldInfo::choices)
        .def_prop_ro("action", [](InspectFieldInfo& self) -> nb::object {
            // If we have a Python action, return it
            if (self.action.ptr() != nullptr && !self.action.is_none()) {
                return self.action;
            }
            // If we have a C++ action callback, lazily create nb::cpp_function
            if (self.cpp_action) {
                auto cpp_fn = self.cpp_action;
                self.action = nb::cpp_function([cpp_fn](nb::object obj) {
                    // Cast to Component* and call C++ callback
                    void* ptr = static_cast<void*>(nb::cast<Component*>(obj));
                    if (ptr) {
                        cpp_fn(ptr);
                    }
                });
                return self.action;
            }
            return nb::none();
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
            std::string full_type_name = nb::cast<std::string>(nb::str(nb::type_name(obj.type())));
            std::string type_name = get_short_type_name(full_type_name);
            void* ptr = get_raw_pointer(obj);
            return self.get(ptr, type_name, field_path);
        }, nb::arg("obj"), nb::arg("field"),
           "Get field value from object")

        .def("set", [](InspectRegistry& self, nb::object obj, const std::string& field_path, nb::object value) {
            std::string full_type_name = nb::cast<std::string>(nb::str(nb::type_name(obj.type())));
            std::string type_name = get_short_type_name(full_type_name);
            void* ptr = get_raw_pointer(obj);
            self.set(ptr, type_name, field_path, value);
        }, nb::arg("obj"), nb::arg("field"), nb::arg("value"),
           "Set field value on object")

        .def("serialize_all", [](InspectRegistry& self, nb::object obj) {
            std::string full_type_name = nb::cast<std::string>(nb::str(nb::type_name(obj.type())));
            std::string type_name = get_short_type_name(full_type_name);
            void* ptr = get_raw_pointer(obj);
            tc_value v = self.serialize_all(ptr, type_name);
            nb::object result = tc_value_to_py(&v);
            tc_value_free(&v);
            return result;
        }, nb::arg("obj"),
           "Serialize all fields of object to dict")

        .def("deserialize_all", [](InspectRegistry& self, nb::object obj, nb::object data) {
            std::string full_type_name = nb::cast<std::string>(nb::str(nb::type_name(obj.type())));
            std::string type_name = get_short_type_name(full_type_name);
            void* ptr = get_raw_pointer(obj);
            nb::dict py_data = nb::cast<nb::dict>(data);
            self.deserialize_component_fields_over_python(ptr, obj, type_name, py_data);
        }, nb::arg("obj"), nb::arg("data"),
           "Deserialize all fields from dict to object")

        .def("add_button", &InspectRegistry::add_button,
             nb::arg("type_name"), nb::arg("path"), nb::arg("label"), nb::arg("action"),
             "Add a button field to a type");
}

} // namespace termin
