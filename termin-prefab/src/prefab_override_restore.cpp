#include <termin/prefab/prefab_instance_state.hpp>

#include <algorithm>
#include <charconv>
#include <cmath>
#include <limits>
#include <optional>
#include <set>
#include <tuple>
#include <unordered_map>
#include <unordered_set>

#include <inspect/tc_inspect_component_adapter.h>
#include <inspect/tc_inspect_context.h>
#include <inspect/tc_kind_cpp.hpp>
#include <tcbase/tc_log.hpp>
#include <tcbase/tc_value_trent.hpp>
#include <termin/prefab/prefab_document.hpp>

namespace termin::prefab {
namespace {

using Error = PrefabOverrideRestoreError;
using Failure = PrefabOverrideRestoreFailure;

Failure failure(const PrefabPropertyOverride& item, Error error, std::string message) {
    tc::Log::error(
        "[PrefabPropertyApply] %s/%s/%s: %s",
        item.source_entity_id.c_str(),
        item.source_component_id.c_str(),
        item.field_path.c_str(),
        message.c_str()
    );
    return {
        error,
        item.source_entity_id,
        item.source_component_id,
        item.field_path,
        std::move(message),
    };
}

const nos::trent* find_source_entity(
    const nos::trent& entity,
    const std::string& source_id
) {
    if (!entity.is_dict()) return nullptr;
    if (entity["uuid"].as_string_default("") == source_id) return &entity;
    if (!entity.contains("children") || !entity["children"].is_list()) return nullptr;
    for (const nos::trent& child : entity["children"].as_list()) {
        if (const nos::trent* found = find_source_entity(child, source_id)) {
            return found;
        }
    }
    return nullptr;
}

const nos::trent* find_source_component(
    const nos::trent& entity,
    const std::string& source_id
) {
    if (!entity.contains("components") || !entity["components"].is_list()) return nullptr;
    for (const nos::trent& component : entity["components"].as_list()) {
        if (component.is_dict() &&
            component["source_id"].as_string_default("") == source_id) {
            return &component;
        }
    }
    return nullptr;
}

tc_component* find_runtime_component(
    const Entity& owner,
    const std::string& source_id,
    bool& duplicate
) {
    duplicate = false;
    tc_component* result = nullptr;
    for (size_t index = 0; index < owner.component_count(); ++index) {
        tc_component* candidate = owner.component_at(index);
        if (candidate == nullptr || source_id != tc_component_get_source_id(candidate)) continue;
        if (result != nullptr) {
            duplicate = true;
            return nullptr;
        }
        result = candidate;
    }
    return result;
}

bool finite_vector(const nos::trent& value, size_t size, double* result) {
    if (!value.is_list() || value.as_list().size() != size) return false;
    for (size_t index = 0; index < size; ++index) {
        if (!value.as_list()[index].is_numer()) return false;
        result[index] = static_cast<double>(value.as_list()[index].as_numer());
        if (!std::isfinite(result[index])) return false;
    }
    return true;
}

const nos::trent* entity_source_value(
    const nos::trent& source,
    const std::string& field_path
) {
    if (field_path == "transform.position") {
        if (!source.contains("pose") || !source["pose"].is_dict() ||
            !source["pose"].contains("position")) return nullptr;
        return &source["pose"]["position"];
    }
    if (field_path == "transform.rotation") {
        if (!source.contains("pose") || !source["pose"].is_dict() ||
            !source["pose"].contains("rotation")) return nullptr;
        return &source["pose"]["rotation"];
    }
    if (field_path == "transform.scale") {
        return source.contains("scale") ? &source["scale"] : nullptr;
    }
    static const char* fields[] = {
        "name", "visible", "enabled", "pickable", "selectable",
        "priority", "layer", "flags",
    };
    for (const char* candidate : fields) {
        if (field_path == candidate) {
            return source.contains(candidate) ? &source[candidate] : nullptr;
        }
    }
    return nullptr;
}

bool require_kind(
    const PrefabPropertyOverride& item,
    const char* expected,
    Failure& result
) {
    if (item.target_kind == expected) return true;
    result = failure(
        item,
        Error::KindMismatch,
        "target kind '" + item.target_kind + "' does not match source field kind '" +
            expected + "'"
    );
    return false;
}

std::optional<Failure> apply_entity_value(
    const PrefabPropertyOverride& item,
    const nos::trent& source,
    Entity runtime
) {
    const nos::trent* value = entity_source_value(source, item.field_path);
    if (value == nullptr) {
        return failure(item, Error::FieldNotFound,
                       "entity field is not part of the native prefab path grammar or is absent");
    }

    Failure kind_failure;
    if (item.field_path == "name") {
        if (!require_kind(item, "string", kind_failure)) return kind_failure;
        if (!value->is_string()) {
            return failure(item, Error::InvalidSourceValue, "source name must be a string");
        }
        runtime.set_name(value->as_string());
        return std::nullopt;
    }
    if (item.field_path == "visible" || item.field_path == "enabled" ||
        item.field_path == "pickable" || item.field_path == "selectable") {
        if (!require_kind(item, "bool", kind_failure)) return kind_failure;
        if (!value->is_bool()) {
            return failure(item, Error::InvalidSourceValue, "source flag must be a boolean");
        }
        const bool flag = value->as_bool();
        if (item.field_path == "visible") runtime.set_visible(flag);
        else if (item.field_path == "enabled") runtime.set_enabled(flag);
        else if (item.field_path == "pickable") runtime.set_pickable(flag);
        else runtime.set_selectable(flag);
        return std::nullopt;
    }
    if (item.field_path == "priority") {
        if (!require_kind(item, "int", kind_failure)) return kind_failure;
        if (!value->is_numer() || !std::isfinite(static_cast<double>(value->as_numer())) ||
            value->as_numer() != static_cast<long double>(value->as_integer()) ||
            value->as_integer() < std::numeric_limits<int>::min() ||
            value->as_integer() > std::numeric_limits<int>::max()) {
            return failure(item, Error::InvalidSourceValue,
                           "source priority must fit a signed native int");
        }
        runtime.set_priority(static_cast<int>(value->as_integer()));
        return std::nullopt;
    }
    if (item.field_path == "layer" || item.field_path == "flags") {
        if (!require_kind(item, "uint64", kind_failure)) return kind_failure;
        if (!value->is_numer() || !std::isfinite(static_cast<double>(value->as_numer())) ||
            value->as_numer() != static_cast<long double>(value->as_integer()) ||
            value->as_integer() < 0) {
            return failure(item, Error::InvalidSourceValue,
                           "source bit field must be a non-negative integer");
        }
        const uint64_t bits = static_cast<uint64_t>(value->as_integer());
        if (item.field_path == "layer") runtime.set_layer(bits);
        else runtime.set_flags(bits);
        return std::nullopt;
    }

    const bool rotation = item.field_path == "transform.rotation";
    if (!require_kind(item, rotation ? "quat" : "vec3", kind_failure)) return kind_failure;
    double data[4] = {};
    if (!finite_vector(*value, rotation ? 4 : 3, data)) {
        return failure(item, Error::InvalidSourceValue,
                       rotation ? "source rotation must contain four finite numbers"
                                : "source transform vector must contain three finite numbers");
    }
    if (item.field_path == "transform.position") runtime.set_local_position(data);
    else if (rotation) runtime.set_local_rotation(data);
    else runtime.set_local_scale(data);
    return std::nullopt;
}

std::optional<Failure> apply_component_value(
    const PrefabPropertyOverride& item,
    const nos::trent& source_entity,
    Entity runtime_entity,
    const PrefabInstanceState& state
) {
    const nos::trent* source_component = find_source_component(
        source_entity, item.source_component_id);
    if (source_component == nullptr) {
        return failure(item, Error::SourceComponentNotFound,
                       "source component ID does not belong to the source entity");
    }

    Entity owner = state.component_owner_for_source(item.source_component_id);
    if (!owner.valid()) {
        return failure(item, Error::RuntimeComponentNotFound,
                       "runtime component owner mapping does not resolve");
    }
    if (owner != runtime_entity) {
        return failure(item, Error::ComponentOwnerMismatch,
                       "runtime component owner does not match the mapped source entity");
    }

    bool duplicate = false;
    tc_component* runtime_component = find_runtime_component(
        owner, item.source_component_id, duplicate);
    if (runtime_component == nullptr) {
        return failure(
            item,
            Error::RuntimeComponentNotFound,
            duplicate ? "multiple runtime components share the source component ID"
                      : "runtime component with the source component ID is absent"
        );
    }

    const std::string source_type = (*source_component)["type"].as_string_default("");
    const char* runtime_type_c = tc_component_type_name(runtime_component);
    const std::string runtime_type = runtime_type_c ? runtime_type_c : "";
    if (source_type.empty() || source_type != runtime_type) {
        return failure(item, Error::ComponentTypeMismatch,
                       "runtime component type does not match the current source component type");
    }

    if (!source_component->contains("data") || !(*source_component)["data"].is_dict() ||
        !(*source_component)["data"].contains(item.field_path)) {
        return failure(item, Error::FieldNotFound,
                       "current source component has no serialized value for the field");
    }
    const nos::trent& component_data = (*source_component)["data"];
    if (item.field_path == "display_name") {
        if (item.target_kind != "string" || !component_data[item.field_path].is_string()) {
            return failure(item, Error::InvalidSourceValue,
                           "component display_name must be a string");
        }
        tc_component_set_display_name(
            runtime_component, component_data[item.field_path].as_string().c_str());
        return std::nullopt;
    }
    if (item.field_path == "enabled" || item.field_path == "active_in_editor") {
        if (item.target_kind != "bool" || !component_data[item.field_path].is_bool()) {
            return failure(item, Error::InvalidSourceValue,
                           "component lifecycle field must be a boolean");
        }
        if (item.field_path == "enabled") {
            tc_component_set_enabled(runtime_component, component_data[item.field_path].as_bool());
        } else {
            tc_component_set_active_in_editor(
                runtime_component, component_data[item.field_path].as_bool());
        }
        return std::nullopt;
    }

    tc_field_info field{};
    if (!tc_inspect_find_field_info(runtime_type.c_str(), item.field_path.c_str(), &field)) {
        return failure(item, Error::FieldNotFound, "inspect field is not registered");
    }
    if (!field.is_serializable) {
        return failure(item, Error::FieldNotSerializable,
                       "inspect field is not part of serialized prefab source data");
    }
    if (field.kind == nullptr || item.target_kind != field.kind) {
        return failure(item, Error::KindMismatch,
                       "stored target kind does not match current inspect field kind");
    }
    nos::trent source_value = component_data[item.field_path];
    auto remap_entity_reference = [&state](nos::trent& reference) -> bool {
        if (!reference.is_dict() || !reference.contains("uuid") ||
            !reference["uuid"].is_string()) return false;
        Entity mapped = state.entity_for_source(reference["uuid"].as_string());
        if (!mapped.valid()) return false;
        reference["uuid"] = std::string(mapped.uuid() ? mapped.uuid() : "");
        return true;
    };
    if (item.target_kind == "entity") {
        if (!remap_entity_reference(source_value)) {
            return failure(item, Error::InvalidSourceValue,
                           "source entity reference does not resolve through instance mapping");
        }
    } else if (item.target_kind == "list[entity]") {
        if (!source_value.is_list()) {
            return failure(item, Error::InvalidSourceValue,
                           "source entity reference list must be an array");
        }
        for (nos::trent& reference : source_value.as_list()) {
            if (!remap_entity_reference(reference)) {
                return failure(item, Error::InvalidSourceValue,
                               "source entity reference list contains an unmapped identity");
            }
        }
    }
    tc_scene_handle scene = tc_entity_pool_get_scene(runtime_entity.pool_ptr());
    tc_scene_inspect_context context = tc_scene_inspect_context_make(scene);
    tc_value serialized_value = tc::trent_to_tc_value(source_value);
    const tc::KindCpp* kind = tc::KindRegistryCpp::instance().get(item.target_kind);
    if (kind != nullptr && kind->is_handle &&
        !tc::KindRegistryCpp::instance()
             .deserialize(item.target_kind, &serialized_value, &context)
             .has_value()) {
        tc_value_free(&serialized_value);
        return failure(item, Error::ResourceResolutionFailed,
                       "serialized handle UUID does not resolve in the native runtime registry");
    }
    tc_value one_field = tc_value_dict_new();
    tc_value_dict_set(&one_field, item.field_path.c_str(), serialized_value);
    const tc_inspect_apply_result applied = tc_component_inspect_deserialize_checked(
        runtime_component, &one_field, &context);
    tc_value_free(&one_field);
    if (applied.status != TC_INSPECT_APPLY_OK || applied.applied_fields != 1) {
        const Error code = applied.status == TC_INSPECT_APPLY_KIND_CONVERSION_FAILED
            ? Error::InvalidSourceValue
            : Error::SetterFailed;
        return failure(item, code,
                       "inspect rejected the current serialized source value");
    }
    return std::nullopt;
}

std::optional<Failure> apply_source_value(
    const PrefabPropertyOverride& item,
    const PrefabDocument& document,
    const PrefabInstanceState& state
) {
    const nos::trent* source_entity = find_source_entity(
        document.source_hierarchy(), item.source_entity_id);
    if (source_entity == nullptr) {
        return failure(item, Error::SourceEntityNotFound,
                       "source entity ID is absent from the current prefab document");
    }
    Entity runtime_entity = state.entity_for_source(item.source_entity_id);
    if (!runtime_entity.valid()) {
        return failure(item, Error::RuntimeEntityNotFound,
                       "runtime entity mapping does not resolve");
    }
    if (item.source_component_id.empty()) {
        return apply_entity_value(item, *source_entity, runtime_entity);
    }
    return apply_component_value(item, *source_entity, runtime_entity, state);
}

std::optional<Failure> validate_operation(
    const PrefabInstanceState& state,
    const PrefabDocument& document,
    const PrefabPropertyOverride& identity
) {
    const PrefabDocumentResult validation = document.validate();
    if (!validation.ok()) {
        return failure(identity, Error::InvalidDocument,
                       "current prefab document is invalid: " + validation.message);
    }
    if (document.asset_uuid() != state.prefab_asset_uuid()) {
        return failure(identity, Error::DocumentMismatch,
                       "prefab document asset UUID does not match the instance state");
    }
    if (!state.overrides_valid()) {
        return failure(identity, Error::InvalidState,
                       "property override metadata is invalid and requires explicit repair");
    }
    if (!state.mapping_valid()) {
        return failure(identity, Error::InvalidState,
                       "prefab source-to-runtime mapping is invalid");
    }
    return std::nullopt;
}

PrefabReconcileFailure reconcile_failure(
    PrefabReconcilePhase phase,
    const Failure& source
) {
    return {
        phase,
        source.error,
        source.source_entity_id,
        source.source_component_id,
        source.field_path,
        source.message,
    };
}

struct SourceIndex {
    std::unordered_map<std::string, const nos::trent*> entities;
    std::unordered_map<std::string, const nos::trent*> components;
    std::unordered_map<std::string, std::string> entity_parents;
    std::unordered_map<std::string, std::string> component_owners;
};

void index_source_entity(
    const nos::trent& entity,
    const std::string& parent_id,
    SourceIndex& index
) {
    if (!entity.is_dict()) return;
    const std::string entity_id = entity["uuid"].as_string_default("");
    if (entity_id.empty()) return;
    index.entities.emplace(entity_id, &entity);
    index.entity_parents.emplace(entity_id, parent_id);
    if (entity.contains("components") && entity["components"].is_list()) {
        for (const nos::trent& component : entity["components"].as_list()) {
            if (!component.is_dict()) continue;
            const std::string component_id =
                component["source_id"].as_string_default("");
            if (component_id.empty()) continue;
            index.components.emplace(component_id, &component);
            index.component_owners.emplace(component_id, entity_id);
        }
    }
    if (entity.contains("children") && entity["children"].is_list()) {
        for (const nos::trent& child : entity["children"].as_list()) {
            index_source_entity(child, entity_id, index);
        }
    }
}

std::vector<PrefabPropertyOverride> source_properties(const SourceIndex& index) {
    std::vector<PrefabPropertyOverride> result;
    const auto add = [&result](
        const std::string& entity_id,
        const std::string& component_id,
        const std::string& path,
        const std::string& kind
    ) {
        PrefabPropertyOverride item;
        item.source_entity_id = entity_id;
        item.source_component_id = component_id;
        item.field_path = path;
        item.target_kind = kind;
        result.push_back(std::move(item));
    };
    for (const auto& [entity_id, entity] : index.entities) {
        static const std::pair<const char*, const char*> base_fields[] = {
            {"name", "string"}, {"visible", "bool"}, {"enabled", "bool"},
            {"pickable", "bool"}, {"selectable", "bool"}, {"priority", "int"},
            {"layer", "uint64"}, {"flags", "uint64"},
        };
        for (const auto& [path, kind] : base_fields) {
            if (entity->contains(path)) add(entity_id, "", path, kind);
        }
        if (entity->contains("pose") && (*entity)["pose"].is_dict()) {
            if ((*entity)["pose"].contains("position")) {
                add(entity_id, "", "transform.position", "vec3");
            }
            if ((*entity)["pose"].contains("rotation")) {
                add(entity_id, "", "transform.rotation", "quat");
            }
        }
        if (entity->contains("scale")) add(entity_id, "", "transform.scale", "vec3");
    }
    for (const auto& [component_id, component] : index.components) {
        const std::string entity_id = index.component_owners.at(component_id);
        if (!component->contains("data") || !(*component)["data"].is_dict()) continue;
        for (const auto& [path, value] : (*component)["data"].as_dict()) {
            (void)value;
            std::string kind;
            if (path == "display_name") kind = "string";
            else if (path == "enabled" || path == "active_in_editor") kind = "bool";
            else {
                tc_field_info field{};
                const std::string type = (*component)["type"].as_string_default("");
                if (tc_inspect_find_field_info(type.c_str(), path.c_str(), &field) && field.kind) {
                    kind = field.kind;
                }
            }
            add(entity_id, component_id, path, kind);
        }
    }
    std::sort(result.begin(), result.end(), [](const auto& left, const auto& right) {
        return std::tie(left.source_entity_id, left.source_component_id, left.field_path) <
            std::tie(right.source_entity_id, right.source_component_id, right.field_path);
    });
    return result;
}

std::optional<Failure> apply_override_value(
    const PrefabPropertyOverride& item,
    const PrefabDocument& document,
    const PrefabInstanceState& state,
    const PrefabOverrideResourceResolver* resource_resolver
) {
    const nos::trent* source_entity = find_source_entity(
        document.source_hierarchy(), item.source_entity_id);
    if (source_entity == nullptr) {
        return failure(item, Error::SourceEntityNotFound,
                       "override source entity is absent from the current prefab document");
    }
    Entity runtime_entity = state.entity_for_source(item.source_entity_id);
    if (!runtime_entity.valid()) {
        return failure(item, Error::RuntimeEntityNotFound,
                       "override runtime entity mapping does not resolve");
    }

    std::string materialize_error;
    std::optional<tc::trent> materialized = resource_resolver
        ? item.value.materialize_for_inspect(
              item.target_kind, *resource_resolver, materialize_error)
        : item.value.materialize_for_inspect(item.target_kind, materialize_error);
    if (!materialized) {
        const Error code = item.value.tag() == "resource"
            ? Error::ResourceResolutionFailed
            : Error::InvalidSourceValue;
        return failure(item, code, "cannot materialize stored override: " + materialize_error);
    }

    if (item.source_component_id.empty()) {
        if (item.field_path == "layer" || item.field_path == "flags") {
            if (item.target_kind != "uint64") {
                return failure(item, Error::KindMismatch,
                               "entity bit-field override must target uint64");
            }
            uint64_t bits = 0;
            if (materialized->is_integer()) {
                const int64_t signed_bits = materialized->as_integer();
                if (signed_bits < 0) {
                    return failure(item, Error::InvalidSourceValue,
                                   "entity bit-field override must be non-negative");
                }
                bits = static_cast<uint64_t>(signed_bits);
            } else if (materialized->is_string()) {
                const std::string encoded = materialized->as_string();
                const char* begin = encoded.data();
                const char* end = begin + encoded.size();
                const auto parsed = std::from_chars(begin, end, bits);
                if (parsed.ec != std::errc() || parsed.ptr != end ||
                    std::to_string(bits) != encoded) {
                    return failure(item, Error::InvalidSourceValue,
                                   "entity bit-field override is not canonical uint64");
                }
            } else {
                return failure(item, Error::InvalidSourceValue,
                               "entity bit-field override must materialize as an integer");
            }
            if (item.field_path == "layer") runtime_entity.set_layer(bits);
            else runtime_entity.set_flags(bits);
            return std::nullopt;
        }
        nos::trent synthetic;
        const nos::trent value = tc::tc_value_to_trent(*materialized->raw());
        if (item.field_path == "transform.position") {
            synthetic["pose"]["position"] = value;
        } else if (item.field_path == "transform.rotation") {
            synthetic["pose"]["rotation"] = value;
        } else if (item.field_path == "transform.scale") {
            synthetic["scale"] = value;
        } else {
            synthetic[item.field_path] = value;
        }
        return apply_entity_value(item, synthetic, runtime_entity);
    }

    const nos::trent* source_component = find_source_component(
        *source_entity, item.source_component_id);
    if (source_component == nullptr) {
        return failure(item, Error::SourceComponentNotFound,
                       "override source component is absent from its source entity");
    }
    Entity owner = state.component_owner_for_source(item.source_component_id);
    if (!owner.valid() || owner != runtime_entity) {
        return failure(item, owner.valid() ? Error::ComponentOwnerMismatch
                                           : Error::RuntimeComponentNotFound,
                       "override component owner mapping does not resolve to its entity");
    }
    bool duplicate = false;
    tc_component* component = find_runtime_component(owner, item.source_component_id, duplicate);
    if (component == nullptr) {
        return failure(item, Error::RuntimeComponentNotFound,
                       duplicate ? "multiple runtime components share the source component ID"
                                 : "runtime override component is absent");
    }
    const std::string source_type = (*source_component)["type"].as_string_default("");
    const std::string runtime_type = tc_component_type_name(component)
        ? tc_component_type_name(component) : "";
    if (source_type.empty() || source_type != runtime_type) {
        return failure(item, Error::ComponentTypeMismatch,
                       "override target component type drifted from the source document");
    }
    if (item.field_path == "display_name") {
        if (item.target_kind != "string" || !materialized->is_string()) {
            return failure(item, Error::KindMismatch,
                           "display_name override must materialize as string");
        }
        tc_component_set_display_name(component, materialized->as_c_str());
        return std::nullopt;
    }
    if (item.field_path == "enabled" || item.field_path == "active_in_editor") {
        if (item.target_kind != "bool" || !materialized->is_bool()) {
            return failure(item, Error::KindMismatch,
                           "component lifecycle override must materialize as bool");
        }
        if (item.field_path == "enabled") {
            tc_component_set_enabled(component, materialized->as_bool());
        } else {
            tc_component_set_active_in_editor(component, materialized->as_bool());
        }
        return std::nullopt;
    }
    tc_field_info field{};
    if (!tc_inspect_find_field_info(runtime_type.c_str(), item.field_path.c_str(), &field)) {
        return failure(item, Error::FieldNotFound, "override inspect field is not registered");
    }
    if (!field.is_serializable) {
        return failure(item, Error::FieldNotSerializable,
                       "override target field is not serializable");
    }
    if (field.kind == nullptr || item.target_kind != field.kind) {
        return failure(item, Error::KindMismatch,
                       "stored override kind does not match current inspect field kind");
    }
    tc_scene_handle scene = tc_entity_pool_get_scene(runtime_entity.pool_ptr());
    tc_scene_inspect_context context = tc_scene_inspect_context_make(scene);
    tc_value one_field = tc_value_dict_new();
    tc_value_dict_set(
        &one_field, item.field_path.c_str(), tc_value_copy(materialized->raw()));
    const tc_inspect_apply_result applied = tc_component_inspect_deserialize_checked(
        component, &one_field, &context);
    tc_value_free(&one_field);
    if (applied.status != TC_INSPECT_APPLY_OK || applied.applied_fields != 1) {
        const Error code = applied.status == TC_INSPECT_APPLY_KIND_CONVERSION_FAILED
            ? Error::InvalidSourceValue : Error::SetterFailed;
        return failure(item, code, "inspect rejected the stored override value");
    }
    return std::nullopt;
}

} // namespace

PrefabOverrideRestoreResult PrefabInstanceState::clear_property_override(
    const PrefabDocument& source,
    const std::string& source_entity_id,
    const std::string& source_component_id,
    const std::string& field_path
) {
    PrefabOverrideRestoreResult result;
    result.requested_count = 1;
    PrefabPropertyOverride identity;
    identity.source_entity_id = source_entity_id;
    identity.source_component_id = source_component_id;
    identity.field_path = field_path;

    if (auto invalid = validate_operation(*this, source, identity)) {
        result.failures.push_back(std::move(*invalid));
        return result;
    }
    const PrefabPropertyOverride* stored = property_override(
        source_entity_id, source_component_id, field_path);
    if (stored == nullptr) {
        result.failures.push_back(failure(
            identity, Error::OverrideNotFound, "property override does not exist"));
        return result;
    }

    const PrefabPropertyOverride snapshot = *stored;
    if (auto failed = apply_source_value(snapshot, source, *this)) {
        result.failures.push_back(std::move(*failed));
        return result;
    }
    if (!discard_property_override(source_entity_id, source_component_id, field_path)) {
        result.failures.push_back(failure(
            snapshot, Error::InvalidState,
            "override disappeared after its source value was restored"));
        return result;
    }
    result.restored_count = 1;
    return result;
}

PrefabOverrideRestoreResult PrefabInstanceState::clear_all_property_overrides(
    const PrefabDocument& source
) {
    PrefabOverrideRestoreResult result;
    result.requested_count = _property_overrides.size();
    PrefabPropertyOverride identity;
    if (auto invalid = validate_operation(*this, source, identity)) {
        result.failures.push_back(std::move(*invalid));
        return result;
    }

    std::vector<PrefabPropertyOverride> snapshot = _property_overrides;
    std::sort(snapshot.begin(), snapshot.end(), [](const auto& left, const auto& right) {
        return std::tie(left.source_entity_id, left.source_component_id, left.field_path) <
            std::tie(right.source_entity_id, right.source_component_id, right.field_path);
    });
    for (const PrefabPropertyOverride& item : snapshot) {
        if (auto failed = apply_source_value(item, source, *this)) {
            result.failures.push_back(std::move(*failed));
            continue;
        }
        if (!discard_property_override(
                item.source_entity_id, item.source_component_id, item.field_path)) {
            result.failures.push_back(failure(
                item, Error::InvalidState,
                "override disappeared after its source value was restored"));
            continue;
        }
        ++result.restored_count;
    }
    return result;
}

PrefabReconcileResult PrefabInstanceState::reconcile_properties(
    const PrefabDocument& source,
    const PrefabOverrideResourceResolver* resource_resolver
) {
    PrefabReconcileResult result;
    result.previous_revision = source_revision();
    result.target_revision = source.source_revision();

    PrefabPropertyOverride identity;
    if (auto invalid = validate_operation(*this, source, identity)) {
        result.failures.push_back(reconcile_failure(
            PrefabReconcilePhase::Validation, *invalid));
        return result;
    }

    SourceIndex index;
    index_source_entity(source.source_hierarchy(), "", index);
    const auto has_entity_mapping = [this](const std::string& source_id) {
        return std::find(_source_entity_ids.begin(), _source_entity_ids.end(), source_id) !=
            _source_entity_ids.end();
    };
    const auto has_component_mapping = [this](const std::string& source_id) {
        return std::find(_source_component_ids.begin(), _source_component_ids.end(), source_id) !=
            _source_component_ids.end();
    };
    const auto structural = [&result](
        Error error,
        std::string entity_id,
        std::string component_id,
        std::string message
    ) {
        Failure item;
        item.error = error;
        item.source_entity_id = std::move(entity_id);
        item.source_component_id = std::move(component_id);
        item.message = std::move(message);
        tc::Log::error("[PrefabReconcile] %s", item.message.c_str());
        result.failures.push_back(reconcile_failure(
            PrefabReconcilePhase::Structure, item));
    };

    const std::string root_source_id =
        source.source_hierarchy()["uuid"].as_string_default("");
    if (root_source_id.empty() || entity_for_source(root_source_id) != entity()) {
        structural(Error::ComponentOwnerMismatch, root_source_id, "",
                   "PrefabInstanceState is not attached to its mapped source root");
    }

    for (const auto& [source_id, source_entity] : index.entities) {
        (void)source_entity;
        if (!has_entity_mapping(source_id)) {
            structural(Error::RuntimeEntityNotFound, source_id, "",
                       "source entity has no runtime mapping; structural additions are not reconciled");
            continue;
        }
        Entity runtime = entity_for_source(source_id);
        if (!runtime.valid()) {
            structural(Error::RuntimeEntityNotFound, source_id, "",
                       "mapped runtime entity is no longer live");
            continue;
        }
        const std::string& source_parent_id = index.entity_parents.at(source_id);
        if (!source_parent_id.empty()) {
            Entity expected_parent = entity_for_source(source_parent_id);
            if (!expected_parent.valid() || runtime.parent() != expected_parent) {
                structural(Error::ComponentOwnerMismatch, source_id, "",
                           "mapped entity parent differs from the current source hierarchy");
            }
        }
    }
    for (const std::string& source_id : _source_entity_ids) {
        if (!index.entities.contains(source_id)) {
            structural(Error::SourceEntityNotFound, source_id, "",
                       "mapped source entity was removed; structural removals are not reconciled");
        }
    }
    for (const auto& [component_id, source_component] : index.components) {
        if (!has_component_mapping(component_id)) {
            structural(Error::RuntimeComponentNotFound,
                       index.component_owners.at(component_id), component_id,
                       "source component has no runtime mapping; structural additions are not reconciled");
            continue;
        }
        const std::string& entity_id = index.component_owners.at(component_id);
        Entity owner = component_owner_for_source(component_id);
        Entity expected_owner = entity_for_source(entity_id);
        if (!owner.valid() || owner != expected_owner) {
            structural(Error::ComponentOwnerMismatch, entity_id, component_id,
                       "mapped component owner differs from the source owner");
            continue;
        }
        bool duplicate = false;
        tc_component* runtime = find_runtime_component(owner, component_id, duplicate);
        if (runtime == nullptr) {
            structural(Error::RuntimeComponentNotFound, entity_id, component_id,
                       duplicate ? "multiple runtime components share the source component ID"
                                 : "mapped runtime component is absent");
            continue;
        }
        const std::string source_type =
            source_component->operator[]("type").as_string_default("");
        const char* runtime_type = tc_component_type_name(runtime);
        if (runtime_type == nullptr || source_type != runtime_type) {
            structural(Error::ComponentTypeMismatch, entity_id, component_id,
                       "mapped runtime component type differs from the current source type");
        }
    }
    for (const std::string& source_id : _source_component_ids) {
        if (!index.components.contains(source_id)) {
            structural(Error::SourceComponentNotFound, "", source_id,
                       "mapped source component was removed; structural removals are not reconciled");
        }
    }

    std::vector<PrefabPropertyOverride> overrides = _property_overrides;
    std::sort(overrides.begin(), overrides.end(), [](const auto& left, const auto& right) {
        return std::tie(left.source_entity_id, left.source_component_id, left.field_path) <
            std::tie(right.source_entity_id, right.source_component_id, right.field_path);
    });
    result.override_count = overrides.size();
    std::set<std::tuple<std::string, std::string, std::string>> overridden;
    for (const PrefabPropertyOverride& item : overrides) {
        overridden.emplace(item.source_entity_id, item.source_component_id, item.field_path);
    }

    const std::vector<PrefabPropertyOverride> properties = source_properties(index);
    for (const PrefabPropertyOverride& item : properties) {
        Entity runtime_entity = entity_for_source(item.source_entity_id);
        if (!has_entity_mapping(item.source_entity_id) || !runtime_entity.valid()) {
            continue;
        }
        if (!item.source_component_id.empty()) {
            if (!has_component_mapping(item.source_component_id)) continue;
            Entity owner = component_owner_for_source(item.source_component_id);
            bool duplicate = false;
            tc_component* runtime_component = owner.valid()
                ? find_runtime_component(owner, item.source_component_id, duplicate) : nullptr;
            const nos::trent* source_component = index.components.contains(
                item.source_component_id)
                ? index.components.at(item.source_component_id) : nullptr;
            const std::string source_type = source_component != nullptr
                ? (*source_component)["type"].as_string_default("") : "";
            const char* runtime_type = runtime_component != nullptr
                ? tc_component_type_name(runtime_component) : nullptr;
            if (owner != runtime_entity || duplicate || runtime_component == nullptr ||
                runtime_type == nullptr || source_type != runtime_type) {
                continue;
            }
        }
        if (overridden.contains({
                item.source_entity_id, item.source_component_id, item.field_path})) {
            continue;
        }
        ++result.source_field_count;
        if (auto failed = apply_source_value(item, source, *this)) {
            result.failures.push_back(reconcile_failure(
                PrefabReconcilePhase::SourceValue, *failed));
        } else {
            ++result.source_fields_applied;
        }
    }
    for (const PrefabPropertyOverride& item : overrides) {
        if (auto failed = apply_override_value(
                item, source, *this, resource_resolver)) {
            result.failures.push_back(reconcile_failure(
                PrefabReconcilePhase::OverrideValue, *failed));
        } else {
            ++result.overrides_applied;
        }
    }

    std::sort(result.failures.begin(), result.failures.end(), [](const auto& left, const auto& right) {
        return std::tie(left.phase, left.source_entity_id, left.source_component_id,
                        left.field_path, left.error) <
            std::tie(right.phase, right.source_entity_id, right.source_component_id,
                     right.field_path, right.error);
    });
    if (result.failures.empty() &&
        result.source_fields_applied == result.source_field_count &&
        result.overrides_applied == result.override_count) {
        set_source_revision(result.target_revision);
        result.revision_updated = true;
    }
    return result;
}

} // namespace termin::prefab
