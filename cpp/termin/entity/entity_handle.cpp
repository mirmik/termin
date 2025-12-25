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
        return ent->name;
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
    return EntityHandle(entity->uuid);
}

} // namespace termin
