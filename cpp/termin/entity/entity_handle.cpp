#include "entity_handle.hpp"
#include "entity.hpp"
#include "entity_registry.hpp"

namespace termin {

Entity* EntityHandle::get() const {
    if (uuid.empty()) {
        return nullptr;
    }
    return EntityRegistry::instance().get(uuid);
}

std::string EntityHandle::name() const {
    Entity* ent = get();
    if (ent != nullptr) {
        const char* n = ent->name();
        return n ? n : "";
    }
    if (uuid.size() > 8) {
        return "<" + uuid.substr(0, 8) + "...>";
    }
    return "<" + uuid + ">";
}

EntityHandle EntityHandle::from_entity(Entity* entity) {
    if (entity == nullptr) {
        return EntityHandle();
    }
    const char* u = entity->uuid();
    return EntityHandle(u ? u : "");
}

} // namespace termin
