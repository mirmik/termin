#include "termin/editor/component_editor_visual.hpp"

namespace termin {

    ComponentEditorVisualRegistry& ComponentEditorVisualRegistry::instance() {
        static ComponentEditorVisualRegistry component_editor_visual_registry;
        return component_editor_visual_registry;
    }

    void ComponentEditorVisualRegistry::register_provider(std::unique_ptr<ComponentEditorVisualProvider> provider) {
        if (provider) {
            _providers.push_back(std::move(provider));
        }
    }

    void ComponentEditorVisualRegistry::collect_overlay_items(
        Entity entity,
        tc_component* component,
        const ComponentEditorVisualContext& context,
        std::vector<ComponentEditorVisualContribution>& out_items) {
        if (!entity.valid() || !component) {
            return;
        }

        for (const auto& provider : _providers) {
            provider->collect_overlay_items(entity, component, context, out_items);
        }
    }

} // namespace termin
