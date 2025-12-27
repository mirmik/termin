#include "entity.hpp"
#include "component.hpp"
#include "entity_registry.hpp"
#include "component_registry.hpp"
#include "../inspect/inspect_registry.hpp"
#include <algorithm>
#include <iostream>
#include <cstdio>

namespace termin {

Entity::Entity(const std::string& name, const std::string& uuid) {
    // Create tc_entity which owns all data
    _e = tc_entity_new_with_uuid(name.c_str(), uuid.empty() ? nullptr : uuid.c_str());
    // Set back-pointer for entity_from_tc()
    tc_entity_set_data(_e, this);
    // Register in C++ registry (for Python bindings lookup)
    EntityRegistry::instance().register_entity(this);
}

Entity::Entity(const GeneralPose3& pose, const std::string& name, const std::string& uuid) {
    // Create tc_entity which owns all data
    _e = tc_entity_new_with_uuid(name.c_str(), uuid.empty() ? nullptr : uuid.c_str());
    // Set pose
    tc_entity_set_local_pose(_e, *reinterpret_cast<const tc_general_pose3*>(&pose));
    // Set back-pointer
    tc_entity_set_data(_e, this);
    // Register
    EntityRegistry::instance().register_entity(this);
}

Entity::Entity(tc_entity* e) : _e(e) {
    if (_e) {
        // Set back-pointer
        tc_entity_set_data(_e, this);
        // Register
        EntityRegistry::instance().register_entity(this);
    }
}

Entity::~Entity() {
    if (_e) {
        // Unregister from registry
        EntityRegistry::instance().unregister_entity(this);

        // Clean up C++ components
        size_t count = tc_entity_component_count(_e);
        for (size_t i = 0; i < count; i++) {
            tc_component* tc = tc_entity_component_at(_e, i);
            if (tc && tc->is_native) {
                Component* comp = static_cast<Component*>(tc->data);
                if (comp) {
                    comp->on_removed_from_entity();
                    comp->entity = nullptr;
                    delete comp;
                }
            }
            // PythonComponents are managed by Python GC
        }

        tc_entity_free(_e);
        _e = nullptr;
    }
}

Entity::Entity(Entity&& other) noexcept : _e(other._e) {
    other._e = nullptr;

    if (_e) {
        // Update back-pointer
        tc_entity_set_data(_e, this);

        // Update component->entity pointers
        size_t count = tc_entity_component_count(_e);
        for (size_t i = 0; i < count; i++) {
            tc_component* tc = tc_entity_component_at(_e, i);
            if (tc && tc->is_native) {
                Component* comp = static_cast<Component*>(tc->data);
                if (comp) comp->entity = this;
            }
        }

        // Re-register with new address
        EntityRegistry::instance().register_entity(this);
    }
}

Entity& Entity::operator=(Entity&& other) noexcept {
    if (this != &other) {
        // Clean up old
        if (_e) {
            EntityRegistry::instance().unregister_entity(this);
            size_t count = tc_entity_component_count(_e);
            for (size_t i = 0; i < count; i++) {
                tc_component* tc = tc_entity_component_at(_e, i);
                if (tc && tc->is_native) {
                    Component* comp = static_cast<Component*>(tc->data);
                    if (comp) {
                        comp->on_removed_from_entity();
                        comp->entity = nullptr;
                        delete comp;
                    }
                }
            }
            tc_entity_free(_e);
        }

        _e = other._e;
        other._e = nullptr;

        if (_e) {
            // Update back-pointer
            tc_entity_set_data(_e, this);

            // Update component->entity pointers
            size_t count = tc_entity_component_count(_e);
            for (size_t i = 0; i < count; i++) {
                tc_component* tc = tc_entity_component_at(_e, i);
                if (tc && tc->is_native) {
                    Component* comp = static_cast<Component*>(tc->data);
                    if (comp) comp->entity = this;
                }
            }

            EntityRegistry::instance().register_entity(this);
        }
    }
    return *this;
}

void Entity::add_component(Component* component) {
    if (!component || !_e) return;

    component->entity = this;
    component->sync_to_c();
    tc_entity_add_component(_e, component->c_component());
    component->on_added_to_entity();
}

void Entity::add_component_ptr(tc_component* c) {
    if (!c || !_e) return;

    tc_entity_add_component(_e, c);
    tc_component_on_added_to_entity(c);
}

void Entity::remove_component(Component* component) {
    if (!component || !_e) return;

    tc_entity_remove_component(_e, component->c_component());
    component->on_removed_from_entity();
    component->entity = nullptr;
}

void Entity::remove_component_ptr(tc_component* c) {
    if (!c || !_e) return;

    tc_entity_remove_component(_e, c);
    tc_component_on_removed_from_entity(c);
}

Component* Entity::get_component_by_type(const std::string& type_name) {
    size_t count = component_count();
    for (size_t i = 0; i < count; i++) {
        tc_component* tc = component_at(i);
        if (tc && tc->is_native) {
            Component* comp = static_cast<Component*>(tc->data);
            if (comp && comp->type_name() == type_name) {
                return comp;
            }
        }
    }
    return nullptr;
}

void Entity::set_parent(Entity* parent_entity) {
    if (!_e) return;
    tc_entity_set_parent(_e, parent_entity ? parent_entity->_e : nullptr);
}

Entity* Entity::parent() const {
    if (!_e) return nullptr;
    tc_entity* pe = tc_entity_parent(_e);
    return entity_from_tc(pe);
}

std::vector<Entity*> Entity::children() const {
    std::vector<Entity*> result;
    if (!_e) return result;

    size_t count = tc_entity_children_count(_e);
    result.reserve(count);

    for (size_t i = 0; i < count; i++) {
        tc_entity* ce = tc_entity_child_at(_e, i);
        Entity* child = entity_from_tc(ce);
        if (child) {
            result.push_back(child);
        }
    }
    return result;
}

void Entity::update(float dt) {
    if (!_e || !active()) return;
    tc_entity_update(_e, dt);
}

void Entity::on_added_to_scene(py::object scene) {
    if (!_e) return;
    // Scene is stored as void* in tc_entity
    // For now, we don't store the Python object directly
    tc_entity_on_added_to_scene(_e, nullptr);
}

void Entity::on_removed_from_scene() {
    if (!_e) return;
    tc_entity_on_removed_from_scene(_e);
}

nos::trent Entity::serialize() const {
    if (!_e || !serializable()) {
        return nos::trent::nil();
    }

    nos::trent data;
    data.init(nos::trent_type::dict);

    data["uuid"] = std::string(uuid());
    data["name"] = std::string(name());
    data["priority"] = priority();
    data["visible"] = visible();
    data["active"] = active();
    data["pickable"] = pickable();
    data["selectable"] = selectable();
    data["layer"] = static_cast<int64_t>(layer());
    data["flags"] = static_cast<int64_t>(flags());

    // Pose
    const auto& pose = transform().local_pose();
    nos::trent pose_data;
    pose_data.init(nos::trent_type::dict);

    nos::trent position;
    position.init(nos::trent_type::list);
    position.as_list().push_back(pose.lin.x);
    position.as_list().push_back(pose.lin.y);
    position.as_list().push_back(pose.lin.z);
    pose_data["position"] = std::move(position);

    nos::trent rotation;
    rotation.init(nos::trent_type::list);
    rotation.as_list().push_back(pose.ang.x);
    rotation.as_list().push_back(pose.ang.y);
    rotation.as_list().push_back(pose.ang.z);
    rotation.as_list().push_back(pose.ang.w);
    pose_data["rotation"] = std::move(rotation);

    data["pose"] = std::move(pose_data);

    nos::trent scale;
    scale.init(nos::trent_type::list);
    scale.as_list().push_back(pose.scale.x);
    scale.as_list().push_back(pose.scale.y);
    scale.as_list().push_back(pose.scale.z);
    data["scale"] = std::move(scale);

    // Children
    nos::trent children_data;
    children_data.init(nos::trent_type::list);
    for (auto* child : children()) {
        if (child->serializable()) {
            children_data.as_list().push_back(child->serialize());
        }
    }
    data["children"] = std::move(children_data);

    return data;
}

Entity* Entity::deserialize(const nos::trent& data) {
    if (data.is_nil() || !data.is_dict()) {
        return nullptr;
    }

    std::string entity_uuid = data["uuid"].as_string_default("");
    std::string entity_name = data["name"].as_string_default("entity");

    // Create entity
    Entity* ent = new Entity(entity_name, entity_uuid);

    // Restore flags
    ent->set_priority(static_cast<int>(data["priority"].as_numer_default(0)));
    ent->set_visible(data["visible"].as_bool_default(true));
    ent->set_active(data["active"].as_bool_default(true));
    ent->set_pickable(data["pickable"].as_bool_default(true));
    ent->set_selectable(data["selectable"].as_bool_default(true));
    ent->set_layer(static_cast<uint64_t>(data["layer"].as_numer_default(1)));
    ent->set_flags(static_cast<uint64_t>(data["flags"].as_numer_default(0)));

    // Restore pose
    const nos::trent* pose_ptr = data.get(nos::trent_path("pose"));
    if (pose_ptr && pose_ptr->is_dict()) {
        GeneralPose3 pose;

        const nos::trent* pos = pose_ptr->get(nos::trent_path("position"));
        if (pos && pos->is_list() && pos->as_list().size() >= 3) {
            pose.lin.x = pos->at(0).as_numer();
            pose.lin.y = pos->at(1).as_numer();
            pose.lin.z = pos->at(2).as_numer();
        }

        const nos::trent* rot = pose_ptr->get(nos::trent_path("rotation"));
        if (rot && rot->is_list() && rot->as_list().size() >= 4) {
            pose.ang.x = rot->at(0).as_numer();
            pose.ang.y = rot->at(1).as_numer();
            pose.ang.z = rot->at(2).as_numer();
            pose.ang.w = rot->at(3).as_numer();
        }

        const nos::trent* scl = data.get(nos::trent_path("scale"));
        if (scl && scl->is_list() && scl->as_list().size() >= 3) {
            pose.scale.x = scl->at(0).as_numer();
            pose.scale.y = scl->at(1).as_numer();
            pose.scale.z = scl->at(2).as_numer();
        }

        ent->transform().set_local_pose(pose);
    }

    // Deserialize components
    const nos::trent* components_ptr = data.get(nos::trent_path("components"));
    if (components_ptr && components_ptr->is_list()) {
        ComponentRegistry& reg = ComponentRegistry::instance();

        for (const auto& comp_data : components_ptr->as_list()) {
            if (!comp_data.is_dict()) continue;

            std::string comp_type = comp_data["type"].as_string_default("");
            if (comp_type.empty() || !reg.has(comp_type)) continue;

            Component* comp = reg.create_component(comp_type);
            if (!comp) continue;

            // Deserialize component data via InspectRegistry
            const nos::trent* inner = comp_data.get(nos::trent_path("data"));
            if (inner && inner->is_dict()) {
                InspectRegistry::instance().deserialize_all(comp, comp_type, *inner);
            }

            ent->add_component(comp);
        }
    }

    return ent;
}

} // namespace termin
