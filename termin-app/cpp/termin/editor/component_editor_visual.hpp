#pragma once

#include "termin/editor/transform_gizmo.hpp"
#include <termin/entity/component.hpp>
#include <termin/entity/entity.hpp>

#include <memory>
#include <functional>
#include <vector>
#include <termin_visual_scene/interaction3d.hpp>
#include <termin_visual_scene/visual_item3d.hpp>

namespace termin {

    struct ComponentEditorVisualContext {
        TransformGizmo* transform_gizmo = nullptr;
    };

    struct ComponentEditorVisualContribution {
        std::unique_ptr<visual::VisualItem3D> item;
        std::function<void(visual::SceneInteraction3D&, visual::VisualItem3DHandle)> bind_controller;
    };

    class ComponentEditorVisualProvider {
    public:
        virtual ~ComponentEditorVisualProvider() = default;

        virtual void collect_overlay_items(Entity entity,
                                           tc_component* component,
                                           const ComponentEditorVisualContext& context,
                                           std::vector<ComponentEditorVisualContribution>& out_items) = 0;
    };

    class ComponentEditorVisualRegistry {
    private:
        std::vector<std::unique_ptr<ComponentEditorVisualProvider>> _providers;

    public:
        static ComponentEditorVisualRegistry& instance();

        void register_provider(std::unique_ptr<ComponentEditorVisualProvider> provider);

        void collect_overlay_items(Entity entity,
                                   tc_component* component,
                                   const ComponentEditorVisualContext& context,
                                   std::vector<ComponentEditorVisualContribution>& out_items);
    };

} // namespace termin
