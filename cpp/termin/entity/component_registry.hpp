#pragma once

#include <string>
#include <vector>
#include <type_traits>

#include "component.hpp"
#include "vtable_utils.hpp"
#include "input_handler.hpp"
#include "tc_inspect_cpp.hpp"

#include "../export.hpp"

namespace termin {

// Forward declarations for optional checks
class Drawable;

// Global registry for component types.
// This is a thin wrapper around the C registry (tc_component_registry).
// For Python component support, include component_registry_python.hpp
class ENTITY_API ComponentRegistry {
public:
    // Singleton access
    static ComponentRegistry& instance();

    // C++ component registration - registers directly in C registry
    void register_native(const std::string& name, tc_component_factory factory, void* userdata, const char* parent = nullptr);

    // Register abstract component (no factory, can't be instantiated)
    void register_abstract(const std::string& name, const char* parent = nullptr);

    // Unregistration (for hot-reload)
    void unregister(const std::string& name);

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
    ComponentRegistry() = default;
    ComponentRegistry(const ComponentRegistry&) = delete;
    ComponentRegistry& operator=(const ComponentRegistry&) = delete;
};

// SFINAE helpers for Drawable/InputHandler detection with incomplete types
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

// Factory data stored in static variables per template instantiation
template<typename T>
struct CxxComponentFactoryData {
    static bool has_update;
    static bool has_fixed_update;
    static bool initialized;

    static tc_component* create(void* /*userdata*/) {
        T* comp = new T();
        comp->set_has_update(has_update);
        comp->set_has_fixed_update(has_fixed_update);
        return comp->c_component();
    }
};

template<typename T> bool CxxComponentFactoryData<T>::has_update = false;
template<typename T> bool CxxComponentFactoryData<T>::has_fixed_update = false;
template<typename T> bool CxxComponentFactoryData<T>::initialized = false;

// Helper for static registration of C++ components.
// Used by REGISTER_COMPONENT macro.
template<typename T>
struct ComponentRegistrar {
    ComponentRegistrar(const char* name, const char* parent = nullptr) {
        // Initialize factory data once
        if (!CxxComponentFactoryData<T>::initialized) {
            CxxComponentFactoryData<T>::has_update = component_overrides_update<T>();
            CxxComponentFactoryData<T>::has_fixed_update = component_overrides_fixed_update<T>();
            CxxComponentFactoryData<T>::initialized = true;
        }

        // Register in C registry with static factory function
        ComponentRegistry::instance().register_native(
            name,
            &CxxComponentFactoryData<T>::create,
            nullptr,  // no userdata needed
            parent
        );

        // Register type parent for field inheritance
        if (parent) {
            tc::InspectRegistry::instance().set_type_parent(name, parent);
        }

        // Mark as drawable if component inherits from Drawable
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

// Registration for abstract component types (no factory, can't be instantiated).
// Used for base classes that define shared inspect fields for subclasses.
struct AbstractComponentRegistrar {
    AbstractComponentRegistrar(const char* name, const char* parent = nullptr) {
        ComponentRegistry::instance().register_abstract(name, parent);
        if (parent) {
            tc::InspectRegistry::instance().set_type_parent(name, parent);
        }
    }
};

#define REGISTER_ABSTRACT_COMPONENT(ClassName, Parent) \
    static ::termin::AbstractComponentRegistrar \
        _component_registrar_##ClassName(#ClassName, #Parent)

} // namespace termin
