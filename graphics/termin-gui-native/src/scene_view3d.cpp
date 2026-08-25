#include <termin/gui_native/scene_view3d.hpp>

#include "widgets_internal.hpp"

#include <algorithm>
#include <array>
#include <cmath>
#include <cstddef>
#include <cstring>
#include <exception>
#include <limits>
#include <string>
#include <utility>
#include <vector>

#include <termin/camera/screen_ray.hpp>
#include <termin/geom/mat44.hpp>
#include <termin_visual_scene/items/item3d_packets.hpp>
#include <tgfx2/builtin_shader_sources.hpp>
#include <tgfx2/font_atlas.hpp>
#include <tgfx2/i_render_device.hpp>
#include <tgfx2/immediate_renderer.hpp>
#include <tgfx2/render_context.hpp>
#include <tgfx2/tc_shader_bridge.hpp>
#include <tgfx2/vertex_layout.hpp>

extern "C" {
#include <tgfx/resources/tc_shader.h>
#include <tgfx/resources/tc_shader_registry.h>
}

namespace termin::gui_native {
    namespace {

        constexpr termin::visual::PointerId3D kMousePointer = 1;
        constexpr const char* kTexturedStaticMeshShader = "termin-engine-static-mesh-textured";

        struct TexturedStaticMeshVertex {
            termin::Vec3f position;
            termin::Vec2f uv;
        };

        struct TexturedStaticMeshPush {
            float view_projection[16];
            float base_color_factor[4];
        };

        tgfx::VertexLayoutDesc textured_static_mesh_layout() {
            tgfx::VertexLayoutDesc layout;
            layout.stride = sizeof(TexturedStaticMeshVertex);
            layout.attribute_count = 2;
            layout.attributes[0] = {0,
                                    tgfx::VertexFormat::Float3,
                                    static_cast<std::uint32_t>(offsetof(TexturedStaticMeshVertex, position)),
                                    tgfx::intern_vertex_semantic("position")};
            layout.attributes[1] = {1,
                                    tgfx::VertexFormat::Float2,
                                    static_cast<std::uint32_t>(offsetof(TexturedStaticMeshVertex, uv)),
                                    tgfx::intern_vertex_semantic("uv0")};
            return layout;
        }

        termin::LinearColor flat_lit_color(const termin::visual::StaticMeshDrawPacket3D& packet,
                                           const termin::Vec3& first,
                                           const termin::Vec3& second,
                                           const termin::Vec3& third) {
            if (!packet.flat_lighting.enabled)
                return packet.tint;
            termin::Vec3 normal;
            if (!(second - first).cross(third - first).try_normalized(normal))
                return packet.tint;
            const termin::Vec3 light_direction{packet.flat_lighting.direction.x,
                                               packet.flat_lighting.direction.y,
                                               packet.flat_lighting.direction.z};
            const float intensity = packet.flat_lighting.ambient +
                                    packet.flat_lighting.diffuse *
                                        static_cast<float>(std::max(normal.dot(light_direction), 0.0));
            return {
                packet.tint.r * intensity,
                packet.tint.g * intensity,
                packet.tint.b * intensity,
                packet.tint.a,
            };
        }

        bool finite_camera(const SceneView3DCamera& camera) {
            return termin::Mat44::from_tc_mat44(camera.view_matrix).is_finite() &&
                   termin::Mat44::from_tc_mat44(camera.projection_matrix).is_finite() &&
                   camera.world_position.is_finite();
        }

        tc_mat44 identity_matrix() {
            return termin::Mat44::identity().to_tc_mat44();
        }

        bool same_camera(const SceneView3DCamera& left, const SceneView3DCamera& right) {
            return std::memcmp(&left, &right, sizeof(SceneView3DCamera)) == 0;
        }

        ViewportSurfaceSize pixel_size(tc_ui_rect rect) {
            if (!std::isfinite(rect.width) || !std::isfinite(rect.height) || rect.width <= 0.0f ||
                rect.height <= 0.0f) {
                return {};
            }
            const double width = std::round(static_cast<double>(rect.width));
            const double height = std::round(static_cast<double>(rect.height));
            if (width <= 0.0 || height <= 0.0) {
                return {};
            }
            const double maximum = static_cast<double>(std::numeric_limits<int>::max());
            return {static_cast<int>(std::min(width, maximum)), static_cast<int>(std::min(height, maximum))};
        }

        void release_pointer_capture_if_owned(tc_ui_document_handle document,
                                              tc_widget_handle owner,
                                              const char* transition) {
            if (!tc_ui_document_is_valid(document) || tc_widget_handle_is_invalid(owner) ||
                !tc_widget_handle_eq(tc_ui_document_pointer_capture(document), owner)) {
                return;
            }
            if (!tc_ui_document_release_pointer_capture(document, owner)) {
                tc_log_error("[termin-gui-native] SceneView3D could not release pointer capture after %s", transition);
            }
        }

        struct CollectedDraw {
            tc_visual_item3d_handle item = tc_visual_item3d_handle_invalid();
            termin::Affine3d world_from_local = termin::Affine3d::identity();
            std::string protocol;
            termin::visual::PrimitiveDrawPacket3D primitive;
            termin::visual::StaticMeshDrawPacket3D mesh;
            termin::visual::PointCloudDrawPacket3D point_cloud;
        };

        class CollectingSink final : public termin::visual::ScenePaintSink3D {
        public:
            std::vector<CollectedDraw> draws;

            bool begin(const termin::visual::VisualView3D&) override {
                draws.clear();
                return true;
            }

            bool submit(const termin::visual::DrawSubmission3D& submission) override {
                if (!submission.packet.protocol || !submission.packet.payload) {
                    tc_log_error("[termin-gui-native] SceneView3D received an empty draw packet");
                    return false;
                }
                CollectedDraw draw;
                draw.item = submission.item;
                draw.world_from_local = submission.world_from_local;
                draw.protocol = submission.packet.protocol;
                if (draw.protocol == termin::visual::PrimitiveDrawProtocol3D &&
                    submission.packet.payload_size == sizeof(draw.primitive)) {
                    draw.primitive =
                        *static_cast<const termin::visual::PrimitiveDrawPacket3D*>(submission.packet.payload);
                } else if (draw.protocol == termin::visual::StaticMeshDrawProtocol3D &&
                           submission.packet.payload_size == sizeof(draw.mesh)) {
                    draw.mesh = *static_cast<const termin::visual::StaticMeshDrawPacket3D*>(submission.packet.payload);
                } else if (draw.protocol == termin::visual::PointCloudDrawProtocol3D &&
                           submission.packet.payload_size == sizeof(draw.point_cloud)) {
                    draw.point_cloud =
                        *static_cast<const termin::visual::PointCloudDrawPacket3D*>(submission.packet.payload);
                } else {
                    tc_log_error("[termin-gui-native] SceneView3D has no renderer for protocol '%s'",
                                 submission.packet.protocol);
                    return false;
                }
                draws.push_back(std::move(draw));
                return true;
            }

            bool end() override {
                return true;
            }

            void abort() override {
                draws.clear();
            }
        };

        void append_linear_vertex(std::vector<float>& destination, termin::Vec3 position, termin::LinearColor color) {
            destination.push_back(static_cast<float>(position.x));
            destination.push_back(static_cast<float>(position.y));
            destination.push_back(static_cast<float>(position.z));
            destination.push_back(color.r);
            destination.push_back(color.g);
            destination.push_back(color.b);
            destination.push_back(color.a);
        }

    } // namespace

    struct SceneView3D::RenderState {
        struct PointCloudCache {
            std::shared_ptr<const termin::visual::PointCloudData3D> source;
            termin::Affine3d transform = termin::Affine3d::identity();
            std::unique_ptr<tgfx::PointCloud> gpu;
            bool used = false;
        };

        struct BaseColorTextureCache {
            std::shared_ptr<const termin::visual::BaseColorTextureData3D> source;
            tgfx::TextureHandle gpu{};
            bool used = false;
        };

        tgfx::IRenderDevice* device = nullptr;
        tgfx::TextureHandle color{};
        tgfx::TextureHandle depth{};
        termin::ImmediateRenderer immediate;
        tgfx::PointCloudRenderer point_renderer;
        std::vector<PointCloudCache> point_clouds;
        std::vector<BaseColorTextureCache> base_color_textures;
        tc_shader_handle textured_mesh_shader = tc_shader_handle_invalid();
        tgfx::ShaderHandle textured_mesh_vertex{};
        tgfx::ShaderHandle textured_mesh_fragment{};
    };

    SceneView3D::SceneView3D(termin::visual::TcVisualScene3D scene)
        : NativeWidget("SceneView3D"),
          scene_(scene.handle()),
          render_state_(std::make_unique<RenderState>()) {
        camera_.view_matrix = identity_matrix();
        camera_.projection_matrix = identity_matrix();
        set_style_role(TC_UI_STYLE_PANEL);
        set_focusable(true);
        set_preferred_size(tc_ui_size{320.0f, 200.0f});
    }

    SceneView3D::~SceneView3D() {
        release_render_resources();
    }

    termin::visual::TcVisualScene3D SceneView3D::scene() const {
        return termin::visual::TcVisualScene3D{scene_};
    }

    void SceneView3D::set_scene(termin::visual::TcVisualScene3D scene_value) {
        if (tc_visual_scene3d_handle_eq(scene_, scene_value.handle()))
            return;

        const std::uint64_t replacement_revision = ++scene_revision_;
        const bool active_sequence =
            !pointer_transition_in_progress_ &&
            (scene_pointer_active_ || fallback_pointer_active_ || interaction_.pressed_hit(kMousePointer).has_value() ||
             interaction_.captured_hit(kMousePointer).has_value());
        const bool quarantine_sequence = scene_pointer_cancelled_until_up_ || active_sequence;
        if (active_sequence) {
            tc_ui_pointer_event cancel{};
            cancel.type = TC_UI_POINTER_CANCEL;
            cancel.cancel_reason = TC_UI_POINTER_CANCEL_SUBTREE_INEFFECTIVE;
            bool delivered_by_document = false;
            if (tc_ui_document_is_valid(document())) {
                delivered_by_document = tc_ui_document_cancel_pointer_interaction(document(), cancel.cancel_reason);
            }
            if (!delivered_by_document) {
                cancel_pointer(document(), cancel);
            }
            // A nested replacement from a Cancel callback wins, but the
            // physical sequence terminated by this outer replacement still
            // owns its pending tail.
            scene_pointer_cancelled_until_up_ = scene_pointer_cancelled_until_up_ || quarantine_sequence;
            if (scene_revision_ != replacement_revision)
                return;
        }

        const termin::visual::TcVisualScene3D previous_scene = scene();
        const bool nested_transition = pointer_transition_in_progress_;
        if (!nested_transition)
            pointer_transition_in_progress_ = true;
        if (!nested_transition && previous_scene.valid()) {
            if (interaction_.cancel_all(previous_scene)) {
                tc_log_error("[termin-gui-native] SceneView3D scene replacement cancellation callback failed");
            }
        } else {
            // A callback reentering set_scene() is already inside delivery of
            // the one terminal Cancel for the old sequence. Clear old route
            // state without recursively dispatching that Cancel again.
            interaction_.cancel_all();
        }
        if (!nested_transition)
            pointer_transition_in_progress_ = false;
        if (scene_revision_ != replacement_revision) {
            scene_pointer_cancelled_until_up_ = scene_pointer_cancelled_until_up_ || quarantine_sequence;
            return;
        }

        scene_pointer_active_ = false;
        // Scene replacement terminates an owned physical sequence. Its tail
        // still belongs to this widget even though document capture has been
        // released, so never let a matching Move/Up reach the new scene or
        // fallback without a Down.
        scene_pointer_cancelled_until_up_ = quarantine_sequence;
        fallback_pointer_active_ = false;
        scene_ = scene_value.handle();
        invalidate_scene();
    }

    void SceneView3D::invalidate_scene() {
        render_dirty_ = true;
        mark_dirty(TC_WIDGET_DIRTY_STATE | TC_WIDGET_DIRTY_PAINT);
    }

    void SceneView3D::set_camera(SceneView3DCamera camera_value) {
        if (!finite_camera(camera_value)) {
            tc_log_error("[termin-gui-native] SceneView3D rejected a non-finite camera");
            return;
        }
        if (same_camera(camera_, camera_value) && !camera_provider_)
            return;
        camera_provider_ = {};
        camera_ = camera_value;
        invalidate_view();
    }

    const SceneView3DCamera& SceneView3D::camera() const {
        return camera_;
    }

    void SceneView3D::set_camera_provider(CameraProvider provider) {
        camera_provider_ = std::move(provider);
        invalidate_view();
    }

    void SceneView3D::invalidate_view() {
        render_dirty_ = true;
        mark_dirty(TC_WIDGET_DIRTY_STATE | TC_WIDGET_DIRTY_PAINT);
    }

    ViewportSurfaceSize SceneView3D::framebuffer_size() const {
        return requested_size_;
    }

    uint32_t SceneView3D::texture_id() const {
        return render_state_ && render_state_->color ? render_state_->color.id : 0;
    }

    std::optional<termin::Ray3> SceneView3D::world_ray(float widget_x, float widget_y) const {
        if (requested_size_.width <= 0 || requested_size_.height <= 0) {
            tc_log_error("[termin-gui-native] SceneView3D cannot build a world ray without a positive "
                         "framebuffer size (got %dx%d)",
                         requested_size_.width,
                         requested_size_.height);
            return std::nullopt;
        }
        if (!finite_camera(camera_)) {
            tc_log_error("[termin-gui-native] SceneView3D cannot build a world ray from a non-finite camera");
            return std::nullopt;
        }
        const tc_ui_rect rect = bounds();
        const termin::Mat44 projection = termin::Mat44::from_tc_mat44(camera_.projection_matrix);
        const termin::Mat44 view = termin::Mat44::from_tc_mat44(camera_.view_matrix);
        termin::Ray3 ray;
        termin::ScreenRayError error{};
        if (!termin::try_unproject_screen_ray(projection,
                                              view,
                                              {widget_x, widget_y},
                                              {rect.x, rect.y, rect.width, rect.height},
                                              ray,
                                              &error,
                                              1.0e-12)) {
            tc_log_error("[termin-gui-native] SceneView3D cannot build a world ray: %s",
                         termin::screen_ray_error_message(error));
            return std::nullopt;
        }
        return ray;
    }

    termin::visual::SceneInteraction3D& SceneView3D::interaction() {
        return interaction_;
    }

    const termin::visual::SceneInteraction3D& SceneView3D::interaction() const {
        return interaction_;
    }

    void SceneView3D::set_fallback_pointer_handler(FallbackPointerHandler handler) {
        fallback_pointer_handler_ = std::move(handler);
    }

    void SceneView3D::set_clear_color(termin::LinearColor color) {
        if (!std::isfinite(color.r) || !std::isfinite(color.g) || !std::isfinite(color.b) || !std::isfinite(color.a)) {
            tc_log_error("[termin-gui-native] SceneView3D rejected a non-finite clear color");
            return;
        }
        clear_color_ = color;
        invalidate_view();
    }

    tc_ui_size SceneView3D::measure(tc_ui_document_handle, tc_ui_constraints constraints) {
        return detail::clamp_size(preferred_size(), constraints);
    }

    bool SceneView3D::sync_framebuffer_size() {
        const ViewportSurfaceSize next = pixel_size(bounds());
        if (next == requested_size_)
            return false;
        requested_size_ = next;
        invalidate_view();
        return true;
    }

    void SceneView3D::layout(tc_ui_document_handle document, tc_ui_rect rect) {
        NativeWidget::layout(document, rect);
        sync_framebuffer_size();
    }

    void SceneView3D::paint(tc_ui_document_handle document, tc_ui_paint_context* context) {
        const tc_ui_style style = computed_style(document);
        tc_ui_painter_fill_rect(context, bounds(), style.background);
        if (texture_id() != 0 && requested_size_.width > 0 && requested_size_.height > 0) {
            tc_ui_painter_draw_texture(context,
                                       texture_id(),
                                       bounds(),
                                       tc_ui_srgb_color{1.0f, 1.0f, 1.0f, 1.0f},
                                       TC_UI_TEXTURE_SAMPLING_LINEAR,
                                       false);
        }
    }

    bool SceneView3D::call_fallback(const tc_ui_pointer_event& event, const std::optional<termin::Ray3>& ray) {
        FallbackPointerHandler handler =
            active_fallback_pointer_handler_ ? active_fallback_pointer_handler_ : fallback_pointer_handler_;
        if (!handler)
            return false;
        // A handler may replace/clear itself through the supplied view.
        // Keep the currently executing callable alive across that mutation.
        try {
            return handler(*this, event, ray);
        } catch (const std::exception& error) {
            tc_log_error("[termin-gui-native] SceneView3D fallback pointer handler failed: %s", error.what());
        } catch (...) {
            tc_log_error("[termin-gui-native] SceneView3D fallback pointer handler failed");
        }
        return false;
    }

    void SceneView3D::cancel_pointer(tc_ui_document_handle document, const tc_ui_pointer_event& event) {
        const tc_widget_handle view_handle = handle();
        const bool interaction_active = interaction_.hovered_hit(kMousePointer).has_value() ||
                                        interaction_.pressed_hit(kMousePointer).has_value() ||
                                        interaction_.captured_hit(kMousePointer).has_value();
        const bool cancel_scene = scene_pointer_active_ || interaction_active;
        const bool cancel_fallback = fallback_pointer_active_;
        const termin::visual::TcVisualScene3D cancelled_scene = scene();
        const auto fallback_ray = cancel_fallback ? world_ray(event.x, event.y) : std::nullopt;

        // Publish the terminal transition before invoking user callbacks.
        // Reentrant set_scene() must observe no active owner and clear route
        // state without recursively delivering the same Cancel.
        scene_pointer_active_ = false;
        scene_pointer_cancelled_until_up_ = false;
        fallback_pointer_active_ = false;
        release_pointer_capture_if_owned(document, view_handle, "the initial Cancel transition");

        if (pointer_transition_in_progress_) {
            interaction_.cancel_all();
            release_pointer_capture_if_owned(document, view_handle, "a reentrant Cancel callback");
            invalidate_scene();
            return;
        }

        pointer_transition_in_progress_ = true;
        if (cancel_scene) {
            if (cancelled_scene.valid()) {
                if (interaction_.cancel_all(cancelled_scene)) {
                    tc_log_error("[termin-gui-native] SceneView3D pointer cancellation callback failed");
                }
            } else {
                interaction_.cancel_all();
            }
        } else {
            interaction_.release(kMousePointer);
        }
        if (cancel_fallback)
            call_fallback(event, fallback_ray);
        // Terminal callbacks cannot retain capture for the sequence being
        // closed. Preserve capture if they deliberately transferred it to a
        // different widget.
        release_pointer_capture_if_owned(document, view_handle, "a Cancel callback");
        active_fallback_pointer_handler_ = {};
        pointer_transition_in_progress_ = false;
        invalidate_scene();
    }

    tc_ui_event_result SceneView3D::pointer_event(tc_ui_document_handle document, const tc_ui_pointer_event* event) {
        if (!event)
            return TC_UI_EVENT_IGNORED;
        if (scene_pointer_cancelled_until_up_) {
            if (event->type == TC_UI_POINTER_UP || event->type == TC_UI_POINTER_CANCEL) {
                scene_pointer_cancelled_until_up_ = false;
            } else if (event->type == TC_UI_POINTER_DOWN) {
                // A new Down starts a distinct sequence even if the previous
                // host sequence never supplied its terminal Up.
                scene_pointer_cancelled_until_up_ = false;
            } else {
                return TC_UI_EVENT_HANDLED;
            }
            if (event->type != TC_UI_POINTER_DOWN) {
                release_pointer_capture_if_owned(document, handle(), "a quarantined terminal event");
                return TC_UI_EVENT_HANDLED;
            }
        }
        if (scene_pointer_active_ && !scene().valid()) {
            tc_log_error("[termin-gui-native] SceneView3D cancelled pointer capture because its borrowed scene "
                         "is no longer valid");
            tc_ui_pointer_event cancel = *event;
            cancel.type = TC_UI_POINTER_CANCEL;
            cancel.cancel_reason = TC_UI_POINTER_CANCEL_SUBTREE_INEFFECTIVE;
            const bool await_terminal_up = event->type != TC_UI_POINTER_UP && event->type != TC_UI_POINTER_CANCEL;
            cancel_pointer(document, cancel);
            scene_pointer_cancelled_until_up_ = await_terminal_up;
            return TC_UI_EVENT_HANDLED;
        }
        if (event->type == TC_UI_POINTER_CANCEL) {
            const bool active = scene_pointer_active_ || fallback_pointer_active_ ||
                                interaction_.hovered_hit(kMousePointer).has_value() ||
                                interaction_.pressed_hit(kMousePointer).has_value() ||
                                interaction_.captured_hit(kMousePointer).has_value();
            cancel_pointer(document, *event);
            return active ? TC_UI_EVENT_HANDLED : TC_UI_EVENT_IGNORED;
        }

        const auto ray = world_ray(event->x, event->y);
        if (scene_pointer_active_ && !ray) {
            tc_log_error("[termin-gui-native] SceneView3D cancelled an active scene pointer sequence because "
                         "the current event cannot be projected to a world ray");
            tc_ui_pointer_event cancel = *event;
            cancel.type = TC_UI_POINTER_CANCEL;
            cancel.cancel_reason = TC_UI_POINTER_CANCEL_EXPLICIT;
            const bool await_terminal_up = event->type != TC_UI_POINTER_UP;
            cancel_pointer(document, cancel);
            scene_pointer_cancelled_until_up_ = await_terminal_up;
            return TC_UI_EVENT_HANDLED;
        }
        if (!ray && !tc_visual_item3d_handle_is_invalid(interaction_.hovered(kMousePointer))) {
            // Projection loss also terminates hover: otherwise the controller
            // would keep a stale Enter until some later valid scene event.
            // There is no active press here, so fallback/normal propagation is
            // intentionally still allowed after the final Leave notification.
            if (scene().valid()) {
                if (interaction_.cancel_all(scene())) {
                    tc_log_error("[termin-gui-native] SceneView3D hover cancellation callback failed");
                }
            } else {
                interaction_.cancel_all();
            }
            invalidate_scene();
        }
        if (fallback_pointer_active_) {
            const tc_widget_handle view_handle = handle();
            if (event->type == TC_UI_POINTER_UP) {
                // Publish the terminal state before the callback. A fallback
                // Up handler may replace the scene, but must not then receive
                // a second terminal Cancel from set_scene().
                fallback_pointer_active_ = false;
                release_pointer_capture_if_owned(document, view_handle, "the fallback Up transition");
                scene_pointer_cancelled_until_up_ = false;
            }
            const std::uint64_t routed_scene_revision = scene_revision_;
            const bool handled = call_fallback(*event, ray);
            if (event->type == TC_UI_POINTER_UP)
                release_pointer_capture_if_owned(document, view_handle, "a fallback Up callback");
            if (scene_revision_ != routed_scene_revision) {
                active_fallback_pointer_handler_ = {};
                if (event->type == TC_UI_POINTER_UP)
                    scene_pointer_cancelled_until_up_ = false;
                return TC_UI_EVENT_HANDLED;
            }
            if (event->type == TC_UI_POINTER_UP)
                active_fallback_pointer_handler_ = {};
            if (handled)
                invalidate_view();
            return TC_UI_EVENT_HANDLED;
        }

        if (scene_pointer_active_ && event->type != TC_UI_POINTER_MOVE && event->type != TC_UI_POINTER_DOWN &&
            event->type != TC_UI_POINTER_UP) {
            // The scene target owns the whole physical sequence. Auxiliary
            // events such as Wheel/Leave must not leak to the fallback camera
            // controller in the middle of an item drag.
            return TC_UI_EVENT_HANDLED;
        }

        std::optional<termin::visual::PointerEventKind3D> kind;
        if (event->type == TC_UI_POINTER_MOVE)
            kind = termin::visual::PointerEventKind3D::Move;
        else if (event->type == TC_UI_POINTER_DOWN)
            kind = termin::visual::PointerEventKind3D::Down;
        else if (event->type == TC_UI_POINTER_UP)
            kind = termin::visual::PointerEventKind3D::Up;

        if (kind && ray && scene().valid()) {
            const tc_widget_handle view_handle = handle();
            const tc_visual_scene3d_handle routed_scene = scene_;
            const std::uint64_t routed_scene_revision = scene_revision_;
            if (event->type == TC_UI_POINTER_UP && scene_pointer_active_) {
                // SceneInteraction3D likewise clears pressed/captured before
                // invoking the target Up callback.
                scene_pointer_active_ = false;
                release_pointer_capture_if_owned(document, view_handle, "the scene Up transition");
                scene_pointer_cancelled_until_up_ = false;
            }
            const auto dispatch = interaction_.route(
                scene(), {kMousePointer, *kind, *ray, static_cast<uint32_t>(std::max(event->button, 0))});
            if (event->type == TC_UI_POINTER_UP)
                release_pointer_capture_if_owned(document, view_handle, "a scene Up callback");
            if (scene_revision_ != routed_scene_revision) {
                // set_scene() invalidated this route. Keep no state or result
                // published by the old-scene call even if the replacement
                // callback destroyed that borrowed scene before route returned.
                interaction_.cancel_all();
                scene_pointer_active_ = false;
                fallback_pointer_active_ = false;
                if (event->type == TC_UI_POINTER_DOWN) {
                    // Invalidate the outer document Down even when no capture
                    // had been installed yet (for example replacement from an
                    // Enter callback before route() published its hit).
                    tc_ui_document_cancel_pointer_interaction(document, TC_UI_POINTER_CANCEL_CAPTURE_REPLACED);
                    scene_pointer_cancelled_until_up_ = true;
                } else if (event->type == TC_UI_POINTER_UP) {
                    // This Up is already the terminal tail which set_scene()
                    // tried to quarantine from inside the callback.
                    scene_pointer_cancelled_until_up_ = false;
                }
                invalidate_scene();
                return TC_UI_EVENT_HANDLED;
            }
            const bool routed_to_scene = !tc_visual_item3d_handle_is_invalid(dispatch.target);
            if (event->type == TC_UI_POINTER_DOWN && routed_to_scene) {
                const auto cancel_failed_capture = [&](const char* reason) {
                    tc_log_error("[termin-gui-native] SceneView3D cancelled scene Down because %s", reason);
                    tc_ui_pointer_event cancel = *event;
                    cancel.type = TC_UI_POINTER_CANCEL;
                    cancel.cancel_reason = TC_UI_POINTER_CANCEL_CAPTURE_REPLACED;
                    const bool delivered_by_document =
                        tc_ui_document_cancel_pointer_interaction(document, cancel.cancel_reason);
                    if (!delivered_by_document)
                        cancel_pointer(document, cancel);
                    scene_pointer_cancelled_until_up_ = true;
                };
                if (tc_visual_item3d_handle_is_invalid(dispatch.captured) ||
                    !interaction_.captured_hit(kMousePointer).has_value()) {
                    cancel_failed_capture("the target released scene capture during Down");
                } else {
                    if (!tc_ui_document_set_focus(document, handle())) {
                        cancel_failed_capture("UI focus failed");
                    } else if (!tc_visual_scene3d_handle_eq(scene_, routed_scene) ||
                               !interaction_.captured_hit(kMousePointer).has_value()) {
                        cancel_failed_capture("focus handling changed the scene capture");
                    } else if (!tc_ui_document_set_pointer_capture(document, handle())) {
                        cancel_failed_capture("UI pointer capture failed");
                    } else if (!tc_visual_scene3d_handle_eq(scene_, routed_scene) ||
                               !interaction_.captured_hit(kMousePointer).has_value()) {
                        cancel_failed_capture("UI capture handling changed the scene capture");
                    } else {
                        scene_pointer_active_ = true;
                    }
                }
            }
            invalidate_scene();
            if (routed_to_scene || scene_pointer_active_ || event->type == TC_UI_POINTER_UP) {
                return TC_UI_EVENT_HANDLED;
            }
        }

        if (event->type == TC_UI_POINTER_DOWN) {
            active_fallback_pointer_handler_ = fallback_pointer_handler_;
            // Publish provisional ownership before Down enters user code, as
            // SceneInteraction3D does for a scene target. A reentrant scene
            // replacement can then deliver exactly one terminal Cancel to the
            // snapshotted handler. An ignored Down is rolled back below.
            fallback_pointer_active_ = true;
        }
        const std::uint64_t fallback_scene_revision = scene_revision_;
        const bool fallback_handled = call_fallback(*event, ray);
        if (scene_revision_ != fallback_scene_revision) {
            active_fallback_pointer_handler_ = {};
            if (event->type == TC_UI_POINTER_DOWN) {
                fallback_pointer_active_ = false;
                scene_pointer_cancelled_until_up_ = true;
            } else if (event->type == TC_UI_POINTER_UP) {
                scene_pointer_cancelled_until_up_ = false;
            }
            return TC_UI_EVENT_HANDLED;
        }
        if (fallback_handled) {
            if (event->type == TC_UI_POINTER_DOWN) {
                fallback_pointer_active_ = true;
                const auto cancel_failed_capture = [&](const char* reason) {
                    tc_log_error("[termin-gui-native] SceneView3D cancelled fallback Down because %s", reason);
                    tc_ui_pointer_event cancel = *event;
                    cancel.type = TC_UI_POINTER_CANCEL;
                    cancel.cancel_reason = TC_UI_POINTER_CANCEL_CAPTURE_REPLACED;
                    const bool delivered_by_document =
                        tc_ui_document_cancel_pointer_interaction(document, cancel.cancel_reason);
                    if (!delivered_by_document && fallback_pointer_active_)
                        cancel_pointer(document, cancel);
                    scene_pointer_cancelled_until_up_ = true;
                };
                if (!tc_ui_document_set_focus(document, handle())) {
                    cancel_failed_capture("UI focus failed");
                } else if (scene_revision_ != fallback_scene_revision || !fallback_pointer_active_) {
                    scene_pointer_cancelled_until_up_ = true;
                } else if (!tc_ui_document_set_pointer_capture(document, handle())) {
                    cancel_failed_capture("UI pointer capture failed");
                } else if (scene_revision_ != fallback_scene_revision || !fallback_pointer_active_) {
                    cancel_failed_capture("UI capture handling changed fallback ownership");
                }
            }
            invalidate_view();
            return TC_UI_EVENT_HANDLED;
        }
        if (event->type == TC_UI_POINTER_DOWN) {
            fallback_pointer_active_ = false;
            active_fallback_pointer_handler_ = {};
        }
        return TC_UI_EVENT_IGNORED;
    }

    void SceneView3D::on_destroy(tc_ui_document_handle document) {
        tc_ui_pointer_event cancel{};
        cancel.type = TC_UI_POINTER_CANCEL;
        cancel.cancel_reason = TC_UI_POINTER_CANCEL_SUBTREE_INEFFECTIVE;
        cancel_pointer(document, cancel);
        fallback_pointer_handler_ = {};
        active_fallback_pointer_handler_ = {};
        camera_provider_ = {};
        scene_ = tc_visual_scene3d_handle_invalid();
        release_render_resources();
        NativeWidget::on_destroy(document);
    }

    bool SceneView3D::update_camera_from_provider() {
        if (!camera_provider_)
            return true;
        try {
            const auto provided = camera_provider_(requested_size_);
            if (!provided) {
                tc_log_error("[termin-gui-native] SceneView3D camera provider returned no camera");
                return false;
            }
            if (!finite_camera(*provided)) {
                tc_log_error("[termin-gui-native] SceneView3D camera provider returned a non-finite camera");
                return false;
            }
            if (!same_camera(camera_, *provided)) {
                camera_ = *provided;
                render_dirty_ = true;
            }
            return true;
        } catch (const std::exception& error) {
            tc_log_error("[termin-gui-native] SceneView3D camera provider failed: %s", error.what());
        } catch (...) {
            tc_log_error("[termin-gui-native] SceneView3D camera provider failed");
        }
        return false;
    }

    void SceneView3D::prepare_render(tgfx::RenderContext2& context, tgfx::FontAtlas&, float) {
        if (requested_size_.width <= 0 || requested_size_.height <= 0 || !update_camera_from_provider())
            return;
        RenderState& state = *render_state_;
        tgfx::IRenderDevice& device = context.device();
        if (state.device && state.device != &device) {
            release_render_resources();
        }
        state.device = &device;

        const auto target_mismatch = [&](tgfx::TextureHandle texture) {
            if (!texture)
                return true;
            const tgfx::TextureDesc description = device.texture_desc(texture);
            return description.width != static_cast<uint32_t>(requested_size_.width) ||
                   description.height != static_cast<uint32_t>(requested_size_.height);
        };
        if (target_mismatch(state.color) || target_mismatch(state.depth)) {
            if (state.color)
                device.destroy(state.color);
            if (state.depth)
                device.destroy(state.depth);
            device.invalidate_render_target_cache();
            tgfx::TextureDesc color_description;
            color_description.width = static_cast<uint32_t>(requested_size_.width);
            color_description.height = static_cast<uint32_t>(requested_size_.height);
            color_description.format = tgfx::PixelFormat::RGBA16F;
            color_description.usage = tgfx::TextureUsage::Sampled | tgfx::TextureUsage::ColorAttachment;
            state.color = device.create_texture(color_description);
            tgfx::TextureDesc depth_description;
            depth_description.width = color_description.width;
            depth_description.height = color_description.height;
            depth_description.format = tgfx::PixelFormat::D32F;
            depth_description.usage = tgfx::TextureUsage::DepthStencilAttachment;
            state.depth = device.create_texture(depth_description);
            if (!state.color || !state.depth) {
                tc_log_error("[termin-gui-native] SceneView3D failed to allocate a %dx%d framebuffer",
                             requested_size_.width,
                             requested_size_.height);
                return;
            }
            render_dirty_ = true;
            mark_dirty(TC_WIDGET_DIRTY_PAINT);
        }
        if (!render_dirty_)
            return;

        termin::visual::VisualView3D view{};
        view.view_matrix = camera_.view_matrix;
        view.projection_matrix = camera_.projection_matrix;
        view.camera_world_position = camera_.world_position;
        view.viewport_width = static_cast<uint32_t>(requested_size_.width);
        view.viewport_height = static_cast<uint32_t>(requested_size_.height);
        CollectingSink sink;
        if (scene().valid() && !termin::visual::paint(scene(), view, sink)) {
            tc_log_error("[termin-gui-native] SceneView3D failed to collect a scene frame");
            return;
        }

        context.begin_pass(state.color, state.depth, &clear_color_, 1.0f, true);
        context.set_viewport(0, 0, requested_size_.width, requested_size_.height);
        const termin::Mat44 view_matrix = termin::Mat44::from_tc_mat44(camera_.view_matrix);
        const termin::Mat44 projection_matrix = termin::Mat44::from_tc_mat44(camera_.projection_matrix);
        const termin::Mat44 view_projection = projection_matrix * view_matrix;
        std::array<float, 16> view_projection_float{};
        for (size_t index = 0; index < view_projection_float.size(); ++index)
            view_projection_float[index] = static_cast<float>(view_projection.data[index]);
        for (auto& cache : state.point_clouds)
            cache.used = false;
        for (auto& cache : state.base_color_textures)
            cache.used = false;

        for (const CollectedDraw& draw : sink.draws) {
            if (draw.protocol == termin::visual::PrimitiveDrawProtocol3D && draw.primitive.geometry) {
                const auto& geometry = *draw.primitive.geometry;
                state.immediate.begin();
                auto& vertices =
                    draw.primitive.depth_test ? state.immediate.tri_vertices_depth : state.immediate.tri_vertices;
                for (size_t index = 0; index + 2 < geometry.triangles.size(); index += 3) {
                    const uint32_t indices[3] = {
                        geometry.triangles[index], geometry.triangles[index + 1], geometry.triangles[index + 2]};
                    if (indices[0] >= geometry.vertices.size() || indices[1] >= geometry.vertices.size() ||
                        indices[2] >= geometry.vertices.size()) {
                        tc_log_error("[termin-gui-native] SceneView3D skipped an invalid primitive triangle");
                        continue;
                    }
                    for (uint32_t vertex_index : indices) {
                        const auto& vertex = geometry.vertices[vertex_index];
                        append_linear_vertex(vertices,
                                             draw.world_from_local.transform_point(
                                                 {vertex.position.x, vertex.position.y, vertex.position.z}),
                                             vertex.color);
                    }
                }
                state.immediate.flush_depth(&context, view_matrix, projection_matrix, true);
                state.immediate.flush(&context, view_matrix, projection_matrix, false, true);
            } else if (draw.protocol == termin::visual::StaticMeshDrawProtocol3D && draw.mesh.mesh &&
                       draw.mesh.base_color_texture) {
                const auto& mesh = *draw.mesh.mesh;
                const auto& texture_source = draw.mesh.base_color_texture;
                if (!mesh.has_uvs()) {
                    tc_log_error("[termin-gui-native] SceneView3D skipped a textured mesh without UVs");
                    continue;
                }
                auto texture_cache =
                    std::find_if(state.base_color_textures.begin(), state.base_color_textures.end(), [&](const auto& value) {
                        return value.source == texture_source;
                    });
                if (texture_cache == state.base_color_textures.end()) {
                    tgfx::TextureDesc description;
                    description.width = texture_source->width;
                    description.height = texture_source->height;
                    description.format = tgfx::PixelFormat::RGBA8_sRGB;
                    description.usage = tgfx::TextureUsage::Sampled | tgfx::TextureUsage::CopyDst;
                    RenderState::BaseColorTextureCache created;
                    created.source = texture_source;
                    created.gpu = device.create_texture(description);
                    if (!created.gpu) {
                        tc_log_error("[termin-gui-native] SceneView3D failed to create a base-color texture");
                        continue;
                    }
                    device.upload_texture(created.gpu, texture_source->rgba8);
                    state.base_color_textures.push_back(std::move(created));
                    texture_cache = std::prev(state.base_color_textures.end());
                }
                texture_cache->used = true;

                if (tc_shader_handle_is_invalid(state.textured_mesh_shader))
                    state.textured_mesh_shader = tgfx::register_builtin_shader_from_catalog(kTexturedStaticMeshShader);
                tc_shader* shader = tc_shader_get(state.textured_mesh_shader);
                if (!shader || !termin::tc_shader_ensure_tgfx2(shader,
                                                               &device,
                                                               &state.textured_mesh_vertex,
                                                               &state.textured_mesh_fragment)) {
                    tc_log_error("[termin-gui-native] SceneView3D textured static-mesh shader is unavailable");
                    continue;
                }

                std::vector<TexturedStaticMeshVertex> vertices;
                vertices.reserve(mesh.triangles.size());
                for (std::uint32_t vertex_index : mesh.triangles) {
                    if (vertex_index >= mesh.vertices.size() || vertex_index >= mesh.uvs.size()) {
                        tc_log_error("[termin-gui-native] SceneView3D skipped an invalid textured mesh triangle");
                        vertices.clear();
                        break;
                    }
                    const auto& vertex = mesh.vertices[vertex_index];
                    const auto world = draw.world_from_local.transform_point({vertex.x, vertex.y, vertex.z});
                    vertices.push_back({{static_cast<float>(world.x),
                                         static_cast<float>(world.y),
                                         static_cast<float>(world.z)},
                                        mesh.uvs[vertex_index]});
                }
                if (vertices.empty())
                    continue;

                TexturedStaticMeshPush push{};
                std::copy(view_projection_float.begin(), view_projection_float.end(), push.view_projection);
                push.base_color_factor[0] = draw.mesh.tint.r;
                push.base_color_factor[1] = draw.mesh.tint.g;
                push.base_color_factor[2] = draw.mesh.tint.b;
                push.base_color_factor[3] = draw.mesh.tint.a;
                context.set_depth_test(draw.mesh.depth_test);
                context.set_depth_write(draw.mesh.depth_test);
                context.set_blend(false);
                context.set_cull(tgfx::CullMode::None);
                context.bind_shader(state.textured_mesh_vertex, state.textured_mesh_fragment);
                context.use_shader_resource_layout(shader);
                context.bind_uniform_data("u_push", &push, sizeof(push));
                context.bind_texture("u_base_color_texture", texture_cache->gpu);
                const auto layout = textured_static_mesh_layout();
                context.draw_transient_arrays(vertices.data(),
                                              static_cast<std::uint32_t>(vertices.size() * sizeof(vertices[0])),
                                              static_cast<std::uint32_t>(vertices.size()),
                                              layout,
                                              tgfx::PrimitiveTopology::TriangleList);
            } else if (draw.protocol == termin::visual::StaticMeshDrawProtocol3D && draw.mesh.mesh) {
                const auto& mesh = *draw.mesh.mesh;
                state.immediate.begin();
                auto& vertices =
                    draw.mesh.depth_test ? state.immediate.tri_vertices_depth : state.immediate.tri_vertices;
                for (size_t index = 0; index + 2 < mesh.triangles.size(); index += 3) {
                    const uint32_t indices[3] = {
                        mesh.triangles[index], mesh.triangles[index + 1], mesh.triangles[index + 2]};
                    if (indices[0] >= mesh.vertices.size() || indices[1] >= mesh.vertices.size() ||
                        indices[2] >= mesh.vertices.size()) {
                        tc_log_error("[termin-gui-native] SceneView3D skipped an invalid mesh triangle");
                        continue;
                    }
                    const auto& first_vertex = mesh.vertices[indices[0]];
                    const auto& second_vertex = mesh.vertices[indices[1]];
                    const auto& third_vertex = mesh.vertices[indices[2]];
                    const std::array<termin::Vec3, 3> world_vertices = {
                        draw.world_from_local.transform_point({first_vertex.x, first_vertex.y, first_vertex.z}),
                        draw.world_from_local.transform_point({second_vertex.x, second_vertex.y, second_vertex.z}),
                        draw.world_from_local.transform_point({third_vertex.x, third_vertex.y, third_vertex.z}),
                    };
                    const auto color = flat_lit_color(
                        draw.mesh, world_vertices[0], world_vertices[1], world_vertices[2]);
                    for (const auto& vertex : world_vertices)
                        append_linear_vertex(vertices, vertex, color);
                }
                state.immediate.flush_depth(&context, view_matrix, projection_matrix, true);
                state.immediate.flush(&context, view_matrix, projection_matrix, false, true);
            } else if (draw.protocol == termin::visual::PointCloudDrawProtocol3D && draw.point_cloud.cloud) {
                auto cache = std::find_if(state.point_clouds.begin(), state.point_clouds.end(), [&](const auto& value) {
                    return value.source == draw.point_cloud.cloud &&
                           std::memcmp(&value.transform, &draw.world_from_local, sizeof(termin::Affine3d)) == 0;
                });
                if (cache == state.point_clouds.end()) {
                    RenderState::PointCloudCache created;
                    created.source = draw.point_cloud.cloud;
                    created.transform = draw.world_from_local;
                    created.gpu = std::make_unique<tgfx::PointCloud>();
                    std::vector<tgfx::PointCloudPoint> transformed = created.source->points;
                    for (auto& point : transformed) {
                        const termin::Vec3 world =
                            created.transform.transform_point({point.position.x, point.position.y, point.position.z});
                        point.position = {
                            static_cast<float>(world.x), static_cast<float>(world.y), static_cast<float>(world.z)};
                    }
                    if (!created.gpu->upload(context, transformed)) {
                        tc_log_error("[termin-gui-native] SceneView3D failed to upload a point cloud");
                        continue;
                    }
                    state.point_clouds.push_back(std::move(created));
                    cache = std::prev(state.point_clouds.end());
                }
                cache->used = true;
                tgfx::PointCloudDrawParams parameters;
                parameters.view_projection = view_projection_float;
                state.point_renderer.draw(context, *cache->gpu, draw.point_cloud.style, parameters);
            }
        }
        context.end_pass();

        std::erase_if(state.point_clouds, [&](auto& cache) {
            if (cache.used)
                return false;
            cache.gpu->release(device);
            return true;
        });
        std::erase_if(state.base_color_textures, [&](auto& cache) {
            if (cache.used)
                return false;
            device.destroy(cache.gpu);
            return true;
        });
        render_dirty_ = false;
        mark_dirty(TC_WIDGET_DIRTY_PAINT);
    }

    void SceneView3D::release_render_resources() {
        if (!render_state_ || !render_state_->device)
            return;
        RenderState& state = *render_state_;
        for (auto& cache : state.point_clouds) {
            if (cache.gpu)
                cache.gpu->release(*state.device);
        }
        state.point_clouds.clear();
        for (auto& cache : state.base_color_textures) {
            if (cache.gpu)
                state.device->destroy(cache.gpu);
        }
        state.base_color_textures.clear();
        state.textured_mesh_vertex = {};
        state.textured_mesh_fragment = {};
        state.point_renderer.release(*state.device);
        if (state.color)
            state.device->destroy(state.color);
        if (state.depth)
            state.device->destroy(state.depth);
        state.device->invalidate_render_target_cache();
        state.color = {};
        state.depth = {};
        state.device = nullptr;
        render_dirty_ = true;
    }

} // namespace termin::gui_native
