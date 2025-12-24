#include "scene.hpp"
#include "termin/entity/entity.hpp"
#include "termin/entity/component.hpp"
#include <algorithm>

namespace termin {

Scene::Scene(const std::string& uuid_)
    : Identifiable(uuid_)
    , on_entity_added(py::none())
    , on_entity_removed(py::none()) {
}

Scene::~Scene() {
    // Clear entities but don't delete them - Python owns them
    entities_.clear();
    update_list_.clear();
    fixed_update_list_.clear();
    pending_start_.clear();
}

void Scene::add_non_recurse(Entity* entity) {
    if (entity == nullptr) return;

    // Insert sorted by priority
    auto it = std::lower_bound(
        entities_.begin(), entities_.end(), entity,
        [](Entity* a, Entity* b) { return a->priority <= b->priority; }
    );
    entities_.insert(it, entity);

    // Set scene reference on entity (as Python object for now)
    // entity->scene will be set from Python side

    // Emit event
    if (!on_entity_added.is_none()) {
        py::gil_scoped_acquire gil;
        on_entity_added(py::cast(entity));
    }
}

void Scene::add(Entity* entity) {
    if (entity == nullptr) return;

    add_non_recurse(entity);

    // Recursively add children
    for (auto* child_trans : entity->transform->children) {
        if (child_trans->entity != nullptr) {
            add(child_trans->entity);
        }
    }
}

void Scene::remove(Entity* entity) {
    if (entity == nullptr) return;

    auto it = std::find(entities_.begin(), entities_.end(), entity);
    if (it != entities_.end()) {
        entities_.erase(it);

        // Emit event
        if (!on_entity_removed.is_none()) {
            py::gil_scoped_acquire gil;
            on_entity_removed(py::cast(entity));
        }
    }
}

Entity* Scene::find_entity_by_uuid(const std::string& uuid) const {
    for (Entity* entity : entities_) {
        Entity* result = find_entity_recursive(entity, uuid);
        if (result != nullptr) {
            return result;
        }
    }
    return nullptr;
}

Entity* Scene::find_entity_recursive(Entity* entity, const std::string& uuid) const {
    if (entity->uuid == uuid) {
        return entity;
    }

    for (auto* child_trans : entity->transform->children) {
        if (child_trans->entity != nullptr) {
            Entity* result = find_entity_recursive(child_trans->entity, uuid);
            if (result != nullptr) {
                return result;
            }
        }
    }

    return nullptr;
}

void Scene::register_component(Component* component) {
    if (component == nullptr) return;

    // Check if component has update/fixed_update
    if (component->has_update) {
        update_list_.push_back(component);
    }
    if (component->has_fixed_update) {
        fixed_update_list_.push_back(component);
    }

    // Add to pending start if not started
    if (!component->_started) {
        pending_start_.push_back(component);
    }
}

void Scene::unregister_component(Component* component) {
    if (component == nullptr) return;

    // Remove from update lists
    update_list_.erase(
        std::remove(update_list_.begin(), update_list_.end(), component),
        update_list_.end()
    );
    fixed_update_list_.erase(
        std::remove(fixed_update_list_.begin(), fixed_update_list_.end(), component),
        fixed_update_list_.end()
    );
    pending_start_.erase(
        std::remove(pending_start_.begin(), pending_start_.end(), component),
        pending_start_.end()
    );
}

void Scene::update(double dt) {
    // Start pending components
    if (!pending_start_.empty()) {
        std::vector<Component*> pending = std::move(pending_start_);
        pending_start_.clear();

        for (Component* component : pending) {
            if (component->_started) continue;
            if (component->enabled) {
                component->start();
                component->_started = true;
            } else {
                // Keep disabled components pending
                pending_start_.push_back(component);
            }
        }
    }

    // Fixed update loop
    accumulated_time_ += dt;
    while (accumulated_time_ >= fixed_timestep) {
        for (Component* component : fixed_update_list_) {
            if (component->enabled) {
                component->fixed_update(static_cast<float>(fixed_timestep));
            }
        }
        accumulated_time_ -= fixed_timestep;
    }

    // Regular update
    for (Component* component : update_list_) {
        if (component->enabled) {
            component->update(static_cast<float>(dt));
        }
    }
}

} // namespace termin
