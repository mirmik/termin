#include "entity_handle.hpp"
#include "entity_registry.hpp"

namespace termin {

Entity EntityHandle::get() const {
    if (uuid.empty()) {
        return Entity();
    }
    return EntityRegistry::instance().get(uuid);
}

std::string EntityHandle::name() const {
    fprintf(stderr, "[DEBUG EntityHandle::name] uuid='%s' size=%zu\n", uuid.c_str(), uuid.size());
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
