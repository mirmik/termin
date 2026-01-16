// tc_inspect.hpp - C++ wrapper for tc_inspect with nanobind support
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

#include "trent/trent.h"
// tc_kind.hpp has been moved to cpp/termin/inspect/
// Include via proper path from projects that need both C++ and Python kind support
#include "../../cpp/termin/inspect/tc_kind.hpp"
#include "../../cpp/termin/inspect/tc_inspect_cpp.hpp"

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

    case TC_VALUE_CUSTOM: {
        // Custom types need custom type handler to convert
        const tc_custom_type_handler* h = tc_custom_type_get(v->kind);
        if (h && h->serialize) {
            tc_value serialized = h->serialize(v);
            nb::object result = tc_value_to_nb(&serialized);
            tc_value_free(&serialized);
            return result;
        }
        return nb::none();
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
    bool is_serializable = true;   // Include in serialization
    bool is_inspectable = true;    // Show in inspector
    std::vector<EnumChoice> choices;
    nb::object action;

    // Which language backend owns this field
    TypeBackend backend = TypeBackend::Python;

    // Python getter/setter - for Python fields only
    std::function<nb::object(void*)> py_getter;
    std::function<void(void*, nb::object)> py_setter;

    // C++ getter/setter - for C++ fields only
    std::function<std::any(void*)> cpp_getter;
    std::function<void(void*, const std::any&)> cpp_setter;

    // Trent getter/setter - for SERIALIZABLE_FIELD (serialize-only, no inspector)
    // Returns/accepts trent directly, bypassing kind handlers
    std::function<nos::trent(void*)> trent_getter;
    std::function<void(void*, const nos::trent&)> trent_setter;
};

// ============================================================================
// Forward declarations for trent
// ============================================================================

tc_value trent_to_tc_value(const nos::trent& t);
nos::trent tc_value_to_trent(const tc_value* v);
nos::trent nb_to_trent_compat(nb::object obj);
nb::object trent_to_nb_compat(const nos::trent& t);

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
    #define TC_INSPECT_API __attribute__((visibility("default")))
#endif

class TC_INSPECT_API InspectRegistry {
    // Python-specific storage (for fields registered from Python)
    std::unordered_map<std::string, std::vector<InspectFieldInfo>> _py_fields;

    // Type backend registry
    std::unordered_map<std::string, TypeBackend> _type_backends;

    // Type inheritance (child -> parent)
    std::unordered_map<std::string, std::string> _type_parents;

    // Callback for generating Python handlers (set from nanobind module)
    std::function<KindHandler*(const std::string&)> _handler_generator;

public:
    // Singleton - defined in entity_lib to ensure single instance
    static InspectRegistry& instance();

    // ========================================================================
    // Kind handler access (delegates to KindRegistry)
    // ========================================================================

    bool has_kind_handler(const std::string& kind) const {
        return KindRegistry::instance().get(kind) != nullptr
            || tc_custom_type_exists(kind.c_str());
    }

    // Set callback for generating Python handlers (must be called from nanobind module)
    void set_handler_generator(std::function<KindHandler*(const std::string&)> gen) {
        _handler_generator = std::move(gen);
    }

    KindHandler* get_kind_handler(const std::string& kind) {
        auto* handler = KindRegistry::instance().get(kind);

        // Check if Python vtable exists, not just the kind itself
        if (handler && handler->has_python()) {
            return handler;
        }

        // Try to auto-generate Python handler via callback (runs in nanobind context)
        if (_handler_generator) {
            auto* generated = _handler_generator(kind);
            if (generated) return generated;
        }

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

    // Add a serializable-only field (for SERIALIZABLE_FIELD macro)
    void add_serializable_field(const std::string& type_name, InspectFieldInfo&& info) {
        _py_fields[type_name].push_back(std::move(info));
    }

    // Add a field with choices (for INSPECT_FIELD_CHOICES macro)
    void add_field_with_choices(const std::string& type_name, InspectFieldInfo&& info) {
        _py_fields[type_name].push_back(std::move(info));
        _type_backends[type_name] = TypeBackend::Cpp;
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
    // Field access (Python interop)
    // ========================================================================

    // Get field value as serialized dict (for inspector widgets)
    nb::object get(void* obj, const std::string& type_name, const std::string& field_path) const {
        for (const auto& f : all_fields(type_name)) {
            if (f.path == field_path) {
                if (f.py_getter) {
                    nb::object val = f.py_getter(obj);
                    // Serialize Python value to dict format
                    auto* handler = const_cast<InspectRegistry*>(this)->get_kind_handler(f.kind);
                    if (handler && handler->has_python()) {
                        return handler->python.serialize(val);
                    }
                    return val;
                }
                if (f.cpp_getter) {
                    std::any val = f.cpp_getter(obj);
                    // Serialize C++ value to trent, then convert to Python dict
                    nos::trent t = KindRegistry::instance().serialize_cpp(f.kind, val);
                    return trent_to_nb_compat(t);
                }
                throw nb::type_error(("No getter for field: " + field_path).c_str());
            }
        }
        throw nb::attribute_error(("Field not found: " + field_path).c_str());
    }

    // Set field value from serialized dict (from inspector widgets)
    void set(void* obj, const std::string& type_name, const std::string& field_path, nb::object value, tc_scene* scene = nullptr) {
        for (const auto& f : all_fields(type_name)) {
            if (f.path == field_path) {
                if (f.py_setter) {
                    // Deserialize dict to Python value
                    auto* handler = get_kind_handler(f.kind);
                    if (handler && handler->has_python()) {
                        nb::object deserialized = handler->python.deserialize(value);
                        f.py_setter(obj, deserialized);
                    } else {
                        f.py_setter(obj, value);
                    }
                    return;
                }
                if (f.cpp_setter) {
                    // Convert Python dict to trent, then deserialize to C++ value
                    nos::trent t = nb_to_trent_compat(value);
                    std::any val = KindRegistry::instance().deserialize_cpp(f.kind, t, scene);
                    if (val.has_value()) {
                        f.cpp_setter(obj, val);
                        return;
                    }
                    throw nb::type_error(("deserialize_cpp failed for kind: " + f.kind).c_str());
                }
                throw nb::type_error(("No setter for field: " + field_path).c_str());
            }
        }
        throw nb::attribute_error(("Field not found: " + field_path).c_str());
    }

    // ========================================================================
    // Serialization
    // ========================================================================

    nos::trent serialize_all(void* obj, const std::string& type_name) const {
        nos::trent result;
        result.init(nos::trent_type::dict);

        for (const auto& f : all_fields(type_name)) {
            if (!f.is_serializable) continue;

            // SERIALIZABLE_FIELD: direct trent getter/setter
            if (f.trent_getter) {
                nos::trent val = f.trent_getter(obj);
                if (!val.is_nil()) {
                    result[f.path] = val;
                }
                continue;
            }

            if (f.py_getter) {
                nb::object val = f.py_getter(obj);
                auto* handler = const_cast<InspectRegistry*>(this)->get_kind_handler(f.kind);
                if (handler && handler->has_python()) {
                    // Warn if py_getter returned a dict - likely means inspector
                    // set a dict instead of the proper type
                    if (nb::isinstance<nb::dict>(val)) {
                        tc_log(TC_LOG_WARN,
                            "[InspectRegistry] serialize_all: py_getter for '%s.%s' (kind=%s) "
                            "returned dict - inspector may have set wrong type",
                            type_name.c_str(), f.path.c_str(), f.kind.c_str());
                    }
                    nb::object serialized = handler->python.serialize(val);
                    result[f.path] = nb_to_trent_compat(serialized);
                } else {
                    result[f.path] = nb_to_trent_compat(val);
                }
            } else if (f.cpp_getter) {
                std::any val = f.cpp_getter(obj);
                nos::trent t = KindRegistry::instance().serialize_cpp(f.kind, val);
                result[f.path] = t;
            }
        }

        return result;
    }

    // Takes both raw C++ pointer (for cpp_setter) and nb::object (for py_setter)
    void deserialize_fields_of_cxx_component_over_python(void* ptr, nb::object obj, const std::string& type_name, const nb::dict& data, tc_scene* scene = nullptr) {
        for (const auto& f : all_fields(type_name)) {
            if (!f.is_serializable) continue;

            nb::str key(f.path.c_str());
            if (!data.contains(key)) {
                continue;
            }

            nb::object field_data = data[key];
            if (field_data.is_none()) continue;

            // SERIALIZABLE_FIELD: direct trent getter/setter (no kind handler)
            if (f.trent_setter) {
                nos::trent t = nb_to_trent_compat(field_data);
                f.trent_setter(ptr, t);
                continue;
            }

            if (f.backend == TypeBackend::Cpp) {
                if (!f.cpp_setter) {
                    tc_log_warn("deserialize %s.%s: no cpp_setter", type_name.c_str(), f.path.c_str());
                    continue;
                }

                // Deserialize via trent (handles both primitives and complex types)
                nos::trent t = nb_to_trent_compat(field_data);
                std::any val = KindRegistry::instance().deserialize_cpp(f.kind, t, scene);
                if (val.has_value()) {
                    try {
                        f.cpp_setter(ptr, val);
                    } catch (const std::bad_any_cast& e) {
                        tc_log_error("deserialize %s.%s (kind=%s): cpp_setter failed: %s",
                            type_name.c_str(), f.path.c_str(), f.kind.c_str(), e.what());
                    }
                } else {
                    tc_log_warn("deserialize %s.%s (kind=%s): deserialize_cpp failed",
                        type_name.c_str(), f.path.c_str(), f.kind.c_str());
                }
            } else {
                if (!f.py_setter) {
                    tc_log_warn("deserialize %s.%s: no py_setter", type_name.c_str(), f.path.c_str());
                    continue;
                }

                nb::object val;
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

    void deserialize_fields_of_python_component_over_python(nb::object obj, const std::string& type_name, const nb::dict& data) {
        for (const auto& f : all_fields(type_name)) {
            if (f.backend == TypeBackend::Cpp) {
                tc_log_warn("deserialize %s.%s (kind=%s): C++ backend field in Python component",
                    type_name.c_str(), f.path.c_str(), f.kind.c_str());
                continue;
            }

            if (!f.is_serializable) continue;

            nb::str key(f.path.c_str());
            if (!data.contains(key)) continue;

            nb::object field_data = data[key];
            if (field_data.is_none()) continue;

            if (!f.py_setter) {
                tc_log_warn("deserialize %s.%s (kind=%s): no py_setter",
                    type_name.c_str(), f.path.c_str(), f.kind.c_str());
                continue;
            }

            nb::object val;
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
    void deserialize_component_fields_over_python(void* ptr, nb::object obj, const std::string& type_name, const nb::dict& data, tc_scene* scene = nullptr) {
        if (get_type_backend(type_name) == TypeBackend::Cpp) {
            deserialize_fields_of_cxx_component_over_python(ptr, obj, type_name, data, scene);
        } else {
            deserialize_fields_of_python_component_over_python(obj, type_name, data);
        }
    }


    // Compatibility static methods
    static nb::object trent_to_py(const nos::trent& t) {
        return trent_to_nb_compat(t);
    }

    static nb::dict trent_to_py_dict(const nos::trent& t) {
        nb::object result = trent_to_nb_compat(t);
        if (nb::isinstance<nb::dict>(result)) {
            return nb::cast<nb::dict>(result);
        }
        return nb::dict();
    }

    static nos::trent py_to_trent(nb::object obj) {
        return nb_to_trent_compat(obj);
    }

    static nos::trent py_dict_to_trent(nb::dict d) {
        return nb_to_trent_compat(d);
    }

    static nos::trent py_list_to_trent(nb::list lst) {
        return nb_to_trent_compat(lst);
    }

};

// ============================================================================
// Static registration helpers (for C++ components)
// Uses new C API via tc_inspect_cpp.hpp
// ============================================================================

// Context for C++ field vtable (stores member pointer and kind for KindRegistry)
template<typename C, typename T>
struct CppFieldContext {
    T C::* member;
    std::string kind;
};

// Storage for C++ field contexts (must outlive vtable registrations)
class CppFieldContextStorage {
    std::vector<std::unique_ptr<void, void(*)(void*)>> contexts_;
public:
    static CppFieldContextStorage& instance() {
        static CppFieldContextStorage storage;
        return storage;
    }

    template<typename C, typename T>
    CppFieldContext<C, T>* store(T C::* member, const std::string& kind) {
        auto* ctx = new CppFieldContext<C, T>{member, kind};
        contexts_.emplace_back(ctx, [](void* p) { delete static_cast<CppFieldContext<C, T>*>(p); });
        return ctx;
    }
};

// Context for SERIALIZABLE_FIELD (stores trent getter/setter functions)
template<typename C>
struct SerializableFieldTrentContext {
    std::function<nos::trent(C*)> getter;
    std::function<void(C*, const nos::trent&)> setter;
};

// Storage for serializable field contexts
class SerializableFieldContextStorage {
    std::vector<std::unique_ptr<void, void(*)(void*)>> contexts_;
public:
    static SerializableFieldContextStorage& instance() {
        static SerializableFieldContextStorage storage;
        return storage;
    }

    template<typename C>
    SerializableFieldTrentContext<C>* store(
        std::function<nos::trent(C*)> getter,
        std::function<void(C*, const nos::trent&)> setter
    ) {
        auto* ctx = new SerializableFieldTrentContext<C>{std::move(getter), std::move(setter)};
        contexts_.emplace_back(ctx, [](void* p) { delete static_cast<SerializableFieldTrentContext<C>*>(p); });
        return ctx;
    }
};

// Getter for SERIALIZABLE_FIELD (uses trent getter → tc_value)
template<typename C>
static tc_value serializable_field_getter(void* obj, const tc_field_desc* field, void* user_data) {
    (void)field;
    auto* ctx = static_cast<SerializableFieldTrentContext<C>*>(user_data);
    C* instance = static_cast<C*>(obj);
    nos::trent t = ctx->getter(instance);
    return trent_to_tc_value(t);
}

// Setter for SERIALIZABLE_FIELD (uses tc_value → trent setter)
template<typename C>
static void serializable_field_setter(void* obj, const tc_field_desc* field, tc_value value, void* user_data) {
    (void)field;
    auto* ctx = static_cast<SerializableFieldTrentContext<C>*>(user_data);
    C* instance = static_cast<C*>(obj);
    nos::trent t = tc_value_to_trent(&value);
    ctx->setter(instance, t);
}

// Getter via KindRegistry (converts C++ value → trent → tc_value)
template<typename C, typename T>
static tc_value cpp_field_getter_via_kind(void* obj, const tc_field_desc* field, void* user_data) {
    (void)field;
    auto* ctx = static_cast<CppFieldContext<C, T>*>(user_data);
    C* instance = static_cast<C*>(obj);
    T& value = instance->*(ctx->member);

    // Serialize via KindRegistry
    nos::trent t = KindRegistry::instance().serialize_cpp(ctx->kind, value);
    return trent_to_tc_value(t);
}

// Setter via KindRegistry (converts tc_value → trent → C++ value)
template<typename C, typename T>
static void cpp_field_setter_via_kind(void* obj, const tc_field_desc* field, tc_value value, void* user_data) {
    (void)field;
    auto* ctx = static_cast<CppFieldContext<C, T>*>(user_data);
    C* instance = static_cast<C*>(obj);

    // Deserialize via KindRegistry
    nos::trent t = tc_value_to_trent(&value);
    std::any result = KindRegistry::instance().deserialize_cpp(ctx->kind, t, nullptr);
    if (result.has_value()) {
        try {
            instance->*(ctx->member) = std::any_cast<T>(result);
        } catch (const std::bad_any_cast& e) {
            tc_log_error("cpp_field_setter_via_kind: bad_any_cast for kind=%s: %s",
                ctx->kind.c_str(), e.what());
        }
    }
}

template<typename C, typename T>
struct InspectFieldRegistrar {
    InspectFieldRegistrar(T C::*member, const char* type_name,
                          const char* path, const char* label, const char* kind,
                          double min = 0.0, double max = 1.0, double step = 0.01) {
        // Use new API from tc_inspect_cpp.hpp
        InspectCpp::register_field<C, T>(type_name, member, path, label, kind, min, max, step);
        // Also register in legacy InspectRegistry for backward compatibility during migration
        InspectRegistry::instance().add<C, T>(type_name, member, path, label, kind, min, max, step);

        // Set up C++ vtable for C API access
        auto* ctx = CppFieldContextStorage::instance().store<C, T>(member, kind);

        tc_field_vtable vtable = {};
        vtable.get = cpp_field_getter_via_kind<C, T>;
        vtable.set = cpp_field_setter_via_kind<C, T>;
        vtable.user_data = ctx;

        tc_inspect_set_field_vtable(type_name, path, TC_INSPECT_LANG_CPP, &vtable);
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
        const char* kind,
        std::initializer_list<std::pair<const char*, const char*>> choices_list
    ) {
        InspectFieldInfo info;
        info.type_name = type_name;
        info.path = path;
        info.label = label;
        info.kind = kind;
        info.backend = TypeBackend::Cpp;

        // Convert choices to EnumChoice vector (store as strings, not nb::object)
        for (const auto& [value, choice_label] : choices_list) {
            EnumChoice choice;
            choice.value = value;
            choice.label = choice_label;
            info.choices.push_back(std::move(choice));
        }

        info.cpp_getter = [member](void* obj) -> std::any {
            return static_cast<C*>(obj)->*member;
        };

        info.cpp_setter = [member](void* obj, const std::any& val) {
            static_cast<C*>(obj)->*member = std::any_cast<T>(val);
        };

        InspectRegistry::instance().add_field_with_choices(type_name, std::move(info));
    }
};

// Registrar for SERIALIZABLE_FIELD (serialize-only fields with trent getter/setter)
template<typename C>
struct SerializableFieldRegistrar {
    SerializableFieldRegistrar(
        const char* type_name,
        const char* path,
        std::function<nos::trent(C*)> getter,
        std::function<void(C*, const nos::trent&)> setter
    ) {
        InspectFieldInfo info;
        info.type_name = type_name;
        info.path = path;
        info.label = "";
        info.kind = "";
        info.backend = TypeBackend::Cpp;
        info.is_inspectable = false;  // Not shown in inspector
        info.is_serializable = true;

        info.trent_getter = [getter](void* obj) -> nos::trent {
            return getter(static_cast<C*>(obj));
        };

        info.trent_setter = [setter](void* obj, const nos::trent& val) {
            setter(static_cast<C*>(obj), val);
        };

        // Access private member via friend-like workaround: add to _py_fields directly
        // Note: We need to add a method for this in InspectRegistry
        InspectRegistry::instance().add_serializable_field(type_name, std::move(info));

        // Also register with C API for tc_inspect_serialize/deserialize
        tc_field_desc desc = {};
        desc.path = path;
        desc.label = "";
        desc.kind = "";
        desc.is_serializable = true;
        desc.is_inspectable = false;
        tc_inspect_add_field(type_name, &desc);

        // Set up vtable for C API
        auto* ctx = SerializableFieldContextStorage::instance().store<C>(getter, setter);
        tc_field_vtable vtable = {};
        vtable.get = serializable_field_getter<C>;
        vtable.set = serializable_field_setter<C>;
        vtable.user_data = ctx;
        tc_inspect_set_field_vtable(type_name, path, TC_INSPECT_LANG_CPP, &vtable);
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

// nb::object <-> trent (for backward compatibility)
inline nos::trent nb_to_trent_compat(nb::object obj) {
    tc_value v = nb_to_tc_value(obj);
    nos::trent result = tc_value_to_trent(&v);
    tc_value_free(&v);
    return result;
}

inline nb::object trent_to_nb_compat(const nos::trent& t) {
    tc_value v = trent_to_tc_value(t);
    nb::object result = tc_value_to_nb(&v);
    tc_value_free(&v);
    return result;
}

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

// SERIALIZABLE_FIELD - serialize-only field with custom trent getter/setter
// Not shown in inspector, only used for serialization/deserialization
// Usage: SERIALIZABLE_FIELD(MyClass, field_key, get_data(), set_data(val))
//   - getter expression receives 'this' implicitly, returns nos::trent
//   - setter expression receives 'this' and 'val' (const nos::trent&)
#define SERIALIZABLE_FIELD(cls, name, getter_expr, setter_expr) \
    inline static ::tc::SerializableFieldRegistrar<cls> \
        _serialize_reg_##cls##_##name{#cls, #name, \
            [](cls* self) -> nos::trent { return self->getter_expr; }, \
            [](cls* self, const nos::trent& val) { self->setter_expr; }};

// INSPECT_FIELD_CHOICES - field with enum-like choices (variadic)
// Usage: INSPECT_FIELD_CHOICES(ColorPass, sort_mode, "Sort Mode", "string",
//            {"none", "None"}, {"near_to_far", "Near to Far"}, {"far_to_near", "Far to Near"})
#define INSPECT_FIELD_CHOICES(cls, field, label, kind, ...) \
    inline static ::tc::InspectFieldChoicesRegistrar<cls, decltype(cls::field)> \
        _inspect_reg_##cls##_##field{&cls::field, #cls, #field, label, kind, {__VA_ARGS__}};
