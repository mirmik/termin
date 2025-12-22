#include "entity.hpp"
#include "component.hpp"
#include "entity_registry.hpp"
#include <algorithm>
#include <iostream>
#include <random>
#include <sstream>
#include <iomanip>

namespace termin {

namespace {

// Generate UUID v4
std::string generate_uuid() {
    static std::random_device rd;
    static std::mt19937_64 gen(rd());
    static std::uniform_int_distribution<uint64_t> dist;

    uint64_t a = dist(gen);
    uint64_t b = dist(gen);

    // Set version (4) and variant bits
    a = (a & 0xFFFFFFFFFFFF0FFFULL) | 0x0000000000004000ULL;
    b = (b & 0x3FFFFFFFFFFFFFFFULL) | 0x8000000000000000ULL;

    std::ostringstream ss;
    ss << std::hex << std::setfill('0');
    ss << std::setw(8) << ((a >> 32) & 0xFFFFFFFF) << "-";
    ss << std::setw(4) << ((a >> 16) & 0xFFFF) << "-";
    ss << std::setw(4) << (a & 0xFFFF) << "-";
    ss << std::setw(4) << ((b >> 48) & 0xFFFF) << "-";
    ss << std::setw(12) << (b & 0xFFFFFFFFFFFFULL);
    return ss.str();
}

} // anonymous namespace

Entity::Entity(const std::string& name_, const std::string& uuid_)
    : uuid(uuid_.empty() ? generate_uuid() : uuid_)
    , name(name_)
    , transform(std::make_unique<geom::GeneralTransform3>())
    , scene(py::none()) {

    // Register in global registry
    EntityRegistry::instance().register_entity(this);
}

Entity::Entity(const geom::GeneralPose3& pose, const std::string& name_, const std::string& uuid_)
    : uuid(uuid_.empty() ? generate_uuid() : uuid_)
    , name(name_)
    , transform(std::make_unique<geom::GeneralTransform3>(pose))
    , scene(py::none()) {

    EntityRegistry::instance().register_entity(this);
}

Entity::~Entity() {
    // Unregister from registry
    EntityRegistry::instance().unregister_entity(this);

    // Clean up components
    for (Component* comp : components) {
        comp->on_removed_from_entity();
        comp->entity = nullptr;
        if (comp->is_native) {
            delete comp;
        }
    }
    components.clear();
}

Entity::Entity(Entity&& other) noexcept
    : uuid(std::move(other.uuid))
    , name(std::move(other.name))
    , transform(std::move(other.transform))
    , visible(other.visible)
    , active(other.active)
    , pickable(other.pickable)
    , selectable(other.selectable)
    , priority(other.priority)
    , layer(other.layer)
    , flags(other.flags)
    , scene(std::move(other.scene))
    , components(std::move(other.components))
    , _pick_id(other._pick_id)
    , _pick_id_computed(other._pick_id_computed) {

    // Update component->entity pointers
    for (Component* comp : components) {
        comp->entity = this;
    }

    // Re-register with new address
    EntityRegistry::instance().register_entity(this);
}

Entity& Entity::operator=(Entity&& other) noexcept {
    if (this != &other) {
        // Clean up old components
        for (Component* comp : components) {
            comp->on_removed_from_entity();
            comp->entity = nullptr;
            if (comp->is_native) {
                delete comp;
            }
        }

        uuid = std::move(other.uuid);
        name = std::move(other.name);
        transform = std::move(other.transform);
        visible = other.visible;
        active = other.active;
        pickable = other.pickable;
        selectable = other.selectable;
        priority = other.priority;
        layer = other.layer;
        flags = other.flags;
        scene = std::move(other.scene);
        components = std::move(other.components);
        _pick_id = other._pick_id;
        _pick_id_computed = other._pick_id_computed;

        for (Component* comp : components) {
            comp->entity = this;
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

    component->entity = this;
    components.push_back(component);
    component->on_added_to_entity();

    // If we're in a scene, notify component
    if (!scene.is_none()) {
        component->start();
    }
}

void Entity::remove_component(Component* component) {
    if (!component) return;

    auto it = std::find(components.begin(), components.end(), component);
    if (it == components.end()) return;

    component->on_removed_from_entity();
    component->entity = nullptr;
    components.erase(it);
}

Component* Entity::get_component_by_type(const std::string& type_name) {
    for (Component* comp : components) {
        if (comp->type_name() == type_name) {
            return comp;
        }
    }
    return nullptr;
}

void Entity::set_parent(Entity* parent_entity) {
    if (parent_entity) {
        transform->set_parent(parent_entity->transform.get());
    } else {
        transform->unparent();
    }
}

Entity* Entity::parent() const {
    geom::GeneralTransform3* parent_transform = transform->parent;
    if (!parent_transform) return nullptr;

    // Find entity that owns this transform via registry lookup
    // For now we use a simple search - could optimize with back-pointer
    return EntityRegistry::instance().get_by_transform(parent_transform);
}

std::vector<Entity*> Entity::children() const {
    std::vector<Entity*> result;
    result.reserve(transform->children.size());

    for (geom::GeneralTransform3* child_transform : transform->children) {
        Entity* child_entity = EntityRegistry::instance().get_by_transform(child_transform);
        if (child_entity) {
            result.push_back(child_entity);
        }
    }
    return result;
}

void Entity::update(float dt) {
    if (!active) return;

    for (Component* comp : components) {
        if (comp->enabled) {
            comp->update(dt);
        }
    }
}

void Entity::on_added_to_scene(py::object scene_) {
    scene = scene_;

    for (Component* comp : components) {
        comp->start();
    }
}

void Entity::on_removed_from_scene() {
    for (Component* comp : components) {
        comp->on_destroy();
    }
    scene = py::none();
}

} // namespace termin
