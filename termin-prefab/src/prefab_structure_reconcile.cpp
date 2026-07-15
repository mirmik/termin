#include <termin/prefab/prefab_instance_state.hpp>

#include <algorithm>
#include <functional>
#include <unordered_map>
#include <unordered_set>

#include <inspect/tc_inspect_component_adapter.h>
#include <inspect/tc_inspect_context.h>
#include <tcbase/tc_log.hpp>
#include <tcbase/tc_value_trent.hpp>
#include <termin/entity/component.hpp>
#include <termin/entity/component_registry.hpp>
#include <termin/prefab/prefab_document.hpp>

namespace termin::prefab {
namespace {

using Error = PrefabPropertyApplyError;

struct OrderedSourceIndex {
    std::unordered_map<std::string, const nos::trent*> entities;
    std::unordered_map<std::string, const nos::trent*> components;
    std::unordered_map<std::string, std::string> entity_parents;
    std::unordered_map<std::string, std::string> component_owners;
    std::unordered_map<std::string, std::vector<std::string>> children;
    std::unordered_map<std::string, std::vector<std::string>> entity_components;
    std::vector<std::string> entity_preorder;
};

void index_entity(
    const nos::trent& entity,
    const std::string& parent_id,
    OrderedSourceIndex& index
) {
    const std::string entity_id = entity["uuid"].as_string_default("");
    if (entity_id.empty()) return;
    index.entities.emplace(entity_id, &entity);
    index.entity_parents.emplace(entity_id, parent_id);
    index.entity_preorder.push_back(entity_id);
    auto& component_order = index.entity_components[entity_id];
    if (entity.contains("components") && entity["components"].is_list()) {
        for (const nos::trent& component : entity["components"].as_list()) {
            const std::string component_id =
                component["source_id"].as_string_default("");
            if (component_id.empty()) continue;
            index.components.emplace(component_id, &component);
            index.component_owners.emplace(component_id, entity_id);
            component_order.push_back(component_id);
        }
    }
    auto& child_order = index.children[entity_id];
    if (entity.contains("children") && entity["children"].is_list()) {
        for (const nos::trent& child : entity["children"].as_list()) {
            const std::string child_id = child["uuid"].as_string_default("");
            if (!child_id.empty()) child_order.push_back(child_id);
            index_entity(child, entity_id, index);
        }
    }
}

void add_failure(
    PrefabReconcileResult& result,
    Error error,
    const std::string& entity_id,
    const std::string& component_id,
    std::string message
) {
    tc::Log::error("[PrefabStructureReconcile] %s", message.c_str());
    result.failures.push_back({
        PrefabReconcilePhase::Structure,
        error,
        entity_id,
        component_id,
        "",
        std::move(message),
    });
}

std::vector<tc_component*> components_for_source(
    Entity owner,
    const std::string& source_id
) {
    std::vector<tc_component*> result;
    for (size_t index = 0; index < owner.component_count(); ++index) {
        tc_component* candidate = owner.component_at(index);
        if (candidate == nullptr || source_id != tc_component_get_source_id(candidate)) {
            continue;
        }
        result.push_back(candidate);
    }
    return result;
}

tc_component* find_component(Entity owner, const std::string& source_id) {
    const std::vector<tc_component*> matches = components_for_source(owner, source_id);
    return matches.size() == 1 ? matches.front() : nullptr;
}

bool has_assignable_component(Entity owner, const char* required_type) {
    for (size_t index = 0; index < owner.component_count(); ++index) {
        tc_component* component = owner.component_at(index);
        const char* type = component ? tc_component_type_name(component) : nullptr;
        if (type != nullptr && tc_component_registry_is_a(type, required_type)) return true;
    }
    return false;
}

bool is_descendant_or_self(Entity entity, Entity ancestor) {
    for (Entity current = entity; current.valid(); current = current.parent()) {
        if (current == ancestor) return true;
    }
    return false;
}

std::string mapped_source_for_entity(
    const std::vector<std::string>& ids,
    const std::vector<Entity>& entities,
    Entity entity
) {
    const size_t count = std::min(ids.size(), entities.size());
    for (size_t index = 0; index < count; ++index) {
        if (entities[index] == entity) return ids[index];
    }
    return {};
}

bool property_targets_component(
    const std::vector<PrefabPropertyOverride>& overrides,
    const std::string& component_id
) {
    return std::any_of(overrides.begin(), overrides.end(), [&](const auto& item) {
        return item.source_component_id == component_id;
    });
}

bool property_targets_entity(
    const std::vector<PrefabPropertyOverride>& overrides,
    const std::string& entity_id
) {
    return std::any_of(overrides.begin(), overrides.end(), [&](const auto& item) {
        return item.source_entity_id == entity_id;
    });
}

bool component_override_compatible(
    const nos::trent& source_component,
    const std::vector<PrefabPropertyOverride>& overrides,
    std::string& message
) {
    const std::string component_id = source_component["source_id"].as_string_default("");
    const std::string type = source_component["type"].as_string_default("");
    for (const PrefabPropertyOverride& item : overrides) {
        if (item.source_component_id != component_id) continue;
        if (item.field_path == "display_name") {
            if (item.target_kind == "string") continue;
        } else if (item.field_path == "enabled" ||
                   item.field_path == "active_in_editor") {
            if (item.target_kind == "bool") continue;
        } else {
            tc_field_info field{};
            if (tc_inspect_find_field_info(type.c_str(), item.field_path.c_str(), &field) &&
                field.is_serializable && field.kind != nullptr &&
                item.target_kind == field.kind) {
                continue;
            }
        }
        message = "component type replacement is incompatible with stored property override '" +
            item.field_path + "'";
        return false;
    }
    return true;
}

std::vector<std::string> dependency_ordered_components(
    const std::vector<std::string>& source_order,
    const OrderedSourceIndex& index
) {
    std::vector<std::string> result;
    std::unordered_set<std::string> visiting;
    std::unordered_set<std::string> visited;
    std::function<void(const std::string&)> visit = [&](const std::string& component_id) {
        if (visited.contains(component_id) || !visiting.insert(component_id).second) return;
        const std::string type =
            (*index.components.at(component_id))["type"].as_string_default("");
        for (size_t requirement_index = 0;
             requirement_index < tc_component_registry_requirement_count(type.c_str());
             ++requirement_index) {
            const char* required = tc_component_registry_requirement_at(
                type.c_str(), requirement_index);
            if (required == nullptr) continue;
            for (const std::string& candidate_id : source_order) {
                const std::string candidate_type =
                    (*index.components.at(candidate_id))["type"].as_string_default("");
                if (tc_component_registry_is_a(candidate_type.c_str(), required)) {
                    visit(candidate_id);
                    break;
                }
            }
        }
        visiting.erase(component_id);
        visited.insert(component_id);
        result.push_back(component_id);
    };
    for (const std::string& component_id : source_order) visit(component_id);
    return result;
}

tc_component* create_component_checked(
    Entity owner,
    const nos::trent& source_component,
    const std::unordered_map<std::string, std::string>& uuid_remap,
    std::string& message
) {
    const std::string type = source_component["type"].as_string_default("");
    const std::string source_id = source_component["source_id"].as_string_default("");
    if (type.empty() || !tc_component_registry_has(type.c_str())) {
        message = "source component factory is unavailable for type '" + type + "'";
        return nullptr;
    }
    for (size_t index = 0; index < tc_component_registry_requirement_count(type.c_str());
         ++index) {
        const char* required = tc_component_registry_requirement_at(type.c_str(), index);
        if (required == nullptr || has_assignable_component(owner, required)) continue;
        message = "required component '" + std::string(required) +
            "' must be source-owned or explicitly present before attaching '" + type + "'";
        return nullptr;
    }

    tc_component* component = tc_component_registry_create(type.c_str());
    if (component == nullptr) {
        message = "component factory failed for type '" + type + "'";
        return nullptr;
    }
    tc_component_set_source_id(component, source_id.c_str());

    nos::trent data;
    if (source_component.contains("data")) {
        data = source_component["data"];
    } else {
        data.init(nos::trent::type::dict);
    }
    nos::trent synthetic;
    synthetic["components"].init(nos::trent::type::list);
    nos::trent encoded = source_component;
    encoded["data"] = data;
    synthetic["components"].push_back(std::move(encoded));
    Entity::remap_entity_refs(synthetic, uuid_remap);
    data = synthetic["components"].as_list()[0]["data"];

    if (data.is_dict()) {
        if (data.contains("display_name") && data["display_name"].is_string()) {
            tc_component_set_display_name(
                component, data["display_name"].as_string().c_str());
            data.as_dict().erase("display_name");
        }
        if (data.contains("enabled") && data["enabled"].is_bool()) {
            tc_component_set_enabled(component, data["enabled"].as_bool());
            data.as_dict().erase("enabled");
        }
        if (data.contains("active_in_editor") && data["active_in_editor"].is_bool()) {
            tc_component_set_active_in_editor(
                component, data["active_in_editor"].as_bool());
            data.as_dict().erase("active_in_editor");
        }
    }
    tc_value serialized = tc::trent_to_tc_value(data);
    tc_scene_inspect_context context = tc_scene_inspect_context_make(
        tc_entity_pool_get_scene(owner.pool_ptr()));
    const tc_inspect_apply_result applied = tc_component_inspect_deserialize_checked(
        component, &serialized, &context);
    tc_value_free(&serialized);
    if (applied.status != TC_INSPECT_APPLY_OK) {
        message = "checked deserialization rejected source component type '" + type + "'";
        tc_component_drop(component);
        return nullptr;
    }
    return component;
}

template<typename T>
void erase_parallel(std::vector<std::string>& ids, std::vector<T>& values, size_t index) {
    ids.erase(ids.begin() + static_cast<std::ptrdiff_t>(index));
    values.erase(values.begin() + static_cast<std::ptrdiff_t>(index));
}

} // namespace

void PrefabInstanceState::reconcile_structure(
    const PrefabDocument& source,
    PrefabReconcileResult& result
) {
    OrderedSourceIndex index;
    index_entity(source.source_hierarchy(), "", index);
    const std::string root_id = source.source_hierarchy()["uuid"].as_string_default("");
    if (root_id.empty() || entity_for_source(root_id) != entity()) {
        add_failure(result, Error::ComponentOwnerMismatch, root_id, "",
                    "PrefabInstanceState is not attached to its mapped source root");
        return;
    }

    std::unordered_set<std::string> suppressed_entities;
    std::unordered_set<std::string> suppressed_components;
    std::unordered_map<std::string, const PrefabStructuralOverride*> entity_placements;
    std::unordered_map<std::string, const PrefabStructuralOverride*> component_placements;
    for (const PrefabStructuralOverride& item : _structural_overrides) {
        switch (item.kind) {
            case PrefabStructuralOverrideKind::SuppressEntity:
                suppressed_entities.insert(item.source_entity_id);
                break;
            case PrefabStructuralOverrideKind::SuppressComponent:
                suppressed_components.insert(item.source_component_id);
                break;
            case PrefabStructuralOverrideKind::PlaceEntity:
                entity_placements.emplace(item.source_entity_id, &item);
                break;
            case PrefabStructuralOverrideKind::PlaceComponent:
                component_placements.emplace(item.source_component_id, &item);
                break;
        }
    }
    if (suppressed_entities.contains(root_id)) {
        add_failure(result, Error::StructuralOverrideInvalid, root_id, "",
                    "the prefab instance root cannot be suppressed");
        suppressed_entities.erase(root_id);
    }
    bool suppression_changed = true;
    while (suppression_changed) {
        suppression_changed = false;
        for (const auto& [entity_id, parent_id] : index.entity_parents) {
            if (!parent_id.empty() && suppressed_entities.contains(parent_id) &&
                suppressed_entities.insert(entity_id).second) {
                suppression_changed = true;
            }
        }
    }
    for (const auto& [component_id, owner_id] : index.component_owners) {
        if (suppressed_entities.contains(owner_id)) {
            suppressed_components.insert(component_id);
        }
    }
    std::vector<std::string> placed_entity_ids;
    placed_entity_ids.reserve(entity_placements.size());
    for (const auto& [source_id, placement] : entity_placements) {
        (void)placement;
        placed_entity_ids.push_back(source_id);
        if (suppressed_entities.contains(source_id)) {
            add_failure(result, Error::StructuralOverrideInvalid, source_id, "",
                        "an entity cannot be both suppressed and explicitly placed");
        }
    }
    std::sort(placed_entity_ids.begin(), placed_entity_ids.end());
    std::vector<std::string> placed_component_ids;
    placed_component_ids.reserve(component_placements.size());
    for (const auto& [source_id, placement] : component_placements) {
        (void)placement;
        placed_component_ids.push_back(source_id);
        if (suppressed_components.contains(source_id)) {
            add_failure(result, Error::StructuralOverrideInvalid, "", source_id,
                        "a component cannot be both suppressed and explicitly placed");
        }
    }
    std::sort(placed_component_ids.begin(), placed_component_ids.end());

    std::unordered_map<std::string, std::string> placement_parents =
        index.entity_parents;
    for (const std::string& source_id : placed_entity_ids) {
        const PrefabStructuralOverride& placement = *entity_placements.at(source_id);
        if (placement.parent.kind == PrefabStructureReferenceKind::Source) {
            placement_parents[source_id] = placement.parent.source_id;
        } else {
            const std::string local_source = mapped_source_for_entity(
                _source_entity_ids, _runtime_entities, placement.parent.local_entity);
            if (!local_source.empty()) placement_parents[source_id] = local_source;
            else placement_parents.erase(source_id);
        }
    }
    std::unordered_map<std::string, int> placement_colors;
    std::string placement_cycle_id;
    std::function<bool(const std::string&)> visit_parent = [&](const std::string& source_id) {
        const int color = placement_colors[source_id];
        if (color == 1) {
            placement_cycle_id = source_id;
            return false;
        }
        if (color == 2) return true;
        placement_colors[source_id] = 1;
        const auto found = placement_parents.find(source_id);
        if (found != placement_parents.end() && !found->second.empty() &&
            !visit_parent(found->second)) return false;
        placement_colors[source_id] = 2;
        return true;
    };
    std::vector<std::string> placement_graph_ids;
    placement_graph_ids.reserve(placement_parents.size());
    for (const auto& [source_id, parent_id] : placement_parents) {
        (void)parent_id;
        placement_graph_ids.push_back(source_id);
    }
    std::sort(placement_graph_ids.begin(), placement_graph_ids.end());
    for (const std::string& source_id : placement_graph_ids) {
        if (!visit_parent(source_id)) {
            add_failure(result, Error::ParentCycle, placement_cycle_id, "",
                        "structural placement graph contains a parent cycle");
            return;
        }
    }
    const auto anchor_cycle = [](
        const std::vector<std::string>& ids,
        const auto& placements
    ) -> std::string {
        std::unordered_map<std::string, int> colors;
        std::string cycle;
        std::function<bool(const std::string&)> visit = [&](const std::string& source_id) {
            const int color = colors[source_id];
            if (color == 1) {
                cycle = source_id;
                return false;
            }
            if (color == 2) return true;
            colors[source_id] = 1;
            const auto found = placements.find(source_id);
            if (found != placements.end() &&
                found->second->before.kind == PrefabStructureReferenceKind::Source &&
                placements.contains(found->second->before.source_id) &&
                !visit(found->second->before.source_id)) {
                return false;
            }
            colors[source_id] = 2;
            return true;
        };
        for (const std::string& source_id : ids) {
            if (!visit(source_id)) return cycle;
        }
        return {};
    };
    if (const std::string cycle = anchor_cycle(
            placed_entity_ids, entity_placements); !cycle.empty()) {
        add_failure(result, Error::OrderFailed, cycle, "",
                    "entity placement anchors contain an ordering cycle");
        return;
    }
    if (const std::string cycle = anchor_cycle(
            placed_component_ids, component_placements); !cycle.empty()) {
        add_failure(result, Error::OrderFailed, "", cycle,
                    "component placement anchors contain an ordering cycle");
        return;
    }

    const auto erase_entity_mapping = [&](const std::string& source_id) {
        const auto found = std::find(_source_entity_ids.begin(), _source_entity_ids.end(), source_id);
        if (found == _source_entity_ids.end()) return;
        erase_parallel(
            _source_entity_ids,
            _runtime_entities,
            static_cast<size_t>(found - _source_entity_ids.begin())
        );
    };
    const auto erase_component_mapping = [&](const std::string& source_id) {
        const auto found = std::find(
            _source_component_ids.begin(), _source_component_ids.end(), source_id);
        if (found == _source_component_ids.end()) return;
        erase_parallel(
            _source_component_ids,
            _component_owners,
            static_cast<size_t>(found - _source_component_ids.begin())
        );
    };

    // Dead mappings are corruption, not intent. Drop them so the source target can be recreated.
    for (size_t position = _source_component_ids.size(); position-- > 0;) {
        Entity owner = _component_owners[position];
        if (!owner.valid() || components_for_source(
                owner, _source_component_ids[position]).empty()) {
            erase_parallel(_source_component_ids, _component_owners, position);
        }
    }
    for (size_t position = _source_entity_ids.size(); position-- > 0;) {
        if (!_runtime_entities[position].valid()) {
            erase_parallel(_source_entity_ids, _runtime_entities, position);
        }
    }

    // Allocate all missing entities before any component values are materialized so references
    // can resolve through the prospective mapping.
    for (const std::string& source_id : index.entity_preorder) {
        if (suppressed_entities.contains(source_id) || entity_for_source(source_id).valid()) {
            continue;
        }
        ++result.structure_operation_count;
        if (source_id == root_id) {
            add_failure(result, Error::RuntimeEntityNotFound, source_id, "",
                        "the mapped prefab root is missing and cannot be replaced in place");
            continue;
        }
        const nos::trent& source_entity = *index.entities.at(source_id);
        Entity created = Entity::create(
            entity().pool_handle(), source_entity["name"].as_string_default("entity"));
        if (!created.valid()) {
            add_failure(result, Error::AttachmentFailed, source_id, "",
                        "failed to allocate a runtime entity for source addition");
            continue;
        }
        _source_entity_ids.push_back(source_id);
        _runtime_entities.push_back(created);
        ++result.structure_operations_applied;
    }

    std::unordered_map<std::string, std::string> uuid_remap;
    for (size_t position = 0; position < _source_entity_ids.size(); ++position) {
        const Entity runtime = _runtime_entities[position];
        if (runtime.valid() && runtime.uuid() != nullptr) {
            uuid_remap.emplace(_source_entity_ids[position], runtime.uuid());
        }
    }
    for (const std::string& source_id : suppressed_entities) {
        uuid_remap[source_id] = "";
    }

    // Canonical source parenting happens before component creation and removal.
    for (const std::string& source_id : index.entity_preorder) {
        if (source_id == root_id || suppressed_entities.contains(source_id) ||
            entity_placements.contains(source_id)) continue;
        Entity runtime = entity_for_source(source_id);
        Entity parent = entity_for_source(index.entity_parents.at(source_id));
        if (!runtime.valid() || !parent.valid() || runtime.parent() == parent) continue;
        ++result.structure_operation_count;
        if (!runtime.set_parent_checked(parent)) {
            add_failure(result, Error::ParentCycle, source_id, "",
                        "source parent relationship is invalid in the runtime hierarchy");
        } else {
            ++result.structure_operations_applied;
        }
    }

    // Add or replace source-owned components.
    for (const std::string& entity_id : index.entity_preorder) {
        if (suppressed_entities.contains(entity_id)) continue;
        Entity owner = entity_for_source(entity_id);
        if (!owner.valid()) continue;
        const std::vector<std::string> creation_order = dependency_ordered_components(
            index.entity_components.at(entity_id), index);
        for (const std::string& component_id : creation_order) {
            if (suppressed_components.contains(component_id)) continue;
            const nos::trent& source_component = *index.components.at(component_id);
            Entity mapped_owner = component_owner_for_source(component_id);
            tc_component* current = mapped_owner.valid()
                ? find_component(mapped_owner, component_id) : nullptr;
            if (mapped_owner.valid() && components_for_source(
                    mapped_owner, component_id).size() > 1) {
                add_failure(result, Error::RuntimeComponentNotFound, entity_id, component_id,
                            "multiple runtime components share a source component ID");
                continue;
            }
            const std::string desired_type =
                source_component["type"].as_string_default("");
            const std::string current_type = current && tc_component_type_name(current)
                ? tc_component_type_name(current) : "";
            if (current != nullptr && mapped_owner == owner && current_type == desired_type) {
                continue;
            }
            if (current != nullptr && current_type != desired_type) {
                std::string compatibility_error;
                if (!component_override_compatible(
                        source_component, _property_overrides, compatibility_error)) {
                    add_failure(result, Error::ComponentTypeMismatch, entity_id, component_id,
                                std::move(compatibility_error));
                    continue;
                }
            }
            ++result.structure_operation_count;
            std::string message;
            tc_component* replacement = create_component_checked(
                owner, source_component, uuid_remap, message);
            if (replacement == nullptr) {
                add_failure(result, Error::FactoryUnavailable, entity_id, component_id,
                            std::move(message));
                continue;
            }
            if (!owner.add_component_ptr_checked(replacement)) {
                tc_component_drop(replacement);
                add_failure(result, Error::AttachmentFailed, entity_id, component_id,
                            "checked component attachment failed");
                continue;
            }
            const size_t old_index = current != nullptr
                ? mapped_owner.component_index(current) : SIZE_MAX;
            if (current != nullptr) mapped_owner.remove_component_ptr(current);
            if (old_index != SIZE_MAX) owner.set_component_index(replacement, old_index);
            erase_component_mapping(component_id);
            _source_component_ids.push_back(component_id);
            _component_owners.push_back(owner);
            ++result.structure_operations_applied;
        }
    }

    // Remove or suppress components before deciding whether removed entity shells must survive.
    for (size_t position = _source_component_ids.size(); position-- > 0;) {
        const std::string component_id = _source_component_ids[position];
        const bool absent = !index.components.contains(component_id);
        const bool suppressed = suppressed_components.contains(component_id) ||
            (index.component_owners.contains(component_id) &&
             suppressed_entities.contains(index.component_owners.at(component_id)));
        if (!absent && !suppressed) continue;
        Entity owner = _component_owners[position];
        const std::string entity_id = mapped_source_for_entity(
            _source_entity_ids, _runtime_entities, owner);
        if (absent && !suppressed &&
            (property_targets_component(_property_overrides, component_id) ||
             component_placements.contains(component_id))) {
            add_failure(result, Error::RemovalConflict, entity_id, component_id,
                        "source component removal conflicts with retained property overrides");
            continue;
        }
        ++result.structure_operation_count;
        if (owner.valid()) {
            const std::vector<tc_component*> matches = components_for_source(
                owner, component_id);
            for (tc_component* component : matches) {
                owner.remove_component_ptr(component);
            }
        }
        erase_parallel(_source_component_ids, _component_owners, position);
        ++result.structure_operations_applied;
    }

    // Remove source-owned entities deepest-first. Local children are spliced into the old
    // parent. An entity carrying local components is demoted to a local shell.
    std::vector<std::string> mapped_entities = _source_entity_ids;
    std::reverse(mapped_entities.begin(), mapped_entities.end());
    for (const std::string& source_id : mapped_entities) {
        const bool absent = !index.entities.contains(source_id);
        const bool suppressed = suppressed_entities.contains(source_id);
        if ((!absent && !suppressed) || source_id == root_id) continue;
        if (absent && !suppressed &&
            (property_targets_entity(_property_overrides, source_id) ||
             entity_placements.contains(source_id))) {
            add_failure(result, Error::RemovalConflict, source_id, "",
                        "source entity removal conflicts with retained property overrides");
            continue;
        }
        Entity runtime = entity_for_source(source_id);
        if (!runtime.valid()) {
            erase_entity_mapping(source_id);
            continue;
        }
        ++result.structure_operation_count;
        Entity old_parent = runtime.parent();
        bool splice_failed = false;
        for (Entity child : runtime.children()) {
            if (!mapped_source_for_entity(
                    _source_entity_ids, _runtime_entities, child).empty()) continue;
            const GeneralPose3 pose = child.transform().global_pose();
            if (!child.set_parent_checked(old_parent)) {
                splice_failed = true;
                add_failure(result, Error::ParentCycle, source_id, "",
                            "failed to splice a local child out of a removed source entity");
                break;
            }
            child.transform().set_global_pose(pose);
        }
        if (splice_failed) continue;

        bool has_local_component = false;
        for (size_t component_index = 0;
             component_index < runtime.component_count(); ++component_index) {
            tc_component* component = runtime.component_at(component_index);
            if (component == this->tc_component_ptr()) continue;
            const std::string component_id = component
                ? tc_component_get_source_id(component) : "";
            if (std::find(
                    _source_component_ids.begin(), _source_component_ids.end(),
                    component_id) == _source_component_ids.end()) {
                has_local_component = true;
                break;
            }
        }
        erase_entity_mapping(source_id);
        if (!has_local_component) {
            tc_entity_pool_free(runtime.pool_ptr(), runtime.id());
        }
        ++result.structure_operations_applied;
    }

    const auto source_entity_for = [&](Entity runtime) {
        return mapped_source_for_entity(_source_entity_ids, _runtime_entities, runtime);
    };

    // Stable slot merge: local nodes retain their positions while source-owned nodes take
    // source order. Explicitly placed source nodes act as fixed local slots here.
    for (const std::string& parent_id : index.entity_preorder) {
        Entity parent = entity_for_source(parent_id);
        if (!parent.valid()) continue;
        std::vector<Entity> current = parent.children();
        std::vector<size_t> slots;
        std::vector<Entity> desired;
        for (size_t slot = 0; slot < current.size(); ++slot) {
            const std::string child_id = source_entity_for(current[slot]);
            if (!child_id.empty() && index.entity_parents.contains(child_id) &&
                index.entity_parents.at(child_id) == parent_id &&
                !entity_placements.contains(child_id) &&
                !suppressed_entities.contains(child_id)) {
                slots.push_back(slot);
            }
        }
        for (const std::string& child_id : index.children.at(parent_id)) {
            if (entity_placements.contains(child_id) ||
                suppressed_entities.contains(child_id)) continue;
            Entity child = entity_for_source(child_id);
            if (child.valid() && child.parent() == parent) desired.push_back(child);
        }
        if (slots.size() != desired.size()) continue;
        std::vector<Entity> target = current;
        for (size_t index_value = 0; index_value < slots.size(); ++index_value) {
            target[slots[index_value]] = desired[index_value];
        }
        for (size_t target_index = 0; target_index < target.size(); ++target_index) {
            std::vector<Entity> live = parent.children();
            if (live[target_index] == target[target_index]) continue;
            ++result.structure_operation_count;
            if (!target[target_index].set_sibling_index(target_index)) {
                add_failure(result, Error::OrderFailed, source_entity_for(target[target_index]), "",
                            "failed to apply canonical source sibling order");
            } else {
                ++result.structure_operations_applied;
            }
        }
    }

    // Source component order uses the same stable slot merge.
    for (const std::string& entity_id : index.entity_preorder) {
        Entity owner = entity_for_source(entity_id);
        if (!owner.valid()) continue;
        std::vector<tc_component*> current;
        for (size_t component_index = 0; component_index < owner.component_count();
             ++component_index) {
            current.push_back(owner.component_at(component_index));
        }
        std::vector<size_t> slots;
        std::vector<tc_component*> desired;
        for (size_t slot = 0; slot < current.size(); ++slot) {
            const std::string id = current[slot]
                ? tc_component_get_source_id(current[slot]) : "";
            if (index.component_owners.contains(id) &&
                index.component_owners.at(id) == entity_id &&
                !component_placements.contains(id) &&
                !suppressed_components.contains(id)) {
                slots.push_back(slot);
            }
        }
        for (const std::string& component_id : index.entity_components.at(entity_id)) {
            if (component_placements.contains(component_id) ||
                suppressed_components.contains(component_id)) continue;
            if (tc_component* component = find_component(owner, component_id)) {
                desired.push_back(component);
            }
        }
        if (slots.size() != desired.size()) continue;
        std::vector<tc_component*> target = current;
        for (size_t index_value = 0; index_value < slots.size(); ++index_value) {
            target[slots[index_value]] = desired[index_value];
        }
        for (size_t target_index = 0; target_index < target.size(); ++target_index) {
            if (owner.component_at(target_index) == target[target_index]) continue;
            ++result.structure_operation_count;
            if (!owner.set_component_index(target[target_index], target_index)) {
                add_failure(result, Error::OrderFailed, entity_id,
                            tc_component_get_source_id(target[target_index]),
                            "failed to apply canonical source component order");
            } else {
                ++result.structure_operations_applied;
            }
        }
    }

    // Explicit placements win over canonical source structure.
    for (const std::string& source_id : placed_entity_ids) {
        const PrefabStructuralOverride* placement = entity_placements.at(source_id);
        Entity runtime = entity_for_source(source_id);
        if (!runtime.valid()) continue;
        Entity parent;
        if (placement->parent.kind == PrefabStructureReferenceKind::Source) {
            parent = entity_for_source(placement->parent.source_id);
        } else {
            parent = placement->parent.local_entity;
        }
        if (!parent.valid() || !is_descendant_or_self(parent, entity()) ||
            is_descendant_or_self(parent, runtime)) {
            add_failure(result, Error::StructuralOverrideInvalid, source_id, "",
                        "entity placement parent is outside the instance or creates a cycle");
            continue;
        }
        if (runtime.parent() != parent) {
            ++result.structure_operation_count;
            if (!runtime.set_parent_checked(parent)) {
                add_failure(result, Error::ParentCycle, source_id, "",
                            "checked entity placement reparent failed");
                continue;
            }
            ++result.structure_operations_applied;
        }
        size_t target_index = parent.children().size() - 1;
        if (placement->before.kind == PrefabStructureReferenceKind::Source) {
            Entity before = entity_for_source(placement->before.source_id);
            if (!before.valid() || before.parent() != parent) {
                add_failure(result, Error::StructuralOverrideInvalid, source_id, "",
                            "entity placement source anchor is unavailable");
                continue;
            }
            target_index = before.sibling_index();
            if (runtime.sibling_index() < target_index) --target_index;
        } else if (placement->before.kind == PrefabStructureReferenceKind::Local) {
            Entity before = placement->before.local_entity;
            if (!before.valid() || before.parent() != parent) {
                add_failure(result, Error::StructuralOverrideInvalid, source_id, "",
                            "entity placement local anchor is unavailable");
                continue;
            }
            target_index = before.sibling_index();
            if (runtime.sibling_index() < target_index) --target_index;
        }
        if (runtime.sibling_index() != target_index) {
            ++result.structure_operation_count;
            if (!runtime.set_sibling_index(target_index)) {
                add_failure(result, Error::OrderFailed, source_id, "",
                            "explicit entity placement order failed");
            } else {
                ++result.structure_operations_applied;
            }
        }
    }

    for (const std::string& component_id : placed_component_ids) {
        const PrefabStructuralOverride* placement = component_placements.at(component_id);
        Entity owner = component_owner_for_source(component_id);
        tc_component* component = owner.valid() ? find_component(owner, component_id) : nullptr;
        if (component == nullptr) continue;
        size_t target_index = owner.component_count() - 1;
        if (placement->before.kind == PrefabStructureReferenceKind::Source) {
            tc_component* before = find_component(owner, placement->before.source_id);
            if (before == nullptr) {
                add_failure(result, Error::StructuralOverrideInvalid, "", component_id,
                            "component placement source anchor is unavailable");
                continue;
            }
            target_index = owner.component_index(before);
            if (owner.component_index(component) < target_index) --target_index;
        } else if (placement->before.kind == PrefabStructureReferenceKind::Local) {
            if (placement->before.local_entity != owner) {
                add_failure(result, Error::StructuralOverrideInvalid, "", component_id,
                            "component placement local anchor has a different owner");
                continue;
            }
            tc_component* before = find_component(
                owner, placement->before.local_component_source_id);
            if (before == nullptr) {
                add_failure(result, Error::StructuralOverrideInvalid, "", component_id,
                            "component placement local anchor is unavailable");
                continue;
            }
            target_index = owner.component_index(before);
            if (owner.component_index(component) < target_index) --target_index;
        }
        if (owner.component_index(component) != target_index) {
            ++result.structure_operation_count;
            if (!owner.set_component_index(component, target_index)) {
                add_failure(result, Error::OrderFailed, "", component_id,
                            "explicit component placement order failed");
            } else {
                ++result.structure_operations_applied;
            }
        }
    }

    const auto canonicalize_mapping = [](
        const std::vector<std::string>& preferred,
        std::vector<std::string>& ids,
        std::vector<Entity>& values
    ) {
        std::unordered_map<std::string, Entity> current;
        for (size_t index = 0; index < std::min(ids.size(), values.size()); ++index) {
            current.emplace(ids[index], values[index]);
        }
        std::vector<std::string> ordered_ids;
        std::vector<Entity> ordered_values;
        for (const std::string& source_id : preferred) {
            const auto found = current.find(source_id);
            if (found == current.end()) continue;
            ordered_ids.push_back(source_id);
            ordered_values.push_back(found->second);
            current.erase(found);
        }
        std::vector<std::string> remainder;
        remainder.reserve(current.size());
        for (const auto& [source_id, value] : current) {
            (void)value;
            remainder.push_back(source_id);
        }
        std::sort(remainder.begin(), remainder.end());
        for (const std::string& source_id : remainder) {
            ordered_ids.push_back(source_id);
            ordered_values.push_back(current.at(source_id));
        }
        ids = std::move(ordered_ids);
        values = std::move(ordered_values);
    };
    canonicalize_mapping(
        index.entity_preorder, _source_entity_ids, _runtime_entities);
    std::vector<std::string> component_preorder;
    for (const std::string& entity_id : index.entity_preorder) {
        const auto& components = index.entity_components.at(entity_id);
        component_preorder.insert(
            component_preorder.end(), components.begin(), components.end());
    }
    canonicalize_mapping(
        component_preorder, _source_component_ids, _component_owners);

    std::string mapping_error;
    _mapping_valid = validate_mapping(true, mapping_error);
    if (!_mapping_valid) {
        add_failure(result, Error::InvalidState, "", "",
                    "structural reconciliation left an invalid mapping: " + mapping_error);
    }
}

} // namespace termin::prefab
