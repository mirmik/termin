#pragma once

#include <string>
#include <unordered_map>
#include <functional>
#include <vector>
#include <type_traits>
#include <nanobind/nanobind.h>

#include "component.hpp"
#include "vtable_utils.hpp"
#include "input_handler.hpp"
#include "../../../core_c/include/tc_inspect.hpp"
#include "../render/drawable.hpp"

#include "../export.hpp"

namespace nb = nanobind;

namespace termin {

// Global registry for component types.
// Manages both C++ native components and Python components.
// - C++ components register via REGISTER_COMPONENT macro
// - Python components register via Component.__init_subclass__
class ENTITY_API ComponentRegistry {
public:
    // Factory function for C++ components
    using NativeFactory = std::function<CxxComponent*()>;

    struct ComponentInfo {
        std::string name;
        tc_component_kind kind;
        NativeFactory native_factory;  // For C++ components
        nb::object python_class;       // For Python components
    };

    // Singleton access
    static ComponentRegistry& instance();

    // Registration
    void register_native(const std::string& name, NativeFactory factory, const char* parent = nullptr);
    void register_python(const std::string& name, nb::object cls, const char* parent = nullptr);

    // Unregistration (for hot-reload)
    void unregister(const std::string& name);

    // Creation - returns nb::object (for Python compatibility)
    nb::object create(const std::string& name) const;

    // Creation - returns raw CxxComponent* (for Entity::deserialize)
    // Only works for native C++ components
    CxxComponent* create_component(const std::string& name) const;

    // Creation - returns tc_component* (unified API for any component type)
    // Works for both C++ and Python components
    tc_component* create_tc_component(const std::string& name) const;

    // Queries
    bool has(const std::string& name) const;
    const ComponentInfo* get_info(const std::string& name) const;
    nb::object get_class(const std::string& name) const;

    // Listing
    std::vector<std::string> list_all() const;
    std::vector<std::string> list_native() const;
    std::vector<std::string> list_python() const;

    // Clear all (for testing)
    void clear();

    // Mark a component type as drawable
    static void set_drawable(const std::string& name, bool is_drawable);

    // Mark a component type as input handler
    static void set_input_handler(const std::string& name, bool is_input_handler);

private:
    ComponentRegistry() = default;
    ComponentRegistry(const ComponentRegistry&) = delete;
    ComponentRegistry& operator=(const ComponentRegistry&) = delete;

    std::unordered_map<std::string, ComponentInfo> registry_;
};

/**
 * Helper for static registration of C++ components.
 * Used by REGISTER_COMPONENT macro.
 *
 * Detects method overrides via vtable inspection (see vtable_utils.hpp).
 * Detects drawable components via std::is_base_of<Drawable, T>.
 */
template<typename T>
struct ComponentRegistrar {
    ComponentRegistrar(const char* name, const char* parent = nullptr) {
        bool has_update = component_overrides_update<T>();
        bool has_fixed_update = component_overrides_fixed_update<T>();

        ComponentRegistry::instance().register_native(name,
            [name, has_update, has_fixed_update]() -> CxxComponent* {
                T* comp = new T();
                comp->set_type_name(name);
                comp->set_has_update(has_update);
                comp->set_has_fixed_update(has_fixed_update);
                return comp;
            },
            parent);

        // Register type parent for field inheritance
        if (parent) {
            tc::InspectRegistry::instance().set_type_parent(name, parent);
        }

        // Mark as drawable if component inherits from Drawable
        if constexpr (std::is_base_of_v<Drawable, T>) {
            ComponentRegistry::set_drawable(name, true);
        }

        // Mark as input handler if component inherits from InputHandler
        if constexpr (std::is_base_of_v<InputHandler, T>) {
            ComponentRegistry::set_input_handler(name, true);
        }
    }
};

/**
 * Macro for registering C++ components.
 * Place in header file after class definition.
 *
 * Usage:
 *   REGISTER_COMPONENT(MyComponent, Component);
 *   REGISTER_COMPONENT(ChildComponent, ParentComponent);
 */
#define REGISTER_COMPONENT(ClassName, Parent) \
    static ::termin::ComponentRegistrar<ClassName> \
        _component_registrar_##ClassName(#ClassName, #Parent)

} // namespace termin
