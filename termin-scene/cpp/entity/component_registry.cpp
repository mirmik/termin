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

void ComponentRegistry::clear() {
}

void ComponentRegistry::set_drawable(const std::string& name, bool is_drawable) {
    tc_component_registry_set_drawable(name.c_str(), is_drawable);
}

void ComponentRegistry::set_input_handler(const std::string& name, bool is_input_handler) {
    tc_component_registry_set_input_handler(name.c_str(), is_input_handler);
}

} // namespace termin
