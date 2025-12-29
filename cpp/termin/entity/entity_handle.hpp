#pragma once

#include <string>
#include <pybind11/pybind11.h>
#include "entity.hpp"
#include "../../trent/trent.h"

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

class EntityRegistry;

// EntityHandle - lazy reference to Entity by UUID.
// Used when Entity might not exist yet during deserialization.
// Resolves to actual Entity on first access via global EntityRegistry.
class ENTITY_API EntityHandle {
public:
    std::string uuid;

    EntityHandle() = default;
    explicit EntityHandle(const std::string& uuid) : uuid(uuid) {}

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
    void deserialize_from(const nos::trent& data) {
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
    pybind11::dict serialize() const {
        pybind11::dict d;
        d["uuid"] = uuid;
        return d;
    }
};

} // namespace termin
