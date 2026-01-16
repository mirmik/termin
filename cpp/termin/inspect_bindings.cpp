#include <nanobind/nanobind.h>
#include <nanobind/stl/string.h>
#include <nanobind/stl/vector.h>

#include "inspect/inspect_registry.hpp"
#include "entity/component.hpp"
#include "material/tc_material_handle.hpp"
#include "render/frame_pass.hpp"
#include "../../core_c/include/tc_kind.hpp"
#include "inspect_bindings.hpp"

namespace nb = nanobind;

namespace termin {

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
        }),
        // convert
        nb::none()
    );
}

// Generate Python handlers for list[X] kinds
// Must be called from nanobind module context
static tc::TcKind* generate_list_handler(const std::string& kind) {
    char container[64], element[64];
    if (!tc_kind_parse(kind.c_str(), container, sizeof(container),
                      element, sizeof(element))) {
        return nullptr;
    }

    if (std::string(container) != "list") {
        return nullptr;
    }

    auto* elem_handler = tc::KindRegistry::instance().get(element);
    if (!elem_handler) {
        return nullptr;
    }

    std::string elem_kind = element;
    auto& list_handler = tc::KindRegistry::instance().get_or_create(kind);

    // Already has Python handlers?
    if (list_handler.has_python()) {
        return &list_handler;
    }

    // serialize: list -> list of serialized elements
    list_handler.python.serialize = nb::cpp_function([elem_kind](nb::object obj) -> nb::object {
        nb::list result;
        if (obj.is_none()) {
            return result;
        }
        auto* handler = tc::KindRegistry::instance().get(elem_kind);
        for (auto item : obj) {
            nb::object nb_item = nb::borrow<nb::object>(item);
            if (handler && handler->has_python()) {
                result.append(handler->python.serialize(nb_item));
            } else {
                result.append(nb_item);
            }
        }
        return result;
    });

    // deserialize: list -> list of deserialized elements
    list_handler.python.deserialize = nb::cpp_function([elem_kind](nb::object data) -> nb::object {
        nb::list result;
        if (!nb::isinstance<nb::list>(data)) return result;
        auto* handler = tc::KindRegistry::instance().get(elem_kind);
        for (auto item : data) {
            nb::object nb_item = nb::borrow<nb::object>(item);
            if (handler && handler->has_python()) {
                result.append(handler->python.deserialize(nb_item));
            } else {
                result.append(nb_item);
            }
        }
        return result;
    });

    // convert
    list_handler.python.convert = nb::cpp_function([elem_kind](nb::object value) -> nb::object {
        if (value.is_none()) return nb::list();
        auto* handler = tc::KindRegistry::instance().get(elem_kind);
        if (!handler || !handler->has_python()) {
            return value;
        }
        nb::list result;
        for (auto item : value) {
            nb::object nb_item = nb::borrow<nb::object>(item);
            result.append(handler->python.convert(nb_item));
        }
        return result;
    });

    // Prevent Python GC from collecting these
    list_handler.python.serialize.inc_ref();
    list_handler.python.deserialize.inc_ref();
    list_handler.python.convert.inc_ref();
    list_handler._has_python = true;

    return &list_handler;
}

void bind_inspect(nb::module_& m) {
    // Register C++ builtin kinds (bool, int, float, string, etc.)
    tc::register_builtin_kinds();

    // Register Python-specific kind handlers (enum)
    register_builtin_kind_handlers();

    // Set handler generator callback (runs in nanobind module context)
    InspectRegistry::instance().set_handler_generator(generate_list_handler);

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
            nos::trent t = self.serialize_all(ptr, type_name);
            return InspectRegistry::trent_to_py(t);
        }, nb::arg("obj"),
           "Serialize all fields of object to dict")

        .def("deserialize_all", [](InspectRegistry& self, nb::object obj, nb::object data) {
            std::string full_type_name = nb::cast<std::string>(nb::str(nb::type_name(obj.type())));
            std::string type_name = get_short_type_name(full_type_name);
            void* ptr = get_raw_pointer(obj);
            nb::dict py_data = nb::cast<nb::dict>(data);
            self.deserialize_component_fields_over_python(ptr, obj, type_name, py_data);
        }, nb::arg("obj"), nb::arg("data"),
           "Deserialize all fields from dict to object");
}

} // namespace termin
