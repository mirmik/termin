#pragma once

#include <string>
#include <unordered_map>
#include <functional>
#include <vector>
#include <pybind11/pybind11.h>

namespace py = pybind11;

namespace termin {

class Component;

/**
 * Global registry for component types.
 *
 * Manages both C++ native components and Python components.
 * - C++ components register via REGISTER_COMPONENT macro
 * - Python components register via Component.__init_subclass__
 */
class ComponentRegistry {
public:
    // Factory function for C++ components
    using NativeFactory = std::function<Component*()>;

    struct ComponentInfo {
        std::string name;
        bool is_native;
        NativeFactory native_factory;  // For C++ components
        py::object python_class;       // For Python components
    };

    // Singleton access
    static ComponentRegistry& instance();

    // Registration
    void register_native(const std::string& name, NativeFactory factory);
    void register_python(const std::string& name, py::object cls);

    // Unregistration (for hot-reload)
    void unregister(const std::string& name);

    // Creation
    py::object create(const std::string& name) const;

    // Queries
    bool has(const std::string& name) const;
    const ComponentInfo* get_info(const std::string& name) const;

    // Listing
    std::vector<std::string> list_all() const;
    std::vector<std::string> list_native() const;
    std::vector<std::string> list_python() const;

    // Clear all (for testing)
    void clear();

private:
    ComponentRegistry() = default;
    ComponentRegistry(const ComponentRegistry&) = delete;
    ComponentRegistry& operator=(const ComponentRegistry&) = delete;

    std::unordered_map<std::string, ComponentInfo> registry_;
};

/**
 * Helper for static registration of C++ components.
 * Used by REGISTER_COMPONENT macro.
 */
template<typename T>
struct ComponentRegistrar {
    explicit ComponentRegistrar(const char* name) {
        ComponentRegistry::instance().register_native(name, []() -> Component* {
            return new T();
        });
    }
};

/**
 * Macro for registering C++ components.
 * Place in .cpp file after class definition.
 *
 * Usage:
 *   REGISTER_COMPONENT(MyComponent);
 */
#define REGISTER_COMPONENT(ClassName) \
    static ::termin::ComponentRegistrar<ClassName> \
        _component_registrar_##ClassName(#ClassName)

} // namespace termin
