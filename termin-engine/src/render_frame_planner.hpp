#pragma once

#include <vector>
#include "termin/render/render_topology.hpp"

extern "C" {
#include "render/tc_display.h"
#include "render/tc_render_target.h"
#include "render/tc_viewport.h"
}

namespace termin::rendering_manager_detail {

struct OffscreenRenderPlan {
    // Every target owned by an attached viewport, including viewports hidden
    // by transient display policy. Used to keep hidden targets out of the
    // standalone managed-target pass.
    std::vector<tc_render_target_handle> attached_viewport_render_targets;
    // Render-eligible viewport targets after display/viewport gates.
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

void update_viewport_rects(
    const std::vector<RenderTopology::ViewportAttachment>& attachments,
    tc_display_handle only_display = TC_DISPLAY_HANDLE_INVALID
);

void sync_viewport_render_target_resolutions(
    const std::vector<RenderTopology::ViewportAttachment>& attachments,
    tc_display_handle only_display = TC_DISPLAY_HANDLE_INVALID
);

OffscreenRenderPlan build_offscreen_render_plan(
    const std::vector<RenderTopology::ViewportAttachment>& attachments,
    tc_display_handle only_display = TC_DISPLAY_HANDLE_INVALID
);

} // namespace termin::rendering_manager_detail
