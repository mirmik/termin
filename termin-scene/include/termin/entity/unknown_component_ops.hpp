#pragma once

#include <functional>
#include <string>
#include <vector>

#include <termin/export.hpp>
#include <termin/entity/entity.hpp>
#include <termin/entity/unknown_component.hpp>

namespace termin {

struct ENTITY_API UnknownComponentStats {
    size_t degraded = 0;
    size_t upgraded = 0;
    size_t skipped = 0;
    size_t failed = 0;
};

enum class UnknownUpgradeMode {
    Skip,
    DefaultUpgrade,
    CustomUpgrade,
};

struct ENTITY_API UnknownUpgradeDecision {
    UnknownUpgradeMode mode = UnknownUpgradeMode::DefaultUpgrade;
    std::string target_type;
    tc_value target_data = tc_value_nil();

    UnknownUpgradeDecision() = default;
    UnknownUpgradeDecision(const UnknownUpgradeDecision& other);
    UnknownUpgradeDecision& operator=(const UnknownUpgradeDecision& other);
    UnknownUpgradeDecision(UnknownUpgradeDecision&& other) noexcept;
    UnknownUpgradeDecision& operator=(UnknownUpgradeDecision&& other) noexcept;
    ~UnknownUpgradeDecision();

    static UnknownUpgradeDecision skip();
    static UnknownUpgradeDecision default_upgrade();
    static UnknownUpgradeDecision custom(
        std::string target_type,
        const tc_value* target_data
    );
};

using UnknownUpgradeStrategy = std::function<UnknownUpgradeDecision(
    const UnknownComponent& unknown,
    const Entity& entity,
    const TcSceneRef& scene
)>;

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

ENTITY_API UnknownComponentStats upgrade_unknown_components(
    const TcSceneRef& scene,
    const UnknownUpgradeStrategy& strategy,
    const std::vector<std::string>& type_names = {}
);

} // namespace termin
