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
    if (!display) return;
    bool profile = tc_profiler_enabled();
    if (profile) tc_profiler_begin_section("Present Display");

    tc_render_surface* surface = tc_display_get_surface(display);
    if (!surface) {
        tc_log(TC_LOG_WARN, "[RenderingManager] present_display: surface is null");
        if (profile) tc_profiler_end_section();
        return;
    }

    // Make display context current; tgfx2 resources are owned by IRenderDevice.
    tc_render_surface_make_current(surface);

    int width, height;
    tc_render_surface_get_size(surface, &width, &height);
    if (width <= 0 || height <= 0) {
        if (profile) tc_profiler_end_section();
        return;
    }

    // Backend-neutral composite target. Surfaces must expose a tgfx2
    // TextureHandle; raw FBO presentation is intentionally not supported
    // through tgfx2 anymore.
    tgfx::TextureHandle display_color_tex{
        tc_render_surface_get_tgfx_color_tex_id(surface)
    };
    if (!display_color_tex) {
        tc_log(TC_LOG_ERROR,
               "[RenderingManager] present_display: render surface has no tgfx2 color texture target");
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

    if (profile) tc_profiler_begin_section("Present Clear");
    dev->clear_texture(
        display_color_tex,
        0.1f, 0.1f, 0.1f, 1.0f,
        0, 0, width, height
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
            ViewportRenderState* state = manager.get_viewport_state(viewport);
            if (!state || !state->has_output()) {
                continue;
            }
            src_color = state->output_color_tex;
            src_w = state->output_width;
            src_h = state->output_height;
        }

        if (!src_color || src_w == 0 || src_h == 0) {
            continue;
        }

        int px, py, pw, ph;
        tc_viewport_get_pixel_rect(viewport, &px, &py, &pw, &ph);

        dev->blit_to_texture(
            display_color_tex, src_color,
            0, 0, src_w, src_h,
            px, py, pw, ph
        );
    }
    if (profile) tc_profiler_end_section();

    if (profile) tc_profiler_begin_section("Present Swap Buffers");
    tc_render_surface_swap_buffers(surface);
    if (profile) tc_profiler_end_section();
    if (profile) tc_profiler_end_section();
}

} // namespace termin::rendering_manager_detail
