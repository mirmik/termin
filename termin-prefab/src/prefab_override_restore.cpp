#include <termin/prefab/prefab_instance_state.hpp>

#include <algorithm>
#include <cmath>
#include <limits>
#include <optional>
#include <tuple>

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
        "[PrefabOverrideRestore] %s/%s/%s: %s",
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
    if (!source_component->contains("data") || !(*source_component)["data"].is_dict() ||
        !(*source_component)["data"].contains(item.field_path)) {
        return failure(item, Error::FieldNotFound,
                       "current source component has no serialized value for the inspect field");
    }

    nos::trent source_value = (*source_component)["data"][item.field_path];
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

} // namespace termin::prefab
