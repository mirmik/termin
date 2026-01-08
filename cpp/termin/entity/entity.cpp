#include "entity.hpp"
#include "component.hpp"
#include "../../../core_c/include/tc_scene.h"
#include <algorithm>

namespace termin {

// Global standalone pool for entities created outside of Scene
static tc_entity_pool* g_standalone_pool = nullptr;

void Entity::deserialize_from(const nos::trent& data, tc_scene* scene) {
    // Get UUID from trent
    std::string uuid_str;
    if (data.is_string()) {
        uuid_str = data.as_string();
    } else if (data.is_dict() && data.contains("uuid")) {
        uuid_str = data["uuid"].as_string();
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

nb::object Entity::get_python_component(const std::string& type_name) {
    size_t count = component_count();
    for (size_t i = 0; i < count; i++) {
        tc_component* tc = component_at(i);
        if (tc && tc->kind == TC_PYTHON_COMPONENT && tc->py_wrap) {
            const char* comp_type = tc->type_name ? tc->type_name :
                                    (tc->vtable ? tc->vtable->type_name : nullptr);
            if (comp_type && type_name == comp_type) {
                return nb::borrow((PyObject*)tc->py_wrap);
            }
        }
    }
    return nb::none();
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

void Entity::on_added_to_scene(nb::object scene) {
    // Nothing needed - pool manages lifetime
}

void Entity::on_removed_from_scene() {
    // Nothing needed - pool manages lifetime
}

nos::trent Entity::serialize_base() const {
    if (!valid() || !serializable()) {
        return nos::trent::nil();
    }

    nos::trent data;
    data.init(nos::trent_type::dict);

    data["uuid"] = std::string(uuid());
    data["name"] = std::string(name());
    data["priority"] = priority();
    data["visible"] = visible();
    data["enabled"] = enabled();
    data["pickable"] = pickable();
    data["selectable"] = selectable();
    data["layer"] = static_cast<int64_t>(layer());
    data["flags"] = static_cast<int64_t>(flags());

    // Pose - get from pool
    double pos[3], rot[4], scale[3];
    get_local_position(pos);
    get_local_rotation(rot);
    get_local_scale(scale);

    nos::trent pose_data;
    pose_data.init(nos::trent_type::dict);

    nos::trent position;
    position.init(nos::trent_type::list);
    position.as_list().push_back(pos[0]);
    position.as_list().push_back(pos[1]);
    position.as_list().push_back(pos[2]);
    pose_data["position"] = std::move(position);

    nos::trent rotation;
    rotation.init(nos::trent_type::list);
    rotation.as_list().push_back(rot[0]);
    rotation.as_list().push_back(rot[1]);
    rotation.as_list().push_back(rot[2]);
    rotation.as_list().push_back(rot[3]);
    pose_data["rotation"] = std::move(rotation);

    data["pose"] = std::move(pose_data);

    nos::trent scale_t;
    scale_t.init(nos::trent_type::list);
    scale_t.as_list().push_back(scale[0]);
    scale_t.as_list().push_back(scale[1]);
    scale_t.as_list().push_back(scale[2]);
    data["scale"] = std::move(scale_t);

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

Entity Entity::deserialize(tc_entity_pool* pool, const nos::trent& data) {
    if (!pool || data.is_nil() || !data.is_dict()) {
        return Entity();
    }

    std::string entity_name = data["name"].as_string_default("entity");

    // Create entity in pool
    Entity ent = Entity::create(pool, entity_name);
    if (!ent.valid()) return Entity();

    // Restore flags
    ent.set_priority(static_cast<int>(data["priority"].as_numer_default(0)));
    ent.set_visible(data["visible"].as_bool_default(true));
    // Support both "enabled" (new) and "active" (legacy) keys
    if (data.contains("enabled")) {
        ent.set_enabled(data["enabled"].as_bool_default(true));
    } else {
        ent.set_enabled(data["active"].as_bool_default(true));
    }
    ent.set_pickable(data["pickable"].as_bool_default(true));
    ent.set_selectable(data["selectable"].as_bool_default(true));
    ent.set_layer(static_cast<uint64_t>(data["layer"].as_numer_default(1)));
    ent.set_flags(static_cast<uint64_t>(data["flags"].as_numer_default(0)));

    // Restore pose
    const nos::trent* pose_ptr = data.get(nos::trent_path("pose"));
    if (pose_ptr && pose_ptr->is_dict()) {
        const nos::trent* pos = pose_ptr->get(nos::trent_path("position"));
        if (pos && pos->is_list() && pos->as_list().size() >= 3) {
            double xyz[3] = {pos->at(0).as_numer(), pos->at(1).as_numer(), pos->at(2).as_numer()};
            ent.set_local_position(xyz);
        }

        const nos::trent* rot = pose_ptr->get(nos::trent_path("rotation"));
        if (rot && rot->is_list() && rot->as_list().size() >= 4) {
            double xyzw[4] = {rot->at(0).as_numer(), rot->at(1).as_numer(), rot->at(2).as_numer(), rot->at(3).as_numer()};
            ent.set_local_rotation(xyzw);
        }
    }

    const nos::trent* scl = data.get(nos::trent_path("scale"));
    if (scl && scl->is_list() && scl->as_list().size() >= 3) {
        double xyz[3] = {scl->at(0).as_numer(), scl->at(1).as_numer(), scl->at(2).as_numer()};
        ent.set_local_scale(xyz);
    }

    // TODO: Deserialize components - need to adapt to new architecture

    return ent;
}

} // namespace termin
