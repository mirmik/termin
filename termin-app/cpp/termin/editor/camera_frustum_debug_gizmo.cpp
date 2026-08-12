#include "termin/editor/camera_frustum_debug_gizmo.hpp"

#include "termin/editor/editor_interaction_system.hpp"

#include <tcbase/tc_log.h>
#include <tgfx2/immediate_renderer.hpp>

extern "C" {
#include "core/tc_scene.h"
}

namespace termin {

    namespace {

        Mat44 to_mat44(const Mat44f& value) {
            Mat44 result;
            for (std::size_t index = 0; index < 16; ++index)
                result.data[index] = value.data[index];
            return result;
        }

        void
        draw_edge(ImmediateRenderer* renderer, const CameraFrustumCorners& corners, int a, int b, const SrgbColor& color) {
            renderer->line(
                corners.points[static_cast<size_t>(a)], corners.points[static_cast<size_t>(b)], color, false);
        }

        struct FrustumDrawContext {
            ImmediateRenderer* renderer = nullptr;
            double aspect_override = 0.0;
        };

        bool draw_camera_frustum_callback(tc_component* component, void* user_data) {
            auto* ctx = static_cast<FrustumDrawContext*>(user_data);
            const tc_camera_capability* capability = tc_camera_capability_get(component);
            if (!capability || !capability->vtable || !capability->vtable->get_camera_data) {
                tc_log(TC_LOG_ERROR, "[CameraFrustumDebug] camera capability has no get_camera_data callback");
                return true;
            }

            tc_camera_data camera_data = {};
            if (!capability->vtable->get_camera_data(component, ctx->aspect_override, &camera_data)) {
                tc_log(TC_LOG_ERROR, "[CameraFrustumDebug] get_camera_data failed for camera component");
                return true;
            }

            CameraFrustumCorners corners;
            std::string error;
            if (!compute_camera_frustum_corners(camera_data, corners, &error)) {
                tc_log(TC_LOG_ERROR, "[CameraFrustumDebug] cannot compute camera frustum: %s", error.c_str());
                return true;
            }

            const SrgbColor near_color{1.0f, 0.86f, 0.24f, 1.0f};
            const SrgbColor far_color{0.15f, 0.9f, 1.0f, 1.0f};
            const SrgbColor edge_color{0.35f, 1.0f, 0.65f, 1.0f};

            draw_edge(ctx->renderer, corners, 0, 1, near_color);
            draw_edge(ctx->renderer, corners, 1, 3, near_color);
            draw_edge(ctx->renderer, corners, 3, 2, near_color);
            draw_edge(ctx->renderer, corners, 2, 0, near_color);
            draw_edge(ctx->renderer, corners, 4, 5, far_color);
            draw_edge(ctx->renderer, corners, 5, 7, far_color);
            draw_edge(ctx->renderer, corners, 7, 6, far_color);
            draw_edge(ctx->renderer, corners, 6, 4, far_color);
            draw_edge(ctx->renderer, corners, 0, 4, edge_color);
            draw_edge(ctx->renderer, corners, 1, 5, edge_color);
            draw_edge(ctx->renderer, corners, 2, 6, edge_color);
            draw_edge(ctx->renderer, corners, 3, 7, edge_color);
            return true;
        }

    } // namespace

    CameraFrustumOverlayItem3D::CameraFrustumOverlayItem3D(EditorInteractionSystem* system)
        : NativeVisualItem3D("termin.editor.CameraFrustumOverlayItem3D"),
          _system(system) {}

    std::optional<visual::VisualBounds3D> CameraFrustumOverlayItem3D::local_bounds() const {
        return std::nullopt;
    }

    std::optional<visual::HitCandidate3D>
    CameraFrustumOverlayItem3D::hit_test(const visual::HitTestContext3D&) const {
        return std::nullopt;
    }

    bool CameraFrustumOverlayItem3D::paint(visual::GraphicItemPaintContext3D& context) const {
        const EditorOverlayDrawPacket3D packet{this};
        return context.submit(EditorOverlayDrawProtocol3D, &packet, sizeof(packet));
    }

    bool CameraFrustumOverlayItem3D::draw(const EditorOverlayDrawContext3D& context) const {
        if (!_system || !_system->camera_frustums_visible())
            return true;
        if (!context.renderer || !context.render_context) {
            tc_log(TC_LOG_ERROR, "[CameraFrustumOverlay] renderer and render context are required");
            return false;
        }

        tc_scene_handle scene = _system->camera_frustum_scene();
        if (!tc_scene_handle_valid(scene))
            return true;

        FrustumDrawContext ctx;
        ctx.renderer = context.renderer;
        ctx.aspect_override = _system->camera_frustum_aspect_override();

        tc_component_cap_id camera_capability = tc_camera_capability_id();
        if (camera_capability == TC_COMPONENT_CAPABILITY_INVALID_ID) {
            tc_log(TC_LOG_ERROR, "[CameraFrustumDebug] camera capability id is invalid");
            return false;
        }

        context.renderer->begin();
        tc_scene_foreach_with_capability(scene,
                                         camera_capability,
                                         draw_camera_frustum_callback,
                                         &ctx,
                                         TC_SCENE_FILTER_ENABLED | TC_SCENE_FILTER_ENTITY_ENABLED);
        context.renderer->flush(context.render_context,
                                to_mat44(context.view),
                                to_mat44(context.projection),
                                true,
                                false);
        return true;
    }

} // namespace termin
