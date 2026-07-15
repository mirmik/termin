#include <termin/entity/unknown_component_ops.hpp>

#include <unordered_set>
#include <vector>

#include <tcbase/tc_log.hpp>
#include <termin/entity/component.hpp>
#include <termin/entity/component_registry.hpp>
#include <termin/entity/unknown_component.hpp>
#include <termin/tc_scene.hpp>

namespace termin {
namespace {

bool is_unknown_component(tc_component* component) {
    const char* type_name = component ? tc_component_type_name(component) : nullptr;
    return type_name != nullptr && std::string(type_name) == "UnknownComponent";
}

bool data_has_field(const tc_value* data, const char* field_name) {
    return data != nullptr
        && data->type == TC_VALUE_DICT
        && tc_value_dict_has(const_cast<tc_value*>(data), field_name);
}

void apply_component_core_fields(tc_component* component, const tc_value* data) {
    if (component == nullptr || data == nullptr || data->type != TC_VALUE_DICT) {
        return;
    }

    tc_value* display_name = tc_value_dict_get(const_cast<tc_value*>(data), "display_name");
    if (display_name != nullptr && display_name->type == TC_VALUE_STRING) {
        tc_component_set_display_name(component, display_name->data.s ? display_name->data.s : "");
    }

    tc_value* enabled = tc_value_dict_get(const_cast<tc_value*>(data), "enabled");
    if (enabled != nullptr && enabled->type == TC_VALUE_BOOL) {
        component->enabled = enabled->data.b;
    }

    tc_value* active_in_editor = tc_value_dict_get(const_cast<tc_value*>(data), "active_in_editor");
    if (active_in_editor != nullptr && active_in_editor->type == TC_VALUE_BOOL) {
        component->active_in_editor = active_in_editor->data.b;
    }
}

bool is_component_core_field(const char* path) {
    return path != nullptr && (
        std::string(path) == "display_name" ||
        std::string(path) == "enabled" ||
        std::string(path) == "active_in_editor");
}

bool validate_component_core_field(const char* path, const tc_value* value) {
    if (std::string(path) == "display_name") {
        return value != nullptr && value->type == TC_VALUE_STRING;
    }
    return value != nullptr && value->type == TC_VALUE_BOOL;
}

void discard_unattached_component(tc_component* component) {
    if (component == nullptr) {
        return;
    }
    if (component->factory_retained) {
        component->factory_retained = false;
        tc_component_release(component);
    } else {
        tc_component_drop(component);
    }
}

const char* apply_status_name(tc_inspect_apply_status status) {
    switch (status) {
        case TC_INSPECT_APPLY_OK: return "ok";
        case TC_INSPECT_APPLY_INVALID_ARGUMENT: return "invalid argument";
        case TC_INSPECT_APPLY_TYPE_NOT_FOUND: return "type not found";
        case TC_INSPECT_APPLY_NO_FIELDS: return "no fields registered";
        case TC_INSPECT_APPLY_UNKNOWN_FIELD: return "unknown or non-serializable field";
        case TC_INSPECT_APPLY_KIND_CONVERSION_FAILED: return "kind conversion failed";
        case TC_INSPECT_APPLY_SETTER_FAILED: return "setter failed";
    }
    return "unknown apply error";
}

void* component_object_ptr(tc_component* component) {
    if (component == nullptr) {
        return nullptr;
    }

    if (component->kind == TC_CXX_COMPONENT) {
        return CxxComponent::from_tc(component);
    }

    return component->body;
}

std::unordered_set<std::string> make_type_filter(const std::vector<std::string>& type_names) {
    return std::unordered_set<std::string>(type_names.begin(), type_names.end());
}

bool upgrade_unknown_component_ref_impl(const Entity& entity,
                                        tc_component* component,
                                        const std::string& target_type,
                                        const tc_value* target_data,
                                        std::string* error) {
    if (error) {
        error->clear();
    }

    if (!entity.valid()) {
        if (error) {
            *error = "Entity is invalid";
        }
        return false;
    }

    if (component == nullptr) {
        if (error) {
            *error = "Component pointer is null";
        }
        return false;
    }

    if (!is_unknown_component(component)) {
        if (error) {
            *error = "Component is not UnknownComponent";
        }
        return false;
    }

    auto* unknown_obj = dynamic_cast<UnknownComponent*>(CxxComponent::from_tc(component));
    const bool preserve_runtime_state =
        unknown_obj != nullptr && unknown_obj->preserve_runtime_state_on_upgrade;

    if (target_type.empty()) {
        if (error) {
            *error = "Target type is empty";
        }
        return false;
    }

    if (!ComponentRegistry::instance().has(target_type)) {
        if (error) {
            *error = "Target type is not registered: " + target_type;
        }
        return false;
    }

    tc_component* upgraded_tc = tc_component_registry_create(target_type.c_str());
    if (upgraded_tc == nullptr) {
        if (error) {
            *error = "Failed to create component: " + target_type;
        }
        return false;
    }

    void* upgraded_obj = component_object_ptr(upgraded_tc);
    if (upgraded_obj == nullptr) {
        discard_unattached_component(upgraded_tc);
        if (error) {
            *error = "Created component object pointer is null";
        }
        return false;
    }

    tc_scene_handle scene_handle = entity.scene().handle();
    tc_scene_inspect_context inspect_ctx = tc_scene_inspect_context_make(scene_handle);
    tc_value empty_data = tc_value_dict_new();
    const tc_value* data_to_apply = target_data != nullptr ? target_data : &empty_data;
    if (data_to_apply->type != TC_VALUE_DICT) {
        discard_unattached_component(upgraded_tc);
        tc_value_free(&empty_data);
        if (error) {
            *error = "Component restore payload is not a dictionary";
        }
        return false;
    }

    tc_value inspect_data = tc_value_dict_new();
    for (size_t i = 0; i < tc_value_dict_size(data_to_apply); ++i) {
        const char* key = nullptr;
        tc_value* value = tc_value_dict_get_at(const_cast<tc_value*>(data_to_apply), i, &key);
        if (is_component_core_field(key)) {
            if (!validate_component_core_field(key, value)) {
                discard_unattached_component(upgraded_tc);
                tc_value_free(&inspect_data);
                tc_value_free(&empty_data);
                if (error) {
                    *error = "Invalid component core field: " + std::string(key);
                }
                return false;
            }
            continue;
        }
        tc_value_dict_set(&inspect_data, key, tc_value_copy(value));
    }

    const tc_inspect_apply_result apply_result = tc_inspect_deserialize_checked(
        upgraded_obj,
        target_type.c_str(),
        &inspect_data,
        &inspect_ctx
    );
    if (apply_result.status != TC_INSPECT_APPLY_OK) {
        const std::string failed_field = apply_result.field_path
            ? " at field '" + std::string(apply_result.field_path) + "'"
            : std::string();
        tc_value_free(&inspect_data);
        discard_unattached_component(upgraded_tc);
        tc_value_free(&empty_data);
        if (error) {
            *error = "Failed to restore " + target_type + failed_field + ": " +
                apply_status_name(apply_result.status);
        }
        return false;
    }
    tc_value_free(&inspect_data);

    if (preserve_runtime_state && !data_has_field(data_to_apply, "enabled")) {
        upgraded_tc->enabled = component->enabled;
    }
    if (preserve_runtime_state && !data_has_field(data_to_apply, "active_in_editor")) {
        upgraded_tc->active_in_editor = component->active_in_editor;
    }
    if (preserve_runtime_state && !data_has_field(data_to_apply, "display_name")) {
        tc_component_set_display_name(upgraded_tc, tc_component_get_display_name(component));
    }

    apply_component_core_fields(upgraded_tc, data_to_apply);
    tc_component_set_source_id(
        upgraded_tc,
        tc_component_get_source_id(component)
    );

    tc_value_free(&empty_data);

    Entity mutable_entity = entity;
    mutable_entity.add_component_ptr(upgraded_tc);
    mutable_entity.remove_component_ptr(component);
    return true;
}

} // namespace

UnknownUpgradeDecision::UnknownUpgradeDecision(const UnknownUpgradeDecision& other) :
    mode(other.mode),
    target_type(other.target_type),
    target_data(tc_value_copy(&other.target_data)) {}

UnknownUpgradeDecision&
UnknownUpgradeDecision::operator=(const UnknownUpgradeDecision& other) {
    if (this == &other) {
        return *this;
    }

    mode = other.mode;
    target_type = other.target_type;
    tc_value_free(&target_data);
    target_data = tc_value_copy(&other.target_data);
    return *this;
}

UnknownUpgradeDecision::UnknownUpgradeDecision(UnknownUpgradeDecision&& other) noexcept :
    mode(other.mode),
    target_type(std::move(other.target_type)),
    target_data(other.target_data) {
    other.mode = UnknownUpgradeMode::DefaultUpgrade;
    other.target_data = tc_value_nil();
}

UnknownUpgradeDecision&
UnknownUpgradeDecision::operator=(UnknownUpgradeDecision&& other) noexcept {
    if (this == &other) {
        return *this;
    }

    mode = other.mode;
    target_type = std::move(other.target_type);
    tc_value_free(&target_data);
    target_data = other.target_data;
    other.mode = UnknownUpgradeMode::DefaultUpgrade;
    other.target_data = tc_value_nil();
    return *this;
}

UnknownUpgradeDecision::~UnknownUpgradeDecision() {
    tc_value_free(&target_data);
}

UnknownUpgradeDecision UnknownUpgradeDecision::skip() {
    UnknownUpgradeDecision decision;
    decision.mode = UnknownUpgradeMode::Skip;
    return decision;
}

UnknownUpgradeDecision UnknownUpgradeDecision::default_upgrade() {
    return UnknownUpgradeDecision();
}

UnknownUpgradeDecision UnknownUpgradeDecision::custom(
    std::string target_type,
    const tc_value* target_data) {
    UnknownUpgradeDecision decision;
    decision.mode = UnknownUpgradeMode::CustomUpgrade;
    decision.target_type = std::move(target_type);
    if (target_data != nullptr) {
        decision.target_data = tc_value_copy(target_data);
    }
    return decision;
}

bool degrade_component_ref_to_unknown(const Entity& entity, tc_component* component, std::string* error) {
    if (error) {
        error->clear();
    }

    if (!entity.valid()) {
        if (error) {
            *error = "Entity is invalid";
        }
        return false;
    }

    if (component == nullptr) {
        if (error) {
            *error = "Component pointer is null";
        }
        return false;
    }

    if (is_unknown_component(component)) {
        if (error) {
            *error = "Component is already UnknownComponent";
        }
        return false;
    }

    const char* original_type_name = tc_component_type_name(component);
    if (original_type_name == nullptr || original_type_name[0] == '\0') {
        if (error) {
            *error = "Component type name is empty";
        }
        return false;
    }

    void* obj_ptr = component_object_ptr(component);
    if (obj_ptr == nullptr) {
        if (error) {
            *error = "Component object pointer is null";
        }
        return false;
    }

    tc_value original_data = tc_inspect_serialize(obj_ptr, original_type_name);
    if (original_data.type == TC_VALUE_DICT) {
        if (!tc_value_dict_has(&original_data, "enabled")) {
            tc_value_dict_set(&original_data, "enabled", tc_value_bool(component->enabled));
        }
        if (!tc_value_dict_has(&original_data, "active_in_editor")) {
            tc_value_dict_set(
                &original_data,
                "active_in_editor",
                tc_value_bool(component->active_in_editor)
            );
        }

        const char* display_name = tc_component_get_display_name(component);
        if (display_name != nullptr && display_name[0] != '\0'
            && !tc_value_dict_has(&original_data, "display_name")) {
            tc_value_dict_set(&original_data, "display_name", tc_value_string(display_name));
        }
    }

    tc_component* unknown_tc = tc_component_registry_create("UnknownComponent");
    if (unknown_tc == nullptr) {
        tc_value_free(&original_data);
        if (error) {
            *error = "Failed to create UnknownComponent";
        }
        return false;
    }

    auto* unknown_obj = static_cast<UnknownComponent*>(CxxComponent::from_tc(unknown_tc));
    if (unknown_obj == nullptr) {
        tc_value_free(&original_data);
        if (error) {
            *error = "UnknownComponent instance is not a CxxComponent";
        }
        return false;
    }

    unknown_obj->original_type = original_type_name;
    unknown_obj->preserve_runtime_state_on_upgrade = true;
    tc_value_free(&unknown_obj->original_data);
    unknown_obj->original_data = tc_value_copy(&original_data);
    tc_value_free(&original_data);

    unknown_tc->enabled = component->enabled;
    unknown_tc->active_in_editor = component->active_in_editor;
    tc_component_set_display_name(unknown_tc, tc_component_get_display_name(component));
    tc_component_set_source_id(
        unknown_tc,
        tc_component_get_source_id(component)
    );

    Entity mutable_entity = entity;
    mutable_entity.add_component_ptr(unknown_tc);
    mutable_entity.remove_component_ptr(component);
    return true;
}

bool upgrade_unknown_component_ref(const Entity& entity, tc_component* component, std::string* error) {
    if (error) {
        error->clear();
    }

    if (!entity.valid()) {
        if (error) {
            *error = "Entity is invalid";
        }
        return false;
    }

    if (component == nullptr) {
        if (error) {
            *error = "Component pointer is null";
        }
        return false;
    }

    if (!is_unknown_component(component)) {
        if (error) {
            *error = "Component is not UnknownComponent";
        }
        return false;
    }

    auto* unknown_obj = static_cast<UnknownComponent*>(CxxComponent::from_tc(component));
    if (unknown_obj == nullptr) {
        if (error) {
            *error = "UnknownComponent object pointer is null";
        }
        return false;
    }

    if (unknown_obj->original_type.empty()) {
        if (error) {
            *error = "UnknownComponent has empty original_type";
        }
        return false;
    }

    return upgrade_unknown_component_ref_impl(
        entity,
        component,
        unknown_obj->original_type,
        &unknown_obj->original_data,
        error);
}

UnknownComponentStats degrade_components_to_unknown(const TcSceneRef& scene, const std::vector<std::string>& type_names) {
    UnknownComponentStats stats;
    if (!scene.valid()) {
        return stats;
    }

    const auto type_filter = make_type_filter(type_names);

    for (const Entity& entity : scene.get_all_entities()) {
        std::vector<tc_component*> pending;
        const size_t component_count = entity.component_count();
        pending.reserve(component_count);

        for (size_t i = 0; i < component_count; ++i) {
            tc_component* component = entity.component_at(i);
            if (component == nullptr || is_unknown_component(component)) {
                continue;
            }

            const char* type_name = tc_component_type_name(component);
            if (type_name == nullptr) {
                continue;
            }

            if (!type_filter.empty() && type_filter.count(type_name) == 0) {
                continue;
            }

            pending.push_back(component);
        }

        for (tc_component* component : pending) {
            std::string error;
            if (degrade_component_ref_to_unknown(entity, component, &error)) {
                ++stats.degraded;
            } else {
                ++stats.failed;
                tc::Log::error("[UnknownComponent] Failed to degrade component: %s", error.c_str());
            }
        }
    }

    return stats;
}

UnknownComponentStats upgrade_unknown_components(const TcSceneRef& scene, const std::vector<std::string>& type_names) {
    return upgrade_unknown_components(scene, UnknownUpgradeStrategy(), type_names);
}

UnknownComponentStats upgrade_unknown_components(const TcSceneRef& scene,
                                                 const UnknownUpgradeStrategy& strategy,
                                                 const std::vector<std::string>& type_names) {
    UnknownComponentStats stats;
    if (!scene.valid()) {
        return stats;
    }

    const auto type_filter = make_type_filter(type_names);

    for (const Entity& entity : scene.get_all_entities()) {
        std::vector<tc_component*> pending;
        const size_t component_count = entity.component_count();
        pending.reserve(component_count);

        for (size_t i = 0; i < component_count; ++i) {
            tc_component* component = entity.component_at(i);
            if (!is_unknown_component(component)) {
                continue;
            }

            auto* unknown_obj = static_cast<UnknownComponent*>(CxxComponent::from_tc(component));
            if (unknown_obj == nullptr) {
                ++stats.failed;
                continue;
            }

            if (!type_filter.empty() && type_filter.count(unknown_obj->original_type) == 0) {
                ++stats.skipped;
                continue;
            }

            if (!strategy &&
                !ComponentRegistry::instance().has(unknown_obj->original_type)) {
                ++stats.skipped;
                continue;
            }

            pending.push_back(component);
        }

        for (tc_component* component : pending) {
            std::string error;
            auto* unknown_obj = static_cast<UnknownComponent*>(CxxComponent::from_tc(component));
            if (unknown_obj == nullptr) {
                ++stats.failed;
                continue;
            }

            if (!strategy) {
                if (upgrade_unknown_component_ref(entity, component, &error)) {
                    ++stats.upgraded;
                } else {
                    ++stats.failed;
                    tc::Log::error("[UnknownComponent] Failed to upgrade component: %s", error.c_str());
                }
                continue;
            }

            UnknownUpgradeDecision decision = strategy(*unknown_obj, entity, scene);
            switch (decision.mode) {
            case UnknownUpgradeMode::Skip:
                ++stats.skipped;
                break;
            case UnknownUpgradeMode::DefaultUpgrade:
                if (upgrade_unknown_component_ref(entity, component, &error)) {
                    ++stats.upgraded;
                } else {
                    ++stats.failed;
                    tc::Log::error("[UnknownComponent] Failed to upgrade component: %s", error.c_str());
                }
                break;
            case UnknownUpgradeMode::CustomUpgrade:
                if (upgrade_unknown_component_ref_impl(entity,
                                                       component,
                                                       decision.target_type,
                                                       &decision.target_data,
                                                       &error)) {
                    ++stats.upgraded;
                } else {
                    ++stats.failed;
                    tc::Log::error("[UnknownComponent] Failed custom upgrade component: %s",
                                   error.c_str());
                }
                break;
            }
        }
    }

    return stats;
}

} // namespace termin
