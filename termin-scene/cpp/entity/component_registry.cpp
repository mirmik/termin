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

ComponentTypeDescriptorBuilder::ComponentTypeDescriptorBuilder(
    const char* type_name,
    const char* owner,
    const char* parent,
    tc_component_factory factory,
    void* factory_userdata,
    tc_component_kind kind,
    bool is_abstract,
    bool allow_same_owner_replacement)
    : _inspect(type_name ? type_name : ""),
      _type_name(type_name ? type_name : ""),
      _owner(owner ? owner : ""),
      _factory(factory),
      _factory_userdata(factory_userdata),
      _kind(kind),
      _abstract(is_abstract) {
    if (_type_name.empty() || _owner.empty()) {
        tc::Log::error("[ComponentTypeDescriptor] type and owner must be non-empty");
        _valid = false;
        return;
    }
    if (tc_component_registry_has(_type_name.c_str())) {
        const char* existing_owner = tc_runtime_type_registry_get_owner(_type_name.c_str());
        if (existing_owner && _owner == existing_owner) {
            if (!allow_same_owner_replacement) {
                _already_registered = true;
                return;
            }
        } else {
            tc::Log::error(
                "[ComponentTypeDescriptor] type %s is already registered by owner %s",
                _type_name.c_str(), existing_owner ? existing_owner : "<none>");
            _valid = false;
            return;
        }
    }
    _descriptor = tc_runtime_type_descriptor_create(
        _type_name.c_str(), _owner.c_str(), parent && parent[0] ? parent : nullptr);
    if (!_descriptor) {
        _valid = false;
    } else if (tc::InspectRegistry::instance().is_empty_unowned_type_shell(_type_name) &&
               !tc_runtime_type_descriptor_allow_unowned_shell_adoption(_descriptor)) {
        _valid = false;
    } else if (allow_same_owner_replacement &&
               !tc_runtime_type_descriptor_allow_same_owner_replacement(_descriptor)) {
        _valid = false;
    }
}

ComponentTypeDescriptorBuilder::~ComponentTypeDescriptorBuilder() {
    tc_runtime_type_descriptor_destroy(_descriptor);
}

ComponentTypeDescriptorBuilder::ComponentTypeDescriptorBuilder(
    ComponentTypeDescriptorBuilder&& other) noexcept
    : _descriptor(other._descriptor),
      _inspect(std::move(other._inspect)),
      _type_name(std::move(other._type_name)),
      _owner(std::move(other._owner)),
      _factory(other._factory),
      _factory_userdata(other._factory_userdata),
      _kind(other._kind),
      _abstract(other._abstract),
      _already_registered(other._already_registered),
      _valid(other._valid),
      _display_name(std::move(other._display_name)),
      _category(std::move(other._category)),
      _requirements(std::move(other._requirements)),
      _capabilities(std::move(other._capabilities)) {
    other._descriptor = nullptr;
}

ComponentTypeDescriptorBuilder& ComponentTypeDescriptorBuilder::operator=(
    ComponentTypeDescriptorBuilder&& other) noexcept {
    if (this == &other) return *this;
    tc_runtime_type_descriptor_destroy(_descriptor);
    _descriptor = other._descriptor;
    other._descriptor = nullptr;
    _inspect = std::move(other._inspect);
    _type_name = std::move(other._type_name);
    _owner = std::move(other._owner);
    _factory = other._factory;
    _factory_userdata = other._factory_userdata;
    _kind = other._kind;
    _abstract = other._abstract;
    _already_registered = other._already_registered;
    _valid = other._valid;
    _display_name = std::move(other._display_name);
    _category = std::move(other._category);
    _requirements = std::move(other._requirements);
    _capabilities = std::move(other._capabilities);
    return *this;
}

ComponentTypeDescriptorBuilder& ComponentTypeDescriptorBuilder::display_name(std::string value) {
    _display_name = std::move(value);
    return *this;
}

ComponentTypeDescriptorBuilder& ComponentTypeDescriptorBuilder::category(std::string value) {
    _category = std::move(value);
    return *this;
}

ComponentTypeDescriptorBuilder& ComponentTypeDescriptorBuilder::require(std::string type_name) {
    if (type_name.empty()) _valid = false;
    else _requirements.push_back(std::move(type_name));
    return *this;
}

ComponentTypeDescriptorBuilder& ComponentTypeDescriptorBuilder::capability(tc_component_cap_id cap_id) {
    _capabilities.push_back(cap_id);
    return *this;
}

bool ComponentTypeDescriptorBuilder::commit() {
    if (_already_registered) return true;
    if (!_valid || !_descriptor || !_inspect.valid()) {
        tc::Log::error("[ComponentTypeDescriptor] invalid descriptor for %s", _type_name.c_str());
        return false;
    }
    std::vector<const char*> requirements;
    requirements.reserve(_requirements.size());
    for (const std::string& requirement : _requirements) requirements.push_back(requirement.c_str());
    if (!tc_component_type_descriptor_add_facet(
            _descriptor, _factory, _factory_userdata, _kind, _abstract,
            _display_name.c_str(), _category.c_str(),
            requirements.data(), requirements.size(),
            _capabilities.data(), _capabilities.size()) ||
        !_inspect.attach_to(_descriptor)) {
        tc::Log::error("[ComponentTypeDescriptor] failed to stage facets for %s", _type_name.c_str());
        return false;
    }
    tc_runtime_type_descriptor* descriptor = _descriptor;
    _descriptor = nullptr;
    if (!tc_runtime_type_registry_commit_descriptor(descriptor)) {
        tc::Log::error("[ComponentTypeDescriptor] failed to commit %s", _type_name.c_str());
        return false;
    }
    return true;
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
