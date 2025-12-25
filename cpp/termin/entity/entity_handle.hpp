#pragma once

#include <string>

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
class EntityRegistry;

// EntityHandle - lazy reference to Entity by UUID.
// Used when Entity might not exist yet during deserialization.
// Resolves to actual Entity on first access via global EntityRegistry.
class ENTITY_API EntityHandle {
public:
    std::string uuid;

    EntityHandle() = default;
    explicit EntityHandle(const std::string& uuid) : uuid(uuid) {}

    /**
     * Get the referenced Entity. Resolves lazily.
     */
    Entity* get() const;

    /**
     * Check if handle has a UUID set.
     */
    bool is_valid() const { return !uuid.empty(); }

    /**
     * Get entity name, or UUID prefix if not resolved.
     */
    std::string name() const;

    /**
     * Create handle from existing Entity.
     */
    static EntityHandle from_entity(Entity* entity);

    bool operator==(const EntityHandle& other) const { return uuid == other.uuid; }
    bool operator!=(const EntityHandle& other) const { return uuid != other.uuid; }
};

} // namespace termin
