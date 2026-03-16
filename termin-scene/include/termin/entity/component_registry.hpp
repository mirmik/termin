#pragma once

#include <string>
#include <vector>
#include <type_traits>

#include "component.hpp"
#include "vtable_utils.hpp"
#include "tc_inspect_cpp.hpp"

#include <termin/export.hpp>

namespace termin {

class Drawable;

// Global registry for component types.
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
    bool is_a(const std::string& name, const std::string& base_name) const;

    // Listing
    std::vector<std::string> list_all() const;
    std::vector<std::string> list_native() const;
    std::vector<std::string> requirements_of(const std::string& name) const;

    // Clear all (for testing)
    void clear();

    void register_requirement(const std::string& name, const std::string& required_name);

    // Enable or disable a capability for a component type
    static void set_capability(const std::string& name, tc_component_cap_id cap_id, bool enabled);

    // Check whether a component type has a capability
    static bool has_capability(const std::string& name, tc_component_cap_id cap_id);

private:
    ComponentRegistry() = default;
    ComponentRegistry(const ComponentRegistry&) = delete;
    ComponentRegistry& operator=(const ComponentRegistry&) = delete;
};

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
    (void)name;
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
            nullptr,
            parent
        );

        // Register type parent for field inheritance
        if (parent) {
            tc::InspectRegistry::instance().set_type_parent(name, parent);
        }

        mark_drawable_if_base<T>(name);
    }
};

#define REGISTER_COMPONENT(ClassName, Parent) \
    static ::termin::ComponentRegistrar<ClassName> \
        _component_registrar_##ClassName(#ClassName, #Parent)

// Registration for abstract component types (no factory, can't be instantiated).
struct AbstractComponentRegistrar {
    AbstractComponentRegistrar(const char* name, const char* parent = nullptr) {
        ComponentRegistry::instance().register_abstract(name, parent);
        if (parent) {
            tc::InspectRegistry::instance().set_type_parent(name, parent);
        }
    }
};

struct ComponentRequirementRegistrar {
    ComponentRequirementRegistrar(const char* name, const char* required_name) {
        ComponentRegistry::instance().register_requirement(name, required_name);
    }
};

#define REGISTER_ABSTRACT_COMPONENT(ClassName, Parent) \
    static ::termin::AbstractComponentRegistrar \
        _component_registrar_##ClassName(#ClassName, #Parent)

#define REQUIRE_COMPONENT(ClassName, RequiredClassName) \
    static ::termin::ComponentRequirementRegistrar \
        _component_requirement_registrar_##ClassName##_##RequiredClassName( \
            #ClassName, #RequiredClassName)

} // namespace termin
