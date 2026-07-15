#include <termin/prefab/prefab_instance_state.hpp>

#include <algorithm>
#include <stdexcept>
#include <unordered_set>
#include <utility>

#include <tc_inspect_cpp.hpp>
#include <tcbase/tc_log.hpp>
#include <termin/entity/component_registry.hpp>

namespace termin::prefab {
namespace {

template<typename T>
void register_hidden_serialized_field(
    T PrefabInstanceState::* member,
    const char* path,
    const char* kind
) {
    tc::InspectFieldSpec spec = tc::inspect_accessor_field_spec(
        PrefabInstanceState::TypeName,
        path,
        path,
        kind,
        true,
        false
    );
    tc::register_inspect_field(member, spec);
}

struct InstanceSnapshotContext {
    const std::string* asset_uuid;
    std::vector<Entity>* entities;
};

bool collect_scene_instance(tc_component* component, void* user_data) {
    auto* context = static_cast<InstanceSnapshotContext*>(user_data);
    CxxComponent* cxx = CxxComponent::from_tc(component);
    auto* state = dynamic_cast<PrefabInstanceState*>(cxx);
    if (state == nullptr || !state->mapping_valid() ||
        state->prefab_asset_uuid() != *context->asset_uuid) {
        return true;
    }
    Entity root = state->entity();
    if (root.valid()) {
        context->entities->push_back(root);
    }
    return true;
}

struct AllScenesSnapshotContext {
    const std::string* asset_uuid;
    std::vector<Entity>* entities;
};

bool collect_scene(tc_scene_handle scene, void* user_data) {
    auto* context = static_cast<AllScenesSnapshotContext*>(user_data);
    InstanceSnapshotContext scene_context{context->asset_uuid, context->entities};
    tc_scene_foreach_component_of_type(
        scene,
        PrefabInstanceState::TypeName,
        collect_scene_instance,
        &scene_context
    );
    return true;
}

const tc_value* override_field(const tc_value* value, const char* key) {
    if (value == nullptr || value->type != TC_VALUE_DICT) return nullptr;
    return tc_value_dict_get(const_cast<tc_value*>(value), key);
}

bool override_string_field(
    const tc_value* value,
    const char* key,
    std::string& result,
    bool allow_empty,
    std::string& error
) {
    const tc_value* field = override_field(value, key);
    if (field == nullptr || field->type != TC_VALUE_STRING || field->data.s == nullptr) {
        error = "property override field '" + std::string(key) + "' must be a string";
        return false;
    }
    result = field->data.s;
    if (!allow_empty && result.empty()) {
        error = "property override field '" + std::string(key) + "' must not be empty";
        return false;
    }
    return true;
}

std::string override_identity(const PrefabPropertyOverride& property_override) {
    return property_override.source_entity_id + "\x1f" +
        property_override.source_component_id + "\x1f" +
        property_override.field_path;
}

bool validate_property_override(
    const PrefabPropertyOverride& property_override,
    std::string& error
) {
    if (property_override.source_entity_id.empty()) {
        error = "property override source entity ID must not be empty";
        return false;
    }
    if (property_override.field_path.empty()) {
        error = "property override field path must not be empty";
        return false;
    }
    if (property_override.target_kind.empty()) {
        error = "property override target kind must not be empty";
        return false;
    }
    return true;
}

} // namespace

PrefabInstanceState::PrefabInstanceState()
    : CxxComponent(TypeName)
{}

PrefabInstanceState::PrefabInstanceState(std::string prefab_asset_uuid)
    : CxxComponent(TypeName),
      _prefab_asset_uuid(std::move(prefab_asset_uuid))
{}

void PrefabInstanceState::register_type() {
    ComponentRegistry& registry = ComponentRegistry::instance();
    if (!registry.has(TypeName)) {
        register_component_type<PrefabInstanceState>(TypeName, "CxxComponent");
        registry.set_category(TypeName, "Prefab");
    }

    tc::InspectRegistry& inspect = tc::InspectRegistry::instance();
    if (inspect.find_field(TypeName, "prefab_asset_uuid") == nullptr) {
        register_hidden_serialized_field(
            &PrefabInstanceState::_prefab_asset_uuid,
            "prefab_asset_uuid",
            "string"
        );
        register_hidden_serialized_field(
            &PrefabInstanceState::_source_revision,
            "source_revision",
            "string"
        );
        register_hidden_serialized_field(
            &PrefabInstanceState::_source_entity_ids,
            "source_entity_ids",
            "list[string]"
        );
        register_hidden_serialized_field(
            &PrefabInstanceState::_runtime_entities,
            "runtime_entities",
            "list[entity]"
        );
        register_hidden_serialized_field(
            &PrefabInstanceState::_source_component_ids,
            "source_component_ids",
            "list[string]"
        );
        register_hidden_serialized_field(
            &PrefabInstanceState::_component_owners,
            "component_owners",
            "list[entity]"
        );
    }
}

void PrefabInstanceState::set_entity_mapping(
    std::vector<std::string> source_ids,
    std::vector<Entity> runtime_entities
) {
    if (source_ids.size() != runtime_entities.size()) {
        tc::Log::error(
            "[PrefabInstanceState] entity mapping size mismatch: source=%zu runtime=%zu",
            source_ids.size(),
            runtime_entities.size()
        );
        throw std::invalid_argument("prefab entity mapping size mismatch");
    }
    _source_entity_ids = std::move(source_ids);
    _runtime_entities = std::move(runtime_entities);
    std::string message;
    _mapping_valid = validate_mapping(false, message);
    if (!_mapping_valid) {
        tc::Log::error("[PrefabInstanceState] invalid entity mapping: %s", message.c_str());
        throw std::invalid_argument(message);
    }
}

void PrefabInstanceState::set_component_mapping(
    std::vector<std::string> source_ids,
    std::vector<Entity> runtime_owners
) {
    if (source_ids.size() != runtime_owners.size()) {
        tc::Log::error(
            "[PrefabInstanceState] component mapping size mismatch: source=%zu owners=%zu",
            source_ids.size(),
            runtime_owners.size()
        );
        throw std::invalid_argument("prefab component mapping size mismatch");
    }
    _source_component_ids = std::move(source_ids);
    _component_owners = std::move(runtime_owners);
    std::string message;
    _mapping_valid = validate_mapping(false, message);
    if (!_mapping_valid) {
        tc::Log::error("[PrefabInstanceState] invalid component mapping: %s", message.c_str());
        throw std::invalid_argument(message);
    }
}

Entity PrefabInstanceState::entity_for_source(const std::string& source_id) const {
    const size_t count = std::min(_source_entity_ids.size(), _runtime_entities.size());
    for (size_t index = 0; index < count; ++index) {
        if (_source_entity_ids[index] == source_id) {
            Entity result = _runtime_entities[index];
            return result.valid() ? result : Entity();
        }
    }
    return Entity();
}

Entity PrefabInstanceState::component_owner_for_source(const std::string& source_id) const {
    const size_t count = std::min(_source_component_ids.size(), _component_owners.size());
    for (size_t index = 0; index < count; ++index) {
        if (_source_component_ids[index] == source_id) {
            Entity result = _component_owners[index];
            return result.valid() ? result : Entity();
        }
    }
    return Entity();
}

size_t PrefabInstanceState::entity_mapping_count() const {
    return std::min(_source_entity_ids.size(), _runtime_entities.size());
}

size_t PrefabInstanceState::component_mapping_count() const {
    return std::min(_source_component_ids.size(), _component_owners.size());
}

bool PrefabInstanceState::set_property_override(
    PrefabPropertyOverride property_override_value,
    std::string& error
) {
    error.clear();
    if (!_overrides_valid) {
        error = "cannot mutate an invalid property override set; clear all overrides first";
        tc::Log::error("[PrefabInstanceState] %s", error.c_str());
        return false;
    }
    if (!validate_property_override(property_override_value, error)) {
        tc::Log::error("[PrefabInstanceState] rejected property override: %s", error.c_str());
        return false;
    }
    const std::string identity = override_identity(property_override_value);
    for (PrefabPropertyOverride& existing : _property_overrides) {
        if (override_identity(existing) == identity) {
            existing = std::move(property_override_value);
            _overrides_valid = true;
            _invalid_serialized_overrides = tc::trent::nil();
            return true;
        }
    }
    _property_overrides.push_back(std::move(property_override_value));
    _overrides_valid = true;
    _invalid_serialized_overrides = tc::trent::nil();
    return true;
}

bool PrefabInstanceState::clear_property_override(
    const std::string& source_entity_id,
    const std::string& source_component_id,
    const std::string& field_path
) {
    const std::string identity = source_entity_id + "\x1f" + source_component_id +
        "\x1f" + field_path;
    auto found = std::find_if(
        _property_overrides.begin(),
        _property_overrides.end(),
        [&identity](const PrefabPropertyOverride& candidate) {
            return override_identity(candidate) == identity;
        }
    );
    if (found == _property_overrides.end()) return false;
    _property_overrides.erase(found);
    return true;
}

void PrefabInstanceState::clear_all_property_overrides() {
    _property_overrides.clear();
    _invalid_serialized_overrides = tc::trent::nil();
    _overrides_valid = true;
}

const PrefabPropertyOverride* PrefabInstanceState::property_override(
    const std::string& source_entity_id,
    const std::string& source_component_id,
    const std::string& field_path
) const {
    const std::string identity = source_entity_id + "\x1f" + source_component_id +
        "\x1f" + field_path;
    auto found = std::find_if(
        _property_overrides.begin(),
        _property_overrides.end(),
        [&identity](const PrefabPropertyOverride& candidate) {
            return override_identity(candidate) == identity;
        }
    );
    return found == _property_overrides.end() ? nullptr : &*found;
}

tc_value PrefabInstanceState::serialize_data() const {
    tc_value data = CxxComponent::serialize_data();
    tc_value serialized = tc_value_list_new();
    if (!_overrides_valid && !_invalid_serialized_overrides.is_nil()) {
        tc_value_free(&serialized);
        serialized = tc_value_copy(_invalid_serialized_overrides.raw());
    } else {
        for (const PrefabPropertyOverride& property_override_value : _property_overrides) {
            tc_value item = tc_value_dict_new();
            tc_value_dict_set(
                &item,
                "source_entity_id",
                tc_value_string(property_override_value.source_entity_id.c_str())
            );
            tc_value_dict_set(
                &item,
                "source_component_id",
                tc_value_string(property_override_value.source_component_id.c_str())
            );
            tc_value_dict_set(
                &item,
                "field_path",
                tc_value_string(property_override_value.field_path.c_str())
            );
            tc_value_dict_set(
                &item,
                "target_kind",
                tc_value_string(property_override_value.target_kind.c_str())
            );
            tc_value_dict_set(&item, "value", property_override_value.value.serialize());
            tc_value_list_push(&serialized, item);
        }
    }
    tc_value_dict_set(&data, "property_overrides", serialized);
    return data;
}

void PrefabInstanceState::deserialize_data(const tc_value* data, tc_scene_handle scene) {
    CxxComponent::deserialize_data(data, scene);
    _property_overrides.clear();
    _invalid_serialized_overrides = tc::trent::nil();
    _overrides_valid = true;

    const tc_value* serialized = override_field(data, "property_overrides");
    if (serialized == nullptr) return;
    if (serialized->type != TC_VALUE_LIST) {
        _overrides_valid = false;
        _invalid_serialized_overrides = tc::trent::copy_of(serialized);
        tc::Log::error("[PrefabInstanceState] property_overrides must be a list");
        return;
    }

    std::unordered_set<std::string> identities;
    for (size_t index = 0; index < tc_value_list_size(serialized); ++index) {
        const tc_value* item = tc_value_list_get(const_cast<tc_value*>(serialized), index);
        PrefabPropertyOverride property_override_value;
        std::string error;
        if (item == nullptr || item->type != TC_VALUE_DICT ||
            !override_string_field(
                item, "source_entity_id", property_override_value.source_entity_id,
                false, error
            ) ||
            !override_string_field(
                item, "source_component_id", property_override_value.source_component_id,
                true, error
            ) ||
            !override_string_field(item, "field_path", property_override_value.field_path, false, error) ||
            !override_string_field(item, "target_kind", property_override_value.target_kind, false, error)) {
            _overrides_valid = false;
        } else {
            auto value = PrefabOverrideValue::parse(override_field(item, "value"), error);
            if (!value) {
                _overrides_valid = false;
            } else {
                property_override_value.value = std::move(*value);
                const std::string identity = override_identity(property_override_value);
                if (!identities.insert(identity).second) {
                    error = "duplicate property override identity";
                    _overrides_valid = false;
                } else {
                    _property_overrides.push_back(std::move(property_override_value));
                }
            }
        }
        if (!_overrides_valid) {
            _property_overrides.clear();
            _invalid_serialized_overrides = tc::trent::copy_of(serialized);
            tc::Log::error(
                "[PrefabInstanceState] rejected property override at index %zu: %s",
                index,
                error.c_str()
            );
            return;
        }
    }
}

bool PrefabInstanceState::validate_mapping(
    bool require_live_references,
    std::string& message
) const {
    if (_prefab_asset_uuid.empty()) {
        message = "prefab asset UUID is empty";
        return false;
    }
    if (_source_entity_ids.size() != _runtime_entities.size()) {
        message = "source entity IDs and runtime entity references differ in size";
        return false;
    }
    if (_source_component_ids.size() != _component_owners.size()) {
        message = "source component IDs and component owners differ in size";
        return false;
    }

    std::unordered_set<std::string> entity_ids;
    for (size_t index = 0; index < _source_entity_ids.size(); ++index) {
        const std::string& source_id = _source_entity_ids[index];
        if (source_id.empty() || !entity_ids.insert(source_id).second) {
            message = "entity source IDs must be non-empty and unique";
            return false;
        }
        if (require_live_references && !_runtime_entities[index].valid()) {
            message = "runtime entity reference for source '" + source_id + "' did not resolve";
            return false;
        }
    }

    std::unordered_set<std::string> component_ids;
    for (size_t index = 0; index < _source_component_ids.size(); ++index) {
        const std::string& source_id = _source_component_ids[index];
        if (source_id.empty() || !component_ids.insert(source_id).second) {
            message = "component source IDs must be non-empty and unique";
            return false;
        }
        if (require_live_references && !_component_owners[index].valid()) {
            message = "component owner for source '" + source_id + "' did not resolve";
            return false;
        }
    }
    return true;
}

void PrefabInstanceState::on_added() {
    std::string message;
    _mapping_valid = validate_mapping(true, message);
    if (!_mapping_valid) {
        tc::Log::error(
            "[PrefabInstanceState] rejected invalid state on entity '%s': %s",
            entity().valid() ? entity().name() : "<invalid>",
            message.c_str()
        );
    }
    if (!_overrides_valid) {
        tc::Log::error(
            "[PrefabInstanceState] entity '%s' contains invalid property overrides",
            entity().valid() ? entity().name() : "<invalid>"
        );
    }
}

void register_prefab_component_types() {
    PrefabInstanceState::register_type();
}

std::vector<Entity> find_live_prefab_instances(
    const std::string& prefab_asset_uuid
) {
    std::vector<Entity> result;
    if (prefab_asset_uuid.empty()) {
        return result;
    }
    AllScenesSnapshotContext context{&prefab_asset_uuid, &result};
    tc_scene_pool_foreach(collect_scene, &context);
    return result;
}

std::vector<Entity> find_live_prefab_instances(
    tc_scene_handle scene,
    const std::string& prefab_asset_uuid
) {
    std::vector<Entity> result;
    if (!tc_scene_alive(scene) || prefab_asset_uuid.empty()) {
        return result;
    }
    InstanceSnapshotContext context{&prefab_asset_uuid, &result};
    tc_scene_foreach_component_of_type(
        scene,
        PrefabInstanceState::TypeName,
        collect_scene_instance,
        &context
    );
    return result;
}

size_t count_live_prefab_instances(const std::string& prefab_asset_uuid) {
    return find_live_prefab_instances(prefab_asset_uuid).size();
}

} // namespace termin::prefab
