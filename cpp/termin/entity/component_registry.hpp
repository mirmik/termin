#pragma once

#include <string>
#include <unordered_map>
#include <functional>
#include <vector>
#include <type_traits>

#include "component.hpp"
#include "vtable_utils.hpp"
#include "input_handler.hpp"
#include "../../../core_c/include/tc_inspect_cpp.hpp"

#include "../export.hpp"

namespace termin {

// Forward declarations for optional checks
class Drawable;

// Global registry for component types.
// This header provides C++ component registration without nanobind dependency.
// For Python component support, include component_registry_python.hpp
class ENTITY_API ComponentRegistry {
public:
    // Unified factory function - returns tc_component* regardless of language
    using TcFactory = std::function<tc_component*()>;

    // Singleton access
    static ComponentRegistry& instance();

    // C++ component registration
    void register_native(const std::string& name, TcFactory factory, const char* parent = nullptr);

    // Unregistration (for hot-reload)
    void unregister(const std::string& name);

    // Unified creation - returns tc_component* for any component type
    tc_component* create(const std::string& name) const;

    // Queries
    bool has(const std::string& name) const;
    bool is_native(const std::string& name) const;

    // Listing
    std::vector<std::string> list_all() const;
    std::vector<std::string> list_native() const;

    // Clear all (for testing)
    void clear();

    // Mark a component type as drawable
    static void set_drawable(const std::string& name, bool is_drawable);

    // Mark a component type as input handler
    static void set_input_handler(const std::string& name, bool is_input_handler);

private:
    friend class ComponentRegistryPython;

    struct ComponentInfo {
        std::string name;
        tc_component_kind kind;
        TcFactory factory;  // Unified factory returning tc_component*
    };

    ComponentRegistry() = default;
    ComponentRegistry(const ComponentRegistry&) = delete;
    ComponentRegistry& operator=(const ComponentRegistry&) = delete;

    std::unordered_map<std::string, ComponentInfo> registry_;
};

// SFINAE helpers for Drawable/InputHandler detection with incomplete types
// These return false if the base class is incomplete
namespace detail {
    template<typename Base, typename Derived, typename = void>
    struct is_base_of_safe : std::false_type {};

    template<typename Base, typename Derived>
    struct is_base_of_safe<Base, Derived,
        std::enable_if_t<sizeof(Base) != 0 && std::is_base_of_v<Base, Derived>>>
        : std::true_type {};
}

template<typename T>
void mark_drawable_if_base(const char* name) {
    if constexpr (detail::is_base_of_safe<Drawable, T>::value) {
        ComponentRegistry::set_drawable(name, true);
    }
}

template<typename T>
void mark_input_handler_if_base(const char* name) {
    if constexpr (detail::is_base_of_safe<InputHandler, T>::value) {
        ComponentRegistry::set_input_handler(name, true);
    }
}

// Helper for static registration of C++ components.
// Used by REGISTER_COMPONENT macro.
//
// Detects method overrides via vtable inspection (see vtable_utils.hpp).
// Detects drawable components via std::is_base_of<Drawable, T>.
template<typename T>
struct ComponentRegistrar {
    ComponentRegistrar(const char* name, const char* parent = nullptr) {
        bool has_update = component_overrides_update<T>();
        bool has_fixed_update = component_overrides_fixed_update<T>();
        printf("[ComponentRegistrar] %s: has_update=%d, has_fixed_update=%d\n",
            name, has_update ? 1 : 0, has_fixed_update ? 1 : 0);

        ComponentRegistry::instance().register_native(name,
            [name, has_update, has_fixed_update]() -> tc_component* {
                printf("[Factory] Creating %s sizeof(tc_component)=%zu sizeof(T)=%zu offsetof(_c)=%zu\n",
                    name, sizeof(tc_component), sizeof(T), offsetof(T, _c));
                T* comp = new T();
                printf("[Factory] comp=%p comp->c_component()=%p diff=%td\n",
                    (void*)comp, (void*)comp->c_component(),
                    (char*)comp->c_component() - (char*)comp);
                comp->set_type_name(name);
                comp->set_has_update(has_update);
                comp->set_has_fixed_update(has_fixed_update);
                return comp->c_component();
            },
            parent);

        // Register type parent for field inheritance
        if (parent) {
            tc::InspectRegistry::instance().set_type_parent(name, parent);
        }

        // Mark as drawable if component inherits from Drawable
        // Note: requires Drawable to be complete (include drawable.hpp)
        // For external modules without drawable.hpp, this check is skipped
        mark_drawable_if_base<T>(name);

        // Mark as input handler if component inherits from InputHandler
        mark_input_handler_if_base<T>(name);
    }
};

// Macro for registering C++ components.
// Place in header file after class definition.
//
// Usage:
//   REGISTER_COMPONENT(MyComponent, Component);
//   REGISTER_COMPONENT(ChildComponent, ParentComponent);
#define REGISTER_COMPONENT(ClassName, Parent) \
    static ::termin::ComponentRegistrar<ClassName> \
        _component_registrar_##ClassName(#ClassName, #Parent)

} // namespace termin
