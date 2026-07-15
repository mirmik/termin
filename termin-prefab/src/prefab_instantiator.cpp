#include <termin/prefab/prefab_instantiator.hpp>
#include <termin/prefab/prefab_document.hpp>
#include <termin/prefab/prefab_instance_state.hpp>

#include <unordered_map>
#include <unordered_set>

#include <tcbase/tc_log.hpp>
#include <termin/tc_scene.hpp>
#include <termin/entity/component_registry.hpp>

namespace termin::prefab {
namespace {

PrefabInstantiateResult failure(PrefabInstantiateError error, std::string message) {
    tc::Log::error("[PrefabInstantiator] %s", message.c_str());
    PrefabInstantiateResult result;
    result.error = error;
    result.message = std::move(message);
    return result;
}

bool validate_entity_node(
    const nos::trent& node,
    std::unordered_set<std::string>& source_uuids,
    std::unordered_set<std::string>& component_source_ids,
    std::string& message,
    const std::string& path
) {
    if (!node.is_dict()) {
        message = path + " must be an object";
        return false;
    }

    const std::string uuid = node["uuid"].as_string_default("");
    if (uuid.empty()) {
        message = path + ".uuid must be a non-empty string";
        return false;
    }
    if (!source_uuids.insert(uuid).second) {
        message = path + ".uuid duplicates source uuid '" + uuid + "'";
        return false;
    }

    if (node.contains("components") && !node["components"].is_list()) {
        message = path + ".components must be a list";
        return false;
    }
    if (node.contains("components")) {
        size_t index = 0;
        for (const nos::trent& component : node["components"].as_list()) {
            const std::string component_path = path + ".components[" + std::to_string(index) + "]";
            if (!component.is_dict()) {
                message = component_path + " must be an object";
                return false;
            }
            if (component["type"].as_string_default("").empty()) {
                message = component_path + ".type must be a non-empty string";
                return false;
            }
            const std::string source_id = component["source_id"].as_string_default("");
            if (!source_id.empty() && !component_source_ids.insert(source_id).second) {
                message = component_path + ".source_id duplicates component source id '" +
                    source_id + "'";
                return false;
            }
            ++index;
        }
    }

    if (node.contains("children") && !node["children"].is_list()) {
        message = path + ".children must be a list";
        return false;
    }
    if (node.contains("children")) {
        size_t index = 0;
        for (const nos::trent& child : node["children"].as_list()) {
            if (!validate_entity_node(
                    child,
                    source_uuids,
                    component_source_ids,
                    message,
                    path + ".children[" + std::to_string(index) + "]")) {
                return false;
            }
            ++index;
        }
    }
    return true;
}

bool collect_instance_mapping(
    const nos::trent& source,
    const std::unordered_map<std::string, std::string>& uuid_remap,
    tc_entity_pool* target_pool,
    tc_entity_pool_handle target_pool_handle,
    std::vector<std::string>& source_entity_ids,
    std::vector<Entity>& runtime_entities,
    std::vector<std::string>& source_component_ids,
    std::vector<Entity>& component_owners,
    std::string& message
) {
    const std::string source_entity_id = source["uuid"].as_string_default("");
    const auto remap_it = uuid_remap.find(source_entity_id);
    if (remap_it == uuid_remap.end()) {
        message = "missing runtime UUID mapping for source entity '" + source_entity_id + "'";
        return false;
    }
    const tc_entity_id runtime_id = tc_entity_pool_find_by_uuid(
        target_pool,
        remap_it->second.c_str()
    );
    Entity runtime_entity(target_pool_handle, runtime_id);
    if (!runtime_entity.valid()) {
        message = "runtime entity for source '" + source_entity_id + "' is unavailable";
        return false;
    }

    source_entity_ids.push_back(source_entity_id);
    runtime_entities.push_back(runtime_entity);
    if (source.contains("components")) {
        for (const nos::trent& component : source["components"].as_list()) {
            source_component_ids.push_back(component["source_id"].as_string_default(""));
            component_owners.push_back(runtime_entity);
        }
    }
    if (source.contains("children")) {
        for (const nos::trent& child : source["children"].as_list()) {
            if (!collect_instance_mapping(
                    child,
                    uuid_remap,
                    target_pool,
                    target_pool_handle,
                    source_entity_ids,
                    runtime_entities,
                    source_component_ids,
                    component_owners,
                    message)) {
                return false;
            }
        }
    }
    return true;
}

void destroy_hierarchy(Entity root) {
    if (!root.valid()) {
        return;
    }
    root.destroy_children();
    tc_entity_free(root.handle());
}

PrefabInstantiateResult instantiate_hierarchy(
    const nos::trent& source_hierarchy,
    tc_scene_handle target_scene,
    const Entity& parent,
    const PrefabInstantiateOptions& options,
    const PrefabDocument* document
);

} // namespace

PrefabInstantiateResult PrefabInstantiator::instantiate(
    const PrefabDocument& document,
    tc_scene_handle target_scene,
    const Entity& parent,
    const PrefabInstantiateOptions& options
) {
    PrefabDocumentResult validation = document.validate();
    if (!validation.ok()) {
        return failure(
            PrefabInstantiateError::InvalidDocument,
            validation.message
        );
    }
    return instantiate_hierarchy(
        document.source_hierarchy(),
        target_scene,
        parent,
        options,
        &document
    );
}

namespace {

PrefabInstantiateResult instantiate_hierarchy(
    const nos::trent& source_hierarchy,
    tc_scene_handle target_scene,
    const Entity& parent,
    const PrefabInstantiateOptions& options,
    const PrefabDocument* document
) {
    if (!tc_scene_handle_valid(target_scene)) {
        return failure(
            PrefabInstantiateError::InvalidTargetScene,
            "target scene is invalid"
        );
    }

    tc_entity_pool* target_pool = tc_scene_entity_pool(target_scene);
    if (target_pool == nullptr) {
        return failure(
            PrefabInstantiateError::InvalidTargetScene,
            "target scene has no entity pool"
        );
    }
    if (parent.valid() && parent.pool() != target_pool) {
        return failure(
            PrefabInstantiateError::InvalidParent,
            "parent belongs to a different entity pool"
        );
    }

    std::unordered_set<std::string> source_uuids;
    std::unordered_set<std::string> component_source_ids;
    std::string validation_message;
    if (!validate_entity_node(
            source_hierarchy,
            source_uuids,
            component_source_ids,
            validation_message,
            "root")) {
        const PrefabInstantiateError error = validation_message.find("duplicates source uuid") != std::string::npos
            ? PrefabInstantiateError::DuplicateSourceUuid
            : PrefabInstantiateError::InvalidDocument;
        return failure(error, std::move(validation_message));
    }

    if (document != nullptr) {
        register_prefab_component_types();
        if (!ComponentRegistry::instance().has(PrefabInstanceState::TypeName)) {
            return failure(
                PrefabInstantiateError::InstanceStatePublicationFailed,
                "PrefabInstanceState component type is not registered"
            );
        }
    }

    std::unordered_map<std::string, std::string> uuid_remap;
    nos::trent instance_data = Entity::make_clone_payload(source_hierarchy, "", uuid_remap);
    if (!instance_data.is_dict()) {
        return failure(
            PrefabInstantiateError::HierarchyCreationFailed,
            "failed to create hierarchy clone payload"
        );
    }
    Entity::remap_entity_refs(instance_data, uuid_remap);

    Entity root = Entity::deserialize_hierarchy(instance_data, target_scene, parent);
    if (!root.valid()) {
        return failure(
            PrefabInstantiateError::HierarchyCreationFailed,
            "failed to deserialize hierarchy into target scene"
        );
    }

    if (!options.root_name.empty()) {
        root.set_name(options.root_name);
    }
    if (options.has_position) {
        root.set_local_position(options.position);
    }

    if (document != nullptr) {
        std::vector<std::string> source_entity_ids;
        std::vector<Entity> runtime_entities;
        std::vector<std::string> source_component_ids;
        std::vector<Entity> component_owners;
        std::string mapping_message;
        if (!collect_instance_mapping(
                source_hierarchy,
                uuid_remap,
                target_pool,
                root.pool_handle(),
                source_entity_ids,
                runtime_entities,
                source_component_ids,
                component_owners,
                mapping_message)) {
            destroy_hierarchy(root);
            return failure(
                PrefabInstantiateError::InstanceStatePublicationFailed,
                std::move(mapping_message)
            );
        }

        PrefabInstanceState* state = nullptr;
        try {
            state = new PrefabInstanceState(document->asset_uuid());
            state->set_source_revision(document->source_revision());
            state->set_entity_mapping(
                std::move(source_entity_ids),
                std::move(runtime_entities)
            );
            state->set_component_mapping(
                std::move(source_component_ids),
                std::move(component_owners)
            );
            root.add_component(state);
            if (root.get_component<PrefabInstanceState>() != state) {
                if (state->entity().valid()) {
                    root.remove_component(state);
                } else {
                    delete state;
                }
                destroy_hierarchy(root);
                return failure(
                    PrefabInstantiateError::InstanceStatePublicationFailed,
                    "failed to attach PrefabInstanceState to instance root"
                );
            }
            const std::string root_source_id =
                source_hierarchy["uuid"].as_string_default("");
            const auto store_option_override = [state, &root_source_id](
                const char* field_path,
                const char* target_kind,
                const tc_value& value
            ) {
                std::string error;
                auto encoded = PrefabOverrideValue::from_inspect_value(
                    &value, target_kind, error);
                if (!encoded) return error;
                PrefabPropertyOverride property_override;
                property_override.source_entity_id = root_source_id;
                property_override.field_path = field_path;
                property_override.target_kind = target_kind;
                property_override.value = std::move(*encoded);
                if (!state->set_property_override(std::move(property_override), error)) {
                    return error;
                }
                return std::string();
            };
            if (!options.root_name.empty()) {
                tc_value value = tc_value_string(options.root_name.c_str());
                const std::string error = store_option_override("name", "string", value);
                tc_value_free(&value);
                if (!error.empty()) {
                    throw std::runtime_error(
                        "failed to record root_name prefab override: " + error);
                }
            }
            if (options.has_position) {
                tc_value value = tc_value_list_new();
                for (double coordinate : options.position) {
                    tc_value_list_push(&value, tc_value_double(coordinate));
                }
                const std::string error = store_option_override(
                    "transform.position", "vec3", value);
                tc_value_free(&value);
                if (!error.empty()) {
                    throw std::runtime_error(
                        "failed to record position prefab override: " + error);
                }
            }
        } catch (const std::exception& error) {
            if (state != nullptr) {
                if (state->entity().valid()) {
                    root.remove_component(state);
                } else {
                    delete state;
                }
            }
            destroy_hierarchy(root);
            return failure(
                PrefabInstantiateError::InstanceStatePublicationFailed,
                std::string("failed to publish PrefabInstanceState: ") + error.what()
            );
        }
    }

    PrefabInstantiateResult result;
    result.root = root;
    result.message = "ok";
    return result;
}

} // namespace

PrefabInstantiateResult PrefabInstantiator::instantiate(
    const nos::trent& source_hierarchy,
    tc_scene_handle target_scene,
    const Entity& parent,
    const PrefabInstantiateOptions& options
) {
    return instantiate_hierarchy(source_hierarchy, target_scene, parent, options, nullptr);
}

} // namespace termin::prefab
