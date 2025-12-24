#pragma once

#include <string>
#include <vector>
#include <unordered_map>
#include <functional>
#include <pybind11/pybind11.h>

namespace py = pybind11;

namespace termin {

/**
 * Metadata for an inspectable field.
 */
struct InspectFieldInfo {
    std::string type_name;
    std::string path;
    std::string label;
    std::string kind;  // "float", "int", "bool", "vec3", "color", "string"
    double min = 0.0;
    double max = 1.0;
    double step = 0.01;

    // Type-erased getter/setter using void*
    std::function<py::object(void*)> getter;
    std::function<void(void*, py::object)> setter;
};

/**
 * Registry for inspectable fields.
 *
 * Stores field metadata and provides get/set access.
 * Used by editor inspector to display and edit C++ object properties.
 */
class InspectRegistry {
    std::unordered_map<std::string, std::vector<InspectFieldInfo>> _fields;

public:
    static InspectRegistry& instance() {
        static InspectRegistry reg;
        return reg;
    }

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
                return py::cast(static_cast<C*>(obj)->*member);
            },
            .setter = [member](void* obj, py::object val) {
                static_cast<C*>(obj)->*member = val.cast<T>();
            }
        });
    }

    /**
     * Get all fields for a type.
     */
    const std::vector<InspectFieldInfo>& fields(const std::string& type_name) const {
        static std::vector<InspectFieldInfo> empty;
        auto it = _fields.find(type_name);
        return it != _fields.end() ? it->second : empty;
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
     * Get field value by path.
     */
    py::object get(void* obj, const std::string& type_name, const std::string& field_path) const {
        for (const auto& f : fields(type_name)) {
            if (f.path == field_path) {
                return f.getter(obj);
            }
        }
        throw py::attribute_error("Field not found: " + field_path);
    }

    /**
     * Set field value by path.
     */
    void set(void* obj, const std::string& type_name, const std::string& field_path, py::object value) {
        for (const auto& f : fields(type_name)) {
            if (f.path == field_path) {
                f.setter(obj, value);
                return;
            }
        }
        throw py::attribute_error("Field not found: " + field_path);
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
