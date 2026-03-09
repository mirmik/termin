#pragma once

#include <string>
#include <vector>

#include <termin/export.hpp>
#include <termin/entity/entity.hpp>

namespace termin {

struct ENTITY_API UnknownComponentStats {
    size_t degraded = 0;
    size_t upgraded = 0;
    size_t skipped = 0;
    size_t failed = 0;
};

ENTITY_API bool degrade_component_ref_to_unknown(
    const Entity& entity,
    tc_component* component,
    std::string* error = nullptr
);

ENTITY_API bool upgrade_unknown_component_ref(
    const Entity& entity,
    tc_component* component,
    std::string* error = nullptr
);

ENTITY_API UnknownComponentStats degrade_components_to_unknown(
    const TcSceneRef& scene,
    const std::vector<std::string>& type_names
);

ENTITY_API UnknownComponentStats upgrade_unknown_components(
    const TcSceneRef& scene,
    const std::vector<std::string>& type_names = {}
);

} // namespace termin
