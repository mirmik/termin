#pragma once

#include <string>
#include <nanobind/nanobind.h>
#include "entity.hpp"
#include "../../trent/trent.h"

#include "../export.hpp"

// Forward declaration for C struct
struct tc_entity_pool;

namespace termin {

class EntityRegistry;

// EntityHandle - lazy reference to Entity by UUID.
// Used when Entity might not exist yet during deserialization.
// Resolves to actual Entity on first access via stored pool or global EntityRegistry.
class ENTITY_API EntityHandle {
public:
    std::string uuid;
    tc_entity_pool* pool = nullptr;  // Pool to search in (set during deserialization)

    EntityHandle() = default;
    explicit EntityHandle(const std::string& uuid) : uuid(uuid) {}
    EntityHandle(const std::string& uuid, tc_entity_pool* pool) : uuid(uuid), pool(pool) {}

    // Get the referenced Entity. Resolves lazily.
    // Returns invalid Entity if not found.
    Entity get() const;

    // Check if handle has a UUID set.
    bool is_valid() const { return !uuid.empty(); }

    // Get entity name, or UUID prefix if not resolved.
    std::string name() const;

    // Create handle from existing Entity.
    static EntityHandle from_entity(const Entity& entity);

    // Deserialize inplace from scene data.
    // Accepts either a string (uuid directly) or a dict with "uuid" key.
    // Pool can be set to enable scene-local lookup.
    void deserialize_from(const nos::trent& data, tc_entity_pool* p = nullptr) {
        pool = p;
        if (data.is_string()) {
            uuid = data.as_string();
        } else if (data.is_dict() && data.contains("uuid")) {
            uuid = data["uuid"].as_string();
        } else {
            uuid.clear();
        }
    }

    bool operator==(const EntityHandle& other) const { return uuid == other.uuid; }
    bool operator!=(const EntityHandle& other) const { return uuid != other.uuid; }

    // Serialize to Python dict (for register_cpp_handle_kind)
    nanobind::dict serialize() const {
        nanobind::dict d;
        d["uuid"] = uuid;
        return d;
    }
};

} // namespace termin
