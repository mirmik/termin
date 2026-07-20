#include "display_presenter.hpp"

#include "termin/render/tgfx2_bridge.hpp"

#include <algorithm>
#include <vector>

#include <tgfx2/i_render_device.hpp>

extern "C" {
#include <tcbase/tc_log.h>
#include "tc_profiler.h"
#include "render/tc_render_surface.h"
#include "render/tc_render_target.h"
#include "render/tc_viewport.h"
}

namespace termin::rendering_manager_detail {

void present_display(RenderingManager& manager, tc_display* display) {
    (void)manager;
    if (!display) return;
    bool profile = tc_profiler_enabled();
    if (profile) tc_profiler_begin_section("Present Display");

    tc_render_surface* surface = tc_display_get_surface(display);
    if (!surface) {
        tc_log(TC_LOG_WARN, "[RenderingManager] present_display: surface is null");
        if (profile) tc_profiler_end_section();
        return;
    }

    int width, height;
    tc_render_surface_get_size(surface, &width, &height);
    if (width <= 0 || height <= 0) {
        if (profile) tc_profiler_end_section();
        return;
    }

    RenderEngine* engine = manager.render_engine();
    if (engine) {
        engine->ensure_tgfx2();
    }
    tgfx::IRenderDevice* dev = engine ? engine->tgfx2_device() : nullptr;
    if (!dev) {
        tc_log(TC_LOG_WARN, "[RenderingManager] present_display: tgfx2 device not available");
        if (profile) tc_profiler_end_section();
        return;
    }

    uint32_t display_color_texture_id = 0;
    if (!tc_render_surface_validate_output(
            surface,
            reinterpret_cast<uintptr_t>(dev),
            &display_color_texture_id)) {
        tc_log(TC_LOG_ERROR,
               "[RenderingManager] present_display: invalid render surface output");
        if (profile) tc_profiler_end_section();
        return;
    }
    tgfx::TextureHandle display_color_tex{display_color_texture_id};

    if (profile) tc_profiler_begin_section("Present Clear");
    dev->clear_texture(
        display_color_tex,
        Color4{0.1f, 0.1f, 0.1f, 1.0f},
        Bounds2i::from_size(width, height)
    );
    if (profile) tc_profiler_end_section();

    if (profile) tc_profiler_begin_section("Present Collect Viewports");
    std::vector<tc_viewport_handle> viewports;
    tc_viewport_handle vp = tc_display_get_first_viewport(display);
    while (tc_viewport_handle_valid(vp)) {
        if (tc_viewport_get_enabled(vp)) {
            viewports.push_back(vp);
        }
        vp = tc_viewport_get_display_next(vp);
    }
    std::sort(viewports.begin(), viewports.end(), [](tc_viewport_handle a, tc_viewport_handle b) {
        return tc_viewport_get_depth(a) < tc_viewport_get_depth(b);
    });
    if (profile) tc_profiler_end_section();

    if (profile) tc_profiler_begin_section("Present Blit Viewports");
    for (tc_viewport_handle viewport : viewports) {
        tc_viewport_update_pixel_rect(viewport, width, height);

        tc_render_target_handle rt = tc_viewport_get_render_target(viewport);

        tgfx::TextureHandle src_color{};
        int src_w = 0, src_h = 0;

        if (tc_render_target_handle_valid(rt)) {
            if (!tc_render_target_get_enabled(rt)) {
                continue;
            }
            if (tc_render_target_get_kind(rt) != TC_RENDER_TARGET_TEXTURE_2D) {
                continue;
            }
            src_color = wrap_tc_texture_as_tgfx2(
                *dev, tc_render_target_get_color_texture(rt));
            src_w = tc_render_target_get_width(rt);
            src_h = tc_render_target_get_height(rt);
        } else {
            continue;
        }

        if (!src_color || src_w == 0 || src_h == 0) {
            continue;
        }

        int px, py, pw, ph;
        tc_viewport_get_pixel_rect(viewport, &px, &py, &pw, &ph);

        dev->blit_to_texture(
            display_color_tex, src_color,
            Bounds2i::from_size(src_w, src_h),
            Bounds2i{px, py, px + pw, py + ph}
        );
    }
    if (profile) tc_profiler_end_section();

    if (profile) tc_profiler_end_section();
}

} // namespace termin::rendering_manager_detail
