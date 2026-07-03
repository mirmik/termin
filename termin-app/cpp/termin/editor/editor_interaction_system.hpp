// editor_interaction_system.hpp - Singleton editor interaction coordinator
// Owns selection state, gizmo manager. Receives events from EditorViewportInputManager.
#pragma once

#include "termin/editor/selection_manager.hpp"
#include "termin/editor/gizmo_manager.hpp"
#include "termin/editor/transform_gizmo.hpp"
#include "termin/editor/camera_frustum_debug_gizmo.hpp"
#include <termin/geom/general_pose3.hpp>
#include "termin/input/input_events.hpp"
#include "core/tc_scene.h"
#include "render/tc_display.h"
#include "render/tc_viewport.h"

#include <functional>
#include <memory>
#include <string>
#include <array>
#include <chrono>
#include <cstdint>
#include <vector>

namespace termin {

struct SurfacePickResult {
    Entity entity;
    bool has_world_point = false;
    std::array<double, 3> world_point = {0.0, 0.0, 0.0};
    float depth = 1.0f;
    double view_depth = 0.0;
    double reproject_screen_error = 0.0;
    double reproject_depth_error = 0.0;
    bool has_mesh_hit = false;
    std::array<double, 3> mesh_point = {0.0, 0.0, 0.0};
    std::array<double, 3> mesh_normal = {0.0, 0.0, 0.0};
    uint32_t mesh_triangle_index = 0;
    std::array<uint32_t, 3> mesh_indices = {0, 0, 0};
};

class EditorInteractionSystem {
public:
    // Shared state
    SelectionManager selection;
    GizmoManager gizmo_manager;

private:
    TransformGizmo _transform_gizmo;
    CameraFrustumDebugGizmo _camera_frustum_debug_gizmo;
    std::vector<std::unique_ptr<Gizmo>> _component_visual_gizmos;

    // Click/drag detection
    float _press_x = 0.0f;
    float _press_y = 0.0f;
    bool _has_press = false;
    bool _gizmo_handled_press = false;
    float _click_threshold = 5.0f;

    // Double-click detection
    double _last_click_time = 0.0;
    double _double_click_threshold = 0.3;

    // Pending events (processed after render when ID buffer is ready)
    struct PendingEvent {
        float x = 0.0f;
        float y = 0.0f;
        tc_viewport_handle vp = TC_VIEWPORT_HANDLE_INVALID;
        tc_display* display = nullptr;
        bool valid = false;
    };
    PendingEvent _pending_press;
    PendingEvent _pending_release;
    PendingEvent _pending_hover;

    struct PendingEntityPick {
        PendingEvent event;
        int fx = 0;
        int fy = 0;
        uint64_t color_request = 0;
        bool valid = false;
    };
    struct PendingSurfacePick {
        PendingEvent event;
        int fx = 0;
        int fy = 0;
        uint64_t color_request = 0;
        uint64_t depth_request = 0;
        bool color_ready = false;
        bool depth_ready = false;
        float color[4] = {0.0f, 0.0f, 0.0f, 0.0f};
        float depth = 1.0f;
        bool valid = false;
    };
    PendingEntityPick _async_hover_pick;
    PendingSurfacePick _async_release_pick;

    bool _camera_frustums_visible = false;
    tc_scene_handle _camera_frustum_scene = TC_SCENE_HANDLE_INVALID;
    int _camera_frustum_view_width = 0;
    int _camera_frustum_view_height = 0;

public:
    // Callbacks to Python
    std::function<void()> on_request_update;
    std::function<void(const GeneralPose3&, const GeneralPose3&)> on_transform_end;
    std::function<void(const KeyEvent&)> on_key;
    std::function<bool(Entity, float, float, bool, double, double, double, float, double, double, double, bool, double, double, double, double, double, double, uint32_t, uint32_t, uint32_t, uint32_t)> on_entity_click;
    std::function<bool(const std::string&, float, float, float, float, int, int, int)> on_viewport_pointer_event;

public:
    EditorInteractionSystem();
    ~EditorInteractionSystem();

    // Singleton for editor input/picking coordination inside the app native module.
    static EditorInteractionSystem* instance();
    static void set_instance(EditorInteractionSystem* inst);

    // Transform gizmo access
    TransformGizmo* transform_gizmo() { return &_transform_gizmo; }
    void set_gizmo_target(Entity entity);
    void set_camera_frustums_visible(bool visible);
    bool camera_frustums_visible() const { return _camera_frustums_visible; }
    void set_camera_frustum_render_context(tc_scene_handle scene, int width, int height);
    tc_scene_handle camera_frustum_scene() const { return _camera_frustum_scene; }
    double camera_frustum_aspect_override() const;

    // Picking (reads from ID buffer)
    Entity pick_entity_at(float x, float y, tc_viewport_handle viewport, tc_display* display);
    SurfacePickResult pick_surface_at(float x, float y, tc_viewport_handle viewport, tc_display* display);

    // Post-render processing - call once per frame after rendering
    void after_render();
    bool handle_key_event(const KeyEvent& event,
                          float cursor_x,
                          float cursor_y,
                          tc_viewport_handle viewport,
                          tc_display* display);

    // Called by EditorViewportInputManager instances
    void on_mouse_button(int button, int action, int mods,
                         float x, float y, tc_viewport_handle vp, tc_display* display);
    void on_mouse_move(float x, float y, float dx, float dy,
                       tc_viewport_handle vp, tc_display* display);

private:
    void _process_pending_press();
    void _process_pending_release();
    void _process_pending_hover();
    bool _start_async_entity_pick(float x, float y, tc_viewport_handle vp, tc_display* display);
    bool _start_async_surface_pick(float x, float y, tc_viewport_handle vp, tc_display* display);
    void _poll_async_hover_pick();
    void _poll_async_release_pick();
    void _handle_double_click(float x, float y, tc_viewport_handle vp, tc_display* display);
    void _rebuild_component_visual_gizmos(Entity entity);
    void _clear_component_visual_gizmos();
    bool _snap_transform_gizmo_target(float cursor_x,
                                      float cursor_y,
                                      tc_viewport_handle viewport,
                                      tc_display* display);

    bool _window_to_fbo_coords(float x, float y, tc_viewport_handle vp,
                               tc_display* display, int& fx, int& fy);
    Entity _entity_from_pick_color(const float color[4], tc_viewport_handle viewport);
    SurfacePickResult _surface_from_pick_color_depth(const float color[4], float depth,
                                                     int fx, int fy,
                                                     tc_viewport_handle viewport);

    // Get ray from screen coordinates
    bool _screen_to_ray(float x, float y, tc_viewport_handle vp, tc_display* display,
                        Vec3f& origin, Vec3f& direction);

    void _request_update();

    static double _current_time();
};

} // namespace termin
