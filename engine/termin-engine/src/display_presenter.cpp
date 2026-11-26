#include "display_presenter.hpp"
#include "render_frame_planner.hpp"

#include "termin/render/tgfx2_bridge.hpp"

#include <algorithm>
#include <vector>

#include <tgfx2/i_render_device.hpp>
#include <tgfx2/render_context.hpp>

extern "C" {
#include "render/tc_render_surface.h"
#include "render/tc_render_target.h"
#include "render/tc_viewport.h"
#include "tc_profiler.h"
#include <tcbase/tc_log.h>
}

namespace termin::rendering_manager_detail {

    bool present_display(RenderingManager& manager, tc_display_handle display) {
        if (!tc_display_alive(display))
            return false;
        bool profile = tc_profiler_enabled();
        if (profile)
            tc_profiler_begin_section("Present Display");

        tc_render_surface* surface = tc_display_get_surface(display);
        if (!surface) {
            tc_log(TC_LOG_WARN, "[RenderingManager] present_display: surface is null");
            if (profile)
                tc_profiler_end_section();
            return false;
        }

        int width, height;
        tc_render_surface_get_size(surface, &width, &height);
        if (width <= 0 || height <= 0) {
            if (profile)
                tc_profiler_end_section();
            return false;
        }

        RenderEngine* engine = manager.render_engine();
        if (engine) {
            engine->ensure_tgfx2();
        }
        tgfx::IRenderDevice* dev = engine ? engine->tgfx2_device() : nullptr;
        if (!dev) {
            tc_log(TC_LOG_WARN, "[RenderingManager] present_display: tgfx2 device not available");
            if (profile)
                tc_profiler_end_section();
            return false;
        }

        uint32_t display_color_texture_id = 0;
        if (!tc_render_surface_validate_output(surface, reinterpret_cast<uintptr_t>(dev), &display_color_texture_id)) {
            tc_log(TC_LOG_ERROR, "[RenderingManager] present_display: invalid render surface output");
            if (profile)
                tc_profiler_end_section();
            return false;
        }
        tgfx::TextureHandle display_color_tex{display_color_texture_id};
        auto* context = engine->tgfx2_ctx();
        const bool record_in_host_frame = context && context->in_frame() &&
                                          dev->backend_type() == tgfx::BackendType::Vulkan;
        if (context && context->in_pass()) {
            tc_log(TC_LOG_ERROR, "[RenderingManager] cannot composite a display inside a host raster pass");
            if (profile)
                tc_profiler_end_section();
            return false;
        }

        if (profile)
            tc_profiler_begin_section("Present Clear");
        const LinearColor clear_color{0.1f, 0.1f, 0.1f, 1.0f};
        if (record_in_host_frame) {
            tgfx::RenderPassDesc pass;
            tgfx::ColorAttachmentDesc attachment;
            attachment.texture = display_color_tex;
            attachment.load = tgfx::LoadOp::Clear;
            attachment.clear_color = clear_color;
            pass.colors.push_back(attachment);
            if (!context->begin_pass(pass)) {
                tc_log(TC_LOG_ERROR, "[RenderingManager] cannot clear the display in the host frame");
                if (profile) {
                    tc_profiler_end_section();
                    tc_profiler_end_section();
                }
                return false;
            }
            context->end_pass();
        } else {
            dev->clear_texture(display_color_tex, clear_color, Bounds2i::from_size(width, height));
        }
        if (profile)
            tc_profiler_end_section();

        if (profile)
            tc_profiler_begin_section("Present Collect Viewports");
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
        if (profile)
            tc_profiler_end_section();

        if (profile)
            tc_profiler_begin_section("Present Blit Viewports");
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
                src_color = wrap_tc_texture_as_tgfx2(*dev, tc_render_target_get_color_texture(rt));
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

            const Bounds2i source = Bounds2i::from_size(src_w, src_h);
            const Bounds2i destination{px, py, px + pw, py + ph};
            if (record_in_host_frame)
                context->blit_region(src_color, display_color_tex, source, destination);
            else
                dev->blit_to_texture(display_color_tex, src_color, source, destination);
        }
        if (profile)
            tc_profiler_end_section();

        if (profile)
            tc_profiler_end_section();
        return true;
    }

    namespace {
        template <typename Handle>
        uint64_t handle_key(Handle handle) {
            return (static_cast<uint64_t>(handle.generation) << 32) | handle.index;
        }
    }

    void DisplayPresentationCache::present_pending(RenderingManager& manager,
                                                   const OffscreenRenderPlanner& planner,
                                                   tc_display_handle display) {
        if (!tc_display_alive(display) || !tc_display_get_enabled(display)) {
            invalidate(display);
            return;
        }
        tc_render_surface* surface = tc_display_get_surface(display);
        if (!surface) {
            invalidate(display);
            return;
        }
        current_.surface = surface;
        current_.texture = tc_render_surface_get_color_texture_id(surface);
        tc_render_surface_get_size(surface, &current_.width, &current_.height);
        current_.viewports.clear();
        for (auto viewport = tc_display_get_first_viewport(display); tc_viewport_handle_valid(viewport);
             viewport = tc_viewport_get_display_next(viewport)) {
            const auto target = tc_viewport_get_render_target(viewport);
            if (!tc_viewport_get_enabled(viewport) || !tc_render_target_get_enabled(target))
                continue;
            ViewportState state{handle_key(viewport), handle_key(target), planner.output_revision(target), {},
                                tc_viewport_get_depth(viewport)};
            tc_viewport_get_pixel_rect(viewport, &state.rect[0], &state.rect[1], &state.rect[2], &state.rect[3]);
            current_.viewports.push_back(state);
        }
        const auto key = handle_key(display);
        auto previous = presentations_.find(key);
        if (previous != presentations_.end() && previous->second == current_)
            return;
        if (present_display(manager, display)) {
            current_.texture = tc_render_surface_get_color_texture_id(surface);
            std::swap(presentations_[key], current_);
        } else {
            invalidate(display);
        }
    }

    void DisplayPresentationCache::invalidate(tc_display_handle display) {
        presentations_.erase(handle_key(display));
    }

    void DisplayPresentationCache::clear() {
        presentations_.clear();
    }

} // namespace termin::rendering_manager_detail
