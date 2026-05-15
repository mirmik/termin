#include "termin/editor/component_editor_visual.hpp"

namespace termin {

ComponentEditorVisualRegistry& ComponentEditorVisualRegistry::instance() {
    static ComponentEditorVisualRegistry registry;
    return registry;
}

void ComponentEditorVisualRegistry::register_provider(std::unique_ptr<ComponentEditorVisualProvider> provider) {
    if (provider) {
        _providers.push_back(std::move(provider));
    }
}

void ComponentEditorVisualRegistry::collect_gizmos(
    Entity entity,
    tc_component* component,
    const ComponentEditorVisualContext& context,
    std::vector<std::unique_ptr<Gizmo>>& out_gizmos)
{
    if (!entity.valid() || !component) {
        return;
    }

    for (const auto& provider : _providers) {
        provider->collect_gizmos(entity, component, context, out_gizmos);
    }
}

} // namespace termin
