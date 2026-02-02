#include "entity.hpp"
#include "component.hpp"
#include "../../../core_c/include/tc_scene.h"
#include <algorithm>

namespace termin {

// Global standalone pool handle
static tc_entity_pool_handle g_standalone_pool_handle = TC_ENTITY_POOL_HANDLE_INVALID;

// Legacy constructor from raw pointer
Entity::Entity(tc_entity_pool* pool, tc_entity_id id) {
    _h.pool = tc_entity_pool_registry_find(pool);
    _h.id = id;
}

void Entity::deserialize_from(const tc_value* data, tc_scene_handle scene) {
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
    if (!tc_entity_pool_handle_valid(g_standalone_pool_handle)) {
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
    if (!valid()) return result;

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

Entity Entity::find_child(const std::string& name) const {
    if (!valid()) return Entity();

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
    if (!valid() || !serializable()) {
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

} // namespace termin
