// editor_interaction_system.cpp - Singleton editor interaction coordinator

#include "termin/editor/editor_interaction_system.hpp"
#include "core/tc_scene.h"
#include "render/tc_display.h"
#include "render/tc_render_surface.h"
#include "render/tc_render_target.h"
#include "render/tc_viewport.h"
#include "tc_picking.h"
#include "termin/camera/camera_component.hpp"
#include "termin/camera/orbit_camera_controller.hpp"
#include "termin/editor/component_editor_visual.hpp"
#include "termin/editor/editor_snap.hpp"
#include "termin/editor/gizmo_visual_item3d.hpp"
#include "termin/render/mesh_renderer.hpp"
#include "termin/render/render_pipeline.hpp"
#include <components/mesh_component.hpp>
#include <tcbase/input_enums.hpp>
#include <tcbase/tc_log.h>
#include <termin/entity/component.hpp>
#include <termin/tc_scene.hpp>
#include <tgfx2/render_context.hpp>

#include <algorithm>
#include <cmath>
#include <cstdint>
#include <cstdlib>

namespace termin {

    namespace {

        EditorInteractionSystem* g_editor_interaction_instance = nullptr;

        bool picking_debug_enabled() {
            const char* value = std::getenv("TERMIN_PICKING_DEBUG");
            return value && value[0] != '\0' && value[0] != '0';
        }

        struct PickIdLookupScan {
            uint32_t target_pick_id = 0;
            size_t scanned_count = 0;
            bool found = false;
            tc_entity_id found_id = TC_ENTITY_ID_INVALID;
            const char* found_name = nullptr;
            uint32_t min_pick_id = 0;
            uint32_t max_pick_id = 0;
        };

        static bool scan_pick_id_lookup(tc_entity_pool* pool, tc_entity_id id, void* user_data) {
            auto* scan = static_cast<PickIdLookupScan*>(user_data);
            uint32_t current_pick_id = tc_entity_pool_pick_id(pool, id);
            scan->scanned_count++;
            if (current_pick_id != 0) {
                if (scan->min_pick_id == 0 || current_pick_id < scan->min_pick_id) {
                    scan->min_pick_id = current_pick_id;
                }
                if (current_pick_id > scan->max_pick_id) {
                    scan->max_pick_id = current_pick_id;
                }
            }
            if (current_pick_id == scan->target_pick_id) {
                scan->found = true;
                scan->found_id = id;
                scan->found_name = tc_entity_pool_name(pool, id);
                return false;
            }
            return true;
        }

        static void log_pick_lookup_miss_details(tc_entity_pool* pool, uint32_t pick_id, const char* context) {
            PickIdLookupScan scan;
            scan.target_pick_id = pick_id;
            tc_entity_pool_foreach(pool, scan_pick_id_lookup, &scan);

            tc_log(TC_LOG_WARN,
                   "[PickingDebug] %s: pick_id=%u lookup miss; linear_found=%d "
                   "pool_count=%zu scanned=%zu "
                   "pick_range=%u..%u entity='%s' entity_id=(%u,%u)",
                   context ? context : "pick lookup",
                   pick_id,
                   scan.found ? 1 : 0,
                   tc_entity_pool_count(pool),
                   scan.scanned_count,
                   scan.min_pick_id,
                   scan.max_pick_id,
                   scan.found_name ? scan.found_name : "<none>",
                   scan.found_id.index,
                   scan.found_id.generation);
        }

        static bool mesh_triangle_indices(const tc_mesh* mesh, uint32_t tri, uint32_t out[3]) {
            if (!mesh || !mesh->indices) {
                return false;
            }
            size_t first = static_cast<size_t>(tri) * 3;
            if (first + 2 >= mesh->index_count) {
                return false;
            }
            out[0] = mesh->indices[first];
            out[1] = mesh->indices[first + 1];
            out[2] = mesh->indices[first + 2];
            return true;
        }

        static bool try_affine3d_from_mat44f(const Mat44f& matrix, Affine3d& out_affine) {
            const Mat44 double_matrix = matrix.to_double();
            return Affine3d::try_from_matrix4(double_matrix.data, out_affine);
        }

    } // namespace

    // ============================================================================
    // Constructor / Destructor
    // ============================================================================

    EditorInteractionSystem::EditorInteractionSystem() {
        g_editor_interaction_instance = this;

        // Setup transform gizmo
        _transform_gizmo.size = 1.5f;
        _transform_gizmo.visible = false;
        _transform_gizmo.on_transform_changed = [this]() {
            _request_update();
        };
        _transform_gizmo.on_drag_end = [this](const GeneralPose3& old_pose, const GeneralPose3& new_pose) {
            if (on_transform_end) {
                on_transform_end(old_pose, new_pose);
            }
        };
        auto transform_visual = std::make_unique<GizmoVisualItem3D>(_transform_gizmo);
        auto* transform_visual_controller = transform_visual.get();
        const auto transform_visual_handle = _overlay_scene.scene().adopt(std::move(transform_visual));
        if (!transform_visual_handle) {
            tc_log(TC_LOG_ERROR, "[EditorInteractionSystem] failed to adopt the TransformGizmo overlay item");
        } else {
            _transform_gizmo_visual = *transform_visual_handle;
            transform_visual_controller->bind_controller(_overlay_scene.interaction());
        }
        const auto camera_frustum_visual =
            _overlay_scene.scene().adopt(std::make_unique<CameraFrustumOverlayItem3D>(this));
        if (!camera_frustum_visual)
            tc_log(TC_LOG_ERROR, "[EditorInteractionSystem] failed to adopt the camera frustum overlay item");

        tc_log(TC_LOG_INFO, "[EditorInteractionSystem] Created");
    }

    EditorInteractionSystem::~EditorInteractionSystem() {
        _cancel_overlay_pointer_state(false, "editor interaction shutdown");
        _clear_component_visual_gizmos();
        _destroy_transform_gizmo_visual();

        if (g_editor_interaction_instance == this) {
            g_editor_interaction_instance = nullptr;
        }
        tc_log(TC_LOG_INFO, "[EditorInteractionSystem] Destroyed");
    }

    // ============================================================================
    // Singleton
    // ============================================================================

    EditorInteractionSystem* EditorInteractionSystem::instance() {
        return g_editor_interaction_instance;
    }

    void EditorInteractionSystem::set_instance(EditorInteractionSystem* inst) {
        g_editor_interaction_instance = inst;
    }

    void EditorInteractionSystem::clear_callbacks() {
        selection.on_selection_changed = nullptr;
        selection.on_hover_changed = nullptr;
        on_request_update = nullptr;
        on_transform_end = nullptr;
        on_key = nullptr;
        on_entity_click = nullptr;
        on_viewport_pointer_event = nullptr;
    }

    // ============================================================================
    // Gizmo
    // ============================================================================

    void EditorInteractionSystem::set_gizmo_target(Entity entity) {
        const std::uint64_t transition_revision = ++_overlay_transition_revision;
        _cancel_overlay_pointer_state(true, "gizmo target change");
        if (_overlay_transition_revision != transition_revision)
            return;
        _transform_gizmo.set_target(entity);
        if (_overlay_transition_revision != transition_revision)
            return;
        _transform_gizmo.visible = entity.valid();
        _rebuild_component_visual_gizmos(entity);
    }

    void EditorInteractionSystem::set_camera_frustums_visible(bool visible) {
        _camera_frustums_visible = visible;
        _request_update();
    }

    void EditorInteractionSystem::set_camera_frustum_render_context(tc_scene_handle scene, int width, int height) {
        _camera_frustum_scene = scene;
        _camera_frustum_view_width = width;
        _camera_frustum_view_height = height;
    }

    double EditorInteractionSystem::camera_frustum_aspect_override() const {
        if (_camera_frustum_view_width <= 0 || _camera_frustum_view_height <= 0) {
            return 0.0;
        }
        return static_cast<double>(_camera_frustum_view_width) / static_cast<double>(_camera_frustum_view_height);
    }

    void EditorInteractionSystem::_rebuild_component_visual_gizmos(Entity entity) {
        _clear_component_visual_gizmos();
        if (!entity.valid()) {
            return;
        }

        ComponentEditorVisualContext context;
        context.transform_gizmo = &_transform_gizmo;

        std::vector<ComponentEditorVisualContribution> contributions;
        size_t count = entity.component_count();
        for (size_t i = 0; i < count; ++i) {
            tc_component* component = entity.component_at(i);
            ComponentEditorVisualRegistry::instance().collect_overlay_items(entity, component, context, contributions);
        }

        for (auto& contribution : contributions) {
            if (!contribution.item) {
                tc_log(TC_LOG_ERROR, "[EditorInteractionSystem] component visual provider returned an empty item");
                continue;
            }
            const auto handle = _overlay_scene.scene().adopt(std::move(contribution.item));
            if (!handle) {
                tc_log(TC_LOG_ERROR, "[EditorInteractionSystem] failed to adopt a component overlay item");
                continue;
            }
            if (contribution.bind_controller)
                contribution.bind_controller(_overlay_scene.interaction(), *handle);
            _component_visual_items.push_back(*handle);
        }
    }

    void EditorInteractionSystem::_clear_component_visual_gizmos() {
        for (const auto handle : _component_visual_items) {
            _overlay_scene.interaction().clear_target_pointer_handler(handle);
            _overlay_scene.interaction().clear_action_handler(handle);
            if (!_overlay_scene.scene().destroy(handle))
                tc_log(TC_LOG_ERROR, "[EditorInteractionSystem] failed to destroy a component overlay item");
        }
        _component_visual_items.clear();
    }

    void EditorInteractionSystem::_destroy_transform_gizmo_visual() {
        if (tc_visual_item3d_handle_is_invalid(_transform_gizmo_visual))
            return;
        _overlay_scene.interaction().clear_target_pointer_handler(_transform_gizmo_visual);
        _overlay_scene.interaction().clear_action_handler(_transform_gizmo_visual);
        if (!_overlay_scene.scene().destroy(_transform_gizmo_visual))
            tc_log(TC_LOG_ERROR, "[EditorInteractionSystem] failed to destroy the TransformGizmo overlay item");
        _transform_gizmo_visual = tc_visual_item3d_handle_invalid();
    }

    void EditorInteractionSystem::_cancel_overlay_pointer_state(bool quarantine_active_sequence, const char* context) {
        auto& interaction = _overlay_scene.interaction();
        const bool active = interaction.pressed_hit(1).has_value() || interaction.captured_hit(1).has_value();
        // Publish ownership termination before callbacks. A Cancel handler may
        // synchronously select another gizmo target and must observe the old
        // sequence as already finished.
        if (active) {
            _overlay_pointer_cancelled_until_up = quarantine_active_sequence;
        } else if (!quarantine_active_sequence) {
            _overlay_pointer_cancelled_until_up = false;
        }

        // Always invalidate the interaction epoch. During Enter the hover map
        // is not published yet, but a visual rebuild still has to stop that
        // in-flight route before its old handler/item can be used again.
        if (interaction.cancel_all(_overlay_scene.scene())) {
            tc_log(TC_LOG_ERROR,
                   "[EditorInteractionSystem] overlay cancellation callback failed during %s",
                   context ? context : "state transition");
        }
    }

    // ============================================================================
    // Events from EditorViewportInputManager
    // ============================================================================

    void EditorInteractionSystem::on_mouse_button(int button,
                                                  int action,
                                                  int mods,
                                                  uint32_t click_count,
                                                  float x,
                                                  float y,
                                                  tc_viewport_handle vp,
                                                  tc_display_handle display) {
        const auto overlay_kind = action == TC_INPUT_PRESS ? visual::PointerEventKind3D::Down
                                                           : visual::PointerEventKind3D::Up;
        if (_route_overlay_pointer(overlay_kind, Vec2f{x, y}, button, vp)) {
            _request_update();
            return;
        }
        const std::string phase = action == TC_INPUT_PRESS ? "down" : "up";
        if (_dispatch_viewport_pointer(
                ViewportPointerEvent{phase, Vec2f{x, y}, Vec2f{0.0f, 0.0f}, button, action, mods})) {
            _request_update();
            return;
        }

        if (button == tcbase::mouse_button_value(tcbase::MouseButton::LEFT)) {
            if (action == TC_INPUT_PRESS) {
                _pending_press = {Vec2f{x, y}, vp, display, true};

                if (click_count == 2) {
                    _handle_double_click(Vec2f{x, y}, vp, display);
                }
            }
            if (action == TC_INPUT_RELEASE) {
                _pending_release = {Vec2f{x, y}, vp, display, true};
            }
        }

        _request_update();
    }

    void EditorInteractionSystem::on_mouse_move(
        float x, float y, float dx, float dy, tc_viewport_handle vp, tc_display_handle display) {
        if (_route_overlay_pointer(visual::PointerEventKind3D::Move, Vec2f{x, y}, 0, vp)) {
            _request_update();
            return;
        }
        if (_dispatch_viewport_pointer(ViewportPointerEvent{"move", Vec2f{x, y}, Vec2f{dx, dy}, -1, -1, 0})) {
            _request_update();
            return;
        }

        _pending_hover = {Vec2f{x, y}, vp, display, true};

        _request_update();
    }

    void EditorInteractionSystem::on_focus_lost() {
        _cancel_overlay_pointer_state(true, "viewport focus loss");
        _has_press = false;
        _pending_press.valid = false;
        _pending_release.valid = false;
        _pending_hover.valid = false;
        _request_update();
    }

    bool EditorInteractionSystem::handle_key_event(const KeyEvent& event,
                                                   Vec2f cursor,
                                                   tc_viewport_handle viewport,
                                                   tc_display_handle display) {
        if (event.action != TC_ACTION_PRESS) {
            return false;
        }
        if (event.key == TC_KEY_T || event.key == 't' || event.key == 292) {
            bool handled = _snap_transform_gizmo_target(cursor, viewport, display);
            if (!handled) {
                tc_log(TC_LOG_WARN, "[EditorSnap] snap hotkey was not handled");
            }
            return handled;
        }
        return false;
    }

    bool EditorInteractionSystem::_snap_transform_gizmo_target(Vec2f cursor,
                                                               tc_viewport_handle viewport,
                                                               tc_display_handle display) {
        if (!_transform_gizmo.can_snap()) {
            tc_log(TC_LOG_WARN,
                   "[EditorSnap] active transform target cannot snap has_target=%d "
                   "source=%d target_valid=%d",
                   _transform_gizmo.has_target() ? 1 : 0,
                   static_cast<int>(_transform_gizmo.preferred_snap_source()),
                   _transform_gizmo.snap_target_entity().valid() ? 1 : 0);
            return false;
        }

        Entity target_entity = _transform_gizmo.snap_target_entity();
        if (!target_entity.valid()) {
            tc_log(TC_LOG_ERROR, "[EditorSnap] cannot snap: target entity is invalid");
            return false;
        }

        EditorSnapRequest request;
        request.source = _transform_gizmo.preferred_snap_source();
        request.target_entity = target_entity;
        request.reference_position = _transform_gizmo.snap_reference_position();
        request.scene = target_entity.scene().handle();

        SurfacePickResult surface = pick_surface_at(cursor, viewport, display);
        if (surface.has_world_point) {
            request.reference_position = surface.world_point;
        } else {
            tc_log(TC_LOG_WARN, "[EditorSnap] no cursor surface reference at cursor=(%.1f, %.1f)", cursor.x, cursor.y);
            if (request.source == EditorSnapSource::VisibleGeometry) {
                return false;
            }
        }

        EditorSnapResult result;
        if (!EditorSnapRegistry::instance().snap(request, result) || !result.success) {
            tc_log(TC_LOG_WARN, "[EditorSnap] snap failed for source=%d", static_cast<int>(request.source));
            return false;
        }

        if (!_transform_gizmo.snap_to(result.position)) {
            tc_log(TC_LOG_ERROR, "[EditorSnap] failed to apply snapped position");
            return false;
        }

        tc_log(TC_LOG_INFO,
               "[EditorSnap] snapped transform target to (%.3f, %.3f, %.3f)",
               result.position.x,
               result.position.y,
               result.position.z);
        _request_update();
        return true;
    }

    // ============================================================================
    // Post-render processing
    // ============================================================================

    void EditorInteractionSystem::after_render() {
        if (_async_release_pick.valid) {
            _poll_async_release_pick();
        }
        if (_async_hover_pick.valid) {
            _poll_async_hover_pick();
        }
        if (_pending_press.valid) {
            _process_pending_press();
            _pending_press.valid = false;
        }
        if (_pending_release.valid) {
            _process_pending_release();
            _pending_release.valid = false;
        }
        if (_pending_hover.valid) {
            _process_pending_hover();
            _pending_hover.valid = false;
        }
    }

    void EditorInteractionSystem::render_overlays(ImmediateRenderer* renderer,
                                                   tgfx::RenderContext2* render_context,
                                                   const Mat44f& view,
                                                   const Mat44f& projection) {
        const int width = render_context ? render_context->viewport_width() : 0;
        const int height = render_context ? render_context->viewport_height() : 0;
        if (_overlay_scene.scene().size() > 0 &&
            !_overlay_scene.paint(renderer,
                                  render_context,
                                  view,
                                  projection,
                                  static_cast<std::uint32_t>(std::max(width, 0)),
                                  static_cast<std::uint32_t>(std::max(height, 0)))) {
            tc_log(TC_LOG_ERROR, "[EditorInteractionSystem] failed to render editor overlay scene");
        }
    }

    void EditorInteractionSystem::_process_pending_press() {
        Vec2f screen = _pending_press.screen;
        tc_viewport_handle vp = _pending_press.vp;
        tc_display_handle display = _pending_press.display;

        _press_x = screen.x;
        _press_y = screen.y;
        _has_press = true;
        if (!tc_viewport_handle_valid(vp))
            return;
    }

    void EditorInteractionSystem::_process_pending_release() {
        Vec2f screen = _pending_release.screen;
        tc_viewport_handle vp = _pending_release.vp;
        tc_display_handle display = _pending_release.display;

        if (!_has_press) {
            return;
        }

        // Click vs drag detection
        Vec2f drag = screen - Vec2f{_press_x, _press_y};
        float dist_sq = drag.norm_squared();
        float threshold_sq = _click_threshold * _click_threshold;
        if (dist_sq > threshold_sq) {
            // Drag detected, skip selection
            _has_press = false;
            return;
        }
        _has_press = false;

        if (_async_release_pick.valid) {
            _request_update();
            return;
        }
        if (_start_async_surface_pick(screen, vp, display)) {
            _request_update();
            return;
        }

        SurfacePickResult pick = pick_surface_at(screen, vp, display);
        if (_dispatch_entity_click(screen, pick)) {
            _request_update();
            return;
        }

        // Pick entity and select
        selection.select(pick.entity);
        _request_update();
    }

    void EditorInteractionSystem::_process_pending_hover() {
        Vec2f screen = _pending_hover.screen;
        tc_viewport_handle vp = _pending_hover.vp;
        tc_display_handle display = _pending_hover.display;

        if (!tc_viewport_handle_valid(vp))
            return;

        // Pick entity for hover highlight
        if (_async_hover_pick.valid) {
            _request_update();
            return;
        }
        if (_start_async_entity_pick(screen, vp, display)) {
            _request_update();
            return;
        }

        Entity ent = pick_entity_at(screen, vp, display);
        selection.hover(ent);
    }

    bool EditorInteractionSystem::_dispatch_entity_click(Vec2f screen, const SurfacePickResult& pick) {
        if (!on_entity_click) {
            return false;
        }
        EditorEntityClickEvent event;
        event.entity = pick.entity;
        event.screen = screen;
        event.surface = pick;
        return on_entity_click(event);
    }

    bool EditorInteractionSystem::_dispatch_viewport_pointer(const ViewportPointerEvent& event) {
        return on_viewport_pointer_event ? on_viewport_pointer_event(event) : false;
    }

    bool EditorInteractionSystem::_route_overlay_pointer(visual::PointerEventKind3D kind,
                                                         Vec2f screen,
                                                         int button,
                                                         tc_viewport_handle viewport) {
        constexpr visual::PointerId3D overlay_pointer = 1;
        if (_overlay_pointer_cancelled_until_up) {
            if (kind == visual::PointerEventKind3D::Down) {
                tc_log(TC_LOG_WARN,
                       "[EditorInteractionSystem] received a new overlay Down before the cancelled sequence's Up; "
                       "ending stale event suppression");
                _overlay_pointer_cancelled_until_up = false;
            } else {
                if (kind == visual::PointerEventKind3D::Up || kind == visual::PointerEventKind3D::Cancel)
                    _overlay_pointer_cancelled_until_up = false;
                return true;
            }
        }

        auto& interaction = _overlay_scene.interaction();
        const auto reconcile_failed_ray = [&](const char* reason) {
            const bool active = interaction.pressed_hit(overlay_pointer).has_value() ||
                                interaction.captured_hit(overlay_pointer).has_value();
            const bool hovered = interaction.hovered_hit(overlay_pointer).has_value();
            if (!active && !hovered)
                return false;

            if (active) {
                tc_log(TC_LOG_WARN,
                       "[EditorInteractionSystem] %s during an active overlay pointer sequence; "
                       "cancelling capture and consuming the event",
                       reason);
            } else {
                tc_log(TC_LOG_WARN,
                       "[EditorInteractionSystem] %s while an overlay item was hovered; clearing stale hover",
                       reason);
            }
            if (interaction.cancel_all(_overlay_scene.scene())) {
                tc_log(TC_LOG_ERROR,
                       "[EditorInteractionSystem] overlay cancellation callback failed after screen ray loss");
            }
            _overlay_pointer_cancelled_until_up =
                active && kind != visual::PointerEventKind3D::Up && kind != visual::PointerEventKind3D::Cancel;
            return active;
        };

        if (!tc_viewport_handle_valid(viewport))
            return reconcile_failed_ray("viewport became invalid");
        const std::optional<Ray3> ray = _screen_to_ray(screen, viewport);
        if (!ray)
            return reconcile_failed_ray("screen ray construction failed");
        const std::uint64_t transition_revision = _overlay_transition_revision;
        const bool handled =
            _overlay_scene.route_pointer(kind, *ray, static_cast<std::uint32_t>(std::max(button, 0)), overlay_pointer);
        if (_overlay_transition_revision != transition_revision) {
            // Enter is delivered before a Down is published as pressed. A
            // visual/target replacement from that callback invalidates the
            // route, so explicitly retain ownership of the physical tail.
            if (kind == visual::PointerEventKind3D::Down) {
                _overlay_pointer_cancelled_until_up = true;
            } else if (kind == visual::PointerEventKind3D::Up || kind == visual::PointerEventKind3D::Cancel) {
                _overlay_pointer_cancelled_until_up = false;
            }
            return true;
        }
        return handled;
    }

    bool
    EditorInteractionSystem::_start_async_entity_pick(Vec2f screen, tc_viewport_handle vp, tc_display_handle display) {
        if (_async_hover_pick.valid || !tc_viewport_handle_valid(vp))
            return false;

        tc_render_target_handle rt = tc_viewport_get_render_target(vp);
        tc_pipeline_handle pipeline_h = tc_render_target_get_pipeline(rt);
        if (!tc_pipeline_pool_alive(pipeline_h))
            return false;
        RenderPipeline pipeline(pipeline_h);

        tgfx::TextureHandle id_tex = pipeline.get_color_tex2("id");
        if (!id_tex)
            return false;
        auto* dev = pipeline.tex2_device();
        if (!dev)
            return false;

        Vec2i fbo;
        if (!_window_to_fbo_coords(screen, vp, display, fbo))
            return false;

        uint64_t color_request = dev->request_pixel_rgba8(id_tex, fbo.x, fbo.y);
        if (color_request == 0)
            return false;

        _async_hover_pick.event = {screen, vp, display, true};
        _async_hover_pick.fbo = fbo;
        _async_hover_pick.color_request = color_request;
        _async_hover_pick.valid = true;
        return true;
    }

    bool
    EditorInteractionSystem::_start_async_surface_pick(Vec2f screen, tc_viewport_handle vp, tc_display_handle display) {
        const bool debug_pick = picking_debug_enabled();
        if (_async_release_pick.valid || !tc_viewport_handle_valid(vp))
            return false;

        tc_render_target_handle rt = tc_viewport_get_render_target(vp);
        tc_pipeline_handle pipeline_h = tc_render_target_get_pipeline(rt);
        if (!tc_pipeline_pool_alive(pipeline_h))
            return false;
        RenderPipeline pipeline(pipeline_h);

        tgfx::TextureHandle id_tex = pipeline.get_color_tex2("id");
        tgfx::TextureHandle depth_tex = pipeline.get_depth_tex2("id");
        if (!id_tex || !depth_tex)
            return false;
        auto* dev = pipeline.tex2_device();
        if (!dev)
            return false;

        Vec2i fbo;
        if (!_window_to_fbo_coords(screen, vp, display, fbo)) {
            if (debug_pick) {
                int vp_x = 0;
                int vp_y = 0;
                int vp_w = 0;
                int vp_h = 0;
                tc_viewport_get_pixel_rect(vp, &vp_x, &vp_y, &vp_w, &vp_h);
                tc_log(TC_LOG_WARN,
                       "[PickingDebug] async release coords outside viewport: "
                       "cursor=(%.1f,%.1f) viewport_rect=(%d,%d %dx%d)",
                       screen.x,
                       screen.y,
                       vp_x,
                       vp_y,
                       vp_w,
                       vp_h);
            }
            return false;
        }

        uint64_t color_request = dev->request_pixel_rgba8(id_tex, fbo.x, fbo.y);
        uint64_t depth_request = dev->request_pixel_depth_float(depth_tex, fbo.x, fbo.y);
        if (color_request == 0 || depth_request == 0) {
            if (debug_pick) {
                const tgfx::TextureDesc color_desc = dev->texture_desc(id_tex);
                const tgfx::TextureDesc depth_desc = dev->texture_desc(depth_tex);
                tc_log(TC_LOG_WARN,
                       "[PickingDebug] async release request failed: fbo=(%d,%d) "
                       "color_req=%llu depth_req=%llu id_tex=%u size=%ux%u format=%d "
                       "depth_tex=%u size=%ux%u format=%d",
                       fbo.x,
                       fbo.y,
                       static_cast<unsigned long long>(color_request),
                       static_cast<unsigned long long>(depth_request),
                       id_tex.id,
                       color_desc.width,
                       color_desc.height,
                       static_cast<int>(color_desc.format),
                       depth_tex.id,
                       depth_desc.width,
                       depth_desc.height,
                       static_cast<int>(depth_desc.format));
            }
            return false;
        }
        if (debug_pick) {
            const tgfx::TextureDesc color_desc = dev->texture_desc(id_tex);
            tc_log(TC_LOG_INFO,
                   "[PickingDebug] async release requested: cursor=(%.1f,%.1f) "
                   "fbo=(%d,%d) color_req=%llu depth_req=%llu id_tex=%u size=%ux%u "
                   "format=%d",
                   screen.x,
                   screen.y,
                   fbo.x,
                   fbo.y,
                   static_cast<unsigned long long>(color_request),
                   static_cast<unsigned long long>(depth_request),
                   id_tex.id,
                   color_desc.width,
                   color_desc.height,
                   static_cast<int>(color_desc.format));
        }

        _async_release_pick.event = {screen, vp, display, true};
        _async_release_pick.fbo = fbo;
        _async_release_pick.color_request = color_request;
        _async_release_pick.depth_request = depth_request;
        _async_release_pick.color_ready = false;
        _async_release_pick.depth_ready = false;
        _async_release_pick.color[0] = 0.0f;
        _async_release_pick.color[1] = 0.0f;
        _async_release_pick.color[2] = 0.0f;
        _async_release_pick.color[3] = 0.0f;
        _async_release_pick.depth = 1.0f;
        _async_release_pick.valid = true;
        return true;
    }

    void EditorInteractionSystem::_poll_async_hover_pick() {
        float color[4] = {0, 0, 0, 0};
        tc_render_target_handle rt = tc_viewport_get_render_target(_async_hover_pick.event.vp);
        tc_pipeline_handle pipeline_h = tc_render_target_get_pipeline(rt);
        if (!tc_pipeline_pool_alive(pipeline_h)) {
            _async_hover_pick.valid = false;
            return;
        }
        RenderPipeline pipeline(pipeline_h);
        auto* dev = pipeline.tex2_device();
        if (!dev) {
            _async_hover_pick.valid = false;
            return;
        }
        if (!dev->poll_pixel_rgba8(_async_hover_pick.color_request, color)) {
            _request_update();
            return;
        }

        Entity ent = _entity_from_pick_color(color, _async_hover_pick.event.vp);
        selection.hover(ent);
        _async_hover_pick.valid = false;
    }

    void EditorInteractionSystem::_poll_async_release_pick() {
        const bool debug_pick = picking_debug_enabled();
        tc_render_target_handle rt = tc_viewport_get_render_target(_async_release_pick.event.vp);
        tc_pipeline_handle pipeline_h = tc_render_target_get_pipeline(rt);
        if (!tc_pipeline_pool_alive(pipeline_h)) {
            _async_release_pick.valid = false;
            return;
        }
        RenderPipeline pipeline(pipeline_h);
        auto* dev = pipeline.tex2_device();
        if (!dev) {
            _async_release_pick.valid = false;
            return;
        }
        if (!_async_release_pick.color_ready) {
            _async_release_pick.color_ready =
                dev->poll_pixel_rgba8(_async_release_pick.color_request, _async_release_pick.color);
        }
        if (!_async_release_pick.depth_ready) {
            _async_release_pick.depth_ready =
                dev->poll_pixel_depth_float(_async_release_pick.depth_request, &_async_release_pick.depth);
        }
        if (!_async_release_pick.color_ready || !_async_release_pick.depth_ready) {
            if (debug_pick) {
                tc_log(TC_LOG_INFO,
                       "[PickingDebug] async release pending: color_req=%llu ready=%d "
                       "depth_req=%llu ready=%d",
                       static_cast<unsigned long long>(_async_release_pick.color_request),
                       _async_release_pick.color_ready ? 1 : 0,
                       static_cast<unsigned long long>(_async_release_pick.depth_request),
                       _async_release_pick.depth_ready ? 1 : 0);
            }
            _request_update();
            return;
        }

        const PendingEvent event = _async_release_pick.event;
        if (debug_pick) {
            const int r = (int)std::round(_async_release_pick.color[0] * 255.0f);
            const int g = (int)std::round(_async_release_pick.color[1] * 255.0f);
            const int b = (int)std::round(_async_release_pick.color[2] * 255.0f);
            const int pick_id = tc_picking_rgb_to_id(r, g, b);
            tc_scene_handle viewport_scene = tc_viewport_get_scene(event.vp);
            tc_scene_handle rt_scene = tc_render_target_get_scene(rt);
            tc_log(TC_LOG_INFO,
                   "[PickingDebug] async release read: fbo=(%d,%d) rgb=(%d,%d,%d) "
                   "pick_id=%d depth=%.6f viewport_scene=(%u,%u) rt_scene=(%u,%u)",
                   _async_release_pick.fbo.x,
                   _async_release_pick.fbo.y,
                   r,
                   g,
                   b,
                   pick_id,
                   _async_release_pick.depth,
                   viewport_scene.index,
                   viewport_scene.generation,
                   rt_scene.index,
                   rt_scene.generation);
        }
        SurfacePickResult pick = _surface_from_pick_color_depth(
            _async_release_pick.color, _async_release_pick.depth, _async_release_pick.fbo, event.vp);
        _async_release_pick.valid = false;

        if (debug_pick) {
            tc_log(TC_LOG_INFO,
                   "[PickingDebug] async release resolved: entity_valid=%d entity='%s' "
                   "entity_pick_id=%u selectable=%d has_world=%d has_mesh=%d",
                   pick.entity.valid() ? 1 : 0,
                   pick.entity.valid() ? pick.entity.name() : "<none>",
                   pick.entity.valid() ? pick.entity.pick_id() : 0,
                   (pick.entity.valid() && pick.entity.selectable()) ? 1 : 0,
                   pick.has_world_point ? 1 : 0,
                   pick.has_mesh_hit ? 1 : 0);
        }

        bool click_handled = _dispatch_entity_click(event.screen, pick);
        if (debug_pick) {
            tc_log(TC_LOG_INFO, "[PickingDebug] async release callback: handled=%d", click_handled ? 1 : 0);
        }
        if (click_handled) {
            _request_update();
            return;
        }

        uint32_t previous_selected_pick_id = selection.selected_pick_id;
        selection.select(pick.entity);
        if (debug_pick) {
            tc_log(TC_LOG_INFO,
                   "[PickingDebug] async release selection: before_pick_id=%u "
                   "after_pick_id=%u",
                   previous_selected_pick_id,
                   selection.selected_pick_id);
        }
        _request_update();
    }

    // ============================================================================
    // Double-click
    // ============================================================================

    void EditorInteractionSystem::_handle_double_click(Vec2f screen, tc_viewport_handle vp, tc_display_handle display) {
        Entity ent = pick_entity_at(screen, vp, display);
        if (!ent.valid()) {
            return;
        }

        double pos[3] = {0.0, 0.0, 0.0};
        ent.get_global_position(pos);
        Vec3 focus{pos[0], pos[1], pos[2]};

        tc_render_target_handle rt = tc_viewport_get_render_target(vp);
        if (!tc_render_target_handle_valid(rt)) {
            tc_log(TC_LOG_WARN,
                   "[EditorInteractionSystem] cannot focus double-click "
                   "target: viewport has no render target");
            return;
        }

        tc_component* cam_comp = tc_render_target_get_camera(rt);
        if (!cam_comp) {
            tc_log(TC_LOG_WARN,
                   "[EditorInteractionSystem] cannot focus double-click "
                   "target: render target has no camera");
            return;
        }

        CxxComponent* cxx = CxxComponent::from_tc(cam_comp);
        auto* camera = dynamic_cast<CameraComponent*>(cxx);
        if (!camera || !camera->entity().valid()) {
            tc_log(TC_LOG_WARN,
                   "[EditorInteractionSystem] cannot focus double-click "
                   "target: active camera component is invalid");
            return;
        }

        OrbitCameraController* orbit = camera->entity().get_component<OrbitCameraController>();
        if (!orbit) {
            tc_log(TC_LOG_WARN,
                   "[EditorInteractionSystem] cannot focus double-click target: camera "
                   "entity '%s' has no OrbitCameraController",
                   camera->entity().name());
            return;
        }

        orbit->center_on(focus);
        _request_update();
    }

    // ============================================================================
    // Picking
    // ============================================================================

    Entity
    EditorInteractionSystem::pick_entity_at(Vec2f screen, tc_viewport_handle viewport, tc_display_handle display) {
        if (!tc_viewport_handle_valid(viewport)) {
            tc_log(TC_LOG_INFO, "[DBG pick] viewport invalid");
            return Entity();
        }

        tc_render_target_handle rt = tc_viewport_get_render_target(viewport);
        tc_pipeline_handle pipeline_h = tc_render_target_get_pipeline(rt);
        if (!tc_pipeline_pool_alive(pipeline_h)) {
            tc_log(TC_LOG_INFO, "[DBG pick] pipeline not alive");
            return Entity();
        }
        RenderPipeline pipeline(pipeline_h);

        tgfx::TextureHandle id_tex = pipeline.get_color_tex2("id");
        if (!id_tex)
            return Entity();

        auto* dev = pipeline.tex2_device();
        if (!dev)
            return Entity();

        Vec2i fbo;
        if (!_window_to_fbo_coords(screen, viewport, display, fbo))
            return Entity();

        float color[4] = {0, 0, 0, 0};
        if (!dev->read_pixel_rgba8(id_tex, fbo.x, fbo.y, color))
            return Entity();

        return _entity_from_pick_color(color, viewport);
    }

    Entity EditorInteractionSystem::_entity_from_pick_color(const float color[4], tc_viewport_handle viewport) {
        int r = (int)std::round(color[0] * 255.0f);
        int g = (int)std::round(color[1] * 255.0f);
        int b = (int)std::round(color[2] * 255.0f);
        int pick_id = tc_picking_rgb_to_id(r, g, b);

        if (pick_id == 0)
            return Entity();

        tc_scene_handle scene = tc_viewport_get_scene(viewport);
        if (!tc_scene_handle_valid(scene))
            return Entity();

        tc_entity_pool* pool = tc_scene_entity_pool(scene);
        if (!pool)
            return Entity();

        tc_entity_id eid = tc_entity_pool_find_by_pick_id(pool, pick_id);
        if (!tc_entity_id_valid(eid))
            return Entity();

        return Entity(pool, eid);
    }

    SurfacePickResult
    EditorInteractionSystem::pick_surface_at(Vec2f screen, tc_viewport_handle viewport, tc_display_handle display) {
        SurfacePickResult result;
        const bool debug_pick = picking_debug_enabled();

        if (!tc_viewport_handle_valid(viewport)) {
            tc_log(TC_LOG_INFO, "[DBG pick_surface] viewport invalid");
            return result;
        }

        tc_render_target_handle rt = tc_viewport_get_render_target(viewport);
        tc_pipeline_handle pipeline_h = tc_render_target_get_pipeline(rt);
        if (!tc_pipeline_pool_alive(pipeline_h)) {
            tc_log(TC_LOG_INFO, "[DBG pick_surface] pipeline not alive");
            return result;
        }
        RenderPipeline pipeline(pipeline_h);

        tgfx::TextureHandle id_tex = pipeline.get_color_tex2("id");
        if (!id_tex) {
            if (debug_pick) {
                tc_log(TC_LOG_WARN,
                       "[PickingDebug] surface pick has no id texture for viewport=(%u,%u)",
                       viewport.index,
                       viewport.generation);
            }
            return result;
        }

        auto* dev = pipeline.tex2_device();
        if (!dev) {
            if (debug_pick) {
                tc_log(TC_LOG_WARN,
                       "[PickingDebug] surface pick has no tgfx2 device for "
                       "viewport=(%u,%u)",
                       viewport.index,
                       viewport.generation);
            }
            return result;
        }

        Vec2i fbo;
        if (!_window_to_fbo_coords(screen, viewport, display, fbo)) {
            if (debug_pick) {
                int vp_x = 0;
                int vp_y = 0;
                int vp_w = 0;
                int vp_h = 0;
                tc_viewport_get_pixel_rect(viewport, &vp_x, &vp_y, &vp_w, &vp_h);
                tc_log(TC_LOG_WARN,
                       "[PickingDebug] surface pick coords outside viewport: "
                       "cursor=(%.1f,%.1f) viewport_rect=(%d,%d %dx%d)",
                       screen.x,
                       screen.y,
                       vp_x,
                       vp_y,
                       vp_w,
                       vp_h);
            }
            return result;
        }

        float color[4] = {0, 0, 0, 0};
        if (!dev->read_pixel_rgba8(id_tex, fbo.x, fbo.y, color)) {
            if (debug_pick) {
                const tgfx::TextureDesc desc = dev->texture_desc(id_tex);
                tc_log(TC_LOG_WARN,
                       "[PickingDebug] surface pick color read failed: fbo=(%d,%d) "
                       "id_tex=%u size=%ux%u format=%d",
                       fbo.x,
                       fbo.y,
                       id_tex.id,
                       desc.width,
                       desc.height,
                       static_cast<int>(desc.format));
            }
            return result;
        }

        int r = (int)std::round(color[0] * 255.0f);
        int g = (int)std::round(color[1] * 255.0f);
        int b = (int)std::round(color[2] * 255.0f);
        int pick_id = tc_picking_rgb_to_id(r, g, b);
        if (debug_pick) {
            const tgfx::TextureDesc desc = dev->texture_desc(id_tex);
            tc_scene_handle viewport_scene = tc_viewport_get_scene(viewport);
            tc_scene_handle rt_scene = tc_render_target_get_scene(rt);
            tc_log(TC_LOG_INFO,
                   "[PickingDebug] surface pick read: cursor=(%.1f,%.1f) fbo=(%d,%d) "
                   "id_tex=%u size=%ux%u format=%d rgb=(%d,%d,%d) pick_id=%d "
                   "viewport_scene=(%u,%u) rt_scene=(%u,%u)",
                   screen.x,
                   screen.y,
                   fbo.x,
                   fbo.y,
                   id_tex.id,
                   desc.width,
                   desc.height,
                   static_cast<int>(desc.format),
                   r,
                   g,
                   b,
                   pick_id,
                   viewport_scene.index,
                   viewport_scene.generation,
                   rt_scene.index,
                   rt_scene.generation);
        }
        if (pick_id == 0)
            return result;

        tc_scene_handle scene = tc_viewport_get_scene(viewport);
        if (!tc_scene_handle_valid(scene)) {
            if (debug_pick) {
                tc_log(TC_LOG_WARN,
                       "[PickingDebug] surface pick decoded pick_id=%d but viewport "
                       "scene is invalid",
                       pick_id);
            }
            return result;
        }

        tc_entity_pool* pool = tc_scene_entity_pool(scene);
        if (!pool) {
            if (debug_pick) {
                tc_log(TC_LOG_WARN,
                       "[PickingDebug] surface pick decoded pick_id=%d but scene has no "
                       "entity pool",
                       pick_id);
            }
            return result;
        }

        tc_entity_id eid = tc_entity_pool_find_by_pick_id(pool, pick_id);
        if (!tc_entity_id_valid(eid)) {
            if (debug_pick) {
                tc_log(TC_LOG_WARN,
                       "[PickingDebug] surface pick decoded pick_id=%d but entity lookup "
                       "failed in viewport scene",
                       pick_id);
                log_pick_lookup_miss_details(pool, static_cast<uint32_t>(pick_id), "surface pick viewport scene");
            }
            return result;
        }

        result.entity = Entity(pool, eid);

        tgfx::TextureHandle depth_tex = pipeline.get_depth_tex2("id");
        if (!depth_tex)
            return result;

        float depth = 1.0f;
        if (!dev->read_pixel_depth_float(depth_tex, fbo.x, fbo.y, &depth))
            return result;
        return _surface_from_pick_color_depth(color, depth, fbo, viewport);
    }

    SurfacePickResult EditorInteractionSystem::_surface_from_pick_color_depth(const float color[4],
                                                                              float depth,
                                                                              Vec2i fbo,
                                                                              tc_viewport_handle viewport) {
        SurfacePickResult result;

        int r = (int)std::round(color[0] * 255.0f);
        int g = (int)std::round(color[1] * 255.0f);
        int b = (int)std::round(color[2] * 255.0f);
        int pick_id = tc_picking_rgb_to_id(r, g, b);
        const bool debug_pick = picking_debug_enabled();
        if (pick_id == 0)
            return result;

        tc_scene_handle scene = tc_viewport_get_scene(viewport);
        if (!tc_scene_handle_valid(scene)) {
            if (debug_pick) {
                tc_log(TC_LOG_WARN,
                       "[PickingDebug] surface resolve failed: pick_id=%d viewport scene "
                       "is invalid",
                       pick_id);
            }
            return result;
        }

        tc_entity_pool* pool = tc_scene_entity_pool(scene);
        if (!pool) {
            if (debug_pick) {
                tc_log(TC_LOG_WARN,
                       "[PickingDebug] surface resolve failed: pick_id=%d scene has no "
                       "entity pool",
                       pick_id);
            }
            return result;
        }

        tc_entity_id eid = tc_entity_pool_find_by_pick_id(pool, pick_id);
        if (!tc_entity_id_valid(eid)) {
            if (debug_pick) {
                tc_log(TC_LOG_WARN,
                       "[PickingDebug] surface resolve failed: pick_id=%d not found in "
                       "scene entity pool",
                       pick_id);
                log_pick_lookup_miss_details(pool, static_cast<uint32_t>(pick_id), "surface resolve viewport scene");
            }
            return result;
        }

        result.entity = Entity(pool, eid);
        result.depth = depth;
        // Exactly 1 is the cleared depth attachment and therefore has no
        // surface point. Other out-of-range or non-finite values are passed to
        // the checked projection contract below so the owner logs the failure.
        if (depth == 1.0f)
            return result;

        tc_render_target_handle rt = tc_viewport_get_render_target(viewport);
        tc_pipeline_handle pipeline_h = tc_render_target_get_pipeline(rt);
        if (!tc_pipeline_pool_alive(pipeline_h))
            return result;
        RenderPipeline pipeline(pipeline_h);
        tgfx::TextureHandle id_tex = pipeline.get_color_tex2("id");
        if (!id_tex)
            return result;
        auto* dev = pipeline.tex2_device();
        if (!dev)
            return result;

        tc_component* cam_comp = tc_render_target_get_camera(rt);
        if (!cam_comp)
            return result;

        CxxComponent* cxx = CxxComponent::from_tc(cam_comp);
        if (!cxx) {
            const char* type_name = tc_component_type_name(cam_comp);
            tc_log(TC_LOG_ERROR,
                   "[EditorInteractionSystem] surface pick projection failed: camera component '%s' is not "
                   "native C++",
                   type_name ? type_name : "<unnamed>");
            return result;
        }

        auto* camera = dynamic_cast<CameraComponent*>(cxx);
        if (!camera) {
            const char* type_name = tc_component_type_name(cam_comp);
            tc_log(TC_LOG_ERROR,
                   "[EditorInteractionSystem] surface pick projection failed: native component '%s' is not a "
                   "CameraComponent",
                   type_name ? type_name : "<unnamed>");
            return result;
        }

        auto desc = dev->texture_desc(id_tex);
        const double width = static_cast<double>(desc.width);
        const double height = static_cast<double>(desc.height);
        if (width <= 0.0 || height <= 0.0) {
            tc_log(TC_LOG_ERROR,
                   "[EditorInteractionSystem] surface pick projection failed: "
                   "pick_id=%d has invalid framebuffer extent=(%.0f,%.0f)",
                   pick_id,
                   width,
                   height);
            return result;
        }

        const double aspect = width / height;
        const Mat44 view = camera->get_view_matrix();
        const Mat44 projection = camera->compute_projection_matrix(aspect);
        const Rect2 framebuffer_rect{0.0, 0.0, width, height};
        const Vec2 pixel_center{static_cast<double>(fbo.x) + 0.5, static_cast<double>(fbo.y) + 0.5};
        ScreenRayError projection_error = ScreenRayError::None;
        if (!_try_populate_surface_projection(result,
                                              projection,
                                              view,
                                              pixel_center,
                                              static_cast<double>(depth),
                                              framebuffer_rect,
                                              &projection_error)) {
            tc_log(TC_LOG_ERROR,
                   "[EditorInteractionSystem] surface pick world reconstruction failed: "
                   "pick_id=%d fbo=(%d,%d) extent=(%.0f,%.0f) depth=%.9g: %s",
                   pick_id,
                   fbo.x,
                   fbo.y,
                   width,
                   height,
                   static_cast<double>(depth),
                   screen_ray_error_message(projection_error));
            return result;
        }
        MeshComponent* mesh_component = result.entity.get_component<MeshComponent>();
        if (mesh_component) {
            tc_mesh* mesh = mesh_component->mesh.get();
            if (!mesh)
                return result;

            auto log_mesh_refinement_failure = [&](const char* reason) {
                tc_log(TC_LOG_ERROR,
                       "[EditorInteractionSystem] surface pick mesh refinement failed: "
                       "pick_id=%d entity='%s': %s",
                       pick_id,
                       result.entity.name(),
                       reason);
            };

            const GeneralTransform3 transform = result.entity.transform();
            const Affine3d entity_affine = transform.global_affine();
            Ray3 world_ray;
            ScreenRayError ray_error = ScreenRayError::None;
            if (!try_unproject_screen_ray(projection, view, pixel_center, framebuffer_rect, world_ray, &ray_error)) {
                log_mesh_refinement_failure(screen_ray_error_message(ray_error));
                return result;
            }

            const Mat44f mesh_offset = mesh_component->get_mesh_offset_matrix();
            tc_mesh_ray ray;
            if (!_try_build_surface_mesh_ray(world_ray, entity_affine, mesh_offset, ray)) {
                log_mesh_refinement_failure("checked mesh-local ray conversion rejected the transforms or direction");
                return result;
            }

            tc_mesh_hit hit;
            if (tc_mesh_raycast(mesh, &ray, &hit)) {
                if (!_try_apply_surface_mesh_hit(result, hit, mesh_offset, entity_affine)) {
                    log_mesh_refinement_failure("checked mesh hit or normal conversion rejected the result");
                    return result;
                }
            }
        }
        return result;
    }

    bool EditorInteractionSystem::_try_populate_surface_projection(SurfacePickResult& result,
                                                                   const Mat44& projection,
                                                                   const Mat44& view,
                                                                   const Vec2& pixel_center,
                                                                   double depth,
                                                                   const Rect2& framebuffer_rect,
                                                                   ScreenRayError* error) {
        Vec3 world;
        if (!try_unproject_screen_point(projection, view, pixel_center, depth, framebuffer_rect, world, error)) {
            return false;
        }

        ProjectedScreenPoint reprojected;
        if (!try_project_world_point(projection, view, world, framebuffer_rect, reprojected, error)) {
            return false;
        }

        result.world_point = world;
        result.view_depth = reprojected.view_point.y;
        result.reproject_screen_error = (reprojected.screen - pixel_center).norm();
        result.reproject_depth_error = reprojected.depth - depth;
        result.has_world_point = true;
        return true;
    }

    bool EditorInteractionSystem::_try_build_surface_mesh_ray(const Ray3& world_ray,
                                                              const Affine3d& entity_affine,
                                                              const Mat44f& mesh_offset,
                                                              tc_mesh_ray& ray) {
        Affine3d mesh_offset_affine;
        if (!try_affine3d_from_mat44f(mesh_offset, mesh_offset_affine)) {
            return false;
        }

        Vec3 world_direction;
        if (!world_ray.direction.try_normalized(world_direction)) {
            return false;
        }
        Vec3 entity_local_origin;
        if (!entity_affine.try_inverse_transform_point(world_ray.origin, entity_local_origin)) {
            return false;
        }
        Vec3 entity_local_direction;
        Vec3 unnormalized_entity_direction;
        if (!entity_affine.try_inverse_transform_vector(world_direction, unnormalized_entity_direction) ||
            !unnormalized_entity_direction.try_normalized(entity_local_direction)) {
            return false;
        }

        Vec3 local_origin_double;
        if (!mesh_offset_affine.try_inverse_transform_point(entity_local_origin, local_origin_double)) {
            return false;
        }
        Vec3 unnormalized_local_direction;
        Vec3 local_direction_double;
        if (!mesh_offset_affine.try_inverse_transform_vector(entity_local_direction, unnormalized_local_direction) ||
            !unnormalized_local_direction.try_normalized(local_direction_double)) {
            return false;
        }

        const Vec3f local_origin = local_origin_double.to_float();
        Vec3f local_direction;
        if (!local_origin.is_finite() || !local_direction_double.to_float().try_normalized(local_direction)) {
            return false;
        }

        tc_mesh_ray result;
        result.origin = local_origin;
        result.direction = local_direction;
        result.t_min = 0.0f;
        result.t_max = 1000000.0f;
        ray = result;
        return true;
    }

    bool EditorInteractionSystem::_try_apply_surface_mesh_hit(SurfacePickResult& result,
                                                              const tc_mesh_hit& hit,
                                                              const Mat44f& mesh_offset,
                                                              const Affine3d& entity_affine) {
        Affine3d mesh_offset_affine;
        if (!try_affine3d_from_mat44f(mesh_offset, mesh_offset_affine)) {
            return false;
        }

        const Vec3 entity_local_hit = mesh_offset_affine.transform_point(hit.position.to_double());
        Vec3 entity_local_normal;
        if (!mesh_offset_affine.try_transform_normal(hit.normal.to_double(), entity_local_normal)) {
            return false;
        }

        const Vec3 world_hit = entity_affine.transform_point(entity_local_hit);
        Vec3 unnormalized_world_normal;
        Vec3 world_normal;
        if (!entity_affine.try_transform_normal(entity_local_normal, unnormalized_world_normal) ||
            !world_hit.is_finite() || !unnormalized_world_normal.try_normalized(world_normal)) {
            return false;
        }

        result.has_mesh_hit = true;
        result.mesh_point = world_hit;
        result.mesh_normal = world_normal;
        result.mesh_triangle_index = hit.triangle_index;
        result.mesh_indices =
            Vec3i{static_cast<int>(hit.indices[0]), static_cast<int>(hit.indices[1]), static_cast<int>(hit.indices[2])};
        return true;
    }

    // ============================================================================
    // Coordinate conversion
    // ============================================================================

    bool EditorInteractionSystem::_window_to_fbo_coords(Vec2f screen,
                                                        tc_viewport_handle vp,
                                                        tc_display_handle display,
                                                        Vec2i& fbo) {
        if (!tc_display_alive(display))
            return false;

        int fb_w, fb_h;
        tc_display_get_size(display, &fb_w, &fb_h);

        if (fb_w <= 0 || fb_h <= 0)
            return false;

        int vp_x, vp_y, vp_w, vp_h;
        tc_viewport_get_pixel_rect(vp, &vp_x, &vp_y, &vp_w, &vp_h);

        // Display input is already normalized by the host to physical display
        // pixels (top-left origin); render surfaces do not expose window metrics.
        float vx = screen.x - vp_x;
        float vy = screen.y - vp_y;

        if (vx < 0 || vy < 0 || vx >= vp_w || vy >= vp_h)
            return false;

        // Top-down pixel coordinates: same convention as mouse/window input,
        // and the one IRenderDevice::read_pixel_rgba8 expects. Each backend
        // flips internally if its readback API wants bottom-up (GL does).
        fbo = Vec2i{(int)vx, (int)vy};
        return true;
    }

    // ============================================================================
    // Ray casting
    // ============================================================================

    std::optional<Ray3> EditorInteractionSystem::_screen_to_ray(Vec2f screen, tc_viewport_handle vp) {
        if (!tc_viewport_handle_valid(vp)) {
            tc_log(TC_LOG_WARN, "[EditorInteractionSystem] cannot construct screen ray: viewport is invalid");
            return std::nullopt;
        }

        tc_render_target_handle rt = tc_viewport_get_render_target(vp);
        if (!tc_render_target_handle_valid(rt)) {
            tc_log(TC_LOG_WARN,
                   "[EditorInteractionSystem] cannot construct screen ray: viewport has no live render target");
            return std::nullopt;
        }
        tc_component* cam_comp = tc_render_target_get_camera(rt);
        if (!cam_comp) {
            tc_log(TC_LOG_WARN, "[EditorInteractionSystem] cannot construct screen ray: render target has no camera");
            return std::nullopt;
        }

        CxxComponent* cxx = CxxComponent::from_tc(cam_comp);
        if (!cxx) {
            const char* type_name = tc_component_type_name(cam_comp);
            tc_log(TC_LOG_ERROR,
                   "[EditorInteractionSystem] cannot construct screen ray: camera component '%s' is not native C++",
                   type_name ? type_name : "<unnamed>");
            return std::nullopt;
        }

        auto* camera = dynamic_cast<CameraComponent*>(cxx);
        if (!camera) {
            const char* type_name = tc_component_type_name(cam_comp);
            tc_log(TC_LOG_ERROR,
                   "[EditorInteractionSystem] cannot construct screen ray: native component '%s' is not a "
                   "CameraComponent",
                   type_name ? type_name : "<unnamed>");
            return std::nullopt;
        }

        int vp_x, vp_y, vp_w, vp_h;
        tc_viewport_get_pixel_rect(vp, &vp_x, &vp_y, &vp_w, &vp_h);

        const Rect2 viewport{
            static_cast<double>(vp_x), static_cast<double>(vp_y), static_cast<double>(vp_w), static_cast<double>(vp_h)};
        return camera->try_screen_point_to_ray(screen.to_double(), viewport);
    }

    // ============================================================================
    // Helpers
    // ============================================================================

    void EditorInteractionSystem::_request_update() {
        if (on_request_update) {
            on_request_update();
        }
    }

} // namespace termin
