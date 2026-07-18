#pragma once

#include <functional>
#include <memory>
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

// Optional dependency injection for focused failure-path tests. Production
// callers should use the defaults, which serialize through tc_inspect and
// create UnknownComponent through the component registry.
struct ENTITY_API UnknownComponentPreparationHooks {
    std::function<tc_value(void*, const char*)> serialize;
    std::function<tc_component*()> create_replacement;
};

class ENTITY_API UnknownComponentDegradationPlan {
public:
    UnknownComponentDegradationPlan();
    UnknownComponentDegradationPlan(UnknownComponentDegradationPlan&&) noexcept;
    UnknownComponentDegradationPlan& operator=(UnknownComponentDegradationPlan&&) noexcept;
    ~UnknownComponentDegradationPlan();

    UnknownComponentDegradationPlan(const UnknownComponentDegradationPlan&) = delete;
    UnknownComponentDegradationPlan& operator=(const UnknownComponentDegradationPlan&) = delete;

    size_t size() const;
    bool empty() const;
    bool committed() const;
    bool validate(std::string* error = nullptr) const;
    bool commit(std::string* error = nullptr);

private:
    struct Impl;
    std::unique_ptr<Impl> _impl;

    friend bool prepare_components_to_unknown(
        const std::vector<TcSceneRef>&,
        const std::vector<std::string>&,
        UnknownComponentDegradationPlan&,
        std::string*,
        const UnknownComponentPreparationHooks&
    );
};

// Serialize and construct every replacement across all supplied scenes without
// mutating any entity. The returned plan validates source pointer/index
// identity again before publishing its in-place replacements.
ENTITY_API bool prepare_components_to_unknown(
    const std::vector<TcSceneRef>& scenes,
    const std::vector<std::string>& type_names,
    UnknownComponentDegradationPlan& plan,
    std::string* error = nullptr,
    const UnknownComponentPreparationHooks& hooks = {}
);

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
