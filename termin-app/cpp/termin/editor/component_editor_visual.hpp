#pragma once

#include "termin/editor/gizmo.hpp"
#include "termin/editor/transform_gizmo.hpp"
#include <termin/entity/component.hpp>
#include <termin/entity/entity.hpp>

#include <memory>
#include <vector>

namespace termin {

struct ComponentEditorVisualContext {
    TransformGizmo* transform_gizmo = nullptr;
};

class ComponentEditorVisualProvider {
public:
    virtual ~ComponentEditorVisualProvider() = default;

    virtual void collect_gizmos(
        Entity entity,
        tc_component* component,
        const ComponentEditorVisualContext& context,
        std::vector<std::unique_ptr<Gizmo>>& out_gizmos) = 0;
};

class ComponentEditorVisualRegistry {
private:
    std::vector<std::unique_ptr<ComponentEditorVisualProvider>> _providers;

public:
    static ComponentEditorVisualRegistry& instance();

    void register_provider(std::unique_ptr<ComponentEditorVisualProvider> provider);

    void collect_gizmos(
        Entity entity,
        tc_component* component,
        const ComponentEditorVisualContext& context,
        std::vector<std::unique_ptr<Gizmo>>& out_gizmos);
};

} // namespace termin
