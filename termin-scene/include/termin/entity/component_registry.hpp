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

class ENTITY_API ComponentTypeDescriptorBuilder {
    tc_runtime_type_descriptor* _descriptor = nullptr;
    tc::InspectFacetBuilder _inspect;
    std::string _type_name;
    std::string _owner;
    tc_component_factory _factory = nullptr;
    void* _factory_userdata = nullptr;
    tc_component_kind _kind = TC_CXX_COMPONENT;
    bool _abstract = false;
    bool _valid = true;
    std::string _display_name;
    std::string _category;
    std::vector<std::string> _requirements;
    std::vector<tc_component_cap_id> _capabilities;

public:
    ComponentTypeDescriptorBuilder(
        const char* type_name,
        const char* owner,
        const char* parent,
        tc_component_factory factory,
        void* factory_userdata,
        tc_component_kind kind,
        bool is_abstract = false,
        bool allow_same_owner_replacement = false);
    ~ComponentTypeDescriptorBuilder();
    ComponentTypeDescriptorBuilder(const ComponentTypeDescriptorBuilder&) = delete;
    ComponentTypeDescriptorBuilder& operator=(const ComponentTypeDescriptorBuilder&) = delete;
    ComponentTypeDescriptorBuilder(ComponentTypeDescriptorBuilder&& other) noexcept;
    ComponentTypeDescriptorBuilder& operator=(ComponentTypeDescriptorBuilder&& other) noexcept;

    tc::InspectFacetBuilder& inspect() { return _inspect; }
    void set_inspect(tc::InspectFacetBuilder&& inspect) { _inspect = std::move(inspect); }
    ComponentTypeDescriptorBuilder& display_name(std::string value);
    ComponentTypeDescriptorBuilder& category(std::string value);
    ComponentTypeDescriptorBuilder& require(std::string type_name);
    ComponentTypeDescriptorBuilder& capability(tc_component_cap_id cap_id);
    bool commit();

    template<typename T>
    static ComponentTypeDescriptorBuilder native(
        const char* type_name,
        const char* owner,
        const char* parent = "CxxComponent"
    );

    static ComponentTypeDescriptorBuilder abstract_native(
        const char* type_name,
        const char* owner,
        const char* parent = nullptr) {
        return ComponentTypeDescriptorBuilder(
            type_name, owner, parent, nullptr, nullptr, TC_CXX_COMPONENT, true);
    }
};

// Global registry for component types.
class ENTITY_API ComponentRegistry {
public:
    // Singleton access
    static ComponentRegistry& instance();

    // Unregistration (for hot-reload)
    void unregister(const std::string& name);

    std::string owner_of(const std::string& name) const;
    std::vector<std::string> list_owned(const std::string& owner) const;
    size_t unregister_owner(const std::string& owner);

    // Queries
    bool has(const std::string& name) const;
    bool is_native(const std::string& name) const;
    bool is_a(const std::string& name, const std::string& base_name) const;
    std::string display_name_of(const std::string& name) const;
    std::string category_of(const std::string& name) const;

    // Listing
    std::vector<std::string> list_all() const;
    std::vector<std::string> list_native() const;
    std::vector<std::string> requirements_of(const std::string& name) const;

    // Clear all (for testing)
    void clear();

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

template<typename T>
ComponentTypeDescriptorBuilder ComponentTypeDescriptorBuilder::native(
    const char* type_name,
    const char* owner,
    const char* parent
) {
    if (!CxxComponentFactoryData<T>::initialized) {
        CxxComponentFactoryData<T>::has_update = component_overrides_update<T>();
        CxxComponentFactoryData<T>::has_fixed_update = component_overrides_fixed_update<T>();
        CxxComponentFactoryData<T>::initialized = true;
    }
    return ComponentTypeDescriptorBuilder(
        type_name,
        owner,
        parent,
        &CxxComponentFactoryData<T>::create,
        nullptr,
        TC_CXX_COMPONENT,
        false);
}

} // namespace termin
