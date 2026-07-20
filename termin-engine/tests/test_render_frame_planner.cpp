#include "render_frame_planner.hpp"

#include <iostream>
#include <vector>

extern "C" {
#include "render/tc_display.h"
#include "render/tc_render_target.h"
#include "render/tc_viewport.h"
}

namespace {

bool same_target(tc_render_target_handle left, tc_render_target_handle right)
{
    return tc_render_target_handle_eq(left, right);
}

} // namespace

int main()
{
    using termin::RenderTopology;
    using namespace termin::rendering_manager_detail;

    tc_display_pool_init();
    tc_display_handle display_a = tc_display_new("DisplayA", nullptr);
    tc_display_handle display_b = tc_display_new("DisplayB", nullptr);
    tc_render_target_handle target_a = tc_render_target_new("TargetA");
    tc_render_target_handle target_b = tc_render_target_new("TargetB");
    tc_viewport_handle viewport_a = tc_viewport_new("ViewportA", TC_SCENE_HANDLE_INVALID);
    tc_viewport_handle viewport_b = tc_viewport_new("ViewportB", TC_SCENE_HANDLE_INVALID);
    tc_viewport_set_render_target(viewport_a, target_a);
    tc_viewport_set_render_target(viewport_b, target_b);

    const std::vector<RenderTopology::ViewportAttachment> attachments{
        {TC_SCENE_HANDLE_INVALID, viewport_a, display_a, true},
        {TC_SCENE_HANDLE_INVALID, viewport_b, display_b, true},
    };

    const OffscreenRenderPlan all = build_offscreen_render_plan(attachments);
    if (all.viewport_render_targets.size() != 2
            || all.attached_viewport_render_targets.size() != 2
            || all.viewport_render_target_viewports.size() != 2) {
        std::cerr << "multi-display plan did not include both viewport targets\n";
        return 1;
    }

    tc_display_set_enabled(display_b, false);
    const OffscreenRenderPlan active_display_only = build_offscreen_render_plan(attachments);
    if (active_display_only.viewport_render_targets.size() != 1
            || active_display_only.attached_viewport_render_targets.size() != 2
            || active_display_only.viewport_render_target_viewports.size() != 1
            || !same_target(active_display_only.viewport_render_targets.front(), target_a)) {
        std::cerr << "disabled display leaked into the render plan\n";
        return 1;
    }
    tc_display_set_enabled(display_b, true);

    const OffscreenRenderPlan only_a = build_offscreen_render_plan(attachments, display_a);
    if (only_a.viewport_render_targets.size() != 1
            || only_a.viewport_render_target_viewports.size() != 1
            || !same_target(only_a.viewport_render_targets.front(), target_a)
            || !tc_viewport_handle_eq(only_a.viewport_render_target_viewports.front(), viewport_a)) {
        std::cerr << "single-display plan leaked another display's viewport target\n";
        return 1;
    }

    tc_viewport_free(viewport_a);
    tc_viewport_free(viewport_b);
    tc_render_target_free(target_a);
    tc_render_target_free(target_b);
    tc_display_free(display_a);
    tc_display_free(display_b);
    tc_display_pool_shutdown();
    return 0;
}
