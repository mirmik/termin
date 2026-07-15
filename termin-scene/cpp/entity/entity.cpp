#include <termin/entity/entity.hpp>
#include <termin/entity/component.hpp>
#include <termin/tc_scene.hpp>
#include "core/tc_scene.h"
#include "inspect/tc_inspect.h"
#include "inspect/tc_inspect_context.h"
#include <tcbase/tc_value_trent.hpp>
#include <tcbase/tc_log.hpp>
#include <tcbase/tc_uuid.h>
#include <algorithm>
#include <functional>
#include <numeric>
#include <unordered_map>

namespace termin {

namespace {

std::vector<size_t> component_deserialization_order(const nos::trent& components_data) {
    const auto& components = components_data.as_list();
    std::vector<size_t> order;
    order.reserve(components.size());

    std::vector<uint8_t> state(components.size(), 0);
    bool cycle_detected = false;

    auto component_type = [&components](size_t index) -> std::string {
        const nos::trent& component = components[index];
        if (!component.is_dict() || !component.contains("type")) {
            return {};
        }
        return component["type"].as_string_default("");
    };

    std::function<void(size_t)> visit = [&](size_t index) {
        if (state[index] == 2) {
            return;
        }
        if (state[index] == 1) {
            cycle_detected = true;
            return;
        }

        state[index] = 1;
        const std::string type_name = component_type(index);
        const size_t requirement_count = type_name.empty()
            ? 0
            : tc_component_registry_requirement_count(type_name.c_str());

        for (size_t requirement_index = 0;
             requirement_index < requirement_count;
             ++requirement_index) {
            const char* required_type = tc_component_registry_requirement_at(
                type_name.c_str(), requirement_index);
            if (!required_type) {
                continue;
            }

            for (size_t candidate_index = 0;
                 candidate_index < components.size();
                 ++candidate_index) {
                if (candidate_index == index) {
                    continue;
                }
                const std::string candidate_type = component_type(candidate_index);
                if (!candidate_type.empty()
                    && tc_component_registry_is_a(
                        candidate_type.c_str(), required_type)) {
                    visit(candidate_index);
                    break;
                }
            }
        }

        state[index] = 2;
        order.push_back(index);
    };

    for (size_t index = 0; index < components.size(); ++index) {
        visit(index);
    }

    if (cycle_detected) {
        std::iota(order.begin(), order.end(), size_t{0});
    }
    return order;
}

std::string generate_entity_clone_uuid() {
    char uuid[64] = {};
    tc_generate_uuid(uuid);
    return std::string(uuid);
}

nos::trent serialize_entity_base(
    const Entity& entity,
    const std::string& uuid,
    const std::string& name
) {
    nos::trent data;
    data["uuid"] = uuid;
    data["name"] = name;
    data["priority"] = static_cast<int64_t>(entity.priority());
    data["visible"] = entity.visible();
    data["enabled"] = entity.enabled();
    data["pickable"] = entity.pickable();
    data["selectable"] = entity.selectable();
    data["layer"] = static_cast<int64_t>(entity.layer());
    data["flags"] = static_cast<int64_t>(entity.flags());

    double pos[3], rot[4], scl[3];
    entity.get_local_position(pos);
    entity.get_local_rotation(rot);
    entity.get_local_scale(scl);

    nos::trent position;
    position.init(nos::trent::type::list);
    position.push_back(pos[0]);
    position.push_back(pos[1]);
    position.push_back(pos[2]);

    nos::trent rotation;
    rotation.init(nos::trent::type::list);
    rotation.push_back(rot[0]);
    rotation.push_back(rot[1]);
    rotation.push_back(rot[2]);
    rotation.push_back(rot[3]);

    nos::trent pose;
    pose["position"] = std::move(position);
    pose["rotation"] = std::move(rotation);
    data["pose"] = std::move(pose);

    nos::trent scale;
    scale.init(nos::trent::type::list);
    scale.push_back(scl[0]);
    scale.push_back(scl[1]);
    scale.push_back(scl[2]);
    data["scale"] = std::move(scale);

    return data;
}

nos::trent serialize_entity_hierarchy(const Entity& entity) {
    const char* uuid_c = entity.uuid();
    std::string uuid = uuid_c ? uuid_c : "";
    std::string name = entity.name() ? entity.name() : "Entity";

    nos::trent data = serialize_entity_base(entity, uuid, name);

    nos::trent components;
    components.init(nos::trent::type::list);
    const size_t comp_count = entity.component_count();
    for (size_t i = 0; i < comp_count; ++i) {
        tc_component* tc = entity.component_at(i);
        if (tc == nullptr) {
            continue;
        }

        const char* type_name = tc_component_type_name(tc);
        if (type_name == nullptr || type_name[0] == '\0') {
            continue;
        }

        if (tc->kind != TC_CXX_COMPONENT && tc->body == nullptr) {
            continue;
        }

        nos::trent comp_data;
        comp_data["source_id"] = tc_component_ensure_source_id(tc);
        comp_data["type"] = type_name;
        if (!tc_inspect_has_type(type_name)) {
            tc::Log::warn(
                "[Entity] Component '%s' has no inspect registration; serialized component data will be empty",
                type_name
            );
        }
        tc_value value = serialize_component_data(tc);
        comp_data["data"] = tc::tc_value_to_trent(value);
        tc_value_free(&value);
        components.push_back(std::move(comp_data));
    }
    data["components"] = std::move(components);

    nos::trent children;
    children.init(nos::trent::type::list);
    for (const Entity& child : entity.children()) {
        if (!child.valid()) {
            continue;
        }
        children.push_back(serialize_entity_hierarchy(child));
    }
    data["children"] = std::move(children);

    return data;
}

nos::trent make_clone_payload_recursive(
    const nos::trent& source_data,
    const std::string& root_name_suffix,
    bool is_root,
    std::unordered_map<std::string, std::string>& uuid_remap
) {
    if (!source_data.is_dict()) {
        return nos::trent();
    }

    nos::trent clone_data = source_data;

    const std::string old_uuid = clone_data["uuid"].as_string_default("");
    const std::string new_uuid = generate_entity_clone_uuid();
    if (!old_uuid.empty()) {
        uuid_remap[old_uuid] = new_uuid;
    }
    clone_data["uuid"] = new_uuid;

    if (is_root && !root_name_suffix.empty()) {
        std::string name = clone_data["name"].as_string_default("Entity");
        clone_data["name"] = name + root_name_suffix;
    }

    nos::trent cloned_children;
    cloned_children.init(nos::trent::type::list);
    if (clone_data.contains("children") && clone_data["children"].is_list()) {
        for (const nos::trent& child : clone_data["children"].as_list()) {
            nos::trent cloned_child = make_clone_payload_recursive(
                child,
                root_name_suffix,
                false,
                uuid_remap
            );
            if (cloned_child.is_dict()) {
                cloned_children.push_back(std::move(cloned_child));
            }
        }
    }
    clone_data["children"] = std::move(cloned_children);

    return clone_data;
}

nos::trent* find_trent_path(nos::trent& data, const std::string& path) {
    nos::trent* current = &data;
    size_t start = 0;
    while (start <= path.size()) {
        const size_t dot = path.find('.', start);
        const std::string part = dot == std::string::npos
            ? path.substr(start)
            : path.substr(start, dot - start);
        if (part.empty() || !current->is_dict() || !current->contains(part)) {
            return nullptr;
        }
        current = &((*current)[part]);
        if (dot == std::string::npos) {
            return current;
        }
        start = dot + 1;
    }
    return nullptr;
}

bool remap_entity_ref_value(
    nos::trent& value,
    const std::unordered_map<std::string, std::string>& uuid_remap
) {
    if (value.is_dict()) {
        if (value.contains("uuid") && value["uuid"].is_string()) {
            const std::string current = value["uuid"].as_string();
            auto it = uuid_remap.find(current);
            if (it != uuid_remap.end()) {
                value["uuid"] = it->second;
                return true;
            }
        }
        return false;
    }

    if (value.is_string()) {
        const std::string current = value.as_string();
        auto it = uuid_remap.find(current);
        if (it != uuid_remap.end()) {
            value = it->second;
            return true;
        }
    }
    return false;
}

bool remap_entity_ref_list_value(
    nos::trent& value,
    const std::unordered_map<std::string, std::string>& uuid_remap
) {
    if (!value.is_list()) {
        return false;
    }
    bool changed = false;
    for (nos::trent& item : value.as_list()) {
        changed = remap_entity_ref_value(item, uuid_remap) || changed;
    }
    return changed;
}

void remap_component_entity_refs(
    nos::trent& data,
    const std::unordered_map<std::string, std::string>& uuid_remap
) {
    if (!data.is_dict()) {
        return;
    }

    if (data.contains("components") && data["components"].is_list()) {
        for (nos::trent& component_data : data["components"].as_list()) {
            if (!component_data.is_dict() ||
                !component_data.contains("type") ||
                !component_data.contains("data") ||
                !component_data["data"].is_dict()) {
                continue;
            }

            const std::string type_name = component_data["type"].as_string_default("");
            if (type_name.empty()) {
                continue;
            }

            for (const tc::InspectFieldInfo& field : tc::InspectRegistry::instance().all_fields(type_name)) {
                if (field.kind != "entity" && field.kind != "list[entity]") {
                    continue;
                }

                nos::trent* value = find_trent_path(component_data["data"], field.path);
                if (value == nullptr) {
                    continue;
                }

                if (field.kind == "entity") {
                    remap_entity_ref_value(*value, uuid_remap);
                } else {
                    remap_entity_ref_list_value(*value, uuid_remap);
                }
            }
        }
    }

    if (data.contains("children") && data["children"].is_list()) {
        for (nos::trent& child : data["children"].as_list()) {
            remap_component_entity_refs(child, uuid_remap);
        }
    }
}

bool deserialize_entity_hierarchy(
    const nos::trent& data,
    tc_scene_handle scene,
    Entity* parent,
    std::vector<std::pair<Entity, nos::trent>>& entity_data_pairs,
    Entity& result
) {
    Entity entity = Entity::deserialize_base_trent(data, scene);
    if (!entity.valid()) {
        tc::Log::error("[Entity] hierarchy deserialization failed: could not deserialize entity base");
        return false;
    }

    if (parent != nullptr && parent->valid()) {
        entity.set_parent(*parent);
    }

    entity_data_pairs.emplace_back(entity, data);

    if (data.contains("children") && data["children"].is_list()) {
        for (const nos::trent& child_data : data["children"].as_list()) {
            Entity child;
            if (!deserialize_entity_hierarchy(
                    child_data,
                    scene,
                    &entity,
                    entity_data_pairs,
                    child)) {
                return false;
            }
        }
    }

    result = entity;
    return true;
}

void rollback_deserialized_entities(
    std::vector<std::pair<Entity, nos::trent>>& entity_data_pairs
) {
    for (auto it = entity_data_pairs.rbegin(); it != entity_data_pairs.rend(); ++it) {
        Entity& entity = it->first;
        if (entity.valid()) {
            tc_entity_pool_free(entity.pool(), entity.id());
        }
    }
}

} // namespace

// Global standalone pool handle
static tc_entity_pool_handle g_standalone_pool_handle = TC_ENTITY_POOL_HANDLE_INVALID;

// Legacy constructor from raw pointer
Entity::Entity(tc_entity_pool* pool, tc_entity_id id) {
    _h.pool = tc_entity_pool_registry_find(pool);
    _h.id = id;
}

void Entity::deserialize_from(const tc_value* data, void* context) {
    tc_scene_handle scene = tc_scene_inspect_context_scene(context);
    // Get UUID from tc_value
    std::string uuid_str;
    if (data && data->type == TC_VALUE_STRING && data->data.s) {
        uuid_str = data->data.s;
    } else if (data && data->type == TC_VALUE_DICT) {
        tc_value* uuid_val = tc_value_dict_get(const_cast<tc_value*>(data), "uuid");
        if (uuid_val && uuid_val->type == TC_VALUE_STRING && uuid_val->data.s) {
            uuid_str = uuid_val->data.s;
        }
    }

    if (uuid_str.empty()) {
        _h = TC_ENTITY_HANDLE_INVALID;
        return;
    }

    // Get pool handle from scene or use standalone
    tc_entity_pool_handle pool_handle;
    if (tc_scene_handle_valid(scene)) {
        tc_entity_pool* pool = tc_scene_entity_pool(scene);
        pool_handle = tc_entity_pool_registry_find(pool);
    } else {
        pool_handle = standalone_pool_handle();
    }

    tc_entity_pool* pool = tc_entity_pool_registry_get(pool_handle);
    if (pool) {
        // Find entity by UUID in pool
        tc_entity_id id = tc_entity_pool_find_by_uuid(pool, uuid_str.c_str());
        if (tc_entity_id_valid(id)) {
            _h = tc_entity_handle_make(pool_handle, id);
            return;
        }
    }

    // Entity not found
    _h = TC_ENTITY_HANDLE_INVALID;
}

tc_entity_pool_handle Entity::standalone_pool_handle() {
    // The C pool registry resets its standalone handle during tc_shutdown(),
    // while this C++ cache survives for the process lifetime.  A non-sentinel
    // handle alone is therefore insufficient after a runtime rebootstrap.
    if (!tc_entity_pool_handle_valid(g_standalone_pool_handle) ||
        !tc_entity_pool_registry_get(g_standalone_pool_handle)) {
        g_standalone_pool_handle = tc_entity_pool_standalone_handle();
    }
    return g_standalone_pool_handle;
}

tc_entity_pool* Entity::standalone_pool() {
    return tc_entity_pool_registry_get(standalone_pool_handle());
}

Entity Entity::create(tc_entity_pool_handle pool_handle, const std::string& name) {
    tc_entity_pool* pool = tc_entity_pool_registry_get(pool_handle);
    if (!pool) return Entity();
    tc_entity_id id = tc_entity_pool_alloc(pool, name.c_str());
    return Entity(pool_handle, id);
}

Entity Entity::create_with_uuid(tc_entity_pool_handle pool_handle, const std::string& name, const std::string& uuid) {
    tc_entity_pool* pool = tc_entity_pool_registry_get(pool_handle);
    if (!pool) return Entity();
    tc_entity_id id = tc_entity_pool_alloc_with_uuid(pool, name.c_str(), uuid.c_str());
    return Entity(pool_handle, id);
}

Entity Entity::create(tc_entity_pool* pool, const std::string& name) {
    if (!pool) return Entity();
    tc_entity_pool_handle pool_handle = tc_entity_pool_registry_find(pool);
    if (!tc_entity_pool_handle_valid(pool_handle)) return Entity();
    tc_entity_id id = tc_entity_pool_alloc(pool, name.c_str());
    return Entity(pool_handle, id);
}

Entity Entity::create_with_uuid(tc_entity_pool* pool, const std::string& name, const std::string& uuid) {
    if (!pool) return Entity();
    tc_entity_pool_handle pool_handle = tc_entity_pool_registry_find(pool);
    if (!tc_entity_pool_handle_valid(pool_handle)) return Entity();
    tc_entity_id id = tc_entity_pool_alloc_with_uuid(pool, name.c_str(), uuid.c_str());
    return Entity(pool_handle, id);
}

void Entity::add_component(Component* component) {
    if (!component || !valid()) return;
    tc_entity_add_component(_h, component->c_component());
}

void Entity::add_component_ptr(tc_component* c) {
    if (!c || !valid()) return;
    tc_entity_add_component(_h, c);
}

void Entity::remove_component(Component* component) {
    if (!component || !valid()) return;
    tc_entity_remove_component(_h, component->c_component());
}

void Entity::remove_component_ptr(tc_component* c) {
    if (!c || !valid()) return;
    tc_entity_remove_component(_h, c);
}

CxxComponent* Entity::get_component_by_type(const std::string& type_name) {
    size_t count = component_count();
    for (size_t i = 0; i < count; i++) {
        tc_component* tc = component_at(i);
        if (tc && tc->kind == TC_CXX_COMPONENT) {
            CxxComponent* comp = CxxComponent::from_tc(tc);
            if (comp && comp->type_name() == type_name) {
                return comp;
            }
        }
    }
    return nullptr;
}

tc_component* Entity::get_component_by_type_name(const std::string& type_name) {
    size_t count = component_count();
    for (size_t i = 0; i < count; i++) {
        tc_component* tc = component_at(i);
        if (!tc) continue;

        const char* comp_type = tc_component_type_name(tc);
        if (comp_type && type_name == comp_type) {
            return tc;
        }
    }
    return nullptr;
}

void Entity::set_parent(const Entity& parent_entity) {
    if (!valid()) return;

    // Check that parent is in the same pool
    if (parent_entity.valid() && !tc_entity_pool_handle_eq(parent_entity._h.pool, _h.pool)) {
        throw std::runtime_error("Cannot set parent: entities must be in the same pool");
    }

    tc_entity_set_parent(_h, parent_entity._h);
}

Entity Entity::parent() const {
    tc_entity_handle parent_h = tc_entity_parent(_h);
    return Entity(parent_h);
}

std::vector<Entity> Entity::children() const {
    std::vector<Entity> result;
    if (!valid())
        return result;

    size_t count = tc_entity_children_count(_h);
    result.reserve(count);

    for (size_t i = 0; i < count; i++) {
        tc_entity_handle child_h = tc_entity_child_at(_h, i);
        if (tc_entity_handle_valid(child_h)) {
            result.push_back(Entity(child_h));
        }
    }
    return result;
}

size_t Entity::sibling_index() const { return valid() ? tc_entity_sibling_index(_h) : SIZE_MAX; }

bool Entity::set_sibling_index(size_t index) {
    return valid() && tc_entity_set_sibling_index(_h, index);
}

Entity Entity::find_child(const std::string& name) const {
    if (!valid())
        return Entity();

    size_t count = tc_entity_children_count(_h);
    for (size_t i = 0; i < count; i++) {
        tc_entity_handle child_h = tc_entity_child_at(_h, i);
        if (tc_entity_handle_valid(child_h)) {
            const char* child_name = tc_entity_name(child_h);
            if (child_name && name == child_name) {
                return Entity(child_h);
            }
        }
    }
    return Entity();
}

Entity Entity::create_child(const std::string& name) {
    Entity child = Entity::create(_h.pool, name);
    child.set_parent(*this);
    return child;
}

void Entity::destroy_children() {
    if (!valid()) return;
    auto kids = children();
    for (auto& child : kids) {
        if (child.valid()) {
            child.destroy_children();
            tc_entity_pool_free(child.pool(), child.id());
        }
    }
}

nos::trent Entity::serialize_hierarchy() const {
    if (!valid()) {
        tc::Log::warn("[Entity] hierarchy serialization requested for invalid entity");
        return nos::trent();
    }

    return serialize_entity_hierarchy(*this);
}

nos::trent Entity::make_clone_payload(
    const nos::trent& data,
    const std::string& name_suffix,
    std::unordered_map<std::string, std::string>& uuid_remap
) {
    if (!data.is_dict()) {
        tc::Log::error("[Entity] clone payload creation failed: source data must be a dict");
        return nos::trent();
    }
    return make_clone_payload_recursive(data, name_suffix, true, uuid_remap);
}

void Entity::remap_entity_refs(
    nos::trent& data,
    const std::unordered_map<std::string, std::string>& uuid_remap
) {
    remap_component_entity_refs(data, uuid_remap);
}

Entity Entity::deserialize_hierarchy(
    const nos::trent& data,
    tc_scene_handle scene,
    const Entity& parent
) {
    if (!data.is_dict()) {
        tc::Log::error("[Entity] hierarchy deserialization failed: data must be a dict");
        return Entity();
    }
    tc_entity_pool* target_pool = tc_scene_handle_valid(scene)
        ? tc_scene_entity_pool(scene)
        : Entity::standalone_pool();
    if (target_pool == nullptr) {
        tc::Log::error("[Entity] hierarchy deserialization failed: target entity pool is unavailable");
        return Entity();
    }
    if (parent.valid() && parent.pool() != target_pool) {
        tc::Log::error("[Entity] hierarchy deserialization failed: parent belongs to another entity pool");
        return Entity();
    }

    std::vector<std::pair<Entity, nos::trent>> entity_data_pairs;
    Entity parent_copy = parent;
    Entity cloned_root;
    if (!deserialize_entity_hierarchy(
            data,
            scene,
            parent_copy.valid() ? &parent_copy : nullptr,
            entity_data_pairs,
            cloned_root)) {
        rollback_deserialized_entities(entity_data_pairs);
        tc::Log::error("[Entity] hierarchy deserialization failed: root entity was not deserialized");
        return Entity();
    }

    for (auto& [entity, entity_data] : entity_data_pairs) {
        entity.deserialize_components_trent(entity_data, scene);
    }

    return cloned_root;
}

Entity Entity::clone(const std::string& name_suffix) const {
    if (!valid()) {
        tc::Log::warn("[Entity] clone requested for invalid entity");
        return Entity();
    }

    tc_scene_handle scene_handle = TC_SCENE_HANDLE_INVALID;
    if (tc_entity_pool* p = pool_ptr()) {
        scene_handle = tc_entity_pool_get_scene(p);
    }

    std::unordered_map<std::string, std::string> uuid_remap;
    nos::trent clone_data = Entity::make_clone_payload(serialize_hierarchy(), name_suffix, uuid_remap);
    Entity::remap_entity_refs(clone_data, uuid_remap);
    return Entity::deserialize_hierarchy(clone_data, scene_handle, parent());
}

void Entity::update(float dt) {
    if (!valid() || !enabled()) return;

    size_t count = component_count();
    for (size_t i = 0; i < count; i++) {
        tc_component* tc = component_at(i);
        if (tc && tc->enabled) {
            tc_component_update(tc, dt);
        }
    }
}

void Entity::on_added_to_scene(tc_scene_handle scene) {
    (void)scene;
}

void Entity::on_removed_from_scene() {
}

tc_value Entity::serialize_base() const {
    if (!valid()) {
        return tc_value_nil();
    }

    tc_value data = tc_value_dict_new();

    tc_value_dict_set(&data, "uuid", tc_value_string(uuid()));
    tc_value_dict_set(&data, "name", tc_value_string(name()));
    tc_value_dict_set(&data, "priority", tc_value_int(priority()));
    tc_value_dict_set(&data, "visible", tc_value_bool(visible()));
    tc_value_dict_set(&data, "enabled", tc_value_bool(enabled()));
    tc_value_dict_set(&data, "pickable", tc_value_bool(pickable()));
    tc_value_dict_set(&data, "selectable", tc_value_bool(selectable()));
    tc_value_dict_set(&data, "layer", tc_value_int(static_cast<int64_t>(layer())));
    tc_value_dict_set(&data, "flags", tc_value_int(static_cast<int64_t>(flags())));

    double pos[3], rot[4], scl[3];
    get_local_position(pos);
    get_local_rotation(rot);
    get_local_scale(scl);

    tc_value pose_data = tc_value_dict_new();

    tc_value position = tc_value_list_new();
    tc_value_list_push(&position, tc_value_double(pos[0]));
    tc_value_list_push(&position, tc_value_double(pos[1]));
    tc_value_list_push(&position, tc_value_double(pos[2]));
    tc_value_dict_set(&pose_data, "position", position);

    tc_value rotation = tc_value_list_new();
    tc_value_list_push(&rotation, tc_value_double(rot[0]));
    tc_value_list_push(&rotation, tc_value_double(rot[1]));
    tc_value_list_push(&rotation, tc_value_double(rot[2]));
    tc_value_list_push(&rotation, tc_value_double(rot[3]));
    tc_value_dict_set(&pose_data, "rotation", rotation);

    tc_value_dict_set(&data, "pose", pose_data);

    tc_value scale_v = tc_value_list_new();
    tc_value_list_push(&scale_v, tc_value_double(scl[0]));
    tc_value_list_push(&scale_v, tc_value_double(scl[1]));
    tc_value_list_push(&scale_v, tc_value_double(scl[2]));
    tc_value_dict_set(&data, "scale", scale_v);

    return data;
}

bool Entity::validate_components() const {
    if (!valid()) {
        fprintf(stderr, "[validate_components] Entity not valid\n");
        return false;
    }

    size_t count = component_count();
    if (count > 1000) {
        fprintf(stderr, "[validate_components] Suspicious component count: %zu\n", count);
        return false;
    }

    for (size_t i = 0; i < count; i++) {
        tc_component* tc = component_at(i);

        if (!tc) {
            fprintf(stderr, "[validate_components] Entity '%s' component %zu is NULL\n", name(), i);
            return false;
        }

        if (tc->kind != TC_CXX_COMPONENT && tc->kind != TC_PYTHON_COMPONENT) {
            fprintf(stderr, "[validate_components] Entity '%s' component %zu has invalid kind: %d\n", name(), i, (int)tc->kind);
            return false;
        }

        if (!tc->vtable) {
            fprintf(stderr, "[validate_components] Entity '%s' component %zu has NULL vtable\n", name(), i);
            return false;
        }

        const char* tname = tc_component_type_name(tc);
        if (!tname) {
            fprintf(stderr, "[validate_components] Entity '%s' component %zu has NULL type_name\n", name(), i);
            return false;
        }

        if (tname[0] < 32 || tname[0] > 126) {
            fprintf(stderr, "[validate_components] Entity '%s' component %zu type_name starts with non-printable: 0x%02x\n",
                    name(), i, (unsigned char)tname[0]);
            return false;
        }
    }

    return true;
}

// Helper to get double from tc_value
static double tc_value_as_double(const tc_value* v, double def = 0.0) {
    if (!v) return def;
    switch (v->type) {
        case TC_VALUE_INT: return static_cast<double>(v->data.i);
        case TC_VALUE_FLOAT: return static_cast<double>(v->data.f);
        case TC_VALUE_DOUBLE: return v->data.d;
        default: return def;
    }
}

// Helper to get bool from tc_value
static bool tc_value_as_bool(const tc_value* v, bool def = false) {
    if (!v) return def;
    if (v->type == TC_VALUE_BOOL) return v->data.b;
    return def;
}

// Helper to get string from tc_value dict
static std::string tc_value_dict_string(const tc_value* dict, const char* key, const char* def = "") {
    if (!dict || dict->type != TC_VALUE_DICT) return def;
    tc_value* v = tc_value_dict_get(const_cast<tc_value*>(dict), key);
    if (v && v->type == TC_VALUE_STRING && v->data.s) return v->data.s;
    return def;
}

Entity Entity::deserialize(tc_entity_pool_handle pool_handle, const tc_value* data) {
    tc_entity_pool* pool = tc_entity_pool_registry_get(pool_handle);
    if (!pool || !data || data->type != TC_VALUE_DICT) {
        return Entity();
    }

    std::string entity_name = tc_value_dict_string(data, "name", "entity");

    Entity ent = Entity::create(pool_handle, entity_name);
    if (!ent.valid()) return Entity();

    tc_value* priority_v = tc_value_dict_get(const_cast<tc_value*>(data), "priority");
    ent.set_priority(static_cast<int>(tc_value_as_double(priority_v, 0)));

    tc_value* visible_v = tc_value_dict_get(const_cast<tc_value*>(data), "visible");
    ent.set_visible(tc_value_as_bool(visible_v, true));

    tc_value* enabled_v = tc_value_dict_get(const_cast<tc_value*>(data), "enabled");
    if (enabled_v) {
        ent.set_enabled(tc_value_as_bool(enabled_v, true));
    } else {
        tc_value* active_v = tc_value_dict_get(const_cast<tc_value*>(data), "active");
        ent.set_enabled(tc_value_as_bool(active_v, true));
    }

    tc_value* pickable_v = tc_value_dict_get(const_cast<tc_value*>(data), "pickable");
    ent.set_pickable(tc_value_as_bool(pickable_v, true));

    tc_value* selectable_v = tc_value_dict_get(const_cast<tc_value*>(data), "selectable");
    ent.set_selectable(tc_value_as_bool(selectable_v, true));

    tc_value* layer_v = tc_value_dict_get(const_cast<tc_value*>(data), "layer");
    ent.set_layer(static_cast<uint64_t>(tc_value_as_double(layer_v, 1)));

    tc_value* flags_v = tc_value_dict_get(const_cast<tc_value*>(data), "flags");
    ent.set_flags(static_cast<uint64_t>(tc_value_as_double(flags_v, 0)));

    tc_value* pose_v = tc_value_dict_get(const_cast<tc_value*>(data), "pose");
    if (pose_v && pose_v->type == TC_VALUE_DICT) {
        tc_value* pos = tc_value_dict_get(pose_v, "position");
        if (pos && pos->type == TC_VALUE_LIST && tc_value_list_size(pos) >= 3) {
            double xyz[3] = {
                tc_value_as_double(tc_value_list_get(pos, 0)),
                tc_value_as_double(tc_value_list_get(pos, 1)),
                tc_value_as_double(tc_value_list_get(pos, 2))
            };
            ent.set_local_position(xyz);
        }

        tc_value* rot = tc_value_dict_get(pose_v, "rotation");
        if (rot && rot->type == TC_VALUE_LIST && tc_value_list_size(rot) >= 4) {
            double xyzw[4] = {
                tc_value_as_double(tc_value_list_get(rot, 0)),
                tc_value_as_double(tc_value_list_get(rot, 1)),
                tc_value_as_double(tc_value_list_get(rot, 2)),
                tc_value_as_double(tc_value_list_get(rot, 3))
            };
            ent.set_local_rotation(xyzw);
        }
    }

    tc_value* scl = tc_value_dict_get(const_cast<tc_value*>(data), "scale");
    if (scl && scl->type == TC_VALUE_LIST && tc_value_list_size(scl) >= 3) {
        double xyz[3] = {
            tc_value_as_double(tc_value_list_get(scl, 0)),
            tc_value_as_double(tc_value_list_get(scl, 1)),
            tc_value_as_double(tc_value_list_get(scl, 2))
        };
        ent.set_local_scale(xyz);
    }

    return ent;
}

Entity Entity::deserialize(tc_entity_pool* pool, const tc_value* data) {
    tc_entity_pool_handle pool_handle = tc_entity_pool_registry_find(pool);
    return deserialize(pool_handle, data);
}

// ============================================================================
// Trent-based serialization (for C++ scene serialization)
// ============================================================================

Entity Entity::deserialize_base_trent(const nos::trent& data, tc_scene_handle scene) {
    std::string uuid_str = data["uuid"].as_string_default("");
    std::string name_str = data["name"].as_string_default("Entity");

    if (uuid_str.empty()) {
        return Entity();
    }

    // Get pool from scene or use standalone
    tc_entity_pool_handle pool_handle;
    if (tc_scene_handle_valid(scene)) {
        tc_entity_pool* pool = tc_scene_entity_pool(scene);
        pool_handle = tc_entity_pool_registry_find(pool);
    } else {
        pool_handle = standalone_pool_handle();
    }

    // Create entity with UUID
    Entity ent = Entity::create_with_uuid(pool_handle, name_str, uuid_str);
    if (!ent.valid()) {
        return Entity();
    }

    // Restore flags
    if (data.contains("priority")) {
        ent.set_priority(static_cast<int>(data["priority"].as_numer_default(0)));
    }
    if (data.contains("visible")) {
        ent.set_visible(data["visible"].as_bool_default(true));
    }
    if (data.contains("enabled")) {
        ent.set_enabled(data["enabled"].as_bool_default(true));
    }
    if (data.contains("pickable")) {
        ent.set_pickable(data["pickable"].as_bool_default(true));
    }
    if (data.contains("selectable")) {
        ent.set_selectable(data["selectable"].as_bool_default(true));
    }
    if (data.contains("layer")) {
        ent.set_layer(static_cast<uint64_t>(data["layer"].as_numer_default(0)));
    }
    if (data.contains("flags")) {
        ent.set_flags(static_cast<uint64_t>(data["flags"].as_numer_default(0)));
    }

    // Restore pose
    if (data.contains("pose") && data["pose"].is_dict()) {
        const auto& pose = data["pose"];
        if (pose.contains("position") && pose["position"].is_list()) {
            const auto& p = pose["position"].as_list();
            if (p.size() >= 3) {
                double xyz[3] = {
                    static_cast<double>(p[0].as_numer_default(0)),
                    static_cast<double>(p[1].as_numer_default(0)),
                    static_cast<double>(p[2].as_numer_default(0))
                };
                ent.set_local_position(xyz);
            }
        }
        if (pose.contains("rotation") && pose["rotation"].is_list()) {
            const auto& r = pose["rotation"].as_list();
            if (r.size() >= 4) {
                double xyzw[4] = {
                    static_cast<double>(r[0].as_numer_default(0)),
                    static_cast<double>(r[1].as_numer_default(0)),
                    static_cast<double>(r[2].as_numer_default(0)),
                    static_cast<double>(r[3].as_numer_default(1))
                };
                ent.set_local_rotation(xyzw);
            }
        }
    }

    // Restore scale
    if (data.contains("scale") && data["scale"].is_list()) {
        const auto& s = data["scale"].as_list();
        if (s.size() >= 3) {
            double xyz[3] = {
                static_cast<double>(s[0].as_numer_default(1)),
                static_cast<double>(s[1].as_numer_default(1)),
                static_cast<double>(s[2].as_numer_default(1))
            };
            ent.set_local_scale(xyz);
        }
    }

    return ent;
}

void Entity::deserialize_components_trent(
    const nos::trent& data,
    tc_scene_handle scene,
    ComponentDeserializationMode mode) {
    if (!valid()) return;
    if (!data.contains("components") || !data["components"].is_list()) return;

    const auto& components_data = data["components"];
    const auto& components = components_data.as_list();
    const std::vector<size_t> component_order =
        mode == ComponentDeserializationMode::Direct
            ? component_deserialization_order(components_data)
            : std::vector<size_t>();

    for (size_t ordered_index = 0; ordered_index < components.size(); ++ordered_index) {
        const size_t component_index = mode == ComponentDeserializationMode::Direct
            ? component_order[ordered_index]
            : ordered_index;
        const auto& comp_data = components[component_index];
        if (!comp_data.is_dict()) continue;
        if (!comp_data.contains("type")) continue;

        std::string type_name = comp_data["type"].as_string_default("");
        if (type_name.empty()) continue;
        const std::string source_id = comp_data["source_id"].as_string_default("");

        if (mode == ComponentDeserializationMode::UnknownOnly) {
            tc_component* unk = tc_component_registry_create("UnknownComponent");
            if (unk == nullptr) {
                tc::Log::warn(
                    "[Entity] Failed to create UnknownComponent for %s",
                    type_name.c_str());
                continue;
            }

            tc_component_set_source_id(unk, source_id.c_str());
            add_component_ptr(unk);
            auto* unknown_obj =
                (unk->kind == TC_CXX_COMPONENT)
                    ? dynamic_cast<UnknownComponent*>(CxxComponent::from_tc(unk))
                    : nullptr;
            if (unknown_obj != nullptr) {
                unknown_obj->original_type = type_name;
                tc_value_free(&unknown_obj->original_data);
                unknown_obj->original_data = comp_data.contains("data")
                    ? tc::trent_to_tc_value(comp_data["data"])
                    : tc_value_dict_new();
            }

            continue;
        }

        // Check if type is registered
        if (!tc_component_registry_has(type_name.c_str())) {
            tc::Log::warn("[Entity] Unknown component type: %s (creating placeholder)", type_name.c_str());
            // Create UnknownComponent placeholder
            tc_component* unk = tc_component_registry_create("UnknownComponent");
            if (unk) {
                tc_component_set_source_id(unk, source_id.c_str());
                add_component_ptr(unk);
                // Store original type and data
                auto* unknown_obj =
                    (unk->kind == TC_CXX_COMPONENT)
                        ? dynamic_cast<UnknownComponent*>(CxxComponent::from_tc(unk))
                        : nullptr;
                if (unknown_obj) {
                    unknown_obj->original_type = type_name;
                    tc_value_free(&unknown_obj->original_data);
                    unknown_obj->original_data = comp_data.contains("data")
                        ? tc::trent_to_tc_value(comp_data["data"])
                        : tc_value_dict_new();
                }
            }
            continue;
        }

        // Create component via registry factory
        tc_component* tc = tc_component_registry_create(type_name.c_str());
        if (!tc) {
            tc::Log::warn("[Entity] Failed to create component: %s", type_name.c_str());
            continue;
        }

        tc_component_set_source_id(tc, source_id.c_str());

        // Deserialize data BEFORE adding to entity
        if (comp_data.contains("data")) {
            if (tc->kind == TC_CXX_COMPONENT) {
                CxxComponent* component = CxxComponent::from_tc(tc);
                if (component != nullptr) {
                    tc_value v = tc::trent_to_tc_value(comp_data["data"]);
                    component->deserialize_data(&v, scene);
                    tc_value_free(&v);
                }
            } else if (tc->body != nullptr) {
                tc_value v = tc::trent_to_tc_value(comp_data["data"]);
                tc_scene_inspect_context inspect_ctx = tc_scene_inspect_context_make(scene);
                tc_inspect_deserialize(tc->body, type_name.c_str(), &v, &inspect_ctx);
                tc_value_free(&v);
            }
        }

        // Add to entity (triggers on_added with deserialized fields)
        add_component_ptr(tc);
    }
}

TcSceneRef Entity::scene() const {
    tc_entity_pool* p = pool_ptr();
    if (!p) return TcSceneRef();
    tc_scene_handle h = tc_entity_pool_get_scene(p);
    return TcSceneRef(h);
}

} // namespace termin
