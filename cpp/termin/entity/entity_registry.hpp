#pragma once

#include <string>
#include <unordered_map>
#include <cstdint>
#include <utility>

// DLL export/import macros for Windows
#ifdef _WIN32
    #ifdef ENTITY_LIB_EXPORTS
        #define ENTITY_API __declspec(dllexport)
    #else
        #define ENTITY_API __declspec(dllimport)
    #endif
#else
    #define ENTITY_API
#endif

namespace termin {

class Entity;
struct GeneralTransform3;

// Global registry for entity lookup by UUID, pick_id, and transform.
// Singleton pattern. Entities register themselves on creation
// and unregister on destruction.
class ENTITY_API EntityRegistry {
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
    Entity* get_by_transform(GeneralTransform3* transform) const;

    // Clear all (for testing)
    void clear();

    // Swap registries (for game mode transition)
    // Returns the old registries as a pair
    std::pair<std::unordered_map<std::string, Entity*>,
              std::unordered_map<uint32_t, Entity*>>
    swap_registries(std::unordered_map<std::string, Entity*> new_by_uuid,
                    std::unordered_map<uint32_t, Entity*> new_by_pick_id);

    // Stats
    size_t entity_count() const { return by_uuid_.size(); }

private:
    EntityRegistry() = default;
    EntityRegistry(const EntityRegistry&) = delete;
    EntityRegistry& operator=(const EntityRegistry&) = delete;

    std::unordered_map<std::string, Entity*> by_uuid_;
    std::unordered_map<uint32_t, Entity*> by_pick_id_;
    std::unordered_map<GeneralTransform3*, Entity*> by_transform_;
};

} // namespace termin
