#include <termin/prefab/prefab_instance_state.hpp>

#include <algorithm>
#include <stdexcept>
#include <unordered_set>
#include <utility>

#include <tc_inspect_cpp.hpp>
#include <inspect/tc_inspect_context.h>
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

const char* structural_kind_name(PrefabStructuralOverrideKind kind) {
    switch (kind) {
        case PrefabStructuralOverrideKind::SuppressEntity: return "suppress_entity";
        case PrefabStructuralOverrideKind::SuppressComponent: return "suppress_component";
        case PrefabStructuralOverrideKind::PlaceEntity: return "place_entity";
        case PrefabStructuralOverrideKind::PlaceComponent: return "place_component";
    }
    return nullptr;
}

bool parse_structural_kind(const std::string& value, PrefabStructuralOverrideKind& result) {
    if (value == "suppress_entity") result = PrefabStructuralOverrideKind::SuppressEntity;
    else if (value == "suppress_component") result = PrefabStructuralOverrideKind::SuppressComponent;
    else if (value == "place_entity") result = PrefabStructuralOverrideKind::PlaceEntity;
    else if (value == "place_component") result = PrefabStructuralOverrideKind::PlaceComponent;
    else return false;
    return true;
}

const char* reference_kind_name(PrefabStructureReferenceKind kind) {
    switch (kind) {
        case PrefabStructureReferenceKind::End: return "end";
        case PrefabStructureReferenceKind::Source: return "source";
        case PrefabStructureReferenceKind::Local: return "local";
    }
    return nullptr;
}

bool parse_reference_kind(const std::string& value, PrefabStructureReferenceKind& result) {
    if (value == "end") result = PrefabStructureReferenceKind::End;
    else if (value == "source") result = PrefabStructureReferenceKind::Source;
    else if (value == "local") result = PrefabStructureReferenceKind::Local;
    else return false;
    return true;
}

std::string structural_identity(const PrefabStructuralOverride& item) {
    const std::string& source_id =
        item.kind == PrefabStructuralOverrideKind::SuppressComponent ||
        item.kind == PrefabStructuralOverrideKind::PlaceComponent
            ? item.source_component_id : item.source_entity_id;
    return std::to_string(static_cast<int>(item.kind)) + "\x1f" + source_id;
}

bool validate_reference(
    const PrefabStructureReference& reference,
    bool component_reference,
    std::string& error
) {
    if (reference.kind == PrefabStructureReferenceKind::End) return true;
    if (reference.kind == PrefabStructureReferenceKind::Source) {
        if (reference.source_id.empty()) {
            error = "source structural reference ID must not be empty";
            return false;
        }
        return true;
    }
    if (!reference.local_entity.valid()) {
        error = "local structural reference entity must be live";
        return false;
    }
    if (component_reference && reference.local_component_source_id.empty()) {
        error = "local component structural reference must contain a component source ID";
        return false;
    }
    return true;
}

bool validate_structural_override(
    const PrefabStructuralOverride& item,
    std::string& error
) {
    const bool component =
        item.kind == PrefabStructuralOverrideKind::SuppressComponent ||
        item.kind == PrefabStructuralOverrideKind::PlaceComponent;
    if (component ? item.source_component_id.empty() : item.source_entity_id.empty()) {
        error = component ? "structural component source ID must not be empty"
                          : "structural entity source ID must not be empty";
        return false;
    }
    if (item.kind == PrefabStructuralOverrideKind::SuppressEntity ||
        item.kind == PrefabStructuralOverrideKind::SuppressComponent) {
        return true;
    }
    if (item.kind == PrefabStructuralOverrideKind::PlaceEntity) {
        if (item.parent.kind == PrefabStructureReferenceKind::End) {
            error = "entity placement requires an explicit parent";
            return false;
        }
        return validate_reference(item.parent, false, error) &&
            validate_reference(item.before, false, error);
    }
    return validate_reference(item.before, true, error);
}

tc_value serialize_reference(const PrefabStructureReference& reference) {
    tc_value result = tc_value_dict_new();
    tc_value_dict_set(&result, "kind", tc_value_string(reference_kind_name(reference.kind)));
    if (reference.kind == PrefabStructureReferenceKind::Source) {
        tc_value_dict_set(&result, "source_id", tc_value_string(reference.source_id.c_str()));
    } else if (reference.kind == PrefabStructureReferenceKind::Local) {
        tc_value_dict_set(&result, "entity", reference.local_entity.serialize_to_value());
        if (!reference.local_component_source_id.empty()) {
            tc_value_dict_set(
                &result,
                "component_source_id",
                tc_value_string(reference.local_component_source_id.c_str())
            );
        }
    }
    return result;
}

bool deserialize_reference(
    const tc_value* data,
    tc_scene_handle scene,
    PrefabStructureReference& result,
    std::string& error
) {
    if (data == nullptr || data->type != TC_VALUE_DICT) {
        error = "structural reference must be a dictionary";
        return false;
    }
    std::string kind;
    if (!override_string_field(data, "kind", kind, false, error) ||
        !parse_reference_kind(kind, result.kind)) {
        if (error.empty()) error = "unknown structural reference kind";
        return false;
    }
    if (result.kind == PrefabStructureReferenceKind::Source) {
        return override_string_field(data, "source_id", result.source_id, false, error);
    }
    if (result.kind == PrefabStructureReferenceKind::Local) {
        tc_scene_inspect_context context = tc_scene_inspect_context_make(scene);
        result.local_entity.deserialize_from(override_field(data, "entity"), &context);
        const tc_value* component_id = override_field(data, "component_source_id");
        if (component_id != nullptr && component_id->type == TC_VALUE_STRING &&
            component_id->data.s != nullptr) {
            result.local_component_source_id = component_id->data.s;
        }
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

bool PrefabInstanceState::set_structural_override(
    PrefabStructuralOverride structural_override,
    std::string& error
) {
    if (!_structural_overrides_valid) {
        error = "cannot mutate invalid structural override metadata";
        tc::Log::error("[PrefabInstanceState] %s", error.c_str());
        return false;
    }
    if (!validate_structural_override(structural_override, error)) {
        tc::Log::error(
            "[PrefabInstanceState] rejected structural override: %s",
            error.c_str()
        );
        return false;
    }
    const std::string identity = structural_identity(structural_override);
    for (PrefabStructuralOverride& existing : _structural_overrides) {
        if (structural_identity(existing) == identity) {
            existing = std::move(structural_override);
            return true;
        }
    }
    _structural_overrides.push_back(std::move(structural_override));
    return true;
}

bool PrefabInstanceState::discard_structural_override(
    PrefabStructuralOverrideKind kind,
    const std::string& source_id
) {
    PrefabStructuralOverride identity;
    identity.kind = kind;
    if (kind == PrefabStructuralOverrideKind::SuppressComponent ||
        kind == PrefabStructuralOverrideKind::PlaceComponent) {
        identity.source_component_id = source_id;
    } else {
        identity.source_entity_id = source_id;
    }
    const std::string key = structural_identity(identity);
    const auto found = std::find_if(
        _structural_overrides.begin(),
        _structural_overrides.end(),
        [&key](const PrefabStructuralOverride& candidate) {
            return structural_identity(candidate) == key;
        }
    );
    if (found == _structural_overrides.end()) return false;
    _structural_overrides.erase(found);
    return true;
}

bool PrefabInstanceState::source_entity_suppressed(const std::string& source_id) const {
    return std::any_of(
        _structural_overrides.begin(),
        _structural_overrides.end(),
        [&source_id](const PrefabStructuralOverride& item) {
            return item.kind == PrefabStructuralOverrideKind::SuppressEntity &&
                item.source_entity_id == source_id;
        }
    );
}

bool PrefabInstanceState::discard_property_override(
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

void PrefabInstanceState::discard_all_property_overrides() {
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
        std::vector<PrefabPropertyOverride> ordered = _property_overrides;
        std::sort(ordered.begin(), ordered.end(), [](const auto& left, const auto& right) {
            return override_identity(left) < override_identity(right);
        });
        for (const PrefabPropertyOverride& property_override_value : ordered) {
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

    tc_value structural = tc_value_list_new();
    if (!_structural_overrides_valid &&
        !_invalid_serialized_structural_overrides.is_nil()) {
        tc_value_free(&structural);
        structural = tc_value_copy(_invalid_serialized_structural_overrides.raw());
    } else {
        std::vector<PrefabStructuralOverride> ordered = _structural_overrides;
        std::sort(ordered.begin(), ordered.end(), [](const auto& left, const auto& right) {
            return structural_identity(left) < structural_identity(right);
        });
        for (const PrefabStructuralOverride& item : ordered) {
            tc_value encoded = tc_value_dict_new();
            tc_value_dict_set(
                &encoded,
                "kind",
                tc_value_string(structural_kind_name(item.kind))
            );
            tc_value_dict_set(
                &encoded,
                "source_entity_id",
                tc_value_string(item.source_entity_id.c_str())
            );
            tc_value_dict_set(
                &encoded,
                "source_component_id",
                tc_value_string(item.source_component_id.c_str())
            );
            if (item.kind == PrefabStructuralOverrideKind::PlaceEntity) {
                tc_value_dict_set(&encoded, "parent", serialize_reference(item.parent));
                tc_value_dict_set(&encoded, "before", serialize_reference(item.before));
            } else if (item.kind == PrefabStructuralOverrideKind::PlaceComponent) {
                tc_value_dict_set(&encoded, "before", serialize_reference(item.before));
            }
            tc_value_list_push(&structural, encoded);
        }
    }
    tc_value_dict_set(&data, "structural_overrides_version", tc_value_int(1));
    tc_value_dict_set(&data, "structural_overrides", structural);
    return data;
}

void PrefabInstanceState::deserialize_data(const tc_value* data, tc_scene_handle scene) {
    CxxComponent::deserialize_data(data, scene);
    _property_overrides.clear();
    _invalid_serialized_overrides = tc::trent::nil();
    _overrides_valid = true;
    _structural_overrides.clear();
    _invalid_serialized_structural_overrides = tc::trent::nil();
    _structural_overrides_valid = true;

    const tc_value* serialized = override_field(data, "property_overrides");
    if (serialized != nullptr) {
        if (serialized->type != TC_VALUE_LIST) {
            _overrides_valid = false;
            _invalid_serialized_overrides = tc::trent::copy_of(serialized);
            tc::Log::error("[PrefabInstanceState] property_overrides must be a list");
            return;
        }

        std::unordered_set<std::string> identities;
        for (size_t index = 0; index < tc_value_list_size(serialized); ++index) {
            const tc_value* item = tc_value_list_get(
                const_cast<tc_value*>(serialized), index);
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
                !override_string_field(
                    item, "field_path", property_override_value.field_path, false, error
                ) ||
                !override_string_field(
                    item, "target_kind", property_override_value.target_kind, false, error
                )) {
                _overrides_valid = false;
            } else {
                auto value = PrefabOverrideValue::parse(
                    override_field(item, "value"), error);
                if (!value) {
                    _overrides_valid = false;
                } else {
                    property_override_value.value = std::move(*value);
                    const std::string identity = override_identity(property_override_value);
                    if (!identities.insert(identity).second) {
                        error = "duplicate property override identity";
                        _overrides_valid = false;
                    } else {
                        _property_overrides.push_back(
                            std::move(property_override_value));
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

    const tc_value* structural = override_field(data, "structural_overrides");
    if (structural == nullptr) return;
    const tc_value* version = override_field(data, "structural_overrides_version");
    if (version == nullptr || version->type != TC_VALUE_INT || version->data.i != 1 ||
        structural->type != TC_VALUE_LIST) {
        _structural_overrides_valid = false;
        _invalid_serialized_structural_overrides = tc::trent::copy_of(structural);
        tc::Log::error(
            "[PrefabInstanceState] structural override metadata has an unsupported schema"
        );
        return;
    }
    std::unordered_set<std::string> structural_identities;
    for (size_t index = 0; index < tc_value_list_size(structural); ++index) {
        const tc_value* item = tc_value_list_get(const_cast<tc_value*>(structural), index);
        PrefabStructuralOverride decoded;
        std::string error;
        std::string kind;
        if (item == nullptr || item->type != TC_VALUE_DICT ||
            !override_string_field(item, "kind", kind, false, error) ||
            !parse_structural_kind(kind, decoded.kind) ||
            !override_string_field(
                item, "source_entity_id", decoded.source_entity_id, true, error) ||
            !override_string_field(
                item, "source_component_id", decoded.source_component_id, true, error)) {
            _structural_overrides_valid = false;
            if (error.empty()) {
                error = "unknown structural override kind '" + kind + "'";
            }
        } else if (decoded.kind == PrefabStructuralOverrideKind::PlaceEntity &&
                   (!deserialize_reference(
                        override_field(item, "parent"), scene, decoded.parent, error) ||
                    !deserialize_reference(
                        override_field(item, "before"), scene, decoded.before, error))) {
            _structural_overrides_valid = false;
        } else if (decoded.kind == PrefabStructuralOverrideKind::PlaceComponent &&
                   !deserialize_reference(
                       override_field(item, "before"), scene, decoded.before, error)) {
            _structural_overrides_valid = false;
        } else if (!validate_structural_override(decoded, error)) {
            _structural_overrides_valid = false;
        } else if (!structural_identities.insert(structural_identity(decoded)).second) {
            error = "duplicate structural override identity";
            _structural_overrides_valid = false;
        } else {
            _structural_overrides.push_back(std::move(decoded));
        }
        if (!_structural_overrides_valid) {
            _structural_overrides.clear();
            _invalid_serialized_structural_overrides = tc::trent::copy_of(structural);
            tc::Log::error(
                "[PrefabInstanceState] rejected structural override at index %zu: %s",
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
    if (!_structural_overrides_valid) {
        tc::Log::error(
            "[PrefabInstanceState] entity '%s' contains invalid structural overrides",
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
