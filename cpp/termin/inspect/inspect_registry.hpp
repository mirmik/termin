#pragma once

#include <string>
#include <vector>
#include <unordered_map>
#include <functional>
#include <iostream>
#include <pybind11/pybind11.h>
#include "../../trent/trent.h"

// DLL export/import macros for Windows
#ifdef _WIN32
    #ifdef ENTITY_LIB_EXPORTS
        #define ENTITY_API __declspec(dllexport)
    #else
        #define ENTITY_API __declspec(dllimport)
    #endif
#else
    #define ENTITY_API
#endif

namespace py = pybind11;

namespace termin {

class Component;  // Forward declaration

// Handler functions for a specific inspect field "kind".
// Modules register these to enable serialization of their types.
struct KindHandler {
    // Serialize py::object → trent (for saving)
    std::function<nos::trent(py::object)> serialize;

    // Deserialize trent → py::object (for loading)
    std::function<py::object(const nos::trent&)> deserialize;

    // Convert value for setter (e.g., from None to empty handle)
    std::function<py::object(py::object)> convert;
};

/**
 * Choice for enum fields: (value, label).
 */
struct EnumChoice {
    py::object value;
    std::string label;
};

/**
 * Metadata for an inspectable field.
 */
struct InspectFieldInfo {
    std::string type_name;
    std::string path;
    std::string label;
    std::string kind;  // "float", "int", "bool", "vec3", "color", "string", "enum"
    double min = 0.0;
    double max = 1.0;
    double step = 0.01;
    bool non_serializable = false;  // If true, field is not serialized
    std::vector<EnumChoice> choices;  // For enum fields
    py::object action;  // For button fields: callable(obj) -> None (default: null)

    // Type-erased getter/setter using void*
    std::function<py::object(void*)> getter;
    std::function<void(void*, py::object)> setter;
};

// Registry for inspectable fields.
// Stores field metadata and provides get/set access.
// Used by editor inspector to display and edit C++ object properties.
class ENTITY_API InspectRegistry {
    std::unordered_map<std::string, std::vector<InspectFieldInfo>> _fields;
    std::unordered_map<std::string, KindHandler> _kind_handlers;

public:
    static InspectRegistry& instance();

    /**
     * Register a field via member pointer.
     */
    template<typename C, typename T>
    void add(const char* type_name, T C::*member,
             const char* path, const char* label, const char* kind,
             double min = 0.0, double max = 1.0, double step = 0.01)
    {
        _fields[type_name].push_back({
            .type_name = type_name,
            .path = path,
            .label = label,
            .kind = kind,
            .min = min,
            .max = max,
            .step = step,
            .getter = [member](void* obj) -> py::object {
                auto& val = static_cast<C*>(obj)->*member;
                return py::cast(val);
            },
            .setter = [member, path](void* obj, py::object val) {
                try {
                    static_cast<C*>(obj)->*member = val.cast<T>();
                } catch (const std::exception& e) {
                    std::cerr << "[INSPECT setter error] path=" << path << " error=" << e.what() << std::endl;
                }
            }
        });
    }

    /**
     * Register a field with custom getter/setter functions.
     */
    template<typename C, typename T>
    void add_with_callbacks(
        const char* type_name,
        const char* path,
        const char* label,
        const char* kind,
        std::function<T&(C*)> getter,
        std::function<void(C*, const T&)> setter
    ) {
        _fields[type_name].push_back({
            .type_name = type_name,
            .path = path,
            .label = label,
            .kind = kind,
            .min = 0.0,
            .max = 1.0,
            .step = 0.01,
            .getter = [getter](void* obj) -> py::object {
                return py::cast(getter(static_cast<C*>(obj)));
            },
            .setter = [setter](void* obj, py::object val) {
                setter(static_cast<C*>(obj), val.cast<T>());
            }
        });
    }

    /**
     * Get all fields for a type (type's own fields only).
     */
    const std::vector<InspectFieldInfo>& fields(const std::string& type_name) const {
        static std::vector<InspectFieldInfo> empty;
        auto it = _fields.find(type_name);
        return it != _fields.end() ? it->second : empty;
    }

    /**
     * Get all fields for a type including inherited Component fields.
     * Returns combined vector (Component fields first, then type's own fields).
     */
    std::vector<InspectFieldInfo> all_fields(const std::string& type_name) const {
        std::vector<InspectFieldInfo> result;

        // Add Component base class fields first (if not querying Component itself)
        if (type_name != "Component") {
            auto base_it = _fields.find("Component");
            if (base_it != _fields.end()) {
                result.insert(result.end(), base_it->second.begin(), base_it->second.end());
            }
        }

        // Add type's own fields
        auto it = _fields.find(type_name);
        if (it != _fields.end()) {
            result.insert(result.end(), it->second.begin(), it->second.end());
        }

        return result;
    }

    /**
     * Get all registered type names.
     */
    std::vector<std::string> types() const {
        std::vector<std::string> result;
        for (const auto& [name, _] : _fields) {
            result.push_back(name);
        }
        return result;
    }

    /**
     * Register a kind handler for serialization/deserialization.
     * Modules call this to register their handle types.
     */
    void register_kind(const std::string& kind, KindHandler handler) {
        _kind_handlers[kind] = std::move(handler);
    }

    /**
     * Register fields from Python inspect_fields dict.
     * Called from Python __init_subclass__ to register component fields.
     *
     * @param type_name Component class name
     * @param fields_dict Python dict {field_name: InspectField}
     */
    void register_python_fields(const std::string& type_name, py::dict fields_dict);

private:
    // Helper to split path by '.'
    static std::vector<std::string> split_path(const std::string& path);

public:

    /**
     * Check if a kind handler is registered.
     */
    bool has_kind_handler(const std::string& kind) const {
        return _kind_handlers.find(kind) != _kind_handlers.end();
    }

    /**
     * Get kind handler (returns nullptr if not found).
     * For parameterized types like list[T], auto-generates handler.
     */
    const KindHandler* get_kind_handler(const std::string& kind) const {
        auto it = _kind_handlers.find(kind);
        if (it != _kind_handlers.end()) {
            return &it->second;
        }
        // Try to generate handler for parameterized type
        return const_cast<InspectRegistry*>(this)->try_generate_handler(kind);
    }

    /**
     * Parse parameterized kind like "list[T]" or "dict[K,V]".
     * Returns (container, element_type) or ("", kind) if not parameterized.
     */
    static std::pair<std::string, std::string> parse_kind(const std::string& kind) {
        size_t bracket_start = kind.find('[');
        if (bracket_start == std::string::npos) {
            return {"", kind};
        }
        size_t bracket_end = kind.rfind(']');
        if (bracket_end == std::string::npos || bracket_end <= bracket_start) {
            return {"", kind};
        }
        std::string container = kind.substr(0, bracket_start);
        std::string element = kind.substr(bracket_start + 1, bracket_end - bracket_start - 1);
        return {container, element};
    }

private:
    /**
     * Try to generate handler for parameterized type like list[T].
     * Caches generated handler for future use.
     */
    KindHandler* try_generate_handler(const std::string& kind) {
        auto [container, element] = parse_kind(kind);
        if (container.empty()) {
            return nullptr;
        }

        if (container == "list") {
            // Get element handler
            auto it = _kind_handlers.find(element);
            if (it == _kind_handlers.end()) {
                return nullptr;
            }

            // Generate list handler
            KindHandler list_handler;

            // Serialize: py::list → trent::list
            list_handler.serialize = [element, this](py::object obj) -> nos::trent {
                nos::trent result;
                result.init(nos::trent_type::list);
                if (obj.is_none()) return result;

                auto elem_it = _kind_handlers.find(element);
                if (elem_it == _kind_handlers.end()) return result;

                for (auto item : obj) {
                    py::object py_item = py::reinterpret_borrow<py::object>(item);
                    if (elem_it->second.serialize) {
                        result.push_back(elem_it->second.serialize(py_item));
                    } else {
                        result.push_back(py_to_trent(py_item));
                    }
                }
                return result;
            };

            // Deserialize: trent::list → py::list
            list_handler.deserialize = [element, this](const nos::trent& t) -> py::object {
                py::list result;
                if (!t.is_list()) return result;

                auto elem_it = _kind_handlers.find(element);
                if (elem_it == _kind_handlers.end()) return result;

                for (const auto& item : t.as_list()) {
                    if (elem_it->second.deserialize) {
                        result.append(elem_it->second.deserialize(item));
                    } else {
                        result.append(trent_to_py(item));
                    }
                }
                return result;
            };

            // Convert: ensure each element is properly converted
            list_handler.convert = [element, this](py::object value) -> py::object {
                if (value.is_none()) {
                    return py::list();
                }

                auto elem_it = _kind_handlers.find(element);
                if (elem_it == _kind_handlers.end() || !elem_it->second.convert) {
                    // No element converter, return as-is
                    return value;
                }

                py::list result;
                for (auto item : value) {
                    py::object py_item = py::reinterpret_borrow<py::object>(item);
                    result.append(elem_it->second.convert(py_item));
                }
                return result;
            };

            _kind_handlers[kind] = std::move(list_handler);
            return &_kind_handlers[kind];
        }

        return nullptr;
    }

public:

    /**
     * Get field value by path.
     */
    py::object get(void* obj, const std::string& type_name, const std::string& field_path) const {
        for (const auto& f : all_fields(type_name)) {
            if (f.path == field_path) {
                return f.getter(obj);
            }
        }
        throw py::attribute_error("Field not found: " + field_path);
    }

    /**
     * Set field value by path.
     * Converts value to the expected type based on field kind.
     */
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

    /**
     * Serialize all inspect fields to trent dict.
     */
    nos::trent serialize_all(void* obj, const std::string& type_name) const {
        nos::trent result;
        result.init(nos::trent_type::dict);

        for (const auto& f : all_fields(type_name)) {
            if (f.non_serializable) continue;
            py::object val = f.getter(obj);
            result[f.path] = py_to_trent_with_kind(val, f.kind);
        }
        return result;
    }

    /**
     * Deserialize all inspect fields from trent dict.
     */
    void deserialize_all(void* obj, const std::string& type_name, const nos::trent& data) {
        if (!data.is_dict()) return;

        auto flds = all_fields(type_name);
        for (const auto& f : flds) {
            if (f.non_serializable) continue;
            if (data.contains(f.path)) {
                const auto& field_data = data[f.path];
                // Skip nil values - don't overwrite default with None
                if (field_data.is_nil()) continue;
                py::object val = trent_to_py_with_kind(field_data, f.kind);
                f.setter(obj, val);
            }
        }
    }

    // ===== Utility functions for kind handlers =====

    static nos::trent py_to_trent(py::object obj) {
        if (obj.is_none()) {
            return nos::trent::nil();
        }
        if (py::isinstance<py::bool_>(obj)) {
            return nos::trent(obj.cast<bool>());
        }
        if (py::isinstance<py::int_>(obj)) {
            return nos::trent(static_cast<double>(obj.cast<int64_t>()));
        }
        if (py::isinstance<py::float_>(obj)) {
            return nos::trent(obj.cast<double>());
        }
        if (py::isinstance<py::str>(obj)) {
            return nos::trent(obj.cast<std::string>());
        }
        if (py::isinstance<py::list>(obj)) {
            nos::trent result;
            result.init(nos::trent_type::list);
            for (auto item : obj) {
                result.push_back(py_to_trent(py::reinterpret_borrow<py::object>(item)));
            }
            return result;
        }
        if (py::isinstance<py::dict>(obj)) {
            nos::trent result;
            result.init(nos::trent_type::dict);
            for (auto& item : obj.cast<py::dict>()) {
                std::string key = py::str(item.first).cast<std::string>();
                result[key] = py_to_trent(py::reinterpret_borrow<py::object>(item.second));
            }
            return result;
        }
        // Handle numpy arrays (common for vec3, etc.)
        if (py::hasattr(obj, "tolist")) {
            py::object as_list = obj.attr("tolist")();
            return py_to_trent(as_list);
        }
        return nos::trent::nil();
    }

    static nos::trent py_dict_to_trent(py::dict d) {
        nos::trent result;
        result.init(nos::trent_type::dict);
        for (auto& item : d) {
            std::string key = py::str(item.first).cast<std::string>();
            result[key] = py_to_trent(py::reinterpret_borrow<py::object>(item.second));
        }
        return result;
    }

    static py::dict trent_to_py_dict(const nos::trent& t) {
        py::dict result;
        if (!t.is_dict()) return result;
        for (const auto& [key, val] : t.as_dict()) {
            result[py::str(key)] = trent_to_py(val);
        }
        return result;
    }

    /**
     * Convert py value to correct type for field kind.
     * Used when setting values from editor - ensures proper type conversion.
     */
    static py::object convert_value_for_kind(py::object value, const std::string& kind);

    static nos::trent py_to_trent_with_kind(py::object obj, const std::string& kind);

    static nos::trent py_list_to_trent(py::list lst) {
        nos::trent result;
        result.init(nos::trent_type::list);
        for (auto item : lst) {
            result.push_back(py_to_trent(py::reinterpret_borrow<py::object>(item)));
        }
        return result;
    }

    static py::object trent_to_py_with_kind(const nos::trent& t, const std::string& kind);

    static py::object trent_to_py(const nos::trent& t) {
        switch (t.get_type()) {
            case nos::trent_type::nil:
                return py::none();
            case nos::trent_type::boolean:
                return py::bool_(t.as_bool());
            case nos::trent_type::numer: {
                double val = t.as_numer();
                if (val == static_cast<int64_t>(val)) {
                    return py::int_(static_cast<int64_t>(val));
                }
                return py::float_(val);
            }
            case nos::trent_type::string:
                return py::str(t.as_string());
            case nos::trent_type::list: {
                py::list result;
                for (const auto& item : t.as_list()) {
                    result.append(trent_to_py(item));
                }
                return result;
            }
            case nos::trent_type::dict: {
                py::dict result;
                for (const auto& [key, val] : t.as_dict()) {
                    result[py::str(key)] = trent_to_py(val);
                }
                return result;
            }
            default:
                return py::none();
        }
    }
};

/**
 * Helper for static registration.
 */
template<typename C, typename T>
struct InspectFieldRegistrar {
    InspectFieldRegistrar(T C::*member, const char* type_name,
                          const char* path, const char* label, const char* kind,
                          double min = 0.0, double max = 1.0, double step = 0.01) {
        InspectRegistry::instance().add<C, T>(type_name, member, path, label, kind, min, max, step);
    }
};

/**
 * Helper for callback-based registration.
 */
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

} // namespace termin

/**
 * Macro to register an inspectable field.
 *
 * Usage:
 *   class MyComponent : public Component {
 *   public:
 *       float speed = 1.0f;
 *       INSPECT_FIELD(MyComponent, speed, "Speed", "float", 0.0, 10.0)
 *   };
 */
#define INSPECT_FIELD(cls, field, label, kind, ...) \
    inline static ::termin::InspectFieldRegistrar<cls, decltype(cls::field)> \
        _inspect_reg_##field{&cls::field, #cls, #field, label, kind, ##__VA_ARGS__};

/**
 * Macro to register a field with custom getter/setter.
 *
 * Usage:
 *   INSPECT_FIELD_CALLBACK(MeshRenderer, MeshHandle, mesh, "Mesh", "mesh_handle",
 *       [](auto* self) -> MeshHandle& { return self->_mesh_handle; },
 *       [](auto* self, const MeshHandle& h) { self->set_mesh(h); })
 */
#define INSPECT_FIELD_CALLBACK(cls, type, name, label, kind, getter_fn, setter_fn) \
    inline static ::termin::InspectFieldCallbackRegistrar<cls, type> \
        _inspect_reg_##name{#cls, #name, label, kind, getter_fn, setter_fn};
