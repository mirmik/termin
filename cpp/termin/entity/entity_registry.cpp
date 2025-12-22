#include "entity_registry.hpp"
#include "entity.hpp"

namespace termin {

EntityRegistry& EntityRegistry::instance() {
    static EntityRegistry inst;
    return inst;
}

void EntityRegistry::register_entity(Entity* entity) {
    if (!entity) return;

    if (!entity->uuid.empty()) {
        by_uuid_[entity->uuid] = entity;
    }

    if (entity->transform) {
        by_transform_[entity->transform.get()] = entity;
    }
}

void EntityRegistry::unregister_entity(Entity* entity) {
    if (!entity) return;

    if (!entity->uuid.empty()) {
        by_uuid_.erase(entity->uuid);
    }

    if (entity->transform) {
        by_transform_.erase(entity->transform.get());
    }

    // Also remove from pick_id registry if registered
    for (auto it = by_pick_id_.begin(); it != by_pick_id_.end(); ) {
        if (it->second == entity) {
            it = by_pick_id_.erase(it);
        } else {
            ++it;
        }
    }
}

Entity* EntityRegistry::get(const std::string& uuid) const {
    auto it = by_uuid_.find(uuid);
    return (it != by_uuid_.end()) ? it->second : nullptr;
}

void EntityRegistry::register_pick_id(uint32_t pick_id, Entity* entity) {
    if (entity) {
        by_pick_id_[pick_id] = entity;
    }
}

void EntityRegistry::unregister_pick_id(uint32_t pick_id) {
    by_pick_id_.erase(pick_id);
}

Entity* EntityRegistry::get_by_pick_id(uint32_t pick_id) const {
    auto it = by_pick_id_.find(pick_id);
    return (it != by_pick_id_.end()) ? it->second : nullptr;
}

Entity* EntityRegistry::get_by_transform(geom::GeneralTransform3* transform) const {
    if (!transform) return nullptr;
    auto it = by_transform_.find(transform);
    return (it != by_transform_.end()) ? it->second : nullptr;
}

void EntityRegistry::clear() {
    by_uuid_.clear();
    by_pick_id_.clear();
    by_transform_.clear();
}

} // namespace termin
