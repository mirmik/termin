#pragma once

#include <string>
#include <unordered_map>
#include <cstdint>

namespace termin {

class Entity;

namespace geom {
    struct GeneralTransform3;
}

/**
 * Global registry for entity lookup by UUID, pick_id, and transform.
 *
 * Singleton pattern. Entities register themselves on creation
 * and unregister on destruction.
 */
class EntityRegistry {
public:
    // Singleton access
    static EntityRegistry& instance();

    // Registration by UUID
    void register_entity(Entity* entity);
    void unregister_entity(Entity* entity);
    Entity* get(const std::string& uuid) const;

    // Registration by pick_id
    void register_pick_id(uint32_t pick_id, Entity* entity);
    void unregister_pick_id(uint32_t pick_id);
    Entity* get_by_pick_id(uint32_t pick_id) const;

    // Lookup by transform (for parent/children resolution)
    Entity* get_by_transform(geom::GeneralTransform3* transform) const;

    // Clear all (for testing)
    void clear();

    // Stats
    size_t entity_count() const { return by_uuid_.size(); }

private:
    EntityRegistry() = default;
    EntityRegistry(const EntityRegistry&) = delete;
    EntityRegistry& operator=(const EntityRegistry&) = delete;

    std::unordered_map<std::string, Entity*> by_uuid_;
    std::unordered_map<uint32_t, Entity*> by_pick_id_;
    std::unordered_map<geom::GeneralTransform3*, Entity*> by_transform_;
};

} // namespace termin
