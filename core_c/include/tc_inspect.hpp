// tc_inspect.hpp - C++ wrapper for tc_inspect with pybind11 support
#pragma once

#include "tc_inspect.h"
#include <pybind11/pybind11.h>
#include <pybind11/stl.h>
#include <string>
#include <vector>
#include <unordered_map>
#include <functional>
#include <iostream>

// Optional trent support for serialization compatibility
#ifdef TC_HAS_TRENT
#include "trent/trent.h"
#endif

// Forward declare CxxComponent for Python object casting
namespace termin { class CxxComponent; }

namespace py = pybind11;

namespace tc {

// ============================================================================
// py::object <-> tc_value conversion
// ============================================================================

inline tc_value py_to_tc_value(py::object obj);
inline py::object tc_value_to_py(const tc_value* v);

inline tc_value py_to_tc_value(py::object obj) {
    if (obj.is_none()) {
        return tc_value_nil();
    }

    if (py::isinstance<py::bool_>(obj)) {
        return tc_value_bool(obj.cast<bool>());
    }

    if (py::isinstance<py::int_>(obj)) {
        return tc_value_int(obj.cast<int64_t>());
    }

    if (py::isinstance<py::float_>(obj)) {
        return tc_value_double(obj.cast<double>());
    }

    if (py::isinstance<py::str>(obj)) {
        return tc_value_string(obj.cast<std::string>().c_str());
    }

    if (py::isinstance<py::list>(obj) || py::isinstance<py::tuple>(obj)) {
        tc_value list = tc_value_list_new();
        for (auto item : obj) {
            tc_value_list_push(&list, py_to_tc_value(py::reinterpret_borrow<py::object>(item)));
        }
        return list;
    }

    if (py::isinstance<py::dict>(obj)) {
        tc_value dict = tc_value_dict_new();
        for (auto item : obj.cast<py::dict>()) {
            std::string key = py::str(item.first).cast<std::string>();
            tc_value_dict_set(&dict, key.c_str(),
                py_to_tc_value(py::reinterpret_borrow<py::object>(item.second)));
        }
        return dict;
    }

    // Try numpy array / vec3-like
    if (py::hasattr(obj, "__len__") && py::len(obj) == 3) {
        try {
            py::list lst = obj.cast<py::list>();
            tc_vec3 v = {
                lst[0].cast<double>(),
                lst[1].cast<double>(),
                lst[2].cast<double>()
            };
            return tc_value_vec3(v);
        } catch (...) {}
    }

    // Fallback: try tolist() for numpy
    if (py::hasattr(obj, "tolist")) {
        return py_to_tc_value(obj.attr("tolist")());
    }

    return tc_value_nil();
}

inline py::object tc_value_to_py(const tc_value* v) {
    if (!v) return py::none();

    switch (v->type) {
    case TC_VALUE_NIL:
        return py::none();

    case TC_VALUE_BOOL:
        return py::bool_(v->data.b);

    case TC_VALUE_INT:
        return py::int_(v->data.i);

    case TC_VALUE_FLOAT:
        return py::float_(v->data.f);

    case TC_VALUE_DOUBLE:
        return py::float_(v->data.d);

    case TC_VALUE_STRING:
        if (v->data.s) return py::str(v->data.s);
        return py::none();

    case TC_VALUE_VEC3: {
        py::list lst;
        lst.append(v->data.v3.x);
        lst.append(v->data.v3.y);
        lst.append(v->data.v3.z);
        return lst;
    }

    case TC_VALUE_QUAT: {
        py::list lst;
        lst.append(v->data.q.x);
        lst.append(v->data.q.y);
        lst.append(v->data.q.z);
        lst.append(v->data.q.w);
        return lst;
    }

    case TC_VALUE_LIST: {
        py::list lst;
        for (size_t i = 0; i < v->data.list.count; i++) {
            lst.append(tc_value_to_py(&v->data.list.items[i]));
        }
        return lst;
    }

    case TC_VALUE_DICT: {
        py::dict d;
        for (size_t i = 0; i < v->data.dict.count; i++) {
            d[py::str(v->data.dict.entries[i].key)] =
                tc_value_to_py(v->data.dict.entries[i].value);
        }
        return d;
    }

    case TC_VALUE_CUSTOM: {
        // Custom types need kind handler to convert
        const tc_kind_handler* h = tc_kind_get(v->kind);
        if (h && h->serialize) {
            tc_value serialized = h->serialize(v);
            py::object result = tc_value_to_py(&serialized);
            tc_value_free(&serialized);
            return result;
        }
        return py::none();
    }

    default:
        return py::none();
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
    py::object value;
    std::string label;
};

// ============================================================================
// InspectFieldInfo - mirrors tc_field_desc with Python integration
// ============================================================================

struct InspectFieldInfo {
    std::string type_name;
    std::string path;
    std::string label;
    std::string kind;
    double min = 0.0;
    double max = 1.0;
    double step = 0.01;
    bool non_serializable = false;
    std::vector<EnumChoice> choices;
    py::object action;

    // Getter/setter using tc_inspect
    std::function<py::object(void*)> getter;
    std::function<void(void*, py::object)> setter;
};

// ============================================================================
// Forward declarations for trent compatibility
// ============================================================================

#ifdef TC_HAS_TRENT
tc_value trent_to_tc_value(const nos::trent& t);
nos::trent tc_value_to_trent(const tc_value* v);
nos::trent py_to_trent_compat(py::object obj);
py::object trent_to_py_compat(const nos::trent& t);
#endif

// ============================================================================
// KindHandler - wrapper for tc_kind_handler with Python callbacks
// Uses trent for serialize/deserialize to maintain backward compatibility
// ============================================================================

#ifdef TC_HAS_TRENT
struct KindHandler {
    std::function<nos::trent(py::object)> serialize;
    std::function<py::object(const nos::trent&)> deserialize;
    std::function<py::object(py::object)> convert;
};
#else
struct KindHandler {
    std::function<py::object(py::object)> serialize;
    std::function<py::object(py::object)> deserialize;
    std::function<py::object(py::object)> convert;
};
#endif

// ============================================================================
// InspectRegistry - main wrapper class
// Exported from entity_lib to ensure single instance across all modules
// ============================================================================

// DLL export/import macros
#ifdef _WIN32
    #ifdef ENTITY_LIB_EXPORTS
        #define TC_INSPECT_API __declspec(dllexport)
    #else
        #define TC_INSPECT_API __declspec(dllimport)
    #endif
#else
    #define TC_INSPECT_API
#endif

class TC_INSPECT_API InspectRegistry {
    // Python-specific storage (for fields registered from Python)
    std::unordered_map<std::string, std::vector<InspectFieldInfo>> _py_fields;
    std::unordered_map<std::string, KindHandler> _py_kind_handlers;

    // Type vtables for Python types
    std::unordered_map<std::string, tc_type_vtable> _py_vtables;
    std::unordered_map<std::string, std::vector<tc_field_desc>> _py_field_descs;

    // Type backend registry
    std::unordered_map<std::string, TypeBackend> _type_backends;

public:
    // Singleton - defined in entity_lib to ensure single instance
    static InspectRegistry& instance();

    // ========================================================================
    // Kind handler registration
    // ========================================================================

    void register_kind(const std::string& kind, KindHandler handler) {
        _py_kind_handlers[kind] = std::move(handler);

        // Also register in C layer
        // Note: C layer handlers are simpler, Python layer does the heavy lifting
    }

    bool has_kind_handler(const std::string& kind) const {
        return _py_kind_handlers.find(kind) != _py_kind_handlers.end()
            || tc_kind_exists(kind.c_str());
    }

    const KindHandler* get_kind_handler(const std::string& kind) {
        auto it = _py_kind_handlers.find(kind);
        if (it != _py_kind_handlers.end()) {
            return &it->second;
        }

        // Try to generate for parameterized types like list[T]
        return try_generate_handler(kind);
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

    // ========================================================================
    // Field registration (C++ types via template)
    // ========================================================================

    template<typename C, typename T>
    void add(const char* type_name, T C::*member,
             const char* path, const char* label, const char* kind,
             double min = 0.0, double max = 1.0, double step = 0.01)
    {
        InspectFieldInfo info;
        info.type_name = type_name;
        info.path = path;
        info.label = label;
        info.kind = kind;
        info.min = min;
        info.max = max;
        info.step = step;

        info.getter = [member](void* obj) -> py::object {
            auto& val = static_cast<C*>(obj)->*member;
            return py::cast(val);
        };

        info.setter = [member, path](void* obj, py::object val) {
            try {
                static_cast<C*>(obj)->*member = val.cast<T>();
            } catch (const std::exception& e) {
                std::cerr << "[INSPECT setter error] path=" << path
                          << " error=" << e.what() << std::endl;
            }
        };

        _py_fields[type_name].push_back(std::move(info));
        _type_backends[type_name] = TypeBackend::Cpp;
    }

    template<typename C, typename T>
    void add_with_callbacks(
        const char* type_name,
        const char* path,
        const char* label,
        const char* kind,
        std::function<T&(C*)> getter,
        std::function<void(C*, const T&)> setter
    ) {
        InspectFieldInfo info;
        info.type_name = type_name;
        info.path = path;
        info.label = label;
        info.kind = kind;

        info.getter = [getter](void* obj) -> py::object {
            return py::cast(getter(static_cast<C*>(obj)));
        };

        info.setter = [setter](void* obj, py::object val) {
            setter(static_cast<C*>(obj), val.cast<T>());
        };

        _py_fields[type_name].push_back(std::move(info));
        _type_backends[type_name] = TypeBackend::Cpp;
    }

    // ========================================================================
    // Field registration (Python types)
    // ========================================================================

    // Defined in tc_inspect_instance.cpp (needs Component full definition)
    void register_python_fields(const std::string& type_name, py::dict fields_dict);

    // ========================================================================
    // Field queries
    // ========================================================================

    const std::vector<InspectFieldInfo>& fields(const std::string& type_name) const {
        static std::vector<InspectFieldInfo> empty;
        auto it = _py_fields.find(type_name);
        return it != _py_fields.end() ? it->second : empty;
    }

    std::vector<InspectFieldInfo> all_fields(const std::string& type_name) const {
        std::vector<InspectFieldInfo> result;

        // Add Component base fields first
        if (type_name != "Component") {
            auto base_it = _py_fields.find("Component");
            if (base_it != _py_fields.end()) {
                result.insert(result.end(), base_it->second.begin(), base_it->second.end());
            }
        }

        // Add own fields
        auto it = _py_fields.find(type_name);
        if (it != _py_fields.end()) {
            result.insert(result.end(), it->second.begin(), it->second.end());
        }

        return result;
    }

    std::vector<std::string> types() const {
        std::vector<std::string> result;
        for (const auto& [name, _] : _py_fields) {
            result.push_back(name);
        }
        return result;
    }

    // ========================================================================
    // Field access
    // ========================================================================

    py::object get(void* obj, const std::string& type_name, const std::string& field_path) const {
        for (const auto& f : all_fields(type_name)) {
            if (f.path == field_path) {
                return f.getter(obj);
            }
        }
        throw py::attribute_error("Field not found: " + field_path);
    }

    void set(void* obj, const std::string& type_name, const std::string& field_path, py::object value) {
        for (const auto& f : all_fields(type_name)) {
            if (f.path == field_path) {
                py::object converted = convert_value_for_kind(value, f.kind);
                f.setter(obj, converted);
                return;
            }
        }
        throw py::attribute_error("Field not found: " + field_path);
    }

    // ========================================================================
    // Value conversion
    // ========================================================================

    py::object convert_value_for_kind(py::object value, const std::string& kind) {
        auto* handler = get_kind_handler(kind);
        if (handler && handler->convert) {
            return handler->convert(value);
        }
        return value;
    }

#ifdef TC_HAS_TRENT
    // ========================================================================
    // Serialization (trent-based for backward compatibility)
    // ========================================================================

    nos::trent serialize_all(void* obj, const std::string& type_name) const {
        nos::trent result;
        result.init(nos::trent_type::dict);

        for (const auto& f : all_fields(type_name)) {
            if (f.non_serializable) continue;
            py::object val = f.getter(obj);

            // Apply kind handler if exists (serialize returns trent)
            auto* handler = const_cast<InspectRegistry*>(this)->get_kind_handler(f.kind);
            if (handler && handler->serialize) {
                result[f.path] = handler->serialize(val);
            } else {
                tc_value tv = py_to_tc_value(val);
                result[f.path] = tc_value_to_trent(&tv);
                tc_value_free(&tv);
            }
        }
        return result;
    }

    void deserialize_all(void* obj, const std::string& type_name, const nos::trent& data) {
        if (!data.is_dict()) return;

        for (const auto& f : all_fields(type_name)) {
            if (f.non_serializable) continue;
            if (!data.contains(f.path)) continue;

            const auto& field_data = data[f.path];
            if (field_data.is_nil()) continue;

            py::object val;

            // Apply kind handler if exists (deserialize takes trent)
            auto* handler = get_kind_handler(f.kind);
            if (handler && handler->deserialize) {
                val = handler->deserialize(field_data);
            } else {
                tc_value tv = trent_to_tc_value(field_data);
                val = tc_value_to_py(&tv);
                tc_value_free(&tv);
            }

            f.setter(obj, val);
        }
    }

    // Compatibility static methods
    static py::object trent_to_py(const nos::trent& t) {
        return trent_to_py_compat(t);
    }

    static py::dict trent_to_py_dict(const nos::trent& t) {
        py::object result = trent_to_py_compat(t);
        if (py::isinstance<py::dict>(result)) {
            return result.cast<py::dict>();
        }
        return py::dict();
    }

    static nos::trent py_to_trent(py::object obj) {
        return py_to_trent_compat(obj);
    }

    static nos::trent py_dict_to_trent(py::dict d) {
        return py_to_trent_compat(d);
    }

    static nos::trent py_list_to_trent(py::list lst) {
        return py_to_trent_compat(lst);
    }

#endif // TC_HAS_TRENT

private:
#ifdef TC_HAS_TRENT
    KindHandler* try_generate_handler(const std::string& kind) {
        char container[64], element[64];
        if (!tc_kind_parse(kind.c_str(), container, sizeof(container),
                          element, sizeof(element))) {
            return nullptr;
        }

        if (std::string(container) == "list") {
            auto elem_it = _py_kind_handlers.find(element);
            if (elem_it == _py_kind_handlers.end()) {
                return nullptr;
            }

            KindHandler list_handler;
            std::string elem_kind = element;

            // serialize: py::object (list) -> nos::trent (list)
            list_handler.serialize = [this, elem_kind](py::object obj) -> nos::trent {
                nos::trent result;
                result.init(nos::trent_type::list);
                if (obj.is_none()) return result;

                auto* elem_handler = get_kind_handler(elem_kind);
                for (auto item : obj) {
                    py::object py_item = py::reinterpret_borrow<py::object>(item);
                    if (elem_handler && elem_handler->serialize) {
                        result.push_back(elem_handler->serialize(py_item));
                    } else {
                        result.push_back(py_to_trent_compat(py_item));
                    }
                }
                return result;
            };

            // deserialize: nos::trent (list) -> py::object (list)
            list_handler.deserialize = [this, elem_kind](const nos::trent& t) -> py::object {
                py::list result;
                if (!t.is_list()) return result;

                auto* elem_handler = get_kind_handler(elem_kind);
                for (const auto& item : t.as_list()) {
                    if (elem_handler && elem_handler->deserialize) {
                        result.append(elem_handler->deserialize(item));
                    } else {
                        result.append(trent_to_py_compat(item));
                    }
                }
                return result;
            };

            list_handler.convert = [this, elem_kind](py::object value) -> py::object {
                if (value.is_none()) return py::list();

                auto* elem_handler = get_kind_handler(elem_kind);
                if (!elem_handler || !elem_handler->convert) {
                    return value;
                }

                py::list result;
                for (auto item : value) {
                    py::object py_item = py::reinterpret_borrow<py::object>(item);
                    result.append(elem_handler->convert(py_item));
                }
                return result;
            };

            _py_kind_handlers[kind] = std::move(list_handler);
            return &_py_kind_handlers[kind];
        }

        return nullptr;
    }
#else
    KindHandler* try_generate_handler(const std::string& kind) {
        (void)kind;
        return nullptr;
    }
#endif
};

// ============================================================================
// Static registration helpers (for C++ components)
// ============================================================================

template<typename C, typename T>
struct InspectFieldRegistrar {
    InspectFieldRegistrar(T C::*member, const char* type_name,
                          const char* path, const char* label, const char* kind,
                          double min = 0.0, double max = 1.0, double step = 0.01) {
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

// ============================================================================
// Trent compatibility (when TC_HAS_TRENT is defined)
// ============================================================================

#ifdef TC_HAS_TRENT

inline tc_value trent_to_tc_value(const nos::trent& t) {
    switch (t.get_type()) {
    case nos::trent_type::nil:
        return tc_value_nil();
    case nos::trent_type::boolean:
        return tc_value_bool(t.as_bool());
    case nos::trent_type::numer:
        return tc_value_double(static_cast<double>(t.as_numer()));
    case nos::trent_type::string:
        return tc_value_string(t.as_string().c_str());
    case nos::trent_type::list: {
        tc_value list = tc_value_list_new();
        for (const auto& item : t.as_list()) {
            tc_value_list_push(&list, trent_to_tc_value(item));
        }
        return list;
    }
    case nos::trent_type::dict: {
        tc_value dict = tc_value_dict_new();
        for (const auto& [key, val] : t.as_dict()) {
            tc_value_dict_set(&dict, key.c_str(), trent_to_tc_value(val));
        }
        return dict;
    }
    default:
        return tc_value_nil();
    }
}

inline nos::trent tc_value_to_trent(const tc_value* v) {
    if (!v) return nos::trent::nil();

    switch (v->type) {
    case TC_VALUE_NIL:
        return nos::trent::nil();
    case TC_VALUE_BOOL:
        return nos::trent(v->data.b);
    case TC_VALUE_INT:
        return nos::trent(static_cast<nos::trent::numer_type>(v->data.i));
    case TC_VALUE_FLOAT:
        return nos::trent(static_cast<nos::trent::numer_type>(v->data.f));
    case TC_VALUE_DOUBLE:
        return nos::trent(static_cast<nos::trent::numer_type>(v->data.d));
    case TC_VALUE_STRING:
        return v->data.s ? nos::trent(std::string(v->data.s)) : nos::trent::nil();
    case TC_VALUE_VEC3: {
        nos::trent list;
        list.init(nos::trent_type::list);
        list.push_back(nos::trent(v->data.v3.x));
        list.push_back(nos::trent(v->data.v3.y));
        list.push_back(nos::trent(v->data.v3.z));
        return list;
    }
    case TC_VALUE_QUAT: {
        nos::trent list;
        list.init(nos::trent_type::list);
        list.push_back(nos::trent(v->data.q.x));
        list.push_back(nos::trent(v->data.q.y));
        list.push_back(nos::trent(v->data.q.z));
        list.push_back(nos::trent(v->data.q.w));
        return list;
    }
    case TC_VALUE_LIST: {
        nos::trent list;
        list.init(nos::trent_type::list);
        for (size_t i = 0; i < v->data.list.count; i++) {
            list.push_back(tc_value_to_trent(&v->data.list.items[i]));
        }
        return list;
    }
    case TC_VALUE_DICT: {
        nos::trent dict;
        dict.init(nos::trent_type::dict);
        for (size_t i = 0; i < v->data.dict.count; i++) {
            dict[v->data.dict.entries[i].key] =
                tc_value_to_trent(v->data.dict.entries[i].value);
        }
        return dict;
    }
    default:
        return nos::trent::nil();
    }
}

// py::object <-> trent (for backward compatibility)
inline nos::trent py_to_trent_compat(py::object obj) {
    tc_value v = py_to_tc_value(obj);
    nos::trent result = tc_value_to_trent(&v);
    tc_value_free(&v);
    return result;
}

inline py::object trent_to_py_compat(const nos::trent& t) {
    tc_value v = trent_to_tc_value(t);
    py::object result = tc_value_to_py(&v);
    tc_value_free(&v);
    return result;
}

#endif // TC_HAS_TRENT

} // namespace tc

// ============================================================================
// Macros (compatible with existing code)
// ============================================================================

#define INSPECT_FIELD(cls, field, label, kind, ...) \
    inline static ::tc::InspectFieldRegistrar<cls, decltype(cls::field)> \
        _inspect_reg_##field{&cls::field, #cls, #field, label, kind, ##__VA_ARGS__};

#define INSPECT_FIELD_CALLBACK(cls, type, name, label, kind, getter_fn, setter_fn) \
    inline static ::tc::InspectFieldCallbackRegistrar<cls, type> \
        _inspect_reg_##name{#cls, #name, label, kind, getter_fn, setter_fn};
