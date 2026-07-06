// editor_interaction_system.cpp - Singleton editor interaction coordinator

#include "termin/editor/editor_interaction_system.hpp"
#include "termin/editor/component_editor_visual.hpp"
#include "termin/editor/editor_snap.hpp"
#include "core/tc_scene.h"
#include "termin/render/render_pipeline.hpp"
#include <termin/tc_scene.hpp>
#include "termin/camera/camera_component.hpp"
#include "termin/camera/orbit_camera_controller.hpp"
#include "termin/render/mesh_renderer.hpp"
#include <components/mesh_component.hpp>
#include <termin/entity/component.hpp>
#include "render/tc_viewport.h"
#include "render/tc_display.h"
#include "render/tc_render_target.h"
#include "render/tc_render_surface.h"
#include "tc_picking.h"
#include <tcbase/tc_log.h>

#include <cmath>
#include <algorithm>
#include <cstdlib>
#include <cstdint>

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

static void log_pick_lookup_miss_details(
    tc_entity_pool* pool,
    uint32_t pick_id,
    const char* context
) {
    PickIdLookupScan scan;
    scan.target_pick_id = pick_id;
    tc_entity_pool_foreach(pool, scan_pick_id_lookup, &scan);

    tc_log(
        TC_LOG_WARN,
        "[PickingDebug] %s: pick_id=%u lookup miss; linear_found=%d pool_count=%zu scanned=%zu "
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
        scan.found_id.generation
    );
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

} // namespace

// ============================================================================
// Constructor / Destructor
// ============================================================================

EditorInteractionSystem::EditorInteractionSystem()
    : _camera_frustum_debug_gizmo(this)
{
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
    gizmo_manager.add_gizmo(&_transform_gizmo);
    gizmo_manager.add_gizmo(&_camera_frustum_debug_gizmo);

    tc_log(TC_LOG_INFO, "[EditorInteractionSystem] Created");
}

EditorInteractionSystem::~EditorInteractionSystem() {
    _clear_component_visual_gizmos();
    gizmo_manager.remove_gizmo(&_camera_frustum_debug_gizmo);
    gizmo_manager.remove_gizmo(&_transform_gizmo);

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

// ============================================================================
// Gizmo
// ============================================================================

void EditorInteractionSystem::set_gizmo_target(Entity entity) {
    _transform_gizmo.set_target(entity);
    _transform_gizmo.visible = entity.valid();
    _rebuild_component_visual_gizmos(entity);
}

void EditorInteractionSystem::set_camera_frustums_visible(bool visible) {
    _camera_frustums_visible = visible;
    _camera_frustum_debug_gizmo.visible = visible;
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

    std::vector<std::unique_ptr<Gizmo>> new_gizmos;
    size_t count = entity.component_count();
    for (size_t i = 0; i < count; ++i) {
        tc_component* component = entity.component_at(i);
        ComponentEditorVisualRegistry::instance().collect_gizmos(
            entity,
            component,
            context,
            new_gizmos);
    }

    for (auto& gizmo : new_gizmos) {
        gizmo_manager.add_gizmo(gizmo.get());
        _component_visual_gizmos.push_back(std::move(gizmo));
    }
}

void EditorInteractionSystem::_clear_component_visual_gizmos() {
    for (auto& gizmo : _component_visual_gizmos) {
        gizmo_manager.remove_gizmo(gizmo.get());
    }
    _component_visual_gizmos.clear();
}

// ============================================================================
// Events from EditorViewportInputManager
// ============================================================================

void EditorInteractionSystem::on_mouse_button(
    int button, int action, int mods,
    float x, float y, tc_viewport_handle vp, tc_display* display)
{
    const std::string phase = action == TC_INPUT_PRESS ? "down" : "up";
    if (_dispatch_viewport_pointer(ViewportPointerEvent{
            phase,
            Vec2f{x, y},
            Vec2f{0.0f, 0.0f},
            button,
            action,
            mods})) {
        _request_update();
        return;
    }

    if (button == 0) { // LEFT
        if (action == TC_INPUT_PRESS) {
            _pending_press = {Vec2f{x, y}, vp, display, true};

            // Double-click detection
            double now = _current_time();
            if (now - _last_click_time < _double_click_threshold) {
                _handle_double_click(Vec2f{x, y}, vp, display);
            }
            _last_click_time = now;
        }
        if (action == TC_INPUT_RELEASE) {
            _pending_release = {Vec2f{x, y}, vp, display, true};
            if (gizmo_manager.is_dragging()) {
                gizmo_manager.on_mouse_up();
            }
        }
    }

    _request_update();
}

void EditorInteractionSystem::on_mouse_move(
    float x, float y, float dx, float dy,
    tc_viewport_handle vp, tc_display* display)
{
    if (_dispatch_viewport_pointer(ViewportPointerEvent{
            "move",
            Vec2f{x, y},
            Vec2f{dx, dy},
            -1,
            -1,
            0})) {
        _request_update();
        return;
    }

    _pending_hover = {Vec2f{x, y}, vp, display, true};

    // Forward to gizmo manager for drag updates
    if (gizmo_manager.is_dragging() && tc_viewport_handle_valid(vp)) {
        Vec3f origin, direction;
        if (_screen_to_ray(Vec2f{x, y}, vp, display, origin, direction)) {
            gizmo_manager.on_mouse_move(origin, direction);
        }
    }

    _request_update();
}

bool EditorInteractionSystem::handle_key_event(
    const KeyEvent& event,
    Vec2f cursor,
    tc_viewport_handle viewport,
    tc_display* display)
{
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

bool EditorInteractionSystem::_snap_transform_gizmo_target(
    Vec2f cursor,
    tc_viewport_handle viewport,
    tc_display* display)
{
    if (!_transform_gizmo.can_snap()) {
        tc_log(TC_LOG_WARN,
               "[EditorSnap] active transform target cannot snap has_target=%d source=%d target_valid=%d",
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
        tc_log(TC_LOG_WARN,
               "[EditorSnap] no cursor surface reference at cursor=(%.1f, %.1f)",
               cursor.x,
               cursor.y);
        if (request.source == EditorSnapSource::VisibleGeometry) {
            return false;
        }
    }

    EditorSnapResult result;
    if (!EditorSnapRegistry::instance().snap(request, result) || !result.success) {
        tc_log(TC_LOG_WARN, "[EditorSnap] snap failed for source=%d",
               static_cast<int>(request.source));
        return false;
    }

    if (!_transform_gizmo.snap_to(result.position)) {
        tc_log(TC_LOG_ERROR, "[EditorSnap] failed to apply snapped position");
        return false;
    }

    tc_log(TC_LOG_INFO, "[EditorSnap] snapped transform target to (%.3f, %.3f, %.3f)",
           result.position.x, result.position.y, result.position.z);
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

void EditorInteractionSystem::_process_pending_press() {
    Vec2f screen = _pending_press.screen;
    tc_viewport_handle vp = _pending_press.vp;
    tc_display* display = _pending_press.display;

    _press_x = screen.x;
    _press_y = screen.y;
    _has_press = true;
    _gizmo_handled_press = false;

    if (!tc_viewport_handle_valid(vp)) return;

    Vec3f origin, direction;
    if (_screen_to_ray(screen, vp, display, origin, direction)) {
        bool handled = gizmo_manager.on_mouse_down(origin, direction);
        if (handled) {
            _gizmo_handled_press = true;
        }
    }
}

void EditorInteractionSystem::_process_pending_release() {
    Vec2f screen = _pending_release.screen;
    tc_viewport_handle vp = _pending_release.vp;
    tc_display* display = _pending_release.display;

    // If gizmo handled the press, skip selection
    if (_gizmo_handled_press) {
        _gizmo_handled_press = false;
        _has_press = false;
        return;
    }

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
    tc_display* display = _pending_hover.display;

    if (!tc_viewport_handle_valid(vp)) return;

    // Update gizmo hover state (raycast-based)
    if (!gizmo_manager.is_dragging()) {
        Vec3f origin, direction;
        if (_screen_to_ray(screen, vp, display, origin, direction)) {
            gizmo_manager.on_mouse_move(origin, direction);
        }
    }

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

bool EditorInteractionSystem::_start_async_entity_pick(
    Vec2f screen, tc_viewport_handle vp, tc_display* display)
{
    if (_async_hover_pick.valid || !tc_viewport_handle_valid(vp)) return false;

    tc_render_target_handle rt = tc_viewport_get_render_target(vp);
    tc_pipeline_handle pipeline_h = tc_render_target_get_pipeline(rt);
    if (!tc_pipeline_pool_alive(pipeline_h)) return false;
    RenderPipeline pipeline(pipeline_h);

    tgfx::TextureHandle id_tex = pipeline.get_color_tex2("id");
    if (!id_tex) return false;
    auto* dev = pipeline.tex2_device();
    if (!dev) return false;

    Vec2i fbo;
    if (!_window_to_fbo_coords(screen, vp, display, fbo)) return false;

    uint64_t color_request = dev->request_pixel_rgba8(id_tex, fbo.x, fbo.y);
    if (color_request == 0) return false;

    _async_hover_pick.event = {screen, vp, display, true};
    _async_hover_pick.fbo = fbo;
    _async_hover_pick.color_request = color_request;
    _async_hover_pick.valid = true;
    return true;
}

bool EditorInteractionSystem::_start_async_surface_pick(
    Vec2f screen, tc_viewport_handle vp, tc_display* display)
{
    const bool debug_pick = picking_debug_enabled();
    if (_async_release_pick.valid || !tc_viewport_handle_valid(vp)) return false;

    tc_render_target_handle rt = tc_viewport_get_render_target(vp);
    tc_pipeline_handle pipeline_h = tc_render_target_get_pipeline(rt);
    if (!tc_pipeline_pool_alive(pipeline_h)) return false;
    RenderPipeline pipeline(pipeline_h);

    tgfx::TextureHandle id_tex = pipeline.get_color_tex2("id");
    tgfx::TextureHandle depth_tex = pipeline.get_depth_tex2("id");
    if (!id_tex || !depth_tex) return false;
    auto* dev = pipeline.tex2_device();
    if (!dev) return false;

    Vec2i fbo;
    if (!_window_to_fbo_coords(screen, vp, display, fbo)) {
        if (debug_pick) {
            int vp_x = 0;
            int vp_y = 0;
            int vp_w = 0;
            int vp_h = 0;
            tc_viewport_get_pixel_rect(vp, &vp_x, &vp_y, &vp_w, &vp_h);
            tc_log(TC_LOG_WARN,
                   "[PickingDebug] async release coords outside viewport: cursor=(%.1f,%.1f) viewport_rect=(%d,%d %dx%d)",
                   screen.x, screen.y, vp_x, vp_y, vp_w, vp_h);
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
                   "[PickingDebug] async release request failed: fbo=(%d,%d) color_req=%llu depth_req=%llu id_tex=%u size=%ux%u format=%d depth_tex=%u size=%ux%u format=%d",
                   fbo.x, fbo.y,
                   static_cast<unsigned long long>(color_request),
                   static_cast<unsigned long long>(depth_request),
                   id_tex.id, color_desc.width, color_desc.height,
                   static_cast<int>(color_desc.format),
                   depth_tex.id, depth_desc.width, depth_desc.height,
                   static_cast<int>(depth_desc.format));
        }
        return false;
    }
    if (debug_pick) {
        const tgfx::TextureDesc color_desc = dev->texture_desc(id_tex);
        tc_log(TC_LOG_INFO,
               "[PickingDebug] async release requested: cursor=(%.1f,%.1f) fbo=(%d,%d) color_req=%llu depth_req=%llu id_tex=%u size=%ux%u format=%d",
               screen.x, screen.y, fbo.x, fbo.y,
               static_cast<unsigned long long>(color_request),
               static_cast<unsigned long long>(depth_request),
               id_tex.id, color_desc.width, color_desc.height,
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
                   "[PickingDebug] async release pending: color_req=%llu ready=%d depth_req=%llu ready=%d",
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
               "[PickingDebug] async release read: fbo=(%d,%d) rgb=(%d,%d,%d) pick_id=%d depth=%.6f viewport_scene=(%u,%u) rt_scene=(%u,%u)",
               _async_release_pick.fbo.x, _async_release_pick.fbo.y,
               r, g, b, pick_id, _async_release_pick.depth,
               viewport_scene.index, viewport_scene.generation,
               rt_scene.index, rt_scene.generation);
    }
    SurfacePickResult pick = _surface_from_pick_color_depth(
        _async_release_pick.color,
        _async_release_pick.depth,
        _async_release_pick.fbo,
        event.vp);
    _async_release_pick.valid = false;

    if (debug_pick) {
        tc_log(TC_LOG_INFO,
               "[PickingDebug] async release resolved: entity_valid=%d entity='%s' entity_pick_id=%u selectable=%d has_world=%d has_mesh=%d",
               pick.entity.valid() ? 1 : 0,
               pick.entity.valid() ? pick.entity.name() : "<none>",
               pick.entity.valid() ? pick.entity.pick_id() : 0,
               (pick.entity.valid() && pick.entity.selectable()) ? 1 : 0,
               pick.has_world_point ? 1 : 0,
               pick.has_mesh_hit ? 1 : 0);
    }

    bool click_handled = _dispatch_entity_click(event.screen, pick);
    if (debug_pick) {
        tc_log(TC_LOG_INFO,
               "[PickingDebug] async release callback: handled=%d",
               click_handled ? 1 : 0);
    }
    if (click_handled) {
        _request_update();
        return;
    }

    uint32_t previous_selected_pick_id = selection.selected_pick_id;
    selection.select(pick.entity);
    if (debug_pick) {
        tc_log(TC_LOG_INFO,
               "[PickingDebug] async release selection: before_pick_id=%u after_pick_id=%u",
               previous_selected_pick_id,
               selection.selected_pick_id);
    }
    _request_update();
}

// ============================================================================
// Double-click
// ============================================================================

void EditorInteractionSystem::_handle_double_click(
    Vec2f screen, tc_viewport_handle vp, tc_display* display)
{
    Entity ent = pick_entity_at(screen, vp, display);
    if (!ent.valid()) {
        return;
    }

    double pos[3] = {0.0, 0.0, 0.0};
    ent.get_global_position(pos);
    Vec3 focus{pos[0], pos[1], pos[2]};

    tc_render_target_handle rt = tc_viewport_get_render_target(vp);
    if (!tc_render_target_handle_valid(rt)) {
        tc_log(TC_LOG_WARN, "[EditorInteractionSystem] cannot focus double-click target: viewport has no render target");
        return;
    }

    tc_component* cam_comp = tc_render_target_get_camera(rt);
    if (!cam_comp) {
        tc_log(TC_LOG_WARN, "[EditorInteractionSystem] cannot focus double-click target: render target has no camera");
        return;
    }

    CxxComponent* cxx = CxxComponent::from_tc(cam_comp);
    auto* camera = dynamic_cast<CameraComponent*>(cxx);
    if (!camera || !camera->entity().valid()) {
        tc_log(TC_LOG_WARN, "[EditorInteractionSystem] cannot focus double-click target: active camera component is invalid");
        return;
    }

    OrbitCameraController* orbit = camera->entity().get_component<OrbitCameraController>();
    if (!orbit) {
        tc_log(TC_LOG_WARN,
               "[EditorInteractionSystem] cannot focus double-click target: camera entity '%s' has no OrbitCameraController",
               camera->entity().name());
        return;
    }

    orbit->center_on(focus);
    _request_update();
}

// ============================================================================
// Picking
// ============================================================================

Entity EditorInteractionSystem::pick_entity_at(
    Vec2f screen, tc_viewport_handle viewport, tc_display* display)
{
    if (!tc_viewport_handle_valid(viewport)) {
        tc_log(TC_LOG_INFO, "[DBG pick] viewport invalid"); return Entity();
    }

    tc_render_target_handle rt = tc_viewport_get_render_target(viewport);
    tc_pipeline_handle pipeline_h = tc_render_target_get_pipeline(rt);
    if (!tc_pipeline_pool_alive(pipeline_h)) {
        tc_log(TC_LOG_INFO, "[DBG pick] pipeline not alive"); return Entity();
    }
    RenderPipeline pipeline(pipeline_h);

    tgfx::TextureHandle id_tex = pipeline.get_color_tex2("id");
    if (!id_tex) return Entity();

    auto* dev = pipeline.tex2_device();
    if (!dev) return Entity();

    Vec2i fbo;
    if (!_window_to_fbo_coords(screen, viewport, display, fbo)) return Entity();

    float color[4] = {0, 0, 0, 0};
    if (!dev->read_pixel_rgba8(id_tex, fbo.x, fbo.y, color)) return Entity();

    return _entity_from_pick_color(color, viewport);
}

Entity EditorInteractionSystem::_entity_from_pick_color(
    const float color[4], tc_viewport_handle viewport)
{
    int r = (int)std::round(color[0] * 255.0f);
    int g = (int)std::round(color[1] * 255.0f);
    int b = (int)std::round(color[2] * 255.0f);
    int pick_id = tc_picking_rgb_to_id(r, g, b);

    if (pick_id == 0) return Entity();

    tc_scene_handle scene = tc_viewport_get_scene(viewport);
    if (!tc_scene_handle_valid(scene)) return Entity();

    tc_entity_pool* pool = tc_scene_entity_pool(scene);
    if (!pool) return Entity();

    tc_entity_id eid = tc_entity_pool_find_by_pick_id(pool, pick_id);
    if (!tc_entity_id_valid(eid)) return Entity();

    return Entity(pool, eid);
}

SurfacePickResult EditorInteractionSystem::pick_surface_at(
    Vec2f screen, tc_viewport_handle viewport, tc_display* display)
{
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
                   viewport.index, viewport.generation);
        }
        return result;
    }

    auto* dev = pipeline.tex2_device();
    if (!dev) {
        if (debug_pick) {
            tc_log(TC_LOG_WARN,
                   "[PickingDebug] surface pick has no tgfx2 device for viewport=(%u,%u)",
                   viewport.index, viewport.generation);
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
                   "[PickingDebug] surface pick coords outside viewport: cursor=(%.1f,%.1f) viewport_rect=(%d,%d %dx%d)",
                   screen.x, screen.y, vp_x, vp_y, vp_w, vp_h);
        }
        return result;
    }

    float color[4] = {0, 0, 0, 0};
    if (!dev->read_pixel_rgba8(id_tex, fbo.x, fbo.y, color)) {
        if (debug_pick) {
            const tgfx::TextureDesc desc = dev->texture_desc(id_tex);
            tc_log(TC_LOG_WARN,
                   "[PickingDebug] surface pick color read failed: fbo=(%d,%d) id_tex=%u size=%ux%u format=%d",
                   fbo.x, fbo.y, id_tex.id, desc.width, desc.height,
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
               "[PickingDebug] surface pick read: cursor=(%.1f,%.1f) fbo=(%d,%d) id_tex=%u size=%ux%u format=%d rgb=(%d,%d,%d) pick_id=%d viewport_scene=(%u,%u) rt_scene=(%u,%u)",
               screen.x, screen.y, fbo.x, fbo.y, id_tex.id, desc.width, desc.height,
               static_cast<int>(desc.format), r, g, b, pick_id,
               viewport_scene.index, viewport_scene.generation,
               rt_scene.index, rt_scene.generation);
    }
    if (pick_id == 0) return result;

    tc_scene_handle scene = tc_viewport_get_scene(viewport);
    if (!tc_scene_handle_valid(scene)) {
        if (debug_pick) {
            tc_log(TC_LOG_WARN,
                   "[PickingDebug] surface pick decoded pick_id=%d but viewport scene is invalid",
                   pick_id);
        }
        return result;
    }

    tc_entity_pool* pool = tc_scene_entity_pool(scene);
    if (!pool) {
        if (debug_pick) {
            tc_log(TC_LOG_WARN,
                   "[PickingDebug] surface pick decoded pick_id=%d but scene has no entity pool",
                   pick_id);
        }
        return result;
    }

    tc_entity_id eid = tc_entity_pool_find_by_pick_id(pool, pick_id);
    if (!tc_entity_id_valid(eid)) {
        if (debug_pick) {
            tc_log(TC_LOG_WARN,
                   "[PickingDebug] surface pick decoded pick_id=%d but entity lookup failed in viewport scene",
                   pick_id);
            log_pick_lookup_miss_details(
                pool,
                static_cast<uint32_t>(pick_id),
                "surface pick viewport scene");
        }
        return result;
    }

    result.entity = Entity(pool, eid);

    tgfx::TextureHandle depth_tex = pipeline.get_depth_tex2("id");
    if (!depth_tex) return result;

    float depth = 1.0f;
    if (!dev->read_pixel_depth_float(depth_tex, fbo.x, fbo.y, &depth)) return result;
    return _surface_from_pick_color_depth(color, depth, fbo, viewport);
}

SurfacePickResult EditorInteractionSystem::_surface_from_pick_color_depth(
    const float color[4], float depth, Vec2i fbo, tc_viewport_handle viewport)
{
    SurfacePickResult result;

    int r = (int)std::round(color[0] * 255.0f);
    int g = (int)std::round(color[1] * 255.0f);
    int b = (int)std::round(color[2] * 255.0f);
    int pick_id = tc_picking_rgb_to_id(r, g, b);
    const bool debug_pick = picking_debug_enabled();
    if (pick_id == 0) return result;

    tc_scene_handle scene = tc_viewport_get_scene(viewport);
    if (!tc_scene_handle_valid(scene)) {
        if (debug_pick) {
            tc_log(TC_LOG_WARN,
                   "[PickingDebug] surface resolve failed: pick_id=%d viewport scene is invalid",
                   pick_id);
        }
        return result;
    }

    tc_entity_pool* pool = tc_scene_entity_pool(scene);
    if (!pool) {
        if (debug_pick) {
            tc_log(TC_LOG_WARN,
                   "[PickingDebug] surface resolve failed: pick_id=%d scene has no entity pool",
                   pick_id);
        }
        return result;
    }

    tc_entity_id eid = tc_entity_pool_find_by_pick_id(pool, pick_id);
    if (!tc_entity_id_valid(eid)) {
        if (debug_pick) {
            tc_log(TC_LOG_WARN,
                   "[PickingDebug] surface resolve failed: pick_id=%d not found in scene entity pool",
                   pick_id);
            log_pick_lookup_miss_details(
                pool,
                static_cast<uint32_t>(pick_id),
                "surface resolve viewport scene");
        }
        return result;
    }

    result.entity = Entity(pool, eid);
    result.depth = depth;
    if (depth >= 1.0f) return result;

    tc_render_target_handle rt = tc_viewport_get_render_target(viewport);
    tc_pipeline_handle pipeline_h = tc_render_target_get_pipeline(rt);
    if (!tc_pipeline_pool_alive(pipeline_h)) return result;
    RenderPipeline pipeline(pipeline_h);
    tgfx::TextureHandle id_tex = pipeline.get_color_tex2("id");
    if (!id_tex) return result;
    auto* dev = pipeline.tex2_device();
    if (!dev) return result;

    tc_component* cam_comp = tc_render_target_get_camera(rt);
    if (!cam_comp) return result;

    CxxComponent* cxx = CxxComponent::from_tc(cam_comp);
    if (!cxx) return result;

    auto* camera = static_cast<CameraComponent*>(cxx);

    auto desc = dev->texture_desc(id_tex);
    const double width = std::max(1.0, static_cast<double>(desc.width));
    const double height = std::max(1.0, static_cast<double>(desc.height));

    const double nx = ((static_cast<double>(fbo.x) + 0.5) / width) * 2.0 - 1.0;
    const double ny = ((static_cast<double>(fbo.y) + 0.5) / height) * 2.0 - 1.0;

    const double aspect = width / height;
    Mat44 view = camera->get_view_matrix();
    Mat44 projection = camera->compute_projection_matrix(aspect);
    Mat44 pv = projection * view;
    Mat44 inv_pv = pv.inverse();
    Vec3 world = inv_pv.transform_point(Vec3{nx, ny, static_cast<double>(depth)});
    Vec3 view_point = view.transform_point(world);

    const double clip_x =
        pv(0, 0) * world.x + pv(1, 0) * world.y + pv(2, 0) * world.z + pv(3, 0);
    const double clip_y =
        pv(0, 1) * world.x + pv(1, 1) * world.y + pv(2, 1) * world.z + pv(3, 1);
    const double clip_z =
        pv(0, 2) * world.x + pv(1, 2) * world.y + pv(2, 2) * world.z + pv(3, 2);
    const double clip_w =
        pv(0, 3) * world.x + pv(1, 3) * world.y + pv(2, 3) * world.z + pv(3, 3);
    if (std::abs(clip_w) > 1e-10) {
        const double reproj_x = ((clip_x / clip_w) + 1.0) * 0.5 * width - 0.5;
        const double reproj_y = ((clip_y / clip_w) + 1.0) * 0.5 * height - 0.5;
        const double reproj_depth = clip_z / clip_w;
        const Vec2 reproj_error{
            reproj_x - static_cast<double>(fbo.x),
            reproj_y - static_cast<double>(fbo.y)
        };
        result.reproject_screen_error = reproj_error.norm();
        result.reproject_depth_error = reproj_depth - static_cast<double>(depth);
    }

    result.has_world_point = true;
    result.world_point = world;
    result.view_depth = view_point.y;

    MeshComponent* mesh_component = result.entity.get_component<MeshComponent>();
    if (mesh_component) {
        tc_mesh* mesh = mesh_component->mesh.get();
        if (!mesh) return result;

        GeneralPose3 pose = result.entity.transform().global_pose();
        Mat44f mesh_offset = mesh_component->get_mesh_offset_matrix();
        Mat44f inverse_mesh_offset = mesh_offset.inverse();
        Vec3 camera_position = camera->get_position();
        Vec3 world_direction = (world - camera_position).normalized();
        Vec3 entity_local_origin = pose.inverse_transform_point(camera_position);
        Vec3 entity_local_direction = pose.inverse_transform_vector(world_direction).normalized();
        Vec3 local_origin = inverse_mesh_offset.transform_point(entity_local_origin);
        Vec3 local_direction = inverse_mesh_offset.transform_direction(entity_local_direction).normalized();

        tc_mesh_ray ray;
        ray.origin[0] = static_cast<float>(local_origin.x);
        ray.origin[1] = static_cast<float>(local_origin.y);
        ray.origin[2] = static_cast<float>(local_origin.z);
        ray.direction[0] = static_cast<float>(local_direction.x);
        ray.direction[1] = static_cast<float>(local_direction.y);
        ray.direction[2] = static_cast<float>(local_direction.z);
        ray.t_min = 0.0f;
        ray.t_max = 1000000.0f;

        tc_mesh_hit hit;
        if (tc_mesh_raycast(mesh, &ray, &hit)) {
            Vec3 local_hit(
                static_cast<double>(hit.position[0]),
                static_cast<double>(hit.position[1]),
                static_cast<double>(hit.position[2])
            );
            Vec3 local_normal(
                static_cast<double>(hit.normal[0]),
                static_cast<double>(hit.normal[1]),
                static_cast<double>(hit.normal[2])
            );
            Vec3 entity_local_hit = mesh_offset.transform_point(local_hit);
            Vec3 entity_local_normal = mesh_offset.transform_direction(local_normal).normalized();
            Vec3 world_hit = pose.transform_point(entity_local_hit);
            Vec3 world_normal = pose.to_pose3().transform_vector(entity_local_normal).normalized();

            result.has_mesh_hit = true;
            result.mesh_point = world_hit;
            result.mesh_normal = world_normal;
            result.mesh_triangle_index = hit.triangle_index;
            result.mesh_indices = Vec3i{
                static_cast<int>(hit.indices[0]),
                static_cast<int>(hit.indices[1]),
                static_cast<int>(hit.indices[2])
            };
        }
    }
    return result;
}

// ============================================================================
// Coordinate conversion
// ============================================================================

bool EditorInteractionSystem::_window_to_fbo_coords(
    Vec2f screen, tc_viewport_handle vp,
    tc_display* display, Vec2i& fbo)
{
    if (!display) return false;

    int win_w, win_h, fb_w, fb_h;
    tc_display_get_window_size(display, &win_w, &win_h);
    tc_display_get_size(display, &fb_w, &fb_h);

    if (win_w <= 0 || win_h <= 0 || fb_w <= 0 || fb_h <= 0) return false;

    int vp_x, vp_y, vp_w, vp_h;
    tc_viewport_get_pixel_rect(vp, &vp_x, &vp_y, &vp_w, &vp_h);

    float sx = (float)fb_w / (float)win_w;
    float sy = (float)fb_h / (float)win_h;
    float x_phys = screen.x * sx;
    float y_phys = screen.y * sy;

    float vx = x_phys - vp_x;
    float vy = y_phys - vp_y;

    if (vx < 0 || vy < 0 || vx >= vp_w || vy >= vp_h) return false;

    // Top-down pixel coordinates: same convention as mouse/window input,
    // and the one IRenderDevice::read_pixel_rgba8 expects. Each backend
    // flips internally if its readback API wants bottom-up (GL does).
    fbo = Vec2i{(int)vx, (int)vy};
    return true;
}

// ============================================================================
// Ray casting
// ============================================================================

bool EditorInteractionSystem::_screen_to_ray(
    Vec2f screen, tc_viewport_handle vp, tc_display* display,
    Vec3f& origin, Vec3f& direction)
{
    (void)display;

    tc_render_target_handle rt = tc_viewport_get_render_target(vp);
    tc_component* cam_comp = tc_render_target_get_camera(rt);
    if (!cam_comp) return false;

    CxxComponent* cxx = CxxComponent::from_tc(cam_comp);
    if (!cxx) return false;

    auto* camera = static_cast<CameraComponent*>(cxx);

    int vp_x, vp_y, vp_w, vp_h;
    tc_viewport_get_pixel_rect(vp, &vp_x, &vp_y, &vp_w, &vp_h);

    auto [orig, dir] = camera->screen_point_to_ray(screen.x, screen.y, vp_x, vp_y, vp_w, vp_h);
    origin = Vec3f{(float)orig.x, (float)orig.y, (float)orig.z};
    direction = Vec3f{(float)dir.x, (float)dir.y, (float)dir.z};
    return true;
}

// ============================================================================
// Helpers
// ============================================================================

void EditorInteractionSystem::_request_update() {
    if (on_request_update) {
        on_request_update();
    }
}

double EditorInteractionSystem::_current_time() {
    auto now = std::chrono::high_resolution_clock::now();
    auto duration = now.time_since_epoch();
    return std::chrono::duration<double>(duration).count();
}

} // namespace termin
