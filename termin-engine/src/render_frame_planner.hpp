#pragma once

#include <vector>

extern "C" {
#include "render/tc_display.h"
#include "render/tc_render_target.h"
#include "render/tc_viewport.h"
}

namespace termin::rendering_manager_detail {

struct OffscreenRenderPlan {
    std::vector<tc_render_target_handle> viewport_render_targets;
    std::vector<tc_render_target_handle> scene_pipeline_render_targets;
    std::vector<tc_viewport_handle> viewport_render_target_viewports;
};

void append_unique_render_target(
    std::vector<tc_render_target_handle>& targets,
    tc_render_target_handle rt
);

bool contains_render_target(
    const std::vector<tc_render_target_handle>& targets,
    tc_render_target_handle rt
);

void update_viewport_rects_for_displays(const std::vector<tc_display*>& displays);

void sync_viewport_render_target_resolutions(const std::vector<tc_display*>& displays);

OffscreenRenderPlan build_offscreen_render_plan(
    const std::vector<tc_display*>& scene_displays,
    const std::vector<tc_display*>& editor_displays
);

} // namespace termin::rendering_manager_detail
