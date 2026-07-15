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
