#include "orbit_camera_controller.hpp"
#include "../entity/component_registry.hpp"
#include "tc_log.hpp"

#include <cmath>

namespace termin {

// Register component type
REGISTER_COMPONENT(OrbitCameraController, CxxComponent);

OrbitCameraController::OrbitCameraController(
    double radius,
    double min_radius,
    double max_radius,
    bool prevent_moving
)
    : radius(radius)
    , min_radius(min_radius)
    , max_radius(max_radius)
    , _prevent_moving(prevent_moving)
{
    link_type_entry("OrbitCameraController");
    set_has_update(true);
    set_active_in_editor(true);

    // Install input vtable for receiving input events
    install_input_vtable(&_c);
}

void OrbitCameraController::on_added() {
    CxxComponent::on_added();

    // Find CameraComponent on same entity
    _camera = entity.get_component<CameraComponent>();
    if (!_camera) {
        tc_log(TC_LOG_ERROR, "[OrbitCameraController] No CameraComponent found on entity '%s'",
               entity.name());
    }

    _sync_from_transform();
}

void OrbitCameraController::update(float dt) {
    (void)dt;

    if (!entity.valid()) return;

    // Check for external transform changes
    Vec3 pos = entity.transform().global_position();
    Quat rot = entity.transform().global_rotation();

    if (_has_last_transform) {
        // Check if position changed
        bool pos_changed = (
            std::abs(pos.x - _last_position.x) > 1e-6 ||
            std::abs(pos.y - _last_position.y) > 1e-6 ||
            std::abs(pos.z - _last_position.z) > 1e-6
        );

        // Check if rotation changed
        bool rot_changed = (
            std::abs(rot.x - _last_rotation.x) > 1e-6 ||
            std::abs(rot.y - _last_rotation.y) > 1e-6 ||
            std::abs(rot.z - _last_rotation.z) > 1e-6 ||
            std::abs(rot.w - _last_rotation.w) > 1e-6
        );

        if (pos_changed || rot_changed) {
            _sync_from_transform();
        }
    }

    _last_position = pos;
    _last_rotation = rot;
    _has_last_transform = true;
}

void OrbitCameraController::_sync_from_transform() {
    /**
     * Compute internal state (azimuth, elevation, target) from current transform.
     *
     * Forward direction uses Y-forward convention (local Y is forward).
     * Target is position + forward * radius.
     */
    if (!entity.valid()) return;

    Vec3 pos = entity.transform().global_position();
    Quat rot = entity.transform().global_rotation();

    // Get rotation matrix
    double rm[9];
    rot.to_matrix(rm);

    // Forward direction (Y column of rotation matrix)
    // rm is row-major: rm[0,1,2] = row0, rm[3,4,5] = row1, rm[6,7,8] = row2
    // Column 1 (Y): rm[1], rm[4], rm[7]
    Vec3 forward{rm[1], rm[4], rm[7]};

    // Target is position + forward * radius
    _target = pos + forward * radius;

    // Compute direction from target to camera
    Vec3 to_camera = pos - _target;
    double dist = to_camera.norm();
    if (dist < 1e-6) {
        _last_position = pos;
        _last_rotation = rot;
        _has_last_transform = true;
        return;
    }

    // Normalize
    Vec3 to_camera_norm = to_camera / dist;

    // Elevation: angle from XY plane (asin of Z component)
    double z_clamped = _clamp(to_camera_norm.z, -1.0, 1.0);
    _elevation = std::asin(z_clamped);

    // Azimuth: angle in XY plane
    // At azimuth=0, camera is behind target (-Y direction)
    // atan2(x, -y) gives us the angle from -Y axis
    _azimuth = std::atan2(to_camera_norm.x, -to_camera_norm.y);

    // Update last known position/rotation
    _last_position = pos;
    _last_rotation = rot;
    _has_last_transform = true;
}

void OrbitCameraController::_update_pose() {
    /**
     * Update camera pose from internal state.
     *
     * At azimuth=0, elevation=0: camera is behind target (-Y), looking at +Y.
     * Azimuth rotates around Z axis (up).
     * Elevation raises/lowers the camera.
     */
    if (!entity.valid()) return;

    double r = _clamp(radius, min_radius, max_radius);
    double cos_elev = std::cos(_elevation);

    // Compute eye position
    Vec3 eye{
        _target.x + r * std::sin(_azimuth) * cos_elev,   // X - side
        _target.y - r * std::cos(_azimuth) * cos_elev,   // Y - behind target
        _target.z + r * std::sin(_elevation)              // Z - height
    };

    // Create pose looking at target
    Pose3 pose = Pose3::looking_at(eye, _target);
    entity.transform().relocate(pose);

    // Update last known position to avoid re-sync
    _last_position = entity.transform().global_position();
    _last_rotation = entity.transform().global_rotation();
}

void OrbitCameraController::orbit(double delta_azimuth, double delta_elevation) {
    _azimuth += delta_azimuth * M_PI / 180.0;  // Convert degrees to radians

    // Clamp elevation to avoid gimbal lock at poles
    double new_elevation = _elevation + delta_elevation * M_PI / 180.0;
    _elevation = _clamp(new_elevation, -89.0 * M_PI / 180.0, 89.0 * M_PI / 180.0);

    _update_pose();
}

void OrbitCameraController::zoom(double delta) {
    // Check for orthographic camera
    if (_camera && _camera->get_projection_type_str() == "orthographic") {
        double scale_factor = 1.0 + delta * 0.1;
        _camera->ortho_size = std::max(0.1, _camera->ortho_size * scale_factor);
    } else {
        // Perspective: change radius
        radius = _clamp(radius + delta, min_radius, max_radius);
        _update_pose();
    }
}

void OrbitCameraController::pan(double dx, double dy) {
    if (!entity.valid()) return;

    // Get rotation matrix for local axes
    Quat rot = entity.transform().global_rotation();
    double rm[9];
    rot.to_matrix(rm);

    // Right direction (X column): rm[0], rm[3], rm[6]
    Vec3 right{rm[0], rm[3], rm[6]};

    // Up direction (Z column in Y-forward convention): rm[2], rm[5], rm[8]
    Vec3 up{rm[2], rm[5], rm[8]};

    // Move target
    _target = _target + right * dx + up * dy;
    _update_pose();
}

void OrbitCameraController::center_on(const Vec3& position) {
    _target = position;
    _update_pose();
}

OrbitCameraController::ViewportState& OrbitCameraController::_get_viewport_state(uintptr_t viewport_id) {
    return _viewport_states[viewport_id];
}

// === Input handlers ===
// Events are passed as pointers to C++ event structures (MouseButtonEvent, etc.)
// When called from Python, nanobind automatically converts Python objects to C++ structs.
// When called from C#, SWIG does the same conversion.

void OrbitCameraController::on_mouse_button(void* event) {
    if (!_camera) {
        return;
    }

    auto* e = static_cast<MouseButtonEvent*>(event);
    if (!e) {
        return;
    }

    // Get viewport pointer as key for per-viewport state
    uintptr_t vp_key = reinterpret_cast<uintptr_t>(e->viewport);
    ViewportState& state = _get_viewport_state(vp_key);

    // Middle mouse = orbit
    if (e->button == static_cast<int>(MouseButton::MIDDLE)) {
        state.orbit_active = (e->action == static_cast<int>(Action::PRESS));
    }
    // Right mouse = pan
    else if (e->button == static_cast<int>(MouseButton::RIGHT)) {
        state.pan_active = (e->action == static_cast<int>(Action::PRESS));
    }

    // Reset last position on release
    if (e->action == static_cast<int>(Action::RELEASE)) {
        state.has_last = false;
    }
}

void OrbitCameraController::on_mouse_move(void* event) {
    if (_prevent_moving) return;
    if (!_camera) return;

    auto* e = static_cast<MouseMoveEvent*>(event);
    if (!e) return;

    uintptr_t vp_key = reinterpret_cast<uintptr_t>(e->viewport);
    ViewportState& state = _get_viewport_state(vp_key);

    if (!state.has_last) {
        state.last_x = e->x;
        state.last_y = e->y;
        state.has_last = true;
        return;
    }

    state.last_x = e->x;
    state.last_y = e->y;

    if (state.orbit_active) {
        // Orbit: negative dx because moving mouse right should rotate left
        orbit(-e->dx * _orbit_speed, e->dy * _orbit_speed);
    } else if (state.pan_active) {
        pan(-e->dx * _pan_speed, e->dy * _pan_speed);
    }
}

void OrbitCameraController::on_scroll(void* event) {
    if (_prevent_moving) return;

    auto* e = static_cast<ScrollEvent*>(event);
    if (!e) return;

    // Scroll up (positive yoffset) = zoom in (negative delta)
    zoom(-e->yoffset * _zoom_speed);
}

} // namespace termin
