#include "termin/editor/editor_overlay_scene3d.hpp"

#include <cstring>
#include <utility>
#include <vector>

#include <tcbase/tc_log.h>

namespace termin {
    namespace {

        struct StagedOverlayDraw {
            EditorOverlayDrawPacket3D packet;
            Affine3d world_from_local = Affine3d::identity();
            visual::VisualItem3DHandle item = tc_visual_item3d_handle_invalid();
        };

        class EditorOverlayPaintSink final : public visual::ScenePaintSink3D {
        public:
            explicit EditorOverlayPaintSink(EditorOverlayDrawContext3D context)
                : _context(std::move(context)) {}

            bool begin(const visual::VisualView3D&) override {
                _staged.clear();
                return true;
            }

            bool submit(const visual::DrawSubmission3D& submission) override {
                if (!submission.packet.protocol ||
                    std::strcmp(submission.packet.protocol, EditorOverlayDrawProtocol3D) != 0 ||
                    submission.packet.payload_size != sizeof(EditorOverlayDrawPacket3D) ||
                    !submission.packet.payload) {
                    tc_log(TC_LOG_ERROR,
                           "[EditorOverlayScene3D] unsupported draw protocol '%s'",
                           submission.packet.protocol ? submission.packet.protocol : "<null>");
                    return false;
                }
                const auto packet = *static_cast<const EditorOverlayDrawPacket3D*>(submission.packet.payload);
                if (!packet.drawable) {
                    tc_log(TC_LOG_ERROR, "[EditorOverlayScene3D] draw packet has no drawable");
                    return false;
                }
                _staged.push_back({packet, submission.world_from_local, submission.item});
                return true;
            }

            bool end() override {
                for (const auto& draw : _staged) {
                    EditorOverlayDrawContext3D context = _context;
                    context.world_from_local = draw.world_from_local;
                    context.item = draw.item;
                    if (!draw.packet.drawable->draw(context)) {
                        tc_log(TC_LOG_ERROR, "[EditorOverlayScene3D] overlay drawable rejected a frame");
                        return false;
                    }
                }
                _staged.clear();
                return true;
            }

            void abort() override {
                _staged.clear();
            }

        private:
            EditorOverlayDrawContext3D _context;
            std::vector<StagedOverlayDraw> _staged;
        };

        tc_mat44 to_c_matrix(const Mat44f& matrix) {
            tc_mat44 result{};
            for (std::size_t index = 0; index < 16; ++index)
                result.m[index] = matrix.data[index];
            return result;
        }

    } // namespace

    EditorOverlayScene3D::EditorOverlayScene3D()
        : _handle(tc_visual_scene3d_create()),
          _scene(_handle) {
        if (!_scene.valid())
            tc_log(TC_LOG_ERROR, "[EditorOverlayScene3D] failed to create visual scene");
    }

    EditorOverlayScene3D::~EditorOverlayScene3D() {
        clear();
        if (tc_visual_scene3d_is_valid(_handle))
            tc_visual_scene3d_destroy(_handle);
    }

    bool EditorOverlayScene3D::route_pointer(visual::PointerEventKind3D kind,
                                             Ray3 world_ray,
                                             std::uint32_t button,
                                             visual::PointerId3D pointer) {
        if (!_scene.valid())
            return false;
        const auto dispatch = _interaction.route(_scene, {pointer, kind, world_ray, button});
        return !dispatch.used_fallback;
    }

    bool EditorOverlayScene3D::paint(ImmediateRenderer* renderer,
                                     tgfx::RenderContext2* render_context,
                                     const Mat44f& view,
                                     const Mat44f& projection,
                                     std::uint32_t viewport_width,
                                     std::uint32_t viewport_height) const {
        if (!_scene.valid() || viewport_width == 0 || viewport_height == 0)
            return false;
        visual::VisualView3D visual_view{};
        visual_view.view_matrix = to_c_matrix(view);
        visual_view.projection_matrix = to_c_matrix(projection);
        visual_view.viewport_width = viewport_width;
        visual_view.viewport_height = viewport_height;
        EditorOverlayPaintSink sink({renderer, render_context, view, projection});
        if (!visual::paint(_scene, visual_view, sink)) {
            tc_log(TC_LOG_ERROR, "[EditorOverlayScene3D] failed to paint overlay scene");
            return false;
        }
        return true;
    }

    void EditorOverlayScene3D::clear() {
        if (!_scene.valid()) {
            _interaction.cancel_all();
            return;
        }
        if (_interaction.cancel_all(_scene))
            tc_log(TC_LOG_ERROR, "[EditorOverlayScene3D] interaction callback failed during teardown");
        for (tc_visual_item3d* item : _scene.items()) {
            _interaction.clear_target_pointer_handler(item->handle);
            _interaction.clear_action_handler(item->handle);
        }
        _scene.clear();
    }

} // namespace termin
