#include "entity.hpp"
#include "component.hpp"
#include "entity_registry.hpp"
#include "component_registry.hpp"
#include "../inspect/inspect_registry.hpp"
#include <algorithm>
#include <iostream>
#include <cstdio>

namespace termin {

Entity::Entity(const std::string& name_, const std::string& uuid_)
    : Identifiable(uuid_)
    , name(name_) {

    // Create tc_entity which owns the transform
    _ensure_c_entity();
    // Get transform view from tc_entity
    transform = GeneralTransform3(tc_entity_transform(_e));
    transform.set_entity(this);
    // Register in global registry
    EntityRegistry::instance().register_entity(this);
}

Entity::Entity(const GeneralPose3& pose, const std::string& name_, const std::string& uuid_)
    : Identifiable(uuid_)
    , name(name_) {

    // Create tc_entity which owns the transform
    _ensure_c_entity();
    // Get transform view from tc_entity
    transform = GeneralTransform3(tc_entity_transform(_e));
    transform.set_local_pose(pose);
    transform.set_entity(this);
    EntityRegistry::instance().register_entity(this);
}

Entity::~Entity() {
    // Unregister from registry
    EntityRegistry::instance().unregister_entity(this);

    // Clean up C entity if created
    if (_e) {
        // Call on_removed_from_entity and clean up components
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

Entity::Entity(Entity&& other) noexcept
    : Identifiable(std::move(other))
    , name(std::move(other.name))
    , visible(other.visible)
    , active(other.active)
    , pickable(other.pickable)
    , selectable(other.selectable)
    , priority(other.priority)
    , layer(other.layer)
    , flags(other.flags)
    , _pick_id(other._pick_id)
    , _pick_id_computed(other._pick_id_computed)
    , _e(other._e) {

    // Take ownership of _e
    other._e = nullptr;
    other.transform = GeneralTransform3(nullptr);

    // Update transform view to point to our _e's transform
    if (_e) {
        transform = GeneralTransform3(tc_entity_transform(_e));
        transform.set_entity(this);

        // Update component->entity pointers
        size_t count = tc_entity_component_count(_e);
        for (size_t i = 0; i < count; i++) {
            tc_component* tc = tc_entity_component_at(_e, i);
            if (tc && tc->is_native) {
                Component* comp = static_cast<Component*>(tc->data);
                if (comp) comp->entity = this;
            }
        }
    }

    // Re-register with new address
    EntityRegistry::instance().register_entity(this);
}

Entity& Entity::operator=(Entity&& other) noexcept {
    if (this != &other) {
        // Clean up old components
        if (_e) {
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

        Identifiable::operator=(std::move(other));
        name = std::move(other.name);
        visible = other.visible;
        active = other.active;
        pickable = other.pickable;
        selectable = other.selectable;
        priority = other.priority;
        layer = other.layer;
        flags = other.flags;
        _pick_id = other._pick_id;
        _pick_id_computed = other._pick_id_computed;
        _e = other._e;
        other._e = nullptr;
        other.transform = GeneralTransform3(nullptr);

        // Update transform view
        if (_e) {
            transform = GeneralTransform3(tc_entity_transform(_e));
            transform.set_entity(this);

            // Update component->entity pointers
            size_t count = tc_entity_component_count(_e);
            for (size_t i = 0; i < count; i++) {
                tc_component* tc = tc_entity_component_at(_e, i);
                if (tc && tc->is_native) {
                    Component* comp = static_cast<Component*>(tc->data);
                    if (comp) comp->entity = this;
                }
            }
        }

        EntityRegistry::instance().register_entity(this);
    }
    return *this;
}

void Entity::_compute_pick_id() {
    if (_pick_id_computed) return;

    // Hash from uuid (take lower 31 bits)
    // Remove dashes and convert to uint64
    std::string hex_only;
    for (char c : uuid) {
        if (c != '-') hex_only += c;
    }

    // Simple hash - take lower 31 bits of numeric value
    uint32_t h = 0;
    for (size_t i = 0; i < hex_only.size() && i < 8; ++i) {
        char c = hex_only[i];
        int val = (c >= '0' && c <= '9') ? (c - '0')
                : (c >= 'a' && c <= 'f') ? (c - 'a' + 10)
                : (c >= 'A' && c <= 'F') ? (c - 'A' + 10) : 0;
        h = (h << 4) | val;
    }
    h = h & 0x7FFFFFFF;  // 31-bit positive
    if (h == 0) h = 1;   // 0 means "nothing hit"

    _pick_id = h;
    _pick_id_computed = true;

    EntityRegistry::instance().register_pick_id(_pick_id, this);
}

uint32_t Entity::pick_id() {
    if (!_pick_id_computed) {
        _compute_pick_id();
    }
    return _pick_id;
}

void Entity::add_component(Component* component) {
    if (!component) return;

    _ensure_c_entity();

    component->entity = this;
    component->sync_to_c();
    tc_entity_add_component(_e, component->c_component());
    component->on_added_to_entity();

    // Note: start() is NOT called here anymore.
    // The Python binding handles the full lifecycle:
    // 1) register_component, 2) on_added(scene), 3) start()
}

void Entity::add_component_ptr(tc_component* c) {
    if (!c) return;

    _ensure_c_entity();
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

size_t Entity::component_count() const {
    return _e ? tc_entity_component_count(_e) : 0;
}

tc_component* Entity::component_at(size_t index) const {
    return _e ? tc_entity_component_at(const_cast<tc_entity*>(_e), index) : nullptr;
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
    if (parent_entity) {
        transform.set_parent(parent_entity->transform);
    } else {
        transform.unparent();
    }
}

Entity* Entity::parent() const {
    GeneralTransform3 parent_transform = transform.parent();
    if (!parent_transform.valid()) return nullptr;

    // Use back-pointer from transform
    return parent_transform.entity();
}

std::vector<Entity*> Entity::children() const {
    std::vector<Entity*> result;
    size_t count = transform.children_count();
    result.reserve(count);

    for (size_t i = 0; i < count; i++) {
        GeneralTransform3 child_transform = transform.child_at(i);
        Entity* child_entity = child_transform.entity();
        if (child_entity) {
            result.push_back(child_entity);
        }
    }
    return result;
}

void Entity::update(float dt) {
    if (!active) return;

    // Update is now handled by tc_scene
    // This method is kept for backwards compatibility with direct Entity.update() calls
    size_t count = component_count();
    for (size_t i = 0; i < count; i++) {
        tc_component* tc = component_at(i);
        if (tc && tc->enabled) {
            tc_component_update(tc, dt);
        }
    }
}

void Entity::on_added_to_scene(py::object) {
    // on_added is called from tc_scene_register_component
    // start is called from tc_scene update loop via pending_start
    // Nothing to do here - kept for API compatibility
}

void Entity::on_removed_from_scene() {
    size_t count = component_count();
    for (size_t i = 0; i < count; i++) {
        tc_component* tc = component_at(i);
        if (tc) {
            tc_component_on_destroy(tc);
        }
    }
}

nos::trent Entity::serialize() const {
    if (!serializable) {
        return nos::trent::nil();
    }

    nos::trent data;
    data.init(nos::trent_type::dict);

    data["uuid"] = uuid;
    data["name"] = name;
    data["priority"] = priority;
    data["visible"] = visible;
    data["active"] = active;
    data["pickable"] = pickable;
    data["selectable"] = selectable;
    data["layer"] = static_cast<int64_t>(layer);
    data["flags"] = static_cast<int64_t>(flags);

    // Pose
    const auto& pose = transform.local_pose();
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

    // Components - will be handled by Python wrapper for now
    // (components need their own serialize methods)

    // Children
    nos::trent children_data;
    children_data.init(nos::trent_type::list);
    for (auto* child : children()) {
        if (child->serializable) {
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
    ent->priority = static_cast<int>(data["priority"].as_numer_default(0));
    ent->visible = data["visible"].as_bool_default(true);
    ent->active = data["active"].as_bool_default(true);
    ent->pickable = data["pickable"].as_bool_default(true);
    ent->selectable = data["selectable"].as_bool_default(true);
    ent->layer = static_cast<uint64_t>(data["layer"].as_numer_default(1));
    ent->flags = static_cast<uint64_t>(data["flags"].as_numer_default(0));

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

        ent->transform.set_local_pose(pose);
    }

    // Deserialize components (children are handled by Scene)
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

// ============================================================================
// C Core Integration
// ============================================================================

void Entity::_ensure_c_entity() {
    if (_e) return;

    // Create tc_entity with our uuid
    _e = tc_entity_new_with_uuid(name.c_str(), uuid.c_str());

    // Initial sync
    sync_to_c();
}

tc_entity* Entity::c_entity() {
    _ensure_c_entity();
    return _e;
}

void Entity::sync_to_c() {
    if (!_e) return;

    // Sync flags
    tc_entity_set_visible(_e, visible);
    tc_entity_set_active(_e, active);
    tc_entity_set_pickable(_e, pickable);
    tc_entity_set_selectable(_e, selectable);
    tc_entity_set_serializable(_e, serializable);
    tc_entity_set_priority(_e, priority);
    tc_entity_set_layer(_e, layer);
    tc_entity_set_flags(_e, flags);

    // Sync name if changed
    if (name != tc_entity_name(_e)) {
        tc_entity_set_name(_e, name.c_str());
    }

    // Sync C++ components (components are already in tc_entity)
    size_t count = tc_entity_component_count(_e);
    for (size_t i = 0; i < count; i++) {
        tc_component* tc = tc_entity_component_at(_e, i);
        if (tc && tc->is_native) {
            Component* comp = static_cast<Component*>(tc->data);
            if (comp) comp->sync_to_c();
        }
    }
}

void Entity::sync_from_c() {
    if (!_e) return;

    // Sync flags back
    visible = tc_entity_visible(_e);
    active = tc_entity_active(_e);
    pickable = tc_entity_pickable(_e);
    selectable = tc_entity_selectable(_e);
    serializable = tc_entity_serializable(_e);
    priority = tc_entity_priority(_e);
    layer = tc_entity_layer(_e);
    flags = tc_entity_flags(_e);

    // Sync C++ components back
    size_t count = tc_entity_component_count(_e);
    for (size_t i = 0; i < count; i++) {
        tc_component* tc = tc_entity_component_at(_e, i);
        if (tc && tc->is_native) {
            Component* comp = static_cast<Component*>(tc->data);
            if (comp) comp->sync_from_c();
        }
    }
}

} // namespace termin
