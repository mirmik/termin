#include <termin/entity/component_registry.hpp>
#include <termin/entity/component.hpp>
#include "core/tc_component.h"
#include <stdexcept>
#include <algorithm>
#include <memory>
#include <cstring>
#include <tcbase/tc_log.hpp>

namespace termin {

// ============================================================================
// ComponentRegistry implementation
// ============================================================================

ComponentRegistry& ComponentRegistry::instance() {
    static ComponentRegistry inst;
    return inst;
}

void ComponentRegistry::register_native(const std::string& name, tc_component_factory factory, void* userdata, const char* parent) {
    tc_component_registry_register_with_parent(name.c_str(), factory, userdata, TC_CXX_COMPONENT, parent);
}

void ComponentRegistry::register_abstract(const std::string& name, const char* parent) {
    tc_component_registry_register_abstract(name.c_str(), TC_CXX_COMPONENT, parent);
}

void ComponentRegistry::unregister(const std::string& name) {
    tc_component_registry_unregister(name.c_str());
}

bool ComponentRegistry::has(const std::string& name) const {
    return tc_component_registry_has(name.c_str());
}

bool ComponentRegistry::is_native(const std::string& name) const {
    return tc_component_registry_get_kind(name.c_str()) == TC_CXX_COMPONENT;
}

bool ComponentRegistry::is_a(const std::string& name, const std::string& base_name) const {
    return tc_component_registry_is_a(name.c_str(), base_name.c_str());
}

std::vector<std::string> ComponentRegistry::list_all() const {
    std::vector<std::string> result;
    size_t count = tc_component_registry_type_count();
    result.reserve(count);
    for (size_t i = 0; i < count; i++) {
        const char* name = tc_component_registry_type_at(i);
        if (name) {
            result.push_back(name);
        }
    }
    std::sort(result.begin(), result.end());
    return result;
}

std::vector<std::string> ComponentRegistry::list_native() const {
    std::vector<std::string> result;
    size_t count = tc_component_registry_type_count();
    for (size_t i = 0; i < count; i++) {
        const char* name = tc_component_registry_type_at(i);
        if (name && tc_component_registry_get_kind(name) == TC_CXX_COMPONENT) {
            result.push_back(name);
        }
    }
    std::sort(result.begin(), result.end());
    return result;
}

std::vector<std::string> ComponentRegistry::requirements_of(const std::string& name) const {
    std::vector<std::string> result;
    size_t count = tc_component_registry_requirement_count(name.c_str());
    result.reserve(count);
    for (size_t i = 0; i < count; ++i) {
        const char* required = tc_component_registry_requirement_at(name.c_str(), i);
        if (required) {
            result.emplace_back(required);
        }
    }
    return result;
}

void ComponentRegistry::clear() {
}

void ComponentRegistry::register_requirement(const std::string& name, const std::string& required_name) {
    tc_component_registry_add_requirement(name.c_str(), required_name.c_str());
}

void ComponentRegistry::set_capability(const std::string& name, tc_component_cap_id cap_id, bool enabled) {
    tc_component_registry_set_capability(name.c_str(), cap_id, enabled);
}

bool ComponentRegistry::has_capability(const std::string& name, tc_component_cap_id cap_id) {
    return tc_component_registry_has_capability(name.c_str(), cap_id);
}

} // namespace termin
