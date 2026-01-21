// tc_inspect.hpp - C++ wrapper for tc_inspect with nanobind support
// InspectRegistry is the source of truth for C++ types.
// Registers vtable with C dispatcher.
#pragma once

#include "tc_inspect.h"
#include "tc_log.h"
#include <nanobind/nanobind.h>
#include <nanobind/stl/string.h>
#include <nanobind/stl/vector.h>
#include <string>
#include <vector>
#include <unordered_map>
#include <functional>
#include <any>
#include <memory>

#include "../../cpp/termin/inspect/tc_kind.hpp"

namespace nb = nanobind;

namespace tc {

// ============================================================================
// nb::object <-> tc_value conversion
// ============================================================================

inline tc_value nb_to_tc_value(nb::object obj);
inline nb::object tc_value_to_nb(const tc_value* v);

inline tc_value nb_to_tc_value(nb::object obj) {
    if (obj.is_none()) {
        return tc_value_nil();
    }

    if (nb::isinstance<nb::bool_>(obj)) {
        return tc_value_bool(nb::cast<bool>(obj));
    }

    if (nb::isinstance<nb::int_>(obj)) {
        return tc_value_int(nb::cast<int64_t>(obj));
    }

    if (nb::isinstance<nb::float_>(obj)) {
        return tc_value_double(nb::cast<double>(obj));
    }

    if (nb::isinstance<nb::str>(obj)) {
        return tc_value_string(nb::cast<std::string>(obj).c_str());
    }

    if (nb::isinstance<nb::list>(obj) || nb::isinstance<nb::tuple>(obj)) {
        tc_value list = tc_value_list_new();
        for (auto item : obj) {
            tc_value_list_push(&list, nb_to_tc_value(nb::borrow<nb::object>(item)));
        }
        return list;
    }

    if (nb::isinstance<nb::dict>(obj)) {
        tc_value dict = tc_value_dict_new();
        for (auto item : nb::cast<nb::dict>(obj)) {
            std::string key = nb::cast<std::string>(nb::str(item.first));
            tc_value_dict_set(&dict, key.c_str(),
                nb_to_tc_value(nb::borrow<nb::object>(item.second)));
        }
        return dict;
    }

    // Try numpy array / vec3-like
    if (nb::hasattr(obj, "__len__") && nb::len(obj) == 3) {
        try {
            nb::list lst = nb::cast<nb::list>(obj);
            tc_vec3 v = {
                nb::cast<double>(lst[0]),
                nb::cast<double>(lst[1]),
                nb::cast<double>(lst[2])
            };
            return tc_value_vec3(v);
        } catch (...) {}
    }

    // Fallback: try tolist() for numpy
    if (nb::hasattr(obj, "tolist")) {
        return nb_to_tc_value(obj.attr("tolist")());
    }

    return tc_value_nil();
}

inline nb::object tc_value_to_nb(const tc_value* v) {
    if (!v) return nb::none();

    switch (v->type) {
    case TC_VALUE_NIL:
        return nb::none();

    case TC_VALUE_BOOL:
        return nb::bool_(v->data.b);

    case TC_VALUE_INT:
        return nb::int_(v->data.i);

    case TC_VALUE_FLOAT:
        return nb::float_(v->data.f);

    case TC_VALUE_DOUBLE:
        return nb::float_(v->data.d);

    case TC_VALUE_STRING:
        if (v->data.s) return nb::str(v->data.s);
        return nb::none();

    case TC_VALUE_VEC3: {
        nb::list lst;
        lst.append(v->data.v3.x);
        lst.append(v->data.v3.y);
        lst.append(v->data.v3.z);
        return lst;
    }

    case TC_VALUE_QUAT: {
        nb::list lst;
        lst.append(v->data.q.x);
        lst.append(v->data.q.y);
        lst.append(v->data.q.z);
        lst.append(v->data.q.w);
        return lst;
    }

    case TC_VALUE_LIST: {
        nb::list lst;
        for (size_t i = 0; i < v->data.list.count; i++) {
            lst.append(tc_value_to_nb(&v->data.list.items[i]));
        }
        return lst;
    }

    case TC_VALUE_DICT: {
        nb::dict d;
        for (size_t i = 0; i < v->data.dict.count; i++) {
            d[nb::str(v->data.dict.entries[i].key)] =
                tc_value_to_nb(v->data.dict.entries[i].value);
        }
        return d;
    }

    default:
        return nb::none();
    }
}

// ============================================================================
// TypeBackend - language/runtime that implements the type
// ============================================================================

enum class TypeBackend {
    Cpp,
    Python,
    Rust
};

// ============================================================================
// EnumChoice wrapper
// ============================================================================

struct EnumChoice {
    std::string value;  // Stored as string, converted to nb::object when needed
    std::string label;

    // Get value as nb::object (for Python interop)
    nb::object get_value() const {
        return nb::str(value.c_str());
    }
};

// ============================================================================
// InspectFieldInfo - field metadata + callbacks
// This is the source of truth for C++ type fields
// ============================================================================

struct InspectFieldInfo {
    std::string type_name;
    std::string path;
    std::string label;
    std::string kind;
    double min = 0.0;
    double max = 1.0;
    double step = 0.01;
    bool is_serializable = true;   // Include in serialization
    bool is_inspectable = true;    // Show in inspector
    std::vector<EnumChoice> choices;
    nb::object action;             // Python action (for buttons)
    void (*cpp_action)(void*) = nullptr;  // C++ action callback (for buttons, lazy-wrapped)

    // Unified getter/setter via tc_value - language independent
    std::function<tc_value(void*)> getter;
    std::function<void(void*, tc_value, tc_scene*)> setter;

    // Fill tc_field_info from this InspectFieldInfo
    void fill_c_info(tc_field_info* out) const {
        out->path = path.c_str();
        out->label = label.c_str();
        out->kind = kind.c_str();
        out->min = min;
        out->max = max;
        out->step = step;
        out->is_serializable = is_serializable;
        out->is_inspectable = is_inspectable;
        // Note: choices are stored in InspectFieldInfo, not exposed to C
        out->choices = nullptr;
        out->choice_count = 0;
    }
};

// ============================================================================
// InspectRegistry - main wrapper class
// Source of truth for C++ component fields
// ============================================================================

// DLL export/import macros
#ifdef _WIN32
    #ifdef ENTITY_LIB_EXPORTS
        #define TC_INSPECT_API __declspec(dllexport)
    #else
        #define TC_INSPECT_API __declspec(dllimport)
    #endif
#else
    #define TC_INSPECT_API __attribute__((visibility("default")))
#endif

class TC_INSPECT_API InspectRegistry {
    // Field storage (source of truth for C++ types)
    std::unordered_map<std::string, std::vector<InspectFieldInfo>> _fields;

    // Type backend registry
    std::unordered_map<std::string, TypeBackend> _type_backends;

    // Type parent registry
    std::unordered_map<std::string, std::string> _type_parents;

public:
    // Singleton - defined in entity_lib to ensure single instance
    static InspectRegistry& instance();

    // ========================================================================
    // Kind handler access
    // ========================================================================

    bool has_kind_handler(const std::string& kind) const {
        return KindRegistryPython::instance().has(kind)
            || KindRegistryCpp::instance().has(kind);
    }

    // ========================================================================
    // Type backend registration
    // ========================================================================

    void set_type_backend(const std::string& type_name, TypeBackend backend) {
        _type_backends[type_name] = backend;
    }

    TypeBackend get_type_backend(const std::string& type_name) const {
        auto it = _type_backends.find(type_name);
        if (it != _type_backends.end()) {
            return it->second;
        }
        // Default to C++ for unknown types (legacy behavior)
        return TypeBackend::Cpp;
    }

    bool has_type(const std::string& type_name) const {
        return _type_backends.find(type_name) != _type_backends.end();
    }

    void set_type_parent(const std::string& type_name, const std::string& parent_name) {
        if (!parent_name.empty()) {
            _type_parents[type_name] = parent_name;
            // Register type as C++ so has_type() returns true even for types
            // with only inherited fields (no own fields)
            if (_type_backends.find(type_name) == _type_backends.end()) {
                _type_backends[type_name] = TypeBackend::Cpp;
            }
        }
    }

    std::string get_type_parent(const std::string& type_name) const {
        auto it = _type_parents.find(type_name);
        return it != _type_parents.end() ? it->second : "";
    }

    // ========================================================================
    // Field registration (C++ types via template)
    // ========================================================================

    template<typename C, typename T>
    void add(const char* type_name, T C::*member,
             const char* path, const char* label, const char* kind_str,
             double min = 0.0, double max = 1.0, double step = 0.01)
    {
        InspectFieldInfo info;
        info.type_name = type_name;
        info.path = path;
        info.label = label;
        info.kind = kind_str;
        info.min = min;
        info.max = max;
        info.step = step;

        std::string kind_copy = kind_str;

        info.getter = [member, kind_copy](void* obj) -> tc_value {
            T val = static_cast<C*>(obj)->*member;
            return KindRegistry::instance().serialize_cpp(kind_copy, std::any(val));
        };

        info.setter = [member, kind_copy](void* obj, tc_value value, tc_scene* scene) {
            std::any val = KindRegistry::instance().deserialize_cpp(kind_copy, &value, scene);
            if (val.has_value()) {
                static_cast<C*>(obj)->*member = std::any_cast<T>(val);
            }
        };

        _fields[type_name].push_back(std::move(info));
        _type_backends[type_name] = TypeBackend::Cpp;
    }

    template<typename C, typename T>
    void add_with_callbacks(
        const char* type_name,
        const char* path,
        const char* label,
        const char* kind_str,
        std::function<T&(C*)> getter_fn,
        std::function<void(C*, const T&)> setter_fn
    ) {
        InspectFieldInfo info;
        info.type_name = type_name;
        info.path = path;
        info.label = label;
        info.kind = kind_str;

        std::string kind_copy = kind_str;

        info.getter = [getter_fn, kind_copy](void* obj) -> tc_value {
            T val = getter_fn(static_cast<C*>(obj));
            return KindRegistry::instance().serialize_cpp(kind_copy, std::any(val));
        };

        info.setter = [setter_fn, kind_copy](void* obj, tc_value value, tc_scene* scene) {
            std::any val = KindRegistry::instance().deserialize_cpp(kind_copy, &value, scene);
            if (val.has_value()) {
                setter_fn(static_cast<C*>(obj), std::any_cast<T>(val));
            }
        };

        _fields[type_name].push_back(std::move(info));
        _type_backends[type_name] = TypeBackend::Cpp;
    }

    // Version with value getters (for accessor methods)
    template<typename C, typename T>
    void add_with_accessors(
        const char* type_name,
        const char* path,
        const char* label,
        const char* kind_str,
        std::function<T(C*)> getter_fn,
        std::function<void(C*, T)> setter_fn
    ) {
        InspectFieldInfo info;
        info.type_name = type_name;
        info.path = path;
        info.label = label;
        info.kind = kind_str;

        std::string kind_copy = kind_str;

        info.getter = [getter_fn, kind_copy](void* obj) -> tc_value {
            T val = getter_fn(static_cast<C*>(obj));
            return KindRegistry::instance().serialize_cpp(kind_copy, std::any(val));
        };

        info.setter = [setter_fn, kind_copy](void* obj, tc_value value, tc_scene* scene) {
            std::any val = KindRegistry::instance().deserialize_cpp(kind_copy, &value, scene);
            if (val.has_value()) {
                setter_fn(static_cast<C*>(obj), std::any_cast<T>(val));
            }
        };

        _fields[type_name].push_back(std::move(info));
        _type_backends[type_name] = TypeBackend::Cpp;
    }

    // Version for handle types with deserialize_from (C++ inplace deserialization)
    template<typename C, typename H>
    void add_handle(
        const char* type_name, H C::*member,
        const char* path, const char* label, const char* kind_str
    ) {
        InspectFieldInfo info;
        info.type_name = type_name;
        info.path = path;
        info.label = label;
        info.kind = kind_str;

        std::string kind_copy = kind_str;

        info.getter = [member, kind_copy](void* obj) -> tc_value {
            H val = static_cast<C*>(obj)->*member;
            return KindRegistry::instance().serialize_cpp(kind_copy, std::any(val));
        };

        info.setter = [member, kind_copy](void* obj, tc_value value, tc_scene* scene) {
            std::any val = KindRegistry::instance().deserialize_cpp(kind_copy, &value, scene);
            if (val.has_value()) {
                static_cast<C*>(obj)->*member = std::any_cast<H>(val);
            }
        };

        _fields[type_name].push_back(std::move(info));
        _type_backends[type_name] = TypeBackend::Cpp;
    }

    // Add a serializable-only field (for SERIALIZABLE_FIELD macro)
    void add_serializable_field(const std::string& type_name, InspectFieldInfo&& info) {
        _fields[type_name].push_back(std::move(info));
    }

    // Add a field with choices (for INSPECT_FIELD_CHOICES macro)
    void add_field_with_choices(const std::string& type_name, InspectFieldInfo&& info) {
        _fields[type_name].push_back(std::move(info));
        _type_backends[type_name] = TypeBackend::Cpp;
    }

    // Add a button field (for inspector buttons that trigger actions)
    void add_button(const std::string& type_name, const std::string& path,
                    const std::string& label, nb::object action) {
        InspectFieldInfo info;
        info.type_name = type_name;
        info.path = path;
        info.label = label;
        info.kind = "button";
        info.is_serializable = false;
        info.is_inspectable = true;
        info.action = std::move(action);

        _fields[type_name].push_back(std::move(info));
    }

    // Add a button field with C++ callback (no Python dependency at registration time)
    // The nb::cpp_function is created lazily when action is accessed
    using ButtonActionFn = void (*)(void* component);

    void add_button_cpp(const std::string& type_name, const std::string& path,
                        const std::string& label, ButtonActionFn action_fn) {
        InspectFieldInfo info;
        info.type_name = type_name;
        info.path = path;
        info.label = label;
        info.kind = "button";
        info.is_serializable = false;
        info.is_inspectable = true;
        info.cpp_action = action_fn;  // Store C++ callback
        // info.action will be created lazily

        _fields[type_name].push_back(std::move(info));
    }

    // ========================================================================
    // Field registration (Python types)
    // ========================================================================

    // Defined in tc_inspect_instance.cpp (needs Component full definition)
    void register_python_fields(const std::string& type_name, nb::dict fields_dict);

    // ========================================================================
    // Field queries
    // ========================================================================

    const std::vector<InspectFieldInfo>& fields(const std::string& type_name) const {
        static std::vector<InspectFieldInfo> empty;
        auto it = _fields.find(type_name);
        return it != _fields.end() ? it->second : empty;
    }

    std::vector<InspectFieldInfo> all_fields(const std::string& type_name) const {
        std::vector<InspectFieldInfo> result;

        // Add parent fields first (recursively)
        std::string parent = get_type_parent(type_name);
        if (!parent.empty()) {
            auto parent_fields = all_fields(parent);
            result.insert(result.end(), parent_fields.begin(), parent_fields.end());
        }

        // Add own fields
        auto it = _fields.find(type_name);
        if (it != _fields.end()) {
            result.insert(result.end(), it->second.begin(), it->second.end());
        }
        return result;
    }

    size_t all_fields_count(const std::string& type_name) const {
        size_t count = 0;
        std::string parent = get_type_parent(type_name);
        if (!parent.empty()) {
            count += all_fields_count(parent);
        }
        auto it = _fields.find(type_name);
        if (it != _fields.end()) {
            count += it->second.size();
        }
        return count;
    }

    // Get field info by index (for vtable callback)
    const InspectFieldInfo* get_field_by_index(const std::string& type_name, size_t index) const {
        // First check parent
        std::string parent = get_type_parent(type_name);
        if (!parent.empty()) {
            size_t parent_count = all_fields_count(parent);
            if (index < parent_count) {
                return get_field_by_index(parent, index);
            }
            index -= parent_count;
        }

        // Then own fields
        auto it = _fields.find(type_name);
        if (it != _fields.end() && index < it->second.size()) {
            return &it->second[index];
        }
        return nullptr;
    }

    // Find field by path
    const InspectFieldInfo* find_field(const std::string& type_name, const std::string& path) const {
        // Search own fields first
        auto it = _fields.find(type_name);
        if (it != _fields.end()) {
            for (const auto& f : it->second) {
                if (f.path == path) return &f;
            }
        }

        // Search parent
        std::string parent = get_type_parent(type_name);
        if (!parent.empty()) {
            return find_field(parent, path);
        }

        return nullptr;
    }

    std::vector<std::string> types() const {
        std::vector<std::string> result;
        for (const auto& [name, _] : _fields) {
            result.push_back(name);
        }
        return result;
    }

    // ========================================================================
    // Field access via tc_value (unified)
    // ========================================================================

    tc_value get_tc_value(void* obj, const std::string& type_name, const std::string& field_path) const {
        const InspectFieldInfo* f = find_field(type_name, field_path);
        if (!f || !f->getter) return tc_value_nil();
        return f->getter(obj);
    }

    void set_tc_value(void* obj, const std::string& type_name, const std::string& field_path, tc_value value, tc_scene* scene) {
        const InspectFieldInfo* f = find_field(type_name, field_path);
        if (!f || !f->setter) {
            return;
        }
        f->setter(obj, value, scene);
    }

    // ========================================================================
    // Field access (Python interop) - via tc_value conversion
    // ========================================================================

    nb::object get(void* obj, const std::string& type_name, const std::string& field_path) const {
        const InspectFieldInfo* f = find_field(type_name, field_path);
        if (!f) {
            throw nb::attribute_error(("Field not found: " + field_path).c_str());
        }
        if (!f->getter) {
            throw nb::type_error(("No getter for field: " + field_path).c_str());
        }
        tc_value val = f->getter(obj);
        nb::object result = tc_value_to_nb(&val);
        tc_value_free(&val);
        return result;
    }

    void set(void* obj, const std::string& type_name, const std::string& field_path, nb::object value, tc_scene* scene = nullptr) {
        const InspectFieldInfo* f = find_field(type_name, field_path);
        if (!f) {
            throw nb::attribute_error(("Field not found: " + field_path).c_str());
        }
        if (!f->setter) {
            throw nb::type_error(("No setter for field: " + field_path).c_str());
        }
        tc_value val = nb_to_tc_value(value);
        f->setter(obj, val, scene);
        tc_value_free(&val);
    }

    void action_field(void* obj, const std::string& type_name, const std::string& field_path) {
        const InspectFieldInfo* f = find_field(type_name, field_path);
        if (!f) return;

        if (f->cpp_action) {
            f->cpp_action(obj);
        } else if (f->action.ptr() && !f->action.is_none()) {
            // Call Python action with the object
            // Note: this requires the object to be accessible from Python
            // For C++ objects, we'd need to wrap them first
        }
    }

    // ========================================================================
    // Serialization
    // ========================================================================

    tc_value serialize_all(void* obj, const std::string& type_name) const {
        tc_value result = tc_value_dict_new();

        for (const auto& f : all_fields(type_name)) {
            if (!f.is_serializable) continue;
            if (!f.getter) continue;

            tc_value val = f.getter(obj);
            if (val.type != TC_VALUE_NIL) {
                tc_value_dict_set(&result, f.path.c_str(), val);
            } else {
                tc_value_free(&val);
            }
        }

        return result;
    }

    // Unified deserialization - uses setter via tc_value
    void deserialize_all(void* obj, const std::string& type_name, const nb::dict& data, tc_scene* scene = nullptr) {
        for (const auto& f : all_fields(type_name)) {
            if (!f.is_serializable) continue;
            if (!f.setter) continue;

            nb::str key(f.path.c_str());
            if (!data.contains(key)) continue;

            nb::object field_data = data[key];
            if (field_data.is_none()) continue;

            tc_value val = nb_to_tc_value(field_data);
            f.setter(obj, val, scene);
            tc_value_free(&val);
        }
    }

    // Legacy aliases for compatibility
    void deserialize_fields_of_cxx_component_over_python(void* ptr, nb::object, const std::string& type_name, const nb::dict& data, tc_scene* scene = nullptr) {
        deserialize_all(ptr, type_name, data, scene);
    }

    void deserialize_fields_of_python_component_over_python(nb::object obj, const std::string& type_name, const nb::dict& data) {
        deserialize_all(obj.ptr(), type_name, data, nullptr);
    }

    void deserialize_component_fields_over_python(void* ptr, nb::object obj, const std::string& type_name, const nb::dict& data, tc_scene* scene = nullptr) {
        // For C++ components ptr is the object, for Python components obj.ptr() is used
        void* target = (get_type_backend(type_name) == TypeBackend::Cpp) ? ptr : obj.ptr();
        deserialize_all(target, type_name, data, scene);
    }
};

// ============================================================================
// C++ vtable callbacks - implemented in tc_inspect_instance.cpp
// ============================================================================

TC_INSPECT_API void init_cpp_inspect_vtable();

// ============================================================================
// Static registration helpers (for C++ components)
// ============================================================================

template<typename C, typename T>
struct InspectFieldRegistrar {
    InspectFieldRegistrar(T C::*member, const char* type_name,
                          const char* path, const char* label, const char* kind,
                          double min = 0.0, double max = 1.0, double step = 0.01) {
        // Register in InspectRegistry only - no C API duplication
        InspectRegistry::instance().add<C, T>(type_name, member, path, label, kind, min, max, step);
    }
};

template<typename C, typename T>
struct InspectFieldCallbackRegistrar {
    InspectFieldCallbackRegistrar(
        const char* type_name,
        const char* path,
        const char* label,
        const char* kind,
        std::function<T&(C*)> getter,
        std::function<void(C*, const T&)> setter
    ) {
        InspectRegistry::instance().add_with_callbacks<C, T>(
            type_name, path, label, kind, getter, setter
        );
    }
};

// Registrar for INSPECT_FIELD_CHOICES (fields with enum-like choices)
template<typename C, typename T>
struct InspectFieldChoicesRegistrar {
    InspectFieldChoicesRegistrar(
        T C::*member,
        const char* type_name,
        const char* path,
        const char* label,
        const char* kind_str,
        std::initializer_list<std::pair<const char*, const char*>> choices_list
    ) {
        InspectFieldInfo info;
        info.type_name = type_name;
        info.path = path;
        info.label = label;
        info.kind = kind_str;

        // Convert choices to EnumChoice vector (store as strings, not nb::object)
        for (const auto& [value, choice_label] : choices_list) {
            EnumChoice choice;
            choice.value = value;
            choice.label = choice_label;
            info.choices.push_back(std::move(choice));
        }

        std::string kind_copy = kind_str;

        info.getter = [member, kind_copy](void* obj) -> tc_value {
            T val = static_cast<C*>(obj)->*member;
            return KindRegistry::instance().serialize_cpp(kind_copy, std::any(val));
        };

        info.setter = [member, kind_copy](void* obj, tc_value value, tc_scene* scene) {
            std::any val = KindRegistry::instance().deserialize_cpp(kind_copy, &value, scene);
            if (val.has_value()) {
                static_cast<C*>(obj)->*member = std::any_cast<T>(val);
            }
        };

        InspectRegistry::instance().add_field_with_choices(type_name, std::move(info));
    }
};

// Registrar for SERIALIZABLE_FIELD (serialize-only fields, no kind handler)
template<typename C>
struct SerializableFieldRegistrar {
    SerializableFieldRegistrar(
        const char* type_name,
        const char* path,
        std::function<tc_value(C*)> tc_getter,
        std::function<void(C*, const tc_value*)> tc_setter
    ) {
        InspectFieldInfo info;
        info.type_name = type_name;
        info.path = path;
        info.label = "";
        info.kind = "";
        info.is_inspectable = false;  // Not shown in inspector
        info.is_serializable = true;

        info.getter = [tc_getter](void* obj) -> tc_value {
            return tc_getter(static_cast<C*>(obj));
        };

        info.setter = [tc_setter](void* obj, tc_value value, tc_scene*) {
            tc_setter(static_cast<C*>(obj), &value);
        };

        InspectRegistry::instance().add_serializable_field(type_name, std::move(info));
    }
};

// Button action function type (C++ side, no Python dependency)
using ButtonActionFn = void (*)(void* component);

// Registrar for INSPECT_BUTTON (button field with C++ method callback)
template<typename C>
struct InspectButtonRegistrar {
    template<typename Method>
    InspectButtonRegistrar(
        const char* type_name,
        const char* path,
        const char* label,
        Method method
    ) {
        // Store method in static to capture it without Python
        static Method stored_method = method;

        // C++ callback that doesn't need Python
        ButtonActionFn action_fn = [](void* component) {
            C* ptr = static_cast<C*>(component);
            if (ptr) {
                (ptr->*stored_method)();
            }
        };

        InspectRegistry::instance().add_button_cpp(type_name, path, label, action_fn);
    }
};

} // namespace tc

// ============================================================================
// Macros (compatible with existing code)
// ============================================================================

#define INSPECT_FIELD(cls, field, label, kind, ...) \
    inline static ::tc::InspectFieldRegistrar<cls, decltype(cls::field)> \
        _inspect_reg_##cls##_##field{&cls::field, #cls, #field, label, kind, ##__VA_ARGS__};

#define INSPECT_FIELD_CALLBACK(cls, type, name, label, kind, getter_fn, setter_fn) \
    inline static ::tc::InspectFieldCallbackRegistrar<cls, type> \
        _inspect_reg_##cls##_##name{#cls, #name, label, kind, getter_fn, setter_fn};

// SERIALIZABLE_FIELD - serialize-only field with custom tc_value getter/setter
// Not shown in inspector, only used for serialization/deserialization
// Usage: SERIALIZABLE_FIELD(MyClass, field_key, get_data(), set_data(val))
//   - getter expression receives 'this' implicitly, returns tc_value
//   - setter expression receives 'this' and 'val' (const tc_value*)
#define SERIALIZABLE_FIELD(cls, name, getter_expr, setter_expr) \
    inline static ::tc::SerializableFieldRegistrar<cls> \
        _serialize_reg_##cls##_##name{#cls, #name, \
            [](cls* self) -> tc_value { return self->getter_expr; }, \
            [](cls* self, const tc_value* val) { self->setter_expr; }};

// INSPECT_FIELD_CHOICES - field with enum-like choices (variadic)
// Usage: INSPECT_FIELD_CHOICES(ColorPass, sort_mode, "Sort Mode", "string",
//            {"none", "None"}, {"near_to_far", "Near to Far"}, {"far_to_near", "Far to Near"})
#define INSPECT_FIELD_CHOICES(cls, field, label, kind, ...) \
    inline static ::tc::InspectFieldChoicesRegistrar<cls, decltype(cls::field)> \
        _inspect_reg_##cls##_##field{&cls::field, #cls, #field, label, kind, {__VA_ARGS__}};

// INSPECT_BUTTON - button field with C++ callback
// Usage: INSPECT_BUTTON(MyClass, build_btn, "Build", &MyClass::build)
#define INSPECT_BUTTON(cls, name, label, method) \
    inline static ::tc::InspectButtonRegistrar<cls> \
        _inspect_btn_##cls##_##name{#cls, #name, label, method};
