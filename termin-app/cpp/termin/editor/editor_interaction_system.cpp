// editor_interaction_system.cpp - Singleton editor interaction coordinator

#include "termin/editor/editor_interaction_system.hpp"
#include "termin/editor/component_editor_visual.hpp"
#include "termin/editor/editor_snap.hpp"
#include "core/tc_scene.h"
#include "termin/render/render_pipeline.hpp"
#include <termin/tc_scene.hpp>
#include "termin/camera/camera_component.hpp"
#include "termin/render/mesh_renderer.hpp"
#include <components/mesh_component.hpp>
#include <termin/entity/component.hpp>
#include "editor/tc_editor_interaction.h"
#include "render/tc_viewport.h"
#include "render/tc_display.h"
#include "render/tc_render_target.h"
#include "render/tc_render_surface.h"
#include "tc_picking.h"
#include <tcbase/tc_log.h>

#include <cmath>
#include <algorithm>
#include <cstdint>

namespace termin {

namespace {

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

EditorInteractionSystem::EditorInteractionSystem() {
    tc_editor_interaction_set_instance(
        reinterpret_cast<tc_editor_interaction_system*>(this));

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

    tc_log(TC_LOG_INFO, "[EditorInteractionSystem] Created");
}

EditorInteractionSystem::~EditorInteractionSystem() {
    _clear_component_visual_gizmos();
    gizmo_manager.remove_gizmo(&_transform_gizmo);

    if (tc_editor_interaction_instance() ==
        reinterpret_cast<tc_editor_interaction_system*>(this)) {
        tc_editor_interaction_set_instance(nullptr);
    }
    tc_log(TC_LOG_INFO, "[EditorInteractionSystem] Destroyed");
}

// ============================================================================
// Singleton
// ============================================================================

EditorInteractionSystem* EditorInteractionSystem::instance() {
    return reinterpret_cast<EditorInteractionSystem*>(
        tc_editor_interaction_instance());
}

void EditorInteractionSystem::set_instance(EditorInteractionSystem* inst) {
    tc_editor_interaction_set_instance(
        reinterpret_cast<tc_editor_interaction_system*>(inst));
}

// ============================================================================
// Gizmo
// ============================================================================

void EditorInteractionSystem::set_gizmo_target(Entity entity) {
    _transform_gizmo.set_target(entity);
    _transform_gizmo.visible = entity.valid();
    _rebuild_component_visual_gizmos(entity);
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
    (void)mods;

    if (button == 0) { // LEFT
        if (action == TC_INPUT_PRESS) {
            _pending_press = {x, y, vp, display, true};

            // Double-click detection
            double now = _current_time();
            if (now - _last_click_time < _double_click_threshold) {
                _handle_double_click(x, y, vp, display);
            }
            _last_click_time = now;
        }
        if (action == TC_INPUT_RELEASE) {
            _pending_release = {x, y, vp, display, true};
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
    (void)dx;
    (void)dy;

    _pending_hover = {x, y, vp, display, true};

    // Forward to gizmo manager for drag updates
    if (gizmo_manager.is_dragging() && tc_viewport_handle_valid(vp)) {
        Vec3f origin, direction;
        if (_screen_to_ray(x, y, vp, display, origin, direction)) {
            gizmo_manager.on_mouse_move(origin, direction);
        }
    }

    _request_update();
}

bool EditorInteractionSystem::handle_key_event(
    const KeyEvent& event,
    float cursor_x,
    float cursor_y,
    tc_viewport_handle viewport,
    tc_display* display)
{
    if (event.action != TC_ACTION_PRESS) {
        return false;
    }
    if (event.key == TC_KEY_T || event.key == 't' || event.key == 292) {
        bool handled = _snap_transform_gizmo_target(cursor_x, cursor_y, viewport, display);
        if (!handled) {
            tc_log(TC_LOG_WARN, "[EditorSnap] snap hotkey was not handled");
        }
        return handled;
    }
    return false;
}

bool EditorInteractionSystem::_snap_transform_gizmo_target(
    float cursor_x,
    float cursor_y,
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

    SurfacePickResult surface = pick_surface_at(cursor_x, cursor_y, viewport, display);
    if (surface.has_world_point) {
        request.reference_position = Vec3{
            surface.world_point[0],
            surface.world_point[1],
            surface.world_point[2],
        };
    } else {
        tc_log(TC_LOG_WARN,
               "[EditorSnap] no cursor surface reference at cursor=(%.1f, %.1f)",
               cursor_x,
               cursor_y);
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
    float x = _pending_press.x;
    float y = _pending_press.y;
    tc_viewport_handle vp = _pending_press.vp;
    tc_display* display = _pending_press.display;

    _press_x = x;
    _press_y = y;
    _has_press = true;
    _gizmo_handled_press = false;

    if (!tc_viewport_handle_valid(vp)) return;

    Vec3f origin, direction;
    if (_screen_to_ray(x, y, vp, display, origin, direction)) {
        bool handled = gizmo_manager.on_mouse_down(origin, direction);
        if (handled) {
            _gizmo_handled_press = true;
        }
    }
}

void EditorInteractionSystem::_process_pending_release() {
    float x = _pending_release.x;
    float y = _pending_release.y;
    tc_viewport_handle vp = _pending_release.vp;
    tc_display* display = _pending_release.display;

    // If gizmo handled the press, skip selection
    if (_gizmo_handled_press) {
        _gizmo_handled_press = false;
        _has_press = false;
        return;
    }

    // Click vs drag detection
    if (_has_press) {
        float dx = x - _press_x;
        float dy = y - _press_y;
        float dist_sq = dx * dx + dy * dy;
        float threshold_sq = _click_threshold * _click_threshold;
        if (dist_sq > threshold_sq) {
            // Drag detected, skip selection
            _has_press = false;
            return;
        }
        _has_press = false;
    }

    if (_async_release_pick.valid) {
        _request_update();
        return;
    }
    if (_start_async_surface_pick(x, y, vp, display)) {
        _request_update();
        return;
    }

    SurfacePickResult pick = pick_surface_at(x, y, vp, display);
    if (on_entity_click && on_entity_click(
            pick.entity, x, y, pick.has_world_point,
            pick.world_point[0], pick.world_point[1], pick.world_point[2],
            pick.depth, pick.view_depth,
            pick.reproject_screen_error, pick.reproject_depth_error,
            pick.has_mesh_hit,
            pick.mesh_point[0], pick.mesh_point[1], pick.mesh_point[2],
            pick.mesh_normal[0], pick.mesh_normal[1], pick.mesh_normal[2],
            pick.mesh_triangle_index,
            pick.mesh_indices[0], pick.mesh_indices[1], pick.mesh_indices[2])) {
        _request_update();
        return;
    }

    // Pick entity and select
    selection.select(pick.entity);
    _request_update();
}

void EditorInteractionSystem::_process_pending_hover() {
    float x = _pending_hover.x;
    float y = _pending_hover.y;
    tc_viewport_handle vp = _pending_hover.vp;
    tc_display* display = _pending_hover.display;

    if (!tc_viewport_handle_valid(vp)) return;

    // Update gizmo hover state (raycast-based)
    if (!gizmo_manager.is_dragging()) {
        Vec3f origin, direction;
        if (_screen_to_ray(x, y, vp, display, origin, direction)) {
            gizmo_manager.on_mouse_move(origin, direction);
        }
    }

    // Pick entity for hover highlight
    if (_async_hover_pick.valid) {
        _request_update();
        return;
    }
    if (_start_async_entity_pick(x, y, vp, display)) {
        _request_update();
        return;
    }

    Entity ent = pick_entity_at(x, y, vp, display);
    selection.hover(ent);
}

bool EditorInteractionSystem::_start_async_entity_pick(
    float x, float y, tc_viewport_handle vp, tc_display* display)
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

    int fx = 0;
    int fy = 0;
    if (!_window_to_fbo_coords(x, y, vp, display, fx, fy)) return false;

    uint64_t color_request = dev->request_pixel_rgba8(id_tex, fx, fy);
    if (color_request == 0) return false;

    _async_hover_pick.event = {x, y, vp, display, true};
    _async_hover_pick.fx = fx;
    _async_hover_pick.fy = fy;
    _async_hover_pick.color_request = color_request;
    _async_hover_pick.valid = true;
    return true;
}

bool EditorInteractionSystem::_start_async_surface_pick(
    float x, float y, tc_viewport_handle vp, tc_display* display)
{
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

    int fx = 0;
    int fy = 0;
    if (!_window_to_fbo_coords(x, y, vp, display, fx, fy)) return false;

    uint64_t color_request = dev->request_pixel_rgba8(id_tex, fx, fy);
    uint64_t depth_request = dev->request_pixel_depth_float(depth_tex, fx, fy);
    if (color_request == 0 || depth_request == 0) return false;

    _async_release_pick.event = {x, y, vp, display, true};
    _async_release_pick.fx = fx;
    _async_release_pick.fy = fy;
    _async_release_pick.color_request = color_request;
    _async_release_pick.depth_request = depth_request;
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
    float color[4] = {0, 0, 0, 0};
    float depth = 1.0f;
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
    if (!dev->poll_pixel_rgba8(_async_release_pick.color_request, color) ||
        !dev->poll_pixel_depth_float(_async_release_pick.depth_request, &depth)) {
        _request_update();
        return;
    }

    const PendingEvent event = _async_release_pick.event;
    SurfacePickResult pick = _surface_from_pick_color_depth(
        color, depth, _async_release_pick.fx, _async_release_pick.fy, event.vp);
    _async_release_pick.valid = false;

    if (on_entity_click && on_entity_click(
            pick.entity, event.x, event.y, pick.has_world_point,
            pick.world_point[0], pick.world_point[1], pick.world_point[2],
            pick.depth, pick.view_depth,
            pick.reproject_screen_error, pick.reproject_depth_error,
            pick.has_mesh_hit,
            pick.mesh_point[0], pick.mesh_point[1], pick.mesh_point[2],
            pick.mesh_normal[0], pick.mesh_normal[1], pick.mesh_normal[2],
            pick.mesh_triangle_index,
            pick.mesh_indices[0], pick.mesh_indices[1], pick.mesh_indices[2])) {
        _request_update();
        return;
    }

    selection.select(pick.entity);
    _request_update();
}

// ============================================================================
// Double-click
// ============================================================================

void EditorInteractionSystem::_handle_double_click(
    float x, float y, tc_viewport_handle vp, tc_display* display)
{
    Entity ent = pick_entity_at(x, y, vp, display);
    if (!ent.valid()) return;

    // Get entity position
    double pos[3];
    ent.get_global_position(pos);

    // Find camera controller and center on entity
    tc_render_target_handle rt = tc_viewport_get_render_target(vp);
    tc_component* cam_comp = tc_render_target_get_camera(rt);
    if (!cam_comp) return;

    CxxComponent* cxx = CxxComponent::from_tc(cam_comp);
    if (!cxx) return;

    // TODO: Call center_on via CameraController interface
    // For now, double-click just selects
    (void)pos;
    (void)display;
}

// ============================================================================
// Picking
// ============================================================================

Entity EditorInteractionSystem::pick_entity_at(
    float x, float y, tc_viewport_handle viewport, tc_display* display)
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

    int fx, fy;
    if (!_window_to_fbo_coords(x, y, viewport, display, fx, fy)) return Entity();

    float color[4] = {0, 0, 0, 0};
    if (!dev->read_pixel_rgba8(id_tex, fx, fy, color)) return Entity();

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
    float x, float y, tc_viewport_handle viewport, tc_display* display)
{
    SurfacePickResult result;

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
    if (!id_tex) return result;

    auto* dev = pipeline.tex2_device();
    if (!dev) return result;

    int fx, fy;
    if (!_window_to_fbo_coords(x, y, viewport, display, fx, fy)) return result;

    float color[4] = {0, 0, 0, 0};
    if (!dev->read_pixel_rgba8(id_tex, fx, fy, color)) return result;

    int r = (int)std::round(color[0] * 255.0f);
    int g = (int)std::round(color[1] * 255.0f);
    int b = (int)std::round(color[2] * 255.0f);
    int pick_id = tc_picking_rgb_to_id(r, g, b);
    if (pick_id == 0) return result;

    tc_scene_handle scene = tc_viewport_get_scene(viewport);
    if (!tc_scene_handle_valid(scene)) return result;

    tc_entity_pool* pool = tc_scene_entity_pool(scene);
    if (!pool) return result;

    tc_entity_id eid = tc_entity_pool_find_by_pick_id(pool, pick_id);
    if (!tc_entity_id_valid(eid)) return result;

    result.entity = Entity(pool, eid);

    tgfx::TextureHandle depth_tex = pipeline.get_depth_tex2("id");
    if (!depth_tex) return result;

    float depth = 1.0f;
    if (!dev->read_pixel_depth_float(depth_tex, fx, fy, &depth)) return result;
    return _surface_from_pick_color_depth(color, depth, fx, fy, viewport);
}

SurfacePickResult EditorInteractionSystem::_surface_from_pick_color_depth(
    const float color[4], float depth, int fx, int fy, tc_viewport_handle viewport)
{
    SurfacePickResult result;

    int r = (int)std::round(color[0] * 255.0f);
    int g = (int)std::round(color[1] * 255.0f);
    int b = (int)std::round(color[2] * 255.0f);
    int pick_id = tc_picking_rgb_to_id(r, g, b);
    if (pick_id == 0) return result;

    tc_scene_handle scene = tc_viewport_get_scene(viewport);
    if (!tc_scene_handle_valid(scene)) return result;

    tc_entity_pool* pool = tc_scene_entity_pool(scene);
    if (!pool) return result;

    tc_entity_id eid = tc_entity_pool_find_by_pick_id(pool, pick_id);
    if (!tc_entity_id_valid(eid)) return result;

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

    const double nx = ((static_cast<double>(fx) + 0.5) / width) * 2.0 - 1.0;
    const double ny = ((static_cast<double>(fy) + 0.5) / height) * 2.0 - 1.0;

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
        const double dx = reproj_x - static_cast<double>(fx);
        const double dy = reproj_y - static_cast<double>(fy);
        result.reproject_screen_error = std::sqrt(dx * dx + dy * dy);
        result.reproject_depth_error = reproj_depth - static_cast<double>(depth);
    }

    result.has_world_point = true;
    result.world_point = {world.x, world.y, world.z};
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
            result.mesh_point = {world_hit.x, world_hit.y, world_hit.z};
            result.mesh_normal = {world_normal.x, world_normal.y, world_normal.z};
            result.mesh_triangle_index = hit.triangle_index;
            result.mesh_indices = std::array<uint32_t, 3>{
                hit.indices[0],
                hit.indices[1],
                hit.indices[2]
            };
        }
    }
    return result;
}

// ============================================================================
// Coordinate conversion
// ============================================================================

bool EditorInteractionSystem::_window_to_fbo_coords(
    float x, float y, tc_viewport_handle vp,
    tc_display* display, int& fx, int& fy)
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
    float x_phys = x * sx;
    float y_phys = y * sy;

    float vx = x_phys - vp_x;
    float vy = y_phys - vp_y;

    if (vx < 0 || vy < 0 || vx >= vp_w || vy >= vp_h) return false;

    // Top-down pixel coordinates: same convention as mouse/window input,
    // and the one IRenderDevice::read_pixel_rgba8 expects. Each backend
    // flips internally if its readback API wants bottom-up (GL does).
    fx = (int)vx;
    fy = (int)vy;
    return true;
}

// ============================================================================
// Ray casting
// ============================================================================

bool EditorInteractionSystem::_screen_to_ray(
    float x, float y, tc_viewport_handle vp, tc_display* display,
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

    auto [orig, dir] = camera->screen_point_to_ray(x, y, vp_x, vp_y, vp_w, vp_h);
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
