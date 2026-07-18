#include "render_frame_planner.hpp"

#include <algorithm>

extern "C" {
#include "render/tc_render_surface.h"
}

namespace termin::rendering_manager_detail {

void append_unique_render_target(
    std::vector<tc_render_target_handle>& targets,
    tc_render_target_handle rt
) {
    if (!tc_render_target_handle_valid(rt)) {
        return;
    }
    auto it = std::find_if(
        targets.begin(),
        targets.end(),
        [rt](tc_render_target_handle candidate) {
            return tc_render_target_handle_eq(candidate, rt);
        }
    );
    if (it == targets.end()) {
        targets.push_back(rt);
    }
}

bool contains_render_target(
    const std::vector<tc_render_target_handle>& targets,
    tc_render_target_handle rt
) {
    return std::find_if(
        targets.begin(),
        targets.end(),
        [rt](tc_render_target_handle candidate) {
            return tc_render_target_handle_eq(candidate, rt);
        }
    ) != targets.end();
}

void update_viewport_rects(
    const std::vector<RenderTopology::ViewportAttachment>& attachments,
    tc_display* only_display
) {
    for (const auto& attachment : attachments) {
        tc_display* display = attachment.display;
        if (!display || (only_display && display != only_display)) continue;
        if (!tc_display_get_enabled(display)) {
            continue;
        }

        tc_render_surface* surface = tc_display_get_surface(display);
        if (!surface) {
            continue;
        }

        int width = 0;
        int height = 0;
        tc_render_surface_get_size(surface, &width, &height);
        if (width <= 0 || height <= 0) {
            continue;
        }

        if (tc_viewport_handle_valid(attachment.viewport)) {
            tc_viewport_update_pixel_rect(attachment.viewport, width, height);
        }
    }
}

void sync_viewport_render_target_resolutions(
    const std::vector<RenderTopology::ViewportAttachment>& attachments,
    tc_display* only_display
) {
    for (const auto& attachment : attachments) {
        tc_display* display = attachment.display;
        if (!display || (only_display && display != only_display)) continue;
        if (!tc_display_get_enabled(display)) {
            continue;
        }

        tc_viewport_handle vp = attachment.viewport;
        if (tc_viewport_handle_valid(vp)) {
            tc_render_target_handle rt = tc_viewport_get_render_target(vp);
            if (tc_render_target_handle_valid(rt)
                    && tc_render_target_get_kind(rt) == TC_RENDER_TARGET_TEXTURE_2D
                    && tc_render_target_get_dynamic_resolution(rt)) {
                int px = 0;
                int py = 0;
                int pw = 0;
                int ph = 0;
                tc_viewport_get_pixel_rect(vp, &px, &py, &pw, &ph);
                if (pw > 0 && ph > 0) {
                    tc_render_target_set_width(rt, pw);
                    tc_render_target_set_height(rt, ph);
                }
            }
        }
    }
}

OffscreenRenderPlan build_offscreen_render_plan(
    const std::vector<RenderTopology::ViewportAttachment>& attachments,
    tc_display* only_display
) {
    OffscreenRenderPlan plan;
    for (const auto& attachment : attachments) {
        tc_display* display = attachment.display;
        if (!display || (only_display && display != only_display)) continue;

        tc_viewport_handle vp = attachment.viewport;
        if (tc_viewport_handle_valid(vp)) {
            append_unique_render_target(
                plan.attached_viewport_render_targets,
                tc_viewport_get_render_target(vp)
            );
        }
        if (!tc_display_get_enabled(display)) {
            continue;
        }

        if (tc_viewport_handle_valid(vp)) {
            if (tc_viewport_get_enabled(vp)) {
                tc_render_target_handle rt = tc_viewport_get_render_target(vp);
                if (tc_render_target_handle_valid(rt)) {
                    append_unique_render_target(plan.viewport_render_targets, rt);
                    const char* managed_by = tc_viewport_get_managed_by(vp);
                    if (managed_by && managed_by[0] != '\0') {
                        append_unique_render_target(plan.scene_pipeline_render_targets, rt);
                    } else if (!contains_render_target(plan.scene_pipeline_render_targets, rt)) {
                        plan.viewport_render_target_viewports.push_back(vp);
                    }
                }
            }
        }
    }
    return plan;
}

} // namespace termin::rendering_manager_detail
