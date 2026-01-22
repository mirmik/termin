#include "entity.hpp"
#include "component.hpp"
#include "../../../core_c/include/tc_scene.h"
#include <algorithm>

namespace termin {

// Global standalone pool for entities created outside of Scene
static tc_entity_pool* g_standalone_pool = nullptr;

void Entity::deserialize_from(const tc_value* data, tc_scene* scene) {
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
        _pool = nullptr;
        _id = TC_ENTITY_ID_INVALID;
        return;
    }

    // Get pool from scene
    tc_entity_pool* pool = scene ? tc_scene_entity_pool(scene) : g_standalone_pool;

    if (pool) {
        // Find entity by UUID in pool
        tc_entity_id id = tc_entity_pool_find_by_uuid(pool, uuid_str.c_str());
        if (tc_entity_id_valid(id)) {
            _pool = pool;
            _id = id;
            return;
        }
    }

    // Entity not found
    _pool = nullptr;
    _id = TC_ENTITY_ID_INVALID;
}

tc_entity_pool* Entity::standalone_pool() {
    if (!g_standalone_pool) {
        g_standalone_pool = tc_entity_pool_create(1024);
    }
    return g_standalone_pool;
}

Entity Entity::create(tc_entity_pool* pool, const std::string& name) {
    if (!pool) return Entity();
    tc_entity_id id = tc_entity_pool_alloc(pool, name.c_str());
    return Entity(pool, id);
}

Entity Entity::create_with_uuid(tc_entity_pool* pool, const std::string& name, const std::string& uuid) {
    if (!pool) return Entity();
    tc_entity_id id = tc_entity_pool_alloc_with_uuid(pool, name.c_str(), uuid.c_str());
    return Entity(pool, id);
}

void Entity::add_component(Component* component) {
    if (!component || !valid()) return;

    component->entity = *this;
    tc_entity_pool_add_component(_pool, _id, component->c_component());
    component->on_added_to_entity();
}

void Entity::add_component_ptr(tc_component* c) {
    if (!c || !valid()) return;

    // For CxxComponents, set the entity reference
    if (c->kind == TC_NATIVE_COMPONENT) {
        CxxComponent* cxx = CxxComponent::from_tc(c);
        if (cxx) {
            cxx->entity = *this;
        }
    }

    tc_entity_pool_add_component(_pool, _id, c);
    tc_component_on_added_to_entity(c);
}

void Entity::remove_component(Component* component) {
    if (!component || !valid()) return;

    tc_entity_pool_remove_component(_pool, _id, component->c_component());
    component->on_removed_from_entity();
    component->entity = Entity();  // Invalid entity
}

void Entity::remove_component_ptr(tc_component* c) {
    if (!c || !valid()) return;

    tc_entity_pool_remove_component(_pool, _id, c);
    tc_component_on_removed_from_entity(c);
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

        // Get type name from tc_component
        const char* comp_type = tc->type_name ? tc->type_name :
                                (tc->vtable ? tc->vtable->type_name : nullptr);
        if (comp_type && type_name == comp_type) {
            return tc;
        }
    }
    return nullptr;
}

void Entity::set_parent(const Entity& parent_entity) {
    if (!valid()) return;

    // Check that parent is in the same pool
    if (parent_entity.valid() && parent_entity._pool != _pool) {
        throw std::runtime_error("Cannot set parent: entities must be in the same pool");
    }

    tc_entity_id parent_id = parent_entity.valid() ? parent_entity._id : TC_ENTITY_ID_INVALID;
    tc_entity_pool_set_parent(_pool, _id, parent_id);
}

Entity Entity::parent() const {
    if (!valid()) return Entity();
    tc_entity_id parent_id = tc_entity_pool_parent(_pool, _id);
    if (!tc_entity_id_valid(parent_id)) return Entity();
    return Entity(_pool, parent_id);
}

std::vector<Entity> Entity::children() const {
    std::vector<Entity> result;
    if (!valid()) return result;

    size_t count = tc_entity_pool_children_count(_pool, _id);
    result.reserve(count);

    for (size_t i = 0; i < count; i++) {
        tc_entity_id child_id = tc_entity_pool_child_at(_pool, _id, i);
        if (tc_entity_id_valid(child_id)) {
            result.push_back(Entity(_pool, child_id));
        }
    }
    return result;
}

Entity Entity::find_child(const std::string& name) const {
    if (!valid()) return Entity();

    size_t count = tc_entity_pool_children_count(_pool, _id);
    for (size_t i = 0; i < count; i++) {
        tc_entity_id child_id = tc_entity_pool_child_at(_pool, _id, i);
        if (tc_entity_id_valid(child_id)) {
            const char* child_name = tc_entity_pool_name(_pool, child_id);
            if (child_name && name == child_name) {
                return Entity(_pool, child_id);
            }
        }
    }
    return Entity();
}

void Entity::update(float dt) {
    if (!valid() || !enabled()) return;

    // Update components
    size_t count = component_count();
    for (size_t i = 0; i < count; i++) {
        tc_component* tc = component_at(i);
        if (tc && tc->enabled) {
            tc_component_update(tc, dt);
        }
    }
}

void Entity::on_added_to_scene(tc_scene* scene) {
    (void)scene;  // Pool manages lifetime
}

void Entity::on_removed_from_scene() {
    // Nothing needed - pool manages lifetime
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

    // Pose - get from pool
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
    // Note: dict_set takes ownership, don't free position

    tc_value rotation = tc_value_list_new();
    tc_value_list_push(&rotation, tc_value_double(rot[0]));
    tc_value_list_push(&rotation, tc_value_double(rot[1]));
    tc_value_list_push(&rotation, tc_value_double(rot[2]));
    tc_value_list_push(&rotation, tc_value_double(rot[3]));
    tc_value_dict_set(&pose_data, "rotation", rotation);
    // Note: dict_set takes ownership, don't free rotation

    tc_value_dict_set(&data, "pose", pose_data);
    // Note: dict_set takes ownership, don't free pose_data

    tc_value scale_v = tc_value_list_new();
    tc_value_list_push(&scale_v, tc_value_double(scl[0]));
    tc_value_list_push(&scale_v, tc_value_double(scl[1]));
    tc_value_list_push(&scale_v, tc_value_double(scl[2]));
    tc_value_dict_set(&data, "scale", scale_v);
    // Note: dict_set takes ownership, don't free scale_v

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

        // Check kind is valid
        if (tc->kind != TC_CXX_COMPONENT && tc->kind != TC_PYTHON_COMPONENT) {
            fprintf(stderr, "[validate_components] Entity '%s' component %zu has invalid kind: %d\n", name(), i, (int)tc->kind);
            return false;
        }

        // Check vtable
        if (!tc->vtable) {
            fprintf(stderr, "[validate_components] Entity '%s' component %zu has NULL vtable\n", name(), i);
            return false;
        }

        // Try to get type name
        const char* tname = tc_component_type_name(tc);
        if (!tname) {
            fprintf(stderr, "[validate_components] Entity '%s' component %zu has NULL type_name\n", name(), i);
            return false;
        }

        // Check type_name looks valid (first char is printable)
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

Entity Entity::deserialize(tc_entity_pool* pool, const tc_value* data) {
    if (!pool || !data || data->type != TC_VALUE_DICT) {
        return Entity();
    }

    std::string entity_name = tc_value_dict_string(data, "name", "entity");

    // Create entity in pool
    Entity ent = Entity::create(pool, entity_name);
    if (!ent.valid()) return Entity();

    // Restore flags
    tc_value* priority_v = tc_value_dict_get(const_cast<tc_value*>(data), "priority");
    ent.set_priority(static_cast<int>(tc_value_as_double(priority_v, 0)));

    tc_value* visible_v = tc_value_dict_get(const_cast<tc_value*>(data), "visible");
    ent.set_visible(tc_value_as_bool(visible_v, true));

    // Support both "enabled" (new) and "active" (legacy) keys
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

    // Restore pose
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

    // TODO: Deserialize components - need to adapt to new architecture

    return ent;
}

} // namespace termin
