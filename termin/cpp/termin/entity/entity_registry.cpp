#include "entity_registry.hpp"

namespace termin {

EntityRegistry& EntityRegistry::instance() {
    static EntityRegistry inst;
    return inst;
}

void EntityRegistry::register_entity(const Entity& entity) {
    if (!entity.valid()) return;

    const char* u = entity.uuid();
    if (u && u[0]) {
        by_uuid_[u] = entity;
    }

    // Also register by pick_id
    uint32_t pid = entity.pick_id();
    if (pid != 0) {
        by_pick_id_[pid] = entity;
    }
}

void EntityRegistry::unregister_entity(const Entity& entity) {
    if (!entity.valid()) return;

    const char* u = entity.uuid();
    if (u && u[0]) {
        by_uuid_.erase(u);
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

Entity EntityRegistry::get(const std::string& uuid) const {
    auto it = by_uuid_.find(uuid);
    return (it != by_uuid_.end()) ? it->second : Entity();
}

void EntityRegistry::register_pick_id(uint32_t pick_id, const Entity& entity) {
    if (entity.valid()) {
        by_pick_id_[pick_id] = entity;
    }
}

void EntityRegistry::unregister_pick_id(uint32_t pick_id) {
    by_pick_id_.erase(pick_id);
}

Entity EntityRegistry::get_by_pick_id(uint32_t pick_id) const {
    auto it = by_pick_id_.find(pick_id);
    return (it != by_pick_id_.end()) ? it->second : Entity();
}

void EntityRegistry::clear() {
    by_uuid_.clear();
    by_pick_id_.clear();
}

std::pair<std::unordered_map<std::string, Entity>,
          std::unordered_map<uint32_t, Entity>>
EntityRegistry::swap_registries(std::unordered_map<std::string, Entity> new_by_uuid,
                                std::unordered_map<uint32_t, Entity> new_by_pick_id) {
    auto old_by_uuid = std::move(by_uuid_);
    auto old_by_pick_id = std::move(by_pick_id_);

    by_uuid_ = std::move(new_by_uuid);
    by_pick_id_ = std::move(new_by_pick_id);

    return {std::move(old_by_uuid), std::move(old_by_pick_id)};
}

} // namespace termin
