#include <termin/prefab/prefab_document.hpp>

#include <cmath>
#include <iomanip>
#include <limits>
#include <sstream>
#include <unordered_set>

#include <trent/json.h>
#include <tcbase/tc_log.hpp>
#include <termin/tc_scene.hpp>

namespace termin::prefab {
namespace {

PrefabDocumentResult failure(PrefabDocumentError error, std::string message) {
    tc::Log::error("[PrefabDocument] %s", message.c_str());
    PrefabDocumentResult result;
    result.error = error;
    result.message = std::move(message);
    return result;
}

bool require_string(const nos::trent& entity, const char* field, const std::string& path,
                    std::string& message) {
    if (!entity.contains(field) || !entity[field].is_string()) {
        message = path + "." + field + " must be a string";
        return false;
    }
    return true;
}

bool require_bool(const nos::trent& entity, const char* field, const std::string& path,
                  std::string& message) {
    if (!entity.contains(field) || !entity[field].is_bool()) {
        message = path + "." + field + " must be a boolean";
        return false;
    }
    return true;
}

bool require_integer(
    const nos::trent& entity,
    const char* field,
    long double minimum,
    long double maximum,
    const char* expectation,
    const std::string& path,
    std::string& message
) {
    if (!entity.contains(field) || !entity[field].is_numer()) {
        message = path + "." + field + " " + expectation;
        return false;
    }
    const long double value = entity[field].as_numer();
    if (!std::isfinite(value) || std::trunc(value) != value ||
        value < minimum || value > maximum) {
        message = path + "." + field + " " + expectation;
        return false;
    }
    return true;
}

bool require_finite_vector(
    const nos::trent& value,
    size_t expected_size,
    const std::string& path,
    std::string& message
) {
    if (!value.is_list()) {
        message = path + " must be a list of " + std::to_string(expected_size) +
            " finite numbers";
        return false;
    }
    const auto& items = value.as_list();
    if (items.size() != expected_size) {
        message = path + " must contain exactly " + std::to_string(expected_size) +
            " finite numbers";
        return false;
    }
    for (size_t index = 0; index < items.size(); ++index) {
        if (!items[index].is_numer() || !std::isfinite(items[index].as_numer())) {
            message = path + "[" + std::to_string(index) + "] must be a finite number";
            return false;
        }
    }
    return true;
}

bool validate_entity_base(
    const nos::trent& entity,
    const std::string& path,
    std::string& message
) {
    if (!require_string(entity, "name", path, message)) return false;
    for (const char* field : {"visible", "enabled", "pickable", "selectable"}) {
        if (!require_bool(entity, field, path, message)) return false;
    }
    if (!require_integer(
            entity, "priority",
            std::numeric_limits<int>::min(), std::numeric_limits<int>::max(),
            "must be an integer in the native int range", path, message)) {
        return false;
    }
    for (const char* field : {"layer", "flags"}) {
        if (!require_integer(
                entity, field, 0, std::numeric_limits<int64_t>::max(),
                "must be a non-negative integer", path, message)) {
            return false;
        }
    }
    if (!entity.contains("pose") || !entity["pose"].is_dict()) {
        message = path + ".pose must be an object";
        return false;
    }
    const nos::trent& pose = entity["pose"];
    if (!pose.contains("position") ||
        !require_finite_vector(pose["position"], 3, path + ".pose.position", message)) {
        if (!pose.contains("position")) {
            message = path + ".pose.position must be a list of 3 finite numbers";
        }
        return false;
    }
    if (!pose.contains("rotation") ||
        !require_finite_vector(pose["rotation"], 4, path + ".pose.rotation", message)) {
        if (!pose.contains("rotation")) {
            message = path + ".pose.rotation must be a list of 4 finite numbers";
        }
        return false;
    }
    if (!entity.contains("scale") ||
        !require_finite_vector(entity["scale"], 3, path + ".scale", message)) {
        if (!entity.contains("scale")) {
            message = path + ".scale must be a list of 3 finite numbers";
        }
        return false;
    }
    return true;
}

bool validate_entity(
    const nos::trent& entity,
    std::unordered_set<std::string>& entity_ids,
    std::unordered_set<std::string>& component_ids,
    const std::string& path,
    std::string& message
) {
    if (!entity.is_dict()) {
        message = path + " must be an object";
        return false;
    }

    const std::string entity_id = entity["uuid"].as_string_default("");
    if (entity_id.empty()) {
        message = path + ".uuid must be a non-empty source identity";
        return false;
    }
    if (!entity_ids.insert(entity_id).second) {
        message = path + ".uuid duplicates entity source identity '" + entity_id + "'";
        return false;
    }

    if (!validate_entity_base(entity, path, message)) {
        return false;
    }

    if (!entity.contains("components") || !entity["components"].is_list()) {
        message = path + ".components must be a list";
        return false;
    }
    size_t component_index = 0;
    for (const nos::trent& component : entity["components"].as_list()) {
        const std::string component_path =
            path + ".components[" + std::to_string(component_index) + "]";
        if (!component.is_dict()) {
            message = component_path + " must be an object";
            return false;
        }
        const std::string type_name = component["type"].as_string_default("");
        if (type_name.empty()) {
            message = component_path + ".type must be a non-empty string";
            return false;
        }
        const std::string component_id = component["source_id"].as_string_default("");
        if (component_id.empty()) {
            message = component_path + ".source_id must be non-empty";
            return false;
        }
        if (!component_ids.insert(component_id).second) {
            message = component_path + ".source_id duplicates component source identity '" +
                component_id + "'";
            return false;
        }
        ++component_index;
    }

    if (!entity.contains("children") || !entity["children"].is_list()) {
        message = path + ".children must be a list";
        return false;
    }
    size_t child_index = 0;
    for (const nos::trent& child : entity["children"].as_list()) {
        if (!validate_entity(
                child,
                entity_ids,
                component_ids,
                path + ".children[" + std::to_string(child_index) + "]",
                message)) {
            return false;
        }
        ++child_index;
    }
    return true;
}

} // namespace

bool PrefabDocument::valid() const {
    return !_asset_uuid.empty() && _root.is_dict();
}

PrefabDocumentResult PrefabDocument::parse_json(const std::string& json) {
    nos::trent data;
    try {
        data = nos::json::parse(json);
    } catch (const std::exception& error) {
        return failure(
            PrefabDocumentError::InvalidJson,
            std::string("invalid JSON: ") + error.what()
        );
    }

    if (!data.is_dict()) {
        return failure(PrefabDocumentError::InvalidDocument, "document root must be an object");
    }
    const std::string version = data["version"].as_string_default("");
    if (version != CurrentVersion) {
        return failure(
            PrefabDocumentError::UnsupportedVersion,
            "unsupported prefab version '" + version + "'; expected " + CurrentVersion
        );
    }

    PrefabDocumentResult result;
    result.document._asset_uuid = data["uuid"].as_string_default("");
    if (data.contains("root")) {
        result.document._root = data["root"];
    }
    PrefabDocumentResult validation = result.document.validate();
    if (!validation.ok()) {
        return validation;
    }
    result.message = "ok";
    return result;
}

PrefabDocumentResult PrefabDocument::capture(
    const std::string& asset_uuid,
    const Entity& editable_root
) {
    if (!editable_root.valid()) {
        return failure(PrefabDocumentError::InvalidDocument, "editable root entity is invalid");
    }

    PrefabDocumentResult result;
    result.document._asset_uuid = asset_uuid;
    result.document._root = editable_root.serialize_hierarchy();
    PrefabDocumentResult validation = result.document.validate();
    if (!validation.ok()) {
        return validation;
    }
    result.message = "ok";
    return result;
}

PrefabDocumentResult PrefabDocument::empty(
    const std::string& asset_uuid,
    const std::string& root_source_id,
    const std::string& root_name
) {
    PrefabDocumentResult result;
    result.document._asset_uuid = asset_uuid;
    nos::trent& root = result.document._root;
    root["uuid"] = root_source_id;
    root["name"] = root_name;
    root["priority"] = static_cast<int64_t>(0);
    root["visible"] = true;
    root["enabled"] = true;
    root["pickable"] = true;
    root["selectable"] = true;
    root["layer"] = static_cast<int64_t>(0);
    root["flags"] = static_cast<int64_t>(0);
    root["pose"]["position"].init(nos::trent::type::list);
    root["pose"]["position"].push_back(0.0);
    root["pose"]["position"].push_back(0.0);
    root["pose"]["position"].push_back(0.0);
    root["pose"]["rotation"].init(nos::trent::type::list);
    root["pose"]["rotation"].push_back(0.0);
    root["pose"]["rotation"].push_back(0.0);
    root["pose"]["rotation"].push_back(0.0);
    root["pose"]["rotation"].push_back(1.0);
    root["scale"].init(nos::trent::type::list);
    root["scale"].push_back(1.0);
    root["scale"].push_back(1.0);
    root["scale"].push_back(1.0);
    root["components"].init(nos::trent::type::list);
    root["children"].init(nos::trent::type::list);

    PrefabDocumentResult validation = result.document.validate();
    if (!validation.ok()) {
        return validation;
    }
    result.message = "ok";
    return result;
}

PrefabDocumentResult PrefabDocument::validate() const {
    if (_asset_uuid.empty()) {
        return failure(PrefabDocumentError::InvalidDocument, "document uuid must be non-empty");
    }
    std::unordered_set<std::string> entity_ids;
    std::unordered_set<std::string> component_ids;
    std::string message;
    if (!validate_entity(_root, entity_ids, component_ids, "root", message)) {
        return failure(PrefabDocumentError::InvalidDocument, std::move(message));
    }
    PrefabDocumentResult result;
    result.document = *this;
    result.message = "ok";
    return result;
}

std::string PrefabDocument::to_json(int indent) const {
    PrefabDocumentResult validation = validate();
    if (!validation.ok()) {
        throw std::runtime_error(validation.message);
    }
    nos::trent data;
    data["version"] = CurrentVersion;
    data["uuid"] = _asset_uuid;
    data["root"] = _root;
    return nos::json::dump(data, indent);
}

std::string PrefabDocument::source_revision() const {
    const std::string canonical_source = nos::json::dump(_root);
    uint64_t hash = UINT64_C(14695981039346656037);
    for (const unsigned char byte : canonical_source) {
        hash ^= static_cast<uint64_t>(byte);
        hash *= UINT64_C(1099511628211);
    }
    std::ostringstream stream;
    stream << std::hex << std::setfill('0') << std::setw(16) << hash;
    return stream.str();
}

PrefabDocumentResult PrefabDocument::materialize_source(
    tc_scene_handle target_scene,
    const Entity& parent
) const {
    PrefabDocumentResult validation = validate();
    if (!validation.ok()) {
        return validation;
    }
    if (!tc_scene_handle_valid(target_scene)) {
        return failure(PrefabDocumentError::InvalidTargetScene, "target scene is invalid");
    }
    tc_entity_pool* target_pool = tc_scene_entity_pool(target_scene);
    if (target_pool == nullptr) {
        return failure(PrefabDocumentError::InvalidTargetScene, "target scene has no entity pool");
    }
    if (parent.valid() && parent.pool() != target_pool) {
        return failure(PrefabDocumentError::InvalidParent, "parent belongs to a different entity pool");
    }

    Entity root = Entity::deserialize_hierarchy(_root, target_scene, parent);
    if (!root.valid()) {
        return failure(
            PrefabDocumentError::SourceMaterializationFailed,
            "failed to materialize prefab source hierarchy"
        );
    }

    PrefabDocumentResult result;
    result.document = *this;
    result.root = root;
    result.message = "ok";
    return result;
}

} // namespace termin::prefab
