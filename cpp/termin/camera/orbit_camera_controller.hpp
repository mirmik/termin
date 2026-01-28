#pragma once

#include "../export.hpp"
#include "../entity/component.hpp"
#include "../entity/input_handler.hpp"
#include "../input/input_events.hpp"
#include "../geom/vec3.hpp"
#include "../geom/quat.hpp"
#include "../geom/pose3.hpp"
#include "camera_component.hpp"

#include <cmath>
#include <unordered_map>
#include <cstdint>

#ifndef M_PI
#define M_PI 3.14159265358979323846
#endif

namespace termin {

/**
 * OrbitCameraController - orbit camera controller similar to DCC tools.
 *
 * Transform is the single source of truth. Internal state (azimuth, elevation, target)
 * is derived from transform and updated when external changes are detected.
 *
 * Coordinate convention: Y-forward, Z-up
 *   - At azimuth=0, elevation=0: camera is behind target (-Y), looking at +Y
 *   - Azimuth rotates around Z axis (up)
 *   - Elevation raises/lowers the camera
 *
 * Controls:
 *   - Middle mouse button + drag: Orbit (rotate around target)
 *   - Right mouse button + drag: Pan (move target)
 *   - Scroll wheel: Zoom (change radius or ortho size)
 */
class ENTITY_API OrbitCameraController : public CxxComponent, public InputHandler {
public:
    // === Public parameters (serializable via INSPECT_FIELD) ===

    double radius = 5.0;
    double min_radius = 1.0;
    double max_radius = 100.0;

    // INSPECT_FIELD registrations
    INSPECT_FIELD(OrbitCameraController, radius, "Radius", "double", 0.1, 100.0, 0.1)
    INSPECT_FIELD(OrbitCameraController, min_radius, "Min Radius", "double", 0.1, 100.0, 0.1)
    INSPECT_FIELD(OrbitCameraController, max_radius, "Max Radius", "double", 1.0, 1000.0, 1.0)

    // === Constructor ===

    OrbitCameraController(
        double radius = 5.0,
        double min_radius = 1.0,
        double max_radius = 100.0,
        bool prevent_moving = false
    );

    // === Camera operations ===

    /**
     * Orbit camera around target.
     * @param delta_azimuth Horizontal rotation in degrees
     * @param delta_elevation Vertical rotation in degrees
     */
    void orbit(double delta_azimuth, double delta_elevation);

    /**
     * Pan camera (move target in screen space).
     * @param dx Horizontal offset (positive = right)
     * @param dy Vertical offset (positive = up)
     */
    void pan(double dx, double dy);

    /**
     * Zoom camera.
     * For perspective: changes radius.
     * For orthographic: changes ortho_size.
     * @param delta Zoom amount (positive = zoom out)
     */
    void zoom(double delta);

    /**
     * Center camera on position.
     * @param position New target position
     */
    void center_on(const Vec3& position);

    /**
     * Set whether camera movement is prevented.
     */
    void set_prevent_moving(bool prevent) { _prevent_moving = prevent; }
    bool prevent_moving() const { return _prevent_moving; }

    // === Getters for internal state ===

    Vec3 target() const { return _target; }
    double azimuth() const { return _azimuth; }
    double elevation() const { return _elevation; }

    // === CxxComponent lifecycle ===

    void on_added() override;
    void update(float dt) override;

    // === InputHandler interface ===

    void on_mouse_button(tc_mouse_button_event* event) override;
    void on_mouse_move(tc_mouse_move_event* event) override;
    void on_scroll(tc_scroll_event* event) override;

    // === Internal methods (public for Python compatibility) ===

    void _sync_from_transform();
    void _update_pose();

private:
    // === Internal state (derived from transform) ===

    double _azimuth = 0.0;      // Horizontal angle (radians)
    double _elevation = 0.0;   // Vertical angle (radians)
    Vec3 _target{0.0, 0.0, 0.0};  // Point camera orbits around

    // For detecting external transform changes
    Vec3 _last_position{0.0, 0.0, 0.0};
    Quat _last_rotation = Quat::identity();
    bool _has_last_transform = false;

    // === Control parameters ===

    double _orbit_speed = 0.2;
    double _pan_speed = 0.005;
    double _zoom_speed = 0.5;
    bool _prevent_moving = false;

    // === Per-viewport state for drag operations ===

    struct ViewportState {
        bool orbit_active = false;
        bool pan_active = false;
        double last_x = 0.0;
        double last_y = 0.0;
        bool has_last = false;
    };
    std::unordered_map<uintptr_t, ViewportState> _viewport_states;

    // === Camera component reference ===

    CameraComponent* _camera = nullptr;

    // === Internal methods ===

    ViewportState& _get_viewport_state(uintptr_t viewport_id);

    // Clamp value to range
    static double _clamp(double v, double lo, double hi) {
        return v < lo ? lo : (v > hi ? hi : v);
    }
};

} // namespace termin
