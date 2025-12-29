// tc_inspect.hpp - C++ wrapper for tc_inspect with pybind11 support
#pragma once

#include "tc_inspect.h"
#include "tc_log.h"
#include <pybind11/pybind11.h>
#include <pybind11/stl.h>
#include <string>
#include <vector>
#include <unordered_map>
#include <functional>
#include <any>

#include "trent/trent.h"
#include "tc_kind.hpp"

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

    // Which language backend owns this field
    TypeBackend backend = TypeBackend::Python;

    // Python getter/setter - for Python fields only
    std::function<py::object(void*)> py_getter;
    std::function<void(void*, py::object)> py_setter;

    // C++ getter/setter - for C++ fields only
    std::function<std::any(void*)> cpp_getter;
    std::function<void(void*, const std::any&)> cpp_setter;
};

// ============================================================================
// Forward declarations for trent
// ============================================================================

tc_value trent_to_tc_value(const nos::trent& t);
nos::trent tc_value_to_trent(const tc_value* v);
nos::trent py_to_trent_compat(py::object obj);
py::object trent_to_py_compat(const nos::trent& t);

// ============================================================================
// KindHandler - alias to TcKind from tc_kind.hpp
// ============================================================================

using KindHandler = TcKind;

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

    // Type vtables for Python types
    std::unordered_map<std::string, tc_type_vtable> _py_vtables;
    std::unordered_map<std::string, std::vector<tc_field_desc>> _py_field_descs;

    // Type backend registry
    std::unordered_map<std::string, TypeBackend> _type_backends;

    // Type inheritance (child -> parent)
    std::unordered_map<std::string, std::string> _type_parents;

public:
    // Singleton - defined in entity_lib to ensure single instance
    static InspectRegistry& instance();

    // ========================================================================
    // Kind handler access (delegates to KindRegistry)
    // ========================================================================

    bool has_kind_handler(const std::string& kind) const {
        return KindRegistry::instance().get(kind) != nullptr
            || tc_kind_exists(kind.c_str());
    }

    KindHandler* get_kind_handler(const std::string& kind) {
        auto* handler = KindRegistry::instance().get(kind);
        // Check if Python vtable exists, not just the kind itself
        if (handler && handler->has_python()) return handler;
        // Try to auto-generate Python handler for list[...] kinds
        auto* generated = try_generate_handler(kind);
        if (generated) return generated;
        // Return existing handler even without Python vtable (for C++ usage)
        return handler;
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
        _type_parents[type_name] = parent_name;
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
        info.backend = TypeBackend::Cpp;

        info.cpp_getter = [member](void* obj) -> std::any {
            return static_cast<C*>(obj)->*member;
        };

        info.cpp_setter = [member](void* obj, const std::any& val) {
            static_cast<C*>(obj)->*member = std::any_cast<T>(val);
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
        std::function<T&(C*)> getter_fn,
        std::function<void(C*, const T&)> setter_fn
    ) {
        InspectFieldInfo info;
        info.type_name = type_name;
        info.path = path;
        info.label = label;
        info.kind = kind;
        info.backend = TypeBackend::Cpp;

        info.cpp_getter = [getter_fn](void* obj) -> std::any {
            return getter_fn(static_cast<C*>(obj));
        };

        info.cpp_setter = [setter_fn](void* obj, const std::any& val) {
            setter_fn(static_cast<C*>(obj), std::any_cast<T>(val));
        };

        _py_fields[type_name].push_back(std::move(info));
        _type_backends[type_name] = TypeBackend::Cpp;
    }

    // Version with value getters (for accessor methods)
    template<typename C, typename T>
    void add_with_accessors(
        const char* type_name,
        const char* path,
        const char* label,
        const char* kind,
        std::function<T(C*)> getter_fn,
        std::function<void(C*, T)> setter_fn
    ) {
        InspectFieldInfo info;
        info.type_name = type_name;
        info.path = path;
        info.label = label;
        info.kind = kind;
        info.backend = TypeBackend::Cpp;

        info.cpp_getter = [getter_fn](void* obj) -> std::any {
            return getter_fn(static_cast<C*>(obj));
        };

        info.cpp_setter = [setter_fn](void* obj, const std::any& val) {
            setter_fn(static_cast<C*>(obj), std::any_cast<T>(val));
        };

        _py_fields[type_name].push_back(std::move(info));
        _type_backends[type_name] = TypeBackend::Cpp;
    }

    // Version for handle types with deserialize_from (C++ inplace deserialization)
    template<typename C, typename H>
    void add_handle(
        const char* type_name, H C::*member,
        const char* path, const char* label, const char* kind
    ) {
        InspectFieldInfo info;
        info.type_name = type_name;
        info.path = path;
        info.label = label;
        info.kind = kind;
        info.backend = TypeBackend::Cpp;

        info.cpp_getter = [member](void* obj) -> std::any {
            return static_cast<C*>(obj)->*member;
        };

        info.cpp_setter = [member](void* obj, const std::any& val) {
            static_cast<C*>(obj)->*member = std::any_cast<H>(val);
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

        // Add parent fields first (recursively)
        std::string parent = get_type_parent(type_name);
        if (!parent.empty()) {
            auto parent_fields = all_fields(parent);
            result.insert(result.end(), parent_fields.begin(), parent_fields.end());
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
    // Builtin type conversion helpers
    // ========================================================================

    // Convert std::any to py::object for builtin types
    // Returns py::none() if not a builtin type (caller should use KindRegistry)
    static py::object any_to_py_builtin(const std::any& val) {
        if (auto* v = std::any_cast<bool>(&val)) return py::cast(*v);
        if (auto* v = std::any_cast<int>(&val)) return py::cast(*v);
        if (auto* v = std::any_cast<int64_t>(&val)) return py::cast(*v);
        if (auto* v = std::any_cast<float>(&val)) return py::cast(*v);
        if (auto* v = std::any_cast<double>(&val)) return py::cast(*v);
        if (auto* v = std::any_cast<std::string>(&val)) return py::cast(*v);
        return py::none();
    }

    // Convert py::object to std::any for builtin types based on kind
    // Returns empty std::any if not a builtin kind (caller should use KindRegistry)
    static std::any py_to_any_builtin(py::object value, const std::string& kind) {
        if (kind == "bool" || kind == "checkbox") {
            return value.cast<bool>();
        }
        if (kind == "int" || kind == "slider_int") {
            return value.cast<int>();
        }
        if (kind == "float" || kind == "slider" || kind == "drag_float") {
            return value.cast<float>();
        }
        if (kind == "double") {
            return value.cast<double>();
        }
        if (kind == "string" || kind == "text" || kind == "multiline_text") {
            return value.cast<std::string>();
        }
        return std::any{};
    }

    // Check if kind is a builtin type
    static bool is_builtin_kind(const std::string& kind) {
        return kind == "bool" || kind == "checkbox" ||
               kind == "int" || kind == "slider_int" ||
               kind == "float" || kind == "slider" || kind == "drag_float" ||
               kind == "double" ||
               kind == "string" || kind == "text" || kind == "multiline_text";
    }

    // ========================================================================
    // Field access (Python interop - converts C++ fields via py::cast)
    // ========================================================================

    py::object get(void* obj, const std::string& type_name, const std::string& field_path) const {
        for (const auto& f : all_fields(type_name)) {
            if (f.path == field_path) {
                if (f.py_getter) {
                    return f.py_getter(obj);
                }
                // C++ field - get via cpp_getter
                if (f.cpp_getter) {
                    std::any val = f.cpp_getter(obj);
                    // Try builtin types first
                    py::object result = any_to_py_builtin(val);
                    if (!result.is_none()) {
                        return result;
                    }
                    // Custom kinds - use to_python handler
                    result = KindRegistry::instance().to_python_cpp(f.kind, val);
                    if (!result.is_none()) {
                        return result;
                    }
                    // Fallback: serialize to trent and convert (returns dict, not object!)
                    tc_log_warn("get %s.%s (kind=%s): no to_python handler, returning dict",
                        type_name.c_str(), field_path.c_str(), f.kind.c_str());
                    nos::trent t = KindRegistry::instance().serialize_cpp(f.kind, val);
                    return trent_to_py_compat(t);
                }
                throw py::type_error("No getter for field: " + field_path);
            }
        }
        throw py::attribute_error("Field not found: " + field_path);
    }

    void set(void* obj, const std::string& type_name, const std::string& field_path, py::object value) {
        for (const auto& f : all_fields(type_name)) {
            if (f.path == field_path) {
                if (f.py_setter) {
                    py::object converted = convert_value_for_kind(value, f.kind);
                    f.py_setter(obj, converted);
                    return;
                }
                // C++ field - set via cpp_setter
                if (f.cpp_setter) {
                    // Try builtin types first
                    std::any val = py_to_any_builtin(value, f.kind);
                    if (val.has_value()) {
                        f.cpp_setter(obj, val);
                        return;
                    }
                    // Custom kinds - use KindRegistry
                    nos::trent t = py_to_trent_compat(value);
                    val = KindRegistry::instance().deserialize_cpp(f.kind, t);
                    if (val.has_value()) {
                        f.cpp_setter(obj, val);
                    }
                    return;
                }
                throw py::type_error("No setter for field: " + field_path);
            }
        }
        throw py::attribute_error("Field not found: " + field_path);
    }

    // ========================================================================
    // Value conversion
    // ========================================================================

    py::object convert_value_for_kind(py::object value, const std::string& kind) {
        auto* handler = get_kind_handler(kind);
        if (handler && handler->has_python()) {
            return handler->python.convert(value);
        }
        return value;
    }

    // ========================================================================
    // Serialization
    // ========================================================================

    // Convert std::any to trent for builtin types
    // Returns nil trent if not a builtin type
    static nos::trent any_to_trent_builtin(const std::any& val) {
        if (auto* v = std::any_cast<bool>(&val)) return nos::trent(*v);
        if (auto* v = std::any_cast<int>(&val)) return nos::trent(static_cast<int64_t>(*v));
        if (auto* v = std::any_cast<int64_t>(&val)) return nos::trent(*v);
        if (auto* v = std::any_cast<float>(&val)) return nos::trent(static_cast<double>(*v));
        if (auto* v = std::any_cast<double>(&val)) return nos::trent(*v);
        if (auto* v = std::any_cast<std::string>(&val)) return nos::trent(*v);
        return nos::trent::nil();
    }

    nos::trent serialize_all(void* obj, const std::string& type_name) const {
        nos::trent result;
        result.init(nos::trent_type::dict);

        for (const auto& f : all_fields(type_name)) {
            if (f.non_serializable) continue;

            if (f.py_getter) {
                // Python field
                py::object val = f.py_getter(obj);
                auto* handler = const_cast<InspectRegistry*>(this)->get_kind_handler(f.kind);
                if (handler && handler->has_python()) {
                    py::object serialized = handler->python.serialize(val);
                    result[f.path] = py_to_trent_compat(serialized);
                } else {
                    result[f.path] = py_to_trent_compat(val);
                }
            } else if (f.cpp_getter) {
                // C++ field
                std::any val = f.cpp_getter(obj);
                // Try builtin types first
                nos::trent t = any_to_trent_builtin(val);
                if (!t.is_nil()) {
                    result[f.path] = t;
                    continue;
                }
                // Custom kinds - use KindRegistry
                t = KindRegistry::instance().serialize_cpp(f.kind, val);
                result[f.path] = t;
            }
        }
        return result;
    }

    // Takes both raw C++ pointer (for cpp_setter) and py::object (for py_setter)
    void deserialize_fields_of_cxx_component_over_python(void* ptr, py::object obj, const std::string& type_name, const py::dict& data) {

        for (const auto& f : all_fields(type_name)) {
            if (f.non_serializable) continue;

            py::str key(f.path);
            if (!data.contains(key)) continue;

            py::object field_data = data[key];
            if (field_data.is_none()) continue;

            if (f.backend == TypeBackend::Cpp) {
                // C++ field: py::object → std::any → cpp_setter
                if (!f.cpp_setter) {
                    tc_log_warn("deserialize %s.%s (kind=%s, backend=Cpp): no cpp_setter",
                        type_name.c_str(), f.path.c_str(), f.kind.c_str());
                    continue;
                }

                // Try builtin types first
                std::any val = py_to_any_builtin(field_data, f.kind);
                if (val.has_value()) {
                    f.cpp_setter(ptr, val);
                    continue;
                }

                // Custom kinds - use KindRegistry
                nos::trent t = py_to_trent_compat(field_data);
                val = KindRegistry::instance().deserialize_cpp(f.kind, t);
                if (val.has_value()) {
                    f.cpp_setter(ptr, val);
                } else {
                    tc_log_warn("deserialize %s.%s (kind=%s): no cpp handler, value not set",
                        type_name.c_str(), f.path.c_str(), f.kind.c_str());
                }
            } else {
                // Python field
                if (!f.py_setter) {
                    tc_log_warn("deserialize %s.%s (kind=%s, backend=Python): no py_setter",
                        type_name.c_str(), f.path.c_str(), f.kind.c_str());
                    continue;
                }

                py::object val;
                auto* handler = get_kind_handler(f.kind);
                if (handler && handler->has_python()) {
                    val = handler->python.deserialize(field_data);
                } else {
                    val = field_data;
                }
                f.py_setter(obj.ptr(), val);
            }
        }
    }

    void deserialize_fields_of_python_component_over_python(py::object obj, const std::string& type_name, const py::dict& data) {
        for (const auto& f : all_fields(type_name)) {
            if (f.backend == TypeBackend::Cpp) {
                tc_log_warn("deserialize %s.%s (kind=%s): C++ backend field in Python component",
                    type_name.c_str(), f.path.c_str(), f.kind.c_str());
                continue;
            }

            if (f.non_serializable) continue;

            py::str key(f.path);
            if (!data.contains(key)) continue;

            py::object field_data = data[key];
            if (field_data.is_none()) continue;

            if (!f.py_setter) {
                tc_log_warn("deserialize %s.%s (kind=%s): no py_setter",
                    type_name.c_str(), f.path.c_str(), f.kind.c_str());
                continue;
            }

            py::object val;

            auto* handler = get_kind_handler(f.kind);
            if (handler && handler->has_python()) {
                val = handler->python.deserialize(field_data);
            } else {
                val = field_data;
            }

            f.py_setter(obj.ptr(), val);
        }
    }

    // Dispatches based on type backend
    // For C++ components: ptr is the actual C++ object pointer (e.g. this)
    // For Python components: ptr is unused, obj.ptr() is used for setters
    void deserialize_component_fields_over_python(void* ptr, py::object obj, const std::string& type_name, const py::dict& data) {
        if (get_type_backend(type_name) == TypeBackend::Cpp) {
            deserialize_fields_of_cxx_component_over_python(ptr, obj, type_name, data);
        } else {
            deserialize_fields_of_python_component_over_python(obj, type_name, data);
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

private:
    // Defined in tc_inspect_instance.cpp to ensure single DLL allocation
    KindHandler* try_generate_handler(const std::string& kind);
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
// Trent compatibility functions
// ============================================================================

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
