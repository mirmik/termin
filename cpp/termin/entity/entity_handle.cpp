#include "entity_handle.hpp"
#include "entity_registry.hpp"
#include "../../../core_c/include/tc_entity_pool.h"

namespace termin {

Entity EntityHandle::get() const {
    if (uuid.empty()) {
        return Entity();
    }

    // First try stored pool (scene-local lookup)
    if (pool) {
        tc_entity_id id = tc_entity_pool_find_by_uuid(pool, uuid.c_str());
        if (tc_entity_id_valid(id)) {
            return Entity(pool, id);
        }
    }

    // Fallback to global registry (for backwards compatibility during transition)
    return EntityRegistry::instance().get(uuid);
}

std::string EntityHandle::name() const {
    Entity ent = get();
    if (ent.valid()) {
        const char* n = ent.name();
        return n ? n : "";
    }
    if (uuid.size() > 8) {
        return "<" + uuid.substr(0, 8) + "...>";
    }
    return "<" + uuid + ">";
}

EntityHandle EntityHandle::from_entity(const Entity& entity) {
    if (!entity.valid()) {
        return EntityHandle();
    }
    const char* u = entity.uuid();
    return EntityHandle(u ? u : "");
}

} // namespace termin
