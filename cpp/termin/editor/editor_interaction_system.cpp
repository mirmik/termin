// editor_interaction_system.cpp - Singleton editor interaction coordinator

#include "termin/editor/editor_interaction_system.hpp"
#include "core/tc_scene.h"
#include "termin/render/render_pipeline.hpp"
#include "termin/camera/camera_component.hpp"
#include "termin/entity/component.hpp"
#include "editor/tc_editor_interaction.h"
#include "render/tc_viewport.h"
#include "render/tc_display.h"
#include "render/tc_render_surface.h"
#include "tc_picking.h"
#include "tc_log.h"

#include <cmath>

namespace termin {

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
    gizmo_manager.add_gizmo(&_transform_gizmo);

    tc_log(TC_LOG_INFO, "[EditorInteractionSystem] Created");
}

EditorInteractionSystem::~EditorInteractionSystem() {
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
}

// ============================================================================
// Events from EditorDisplayInputManager
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

// ============================================================================
// Post-render processing
// ============================================================================

void EditorInteractionSystem::after_render() {
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

    // Pick entity and select
    Entity ent = pick_entity_at(x, y, vp, display);
    selection.select(ent);
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
    Entity ent = pick_entity_at(x, y, vp, display);
    selection.hover(ent);
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
    tc_component* cam_comp = tc_viewport_get_camera(vp);
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
    if (!_graphics) return Entity();
    if (!tc_viewport_handle_valid(viewport)) return Entity();

    FramebufferHandle* fbo = _get_viewport_fbo(viewport, "id");
    if (!fbo) return Entity();

    int fx, fy;
    if (!_window_to_fbo_coords(x, y, viewport, display, fx, fy)) {
        return Entity();
    }

    auto color = _graphics->read_pixel(fbo, fx, fy);

    // Restore window framebuffer
    if (display && display->surface) {
        uint32_t window_fbo_id = tc_render_surface_get_framebuffer(display->surface);
        _graphics->bind_framebuffer_id(window_fbo_id);
    }

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

    fx = (int)vx;
    fy = (int)(vp_h - vy - 1); // Flip Y for OpenGL
    return true;
}

FramebufferHandle* EditorInteractionSystem::_get_viewport_fbo(
    tc_viewport_handle vp, const std::string& name)
{
    tc_pipeline_handle pipeline_h = tc_viewport_get_pipeline(vp);
    if (!tc_pipeline_pool_alive(pipeline_h)) return nullptr;

    RenderPipeline* pipeline = RenderPipeline::from_handle(pipeline_h);
    if (!pipeline) return nullptr;

    return pipeline->get_fbo(name);
}

// ============================================================================
// Ray casting
// ============================================================================

bool EditorInteractionSystem::_screen_to_ray(
    float x, float y, tc_viewport_handle vp, tc_display* display,
    Vec3f& origin, Vec3f& direction)
{
    (void)display;

    tc_component* cam_comp = tc_viewport_get_camera(vp);
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
