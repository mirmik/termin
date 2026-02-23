// editor_interaction_system.hpp - Singleton editor interaction coordinator
// Owns selection state, gizmo manager. Receives events from EditorViewportInputManager.
#pragma once

#include "termin/editor/selection_manager.hpp"
#include "termin/editor/gizmo_manager.hpp"
#include "termin/editor/transform_gizmo.hpp"
#include "tgfx/graphics_backend.hpp"
#include "termin/geom/general_pose3.hpp"
#include "termin/input/input_events.hpp"
#include "render/tc_display.h"
#include "render/tc_viewport.h"

#include <functional>
#include <string>
#include <array>
#include <chrono>

namespace termin {

class EditorInteractionSystem {
public:
    // Shared state
    SelectionManager selection;
    GizmoManager gizmo_manager;

private:
    TransformGizmo _transform_gizmo;
    GraphicsBackend* _graphics = nullptr;

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

public:
    // Callbacks to Python
    std::function<void()> on_request_update;
    std::function<void(const GeneralPose3&, const GeneralPose3&)> on_transform_end;
    std::function<void(const KeyEvent&)> on_key;

public:
    EditorInteractionSystem();
    ~EditorInteractionSystem();

    // Singleton via C API
    static EditorInteractionSystem* instance();
    static void set_instance(EditorInteractionSystem* inst);

    // Configuration
    void set_graphics(GraphicsBackend* graphics) { _graphics = graphics; }
    GraphicsBackend* graphics() const { return _graphics; }

    // Transform gizmo access
    TransformGizmo* transform_gizmo() { return &_transform_gizmo; }
    void set_gizmo_target(Entity entity);

    // Picking (reads from ID buffer)
    Entity pick_entity_at(float x, float y, tc_viewport_handle viewport, tc_display* display);

    // Post-render processing - call once per frame after rendering
    void after_render();

    // Called by EditorViewportInputManager instances
    void on_mouse_button(int button, int action, int mods,
                         float x, float y, tc_viewport_handle vp, tc_display* display);
    void on_mouse_move(float x, float y, float dx, float dy,
                       tc_viewport_handle vp, tc_display* display);

private:
    void _process_pending_press();
    void _process_pending_release();
    void _process_pending_hover();
    void _handle_double_click(float x, float y, tc_viewport_handle vp, tc_display* display);

    bool _window_to_fbo_coords(float x, float y, tc_viewport_handle vp,
                               tc_display* display, int& fx, int& fy);
    FramebufferHandle* _get_viewport_fbo(tc_viewport_handle vp, const std::string& name);

    // Get ray from screen coordinates
    bool _screen_to_ray(float x, float y, tc_viewport_handle vp, tc_display* display,
                        Vec3f& origin, Vec3f& direction);

    void _request_update();

    static double _current_time();
};

} // namespace termin
