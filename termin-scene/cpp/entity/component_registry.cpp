#include <termin/entity/component_registry.hpp>
#include <termin/entity/component.hpp>
#include "core/tc_component.h"
#include "inspect/tc_runtime_type_registry.h"
#include <stdexcept>
#include <algorithm>
#include <memory>
#include <cstring>
#include <tcbase/tc_log.hpp>

namespace termin {

namespace {

constexpr const char* kComponentFacet = "termin.scene.component";

}

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

void ComponentRegistry::set_registration_owner(const std::string& owner) {
    tc_component_registry_set_registration_owner(owner.empty() ? nullptr : owner.c_str());
}

std::string ComponentRegistry::registration_owner() const {
    const char* owner = tc_component_registry_get_registration_owner();
    return owner ? std::string(owner) : std::string();
}

std::string ComponentRegistry::owner_of(const std::string& name) const {
    const char* owner = tc_runtime_type_registry_get_owner(name.c_str());
    return owner ? std::string(owner) : std::string();
}

std::vector<std::string> ComponentRegistry::list_owned(const std::string& owner) const {
    std::vector<std::string> result;
    if (owner.empty()) {
        return result;
    }

    struct Ctx {
        const std::string* owner;
        std::vector<std::string>* result;
    } ctx{&owner, &result};
    tc_runtime_type_registry_foreach_type_with_facet(
        kComponentFacet,
        [](const char* name, void* user_data) -> bool {
            auto* ctx = static_cast<Ctx*>(user_data);
            const char* current_owner = tc_runtime_type_registry_get_owner(name);
            if (current_owner && *ctx->owner == current_owner) {
                ctx->result->emplace_back(name);
            }
            return true;
        },
        &ctx);
    std::sort(result.begin(), result.end());
    return result;
}

size_t ComponentRegistry::unregister_owner(const std::string& owner) {
    if (owner.empty()) {
        return 0;
    }
    return tc_component_registry_unregister_owner(owner.c_str());
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

void ComponentRegistry::set_display_name(const std::string& name, const std::string& display_name) {
    tc_component_registry_set_display_name(name.c_str(), display_name.c_str());
}

std::string ComponentRegistry::display_name_of(const std::string& name) const {
    const char* display_name = tc_component_registry_get_display_name(name.c_str());
    return display_name ? std::string(display_name) : std::string();
}

void ComponentRegistry::set_category(const std::string& name, const std::string& category) {
    tc_component_registry_set_category(name.c_str(), category.c_str());
}

std::string ComponentRegistry::category_of(const std::string& name) const {
    const char* category = tc_component_registry_get_category(name.c_str());
    return category ? std::string(category) : std::string();
}

std::vector<std::string> ComponentRegistry::list_all() const {
    std::vector<std::string> result;
    tc_runtime_type_registry_foreach_type_with_facet(
        kComponentFacet,
        [](const char* name, void* user_data) -> bool {
            static_cast<std::vector<std::string>*>(user_data)->emplace_back(name);
            return true;
        },
        &result);
    std::sort(result.begin(), result.end());
    return result;
}

std::vector<std::string> ComponentRegistry::list_native() const {
    std::vector<std::string> result;
    tc_runtime_type_registry_foreach_type_with_facet(
        kComponentFacet,
        [](const char* name, void* user_data) -> bool {
            if (name && tc_component_registry_get_kind(name) == TC_CXX_COMPONENT) {
                static_cast<std::vector<std::string>*>(user_data)->emplace_back(name);
            }
            return true;
        },
        &result);
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
