// tc_component_ref_bindings.cpp - TcComponentRef class binding
#include <termin/bindings/tc_component_ref_bindings.hpp>
#include <termin/bindings/entity_helpers.hpp>

#include <nanobind/nanobind.h>
#include <nanobind/stl/string.h>

#include <tcbase/tc_log.hpp>
#include <termin/entity/component.hpp>
#include <termin/entity/entity.hpp>
#include <termin/tc_scene.hpp>
#include "inspect/tc_inspect.h"
#include "inspect/tc_inspect_context.h"
#include "inspect/tc_inspect_python.hpp"
#include "inspect/tc_kind_python.hpp"
#include "core/tc_component.h"

namespace nb = nanobind;

namespace termin {

// Non-owning reference to a tc_component - allows working with components
// without requiring Python bindings for their specific type
class TcComponentRef {
public:
    tc_component* _c = nullptr;

    TcComponentRef() = default;
    explicit TcComponentRef(tc_component* c) : _c(c) {}

    bool valid() const { return _c != nullptr; }

    const char* type_name() const {
        return _c ? tc_component_type_name(_c) : "";
    }

    bool enabled() const { return _c ? _c->enabled : false; }
    void set_enabled(bool v) { if (_c) _c->enabled = v; }

    bool active_in_editor() const { return _c ? _c->active_in_editor : false; }
    void set_active_in_editor(bool v) { if (_c) _c->active_in_editor = v; }

    bool is_drawable() const { return tc_component_is_drawable(_c); }
    bool is_input_handler() const { return tc_component_is_input_handler(_c); }

    // Call on_destroy via vtable
    void on_destroy() {
        tc_component_on_destroy(_c);
    }

    tc_component_kind kind() const {
        return _c ? _c->kind : TC_CXX_COMPONENT;
    }

    // Try to get typed Python object (may return None if no bindings available)
    nb::object to_python() const {
        if (!_c) return nb::none();
        return tc_component_to_python(_c);
    }

    // Get owner entity
    Entity entity() const {
        if (!_c || !tc_entity_handle_valid(_c->owner)) return Entity();
        return Entity(_c->owner);
    }

    // Serialize component data using tc_inspect
    nb::object serialize_data() const {
        if (!_c) return nb::none();

        void* obj_ptr = nullptr;
        if (_c->kind == TC_CXX_COMPONENT) {
            obj_ptr = CxxComponent::from_tc(_c);
        } else {
            obj_ptr = _c->body;
        }
        if (!obj_ptr) return nb::none();

        tc_value v = tc_inspect_serialize(obj_ptr, tc_component_type_name(_c));
        nb::object result = tc_value_to_py(&v);
        tc_value_free(&v);
        return result;
    }

    // Full serialize (type + data)
    nb::object serialize() const {
        if (!_c) return nb::none();

        // Special case for UnknownComponent
        const char* tname = type_name();
        if (tname && strcmp(tname, "UnknownComponent") == 0 && _c->kind == TC_CXX_COMPONENT) {
            CxxComponent* cxx = CxxComponent::from_tc(_c);
            if (cxx) {
                tc_value orig_type = tc_inspect_get(cxx, "UnknownComponent", "original_type");
                tc_value orig_data = tc_inspect_get(cxx, "UnknownComponent", "original_data");

                nb::dict result;
                if (orig_type.type == TC_VALUE_STRING && orig_type.data.s && orig_type.data.s[0]) {
                    result["type"] = orig_type.data.s;
                } else {
                    result["type"] = "UnknownComponent";
                }
                result["data"] = tc_value_to_py(&orig_data);

                tc_value_free(&orig_type);
                tc_value_free(&orig_data);
                return result;
            }
        }

        // For Python components, check if they have a custom serialize method
        if (_c->native_language == TC_LANGUAGE_PYTHON && _c->body) {
            nb::object py_obj = nb::borrow<nb::object>(reinterpret_cast<PyObject*>(_c->body));
            if (nb::hasattr(py_obj, "serialize")) {
                nb::object result = py_obj.attr("serialize")();
                if (!result.is_none()) {
                    return result;
                }
            }
        }

        nb::dict result;
        result["type"] = type_name();
        result["data"] = serialize_data();
        return result;
    }

    // Deserialize data into component with explicit scene context
    void deserialize_data(nb::object data, TcSceneRef scene = TcSceneRef()) {
        tc_scene_handle scene_handle = scene.handle();
        if (!_c) {
            tc::Log::warn("[Inspect] deserialize_data called on invalid component reference");
            return;
        }
        if (data.is_none()) {
            tc::Log::warn("[Inspect] deserialize_data called with None data for %s", tc_component_type_name(_c));
            return;
        }

        void* obj_ptr = nullptr;
        if (_c->kind == TC_CXX_COMPONENT) {
            obj_ptr = CxxComponent::from_tc(_c);
        } else {
            obj_ptr = _c->body;
        }
        if (!obj_ptr) {
            tc::Log::warn("[Inspect] deserialize_data: null object pointer for %s", tc_component_type_name(_c));
            return;
        }

        tc_value v = py_to_tc_value(data);
        tc_scene_inspect_context inspect_ctx = tc_scene_inspect_context_make(scene_handle);
        tc_inspect_deserialize(obj_ptr, tc_component_type_name(_c), &v, &inspect_ctx);
        tc_value_free(&v);
    }

    // Get field value by name
    nb::object get_field(const std::string& field_name) const {
        if (!_c) return nb::none();

        void* obj_ptr = nullptr;
        if (_c->kind == TC_CXX_COMPONENT) {
            obj_ptr = CxxComponent::from_tc(_c);
        } else {
            obj_ptr = _c->body;
        }
        if (!obj_ptr) return nb::none();

        try {
            return tc::InspectRegistry_get(tc::InspectRegistry::instance(),
                obj_ptr, tc_component_type_name(_c), field_name);
        } catch (...) {
            return nb::none();
        }
    }

    // Set field value by name (inlines tc_component_inspect_set to avoid core_c dependency)
    void set_field(const std::string& field_name, nb::object value, TcSceneRef scene = TcSceneRef()) {
        if (!_c || value.is_none()) return;

        nb::object to_convert = value;

        // Check if value type is registered in kind system
        std::string kind = tc::KindRegistry::instance().kind_for_object(value);
        if (!kind.empty()) {
            nb::object serialized = tc::KindRegistry::instance().serialize_python(kind, value);
            if (!serialized.is_none()) {
                to_convert = serialized;
            }
        }

        // Inline tc_component_inspect_set logic
        void* obj_ptr = (_c->kind == TC_CXX_COMPONENT)
            ? static_cast<void*>(CxxComponent::from_tc(_c))
            : _c->body;
        if (!obj_ptr) return;

        tc_value v = py_to_tc_value(to_convert);
        tc_scene_handle scene_handle = scene.handle();
        tc_scene_inspect_context inspect_ctx = tc_scene_inspect_context_make(scene_handle);
        tc_inspect_set(obj_ptr, tc_component_type_name(_c), field_name.c_str(), v, &inspect_ctx);
        tc_value_free(&v);
    }

    bool operator==(const TcComponentRef& other) const { return _c == other._c; }
    bool operator!=(const TcComponentRef& other) const { return _c != other._c; }
};

void bind_tc_component_ref(nb::module_& m) {
    nb::enum_<tc_component_kind>(m, "TcComponentKind")
        .value("CXX", TC_CXX_COMPONENT)
        .value("PYTHON", TC_PYTHON_COMPONENT);

    nb::class_<TcComponentRef>(m, "TcComponentRef")
        .def(nb::init<>())
        .def("__init__", [](TcComponentRef& self, uintptr_t ptr) {
            new (&self) TcComponentRef(reinterpret_cast<tc_component*>(ptr));
        }, nb::arg("ptr"))
        .def("__bool__", &TcComponentRef::valid)
        .def_prop_ro("valid", &TcComponentRef::valid)
        .def("__eq__", &TcComponentRef::operator==)
        .def("__ne__", &TcComponentRef::operator!=)
        .def("__repr__", [](const TcComponentRef& self) {
            if (!self.valid()) return std::string("<TcComponentRef: invalid>");
            return std::string("<TcComponentRef: ") + self.type_name() + ">";
        })
        .def_prop_ro("type_name", &TcComponentRef::type_name)
        .def_prop_rw("enabled", &TcComponentRef::enabled, &TcComponentRef::set_enabled)
        .def_prop_rw("active_in_editor", &TcComponentRef::active_in_editor, &TcComponentRef::set_active_in_editor)
        .def_prop_ro("is_drawable", &TcComponentRef::is_drawable)
        .def_prop_ro("is_input_handler", &TcComponentRef::is_input_handler)
        .def_prop_ro("tc_component_ptr", [](TcComponentRef& self) -> uintptr_t {
            return reinterpret_cast<uintptr_t>(self._c);
        })
        .def("on_destroy", &TcComponentRef::on_destroy, "Call on_destroy lifecycle method")
        .def_prop_ro("kind", &TcComponentRef::kind)
        .def_prop_ro("entity", &TcComponentRef::entity)
        .def("to_python", &TcComponentRef::to_python,
            "Try to get typed Python component object. Returns None if no bindings available.")
        .def("serialize", &TcComponentRef::serialize,
            "Serialize component to dict with 'type' and 'data' keys.")
        .def("serialize_data", &TcComponentRef::serialize_data,
            "Serialize component data (fields only) to dict.")
        .def("deserialize_data", &TcComponentRef::deserialize_data,
            nb::arg("data"), nb::arg("scene") = TcSceneRef(),
            "Deserialize data dict into component fields. Pass scene for resolution.")
        .def("get_field", &TcComponentRef::get_field,
            nb::arg("field_name"),
            "Get field value by name. Returns None if field not found.")
        .def("set_field", &TcComponentRef::set_field,
            nb::arg("field_name"), nb::arg("value"), nb::arg("scene") = TcSceneRef(),
            "Set field value by name.");
}

} // namespace termin
