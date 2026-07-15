#include <termin/prefab/prefab_instantiator.hpp>

#include <unordered_map>
#include <unordered_set>

#include <tcbase/tc_log.hpp>
#include <termin/tc_scene.hpp>

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
                    message,
                    path + ".children[" + std::to_string(index) + "]")) {
                return false;
            }
            ++index;
        }
    }
    return true;
}

} // namespace

PrefabInstantiateResult PrefabInstantiator::instantiate(
    const nos::trent& source_hierarchy,
    tc_scene_handle target_scene,
    const Entity& parent,
    const PrefabInstantiateOptions& options
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
    std::string validation_message;
    if (!validate_entity_node(source_hierarchy, source_uuids, validation_message, "root")) {
        const PrefabInstantiateError error = validation_message.find("duplicates source uuid") != std::string::npos
            ? PrefabInstantiateError::DuplicateSourceUuid
            : PrefabInstantiateError::InvalidDocument;
        return failure(error, std::move(validation_message));
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

    PrefabInstantiateResult result;
    result.root = root;
    result.message = "ok";
    return result;
}

} // namespace termin::prefab
