#include <tcbase/tc_log.hpp>
#include <termin/camera/orbit_camera_controller.hpp>
#include <termin/entity/component_registry.hpp>

extern "C" {
#include "render/tc_render_target.h"
#include "render/tc_viewport.h"
}

#include <cmath>

namespace termin {

    // Helper to create a unique key from viewport handle
    static inline uint64_t viewport_key(tc_viewport_handle h) {
        return (static_cast<uint64_t>(h.index) << 32) | h.generation;
    }

    OrbitCameraController::OrbitCameraController(double radius,
                                                 double min_radius,
                                                 double max_radius,
                                                 bool prevent_moving)
        : CxxComponent("OrbitCameraController"),
          radius(radius),
          min_radius(min_radius),
          max_radius(max_radius),
          _prevent_moving(prevent_moving) {
        set_has_update(true);
        set_active_in_editor(true);

        // Install input vtable for receiving input events
        install_input_vtable(&_c);
    }

    void OrbitCameraController::register_type() {
        auto descriptor = ComponentTypeDescriptorBuilder::native<OrbitCameraController>(
            "OrbitCameraController", "termin-components-render", "CxxComponent");
        descriptor.category("Input");
        tc::stage_inspect_field(descriptor.inspect(),
                                &OrbitCameraController::radius,
                                "OrbitCameraController",
                                "radius",
                                "Radius",
                                "double",
                                0.1,
                                100.0,
                                0.1);
        tc::stage_inspect_field(descriptor.inspect(),
                                &OrbitCameraController::min_radius,
                                "OrbitCameraController",
                                "min_radius",
                                "Min Radius",
                                "double",
                                0.1,
                                100.0,
                                0.1);
        tc::stage_inspect_field(descriptor.inspect(),
                                &OrbitCameraController::max_radius,
                                "OrbitCameraController",
                                "max_radius",
                                "Max Radius",
                                "double",
                                1.0,
                                1000.0,
                                1.0);
        tc::stage_inspect_field(descriptor.inspect(),
                                &OrbitCameraController::orbit_mouse_button,
                                "OrbitCameraController",
                                "orbit_mouse_button",
                                "Orbit Mouse Button",
                                "int",
                                0.0,
                                2.0,
                                1.0);
        tc::stage_inspect_field(descriptor.inspect(),
                                &OrbitCameraController::pan_mouse_button,
                                "OrbitCameraController",
                                "pan_mouse_button",
                                "Pan Mouse Button",
                                "int",
                                0.0,
                                2.0,
                                1.0);
        tc::stage_inspect_field(descriptor.inspect(),
                                &OrbitCameraController::horizon_lock,
                                "OrbitCameraController",
                                "horizon_lock",
                                "Horizon Lock",
                                "bool");
        (void)descriptor.commit();
    }

    void OrbitCameraController::_ensure_camera() {
        // Re-resolve camera if entity handle became stale
        // (happens when entity moves between pools, e.g. standalone → scene)
        if (!_camera.valid() && entity().valid()) {
            _camera.reset(entity().get_component<CameraComponent>());
        }
    }

    bool OrbitCameraController::_event_targets_this_camera(tc_viewport_handle viewport) {
        _ensure_camera();
        CameraComponent* camera = _camera.get();
        if (!camera || !tc_viewport_alive(viewport)) {
            return false;
        }

        tc_render_target_handle rt = tc_viewport_get_render_target(viewport);
        if (!tc_render_target_handle_valid(rt)) {
            return false;
        }

        return tc_render_target_get_camera(rt) == camera->tc_component_ptr();
    }

    std::optional<OrbitCameraPan>
    OrbitCameraController::_begin_pan_gesture(tc_viewport_handle viewport, const Vec2& screen_position) {
        _ensure_camera();
        CameraComponent* camera = _camera.get();
        if (!camera || !entity().valid()) {
            tc_log_error("[OrbitCameraController] Cannot begin pan without a live camera entity");
            return std::nullopt;
        }

        int viewport_width = 0;
        int viewport_height = 0;
        tc_viewport_get_pixel_rect(viewport, nullptr, nullptr, &viewport_width, &viewport_height);
        if (viewport_width <= 0 || viewport_height <= 0) {
            tc_log_error("[OrbitCameraController] Cannot begin pan with invalid viewport size %dx%d",
                         viewport_width,
                         viewport_height);
            return std::nullopt;
        }

        const double aspect = static_cast<double>(viewport_width) / static_cast<double>(viewport_height);
        const Vec3 eye = entity().transform().global_position();
        std::optional<OrbitCameraPan> gesture = OrbitCameraPan::begin(camera->get_view_matrix(),
                                                                     camera->compute_projection_matrix(aspect),
                                                                     eye,
                                                                     _target,
                                                                     screen_position,
                                                                     Rect2{0.0,
                                                                           0.0,
                                                                           static_cast<double>(viewport_width),
                                                                           static_cast<double>(viewport_height)});
        if (!gesture) {
            tc_log_error("[OrbitCameraController] Failed to unproject orbital pan anchor");
        }
        return gesture;
    }

    void OrbitCameraController::on_added() {
        CxxComponent::on_added();

        // Find CameraComponent on same entity
        _camera.reset(entity().get_component<CameraComponent>());
        if (!_camera.valid()) {
            tc_log(TC_LOG_ERROR, "[OrbitCameraController] No CameraComponent found on entity '%s'", entity().name());
        }

        _sync_from_transform();
    }

    void OrbitCameraController::update(float dt) {
        (void)dt;

        if (!entity().valid())
            return;

        // Check for external transform changes
        Vec3 pos = entity().transform().global_position();
        Quat rot = entity().transform().global_rotation();

        if (_has_last_transform) {
            // Check if position changed
            bool pos_changed = (std::abs(pos.x - _last_position.x) > 1e-6 ||
                                std::abs(pos.y - _last_position.y) > 1e-6 || std::abs(pos.z - _last_position.z) > 1e-6);

            // Check if rotation changed
            bool rot_changed =
                (std::abs(rot.x - _last_rotation.x) > 1e-6 || std::abs(rot.y - _last_rotation.y) > 1e-6 ||
                 std::abs(rot.z - _last_rotation.z) > 1e-6 || std::abs(rot.w - _last_rotation.w) > 1e-6);

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
        if (!entity().valid())
            return;

        Vec3 pos = entity().transform().global_position();
        Quat rot = entity().transform().global_rotation();

        const Vec3 forward = rot.rotate(Vec3::unit_y());

        // Target is position + forward * radius
        _target = pos + forward * radius;

        const std::optional<OrbitCameraAngles> angles = orbit_camera_angles(pos, _target);
        if (!angles) {
            _last_position = pos;
            _last_rotation = rot;
            _has_last_transform = true;
            return;
        }

        _azimuth = angles->azimuth;
        _elevation = angles->elevation;

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
        if (!entity().valid())
            return;

        double r = _clamp(radius, min_radius, max_radius);
        const Vec3 eye = orbit_camera_eye(_target, r, _azimuth, _elevation);

        // Create pose looking at target (always zero-roll, resets fly roll)
        Pose3 pose = Pose3::looking_at(eye, _target);
        entity().transform().relocate(pose);

        // Update last known position to avoid re-sync
        _last_position = entity().transform().global_position();
        _last_rotation = entity().transform().global_rotation();
    }

    void OrbitCameraController::orbit(double delta_azimuth, double delta_elevation) {
        orbit_camera_rotate(_azimuth,
                            _elevation,
                            delta_azimuth * M_PI / 180.0,
                            delta_elevation * M_PI / 180.0,
                            -89.0 * M_PI / 180.0,
                            89.0 * M_PI / 180.0);

        _update_pose();
    }

    void OrbitCameraController::zoom(double delta) {
        // Check for orthographic camera
        CameraComponent* cam = _camera.get();
        if (cam && cam->get_projection_type_str() == "orthographic") {
            double scale_factor = 1.0 + delta * 0.1;
            cam->ortho_size = std::max(0.1, cam->ortho_size * scale_factor);
        } else {
            // Perspective: change radius
            radius = _clamp(radius + delta, min_radius, max_radius);
            _update_pose();
        }
    }

    void OrbitCameraController::translate_target(const Vec2& displacement) {
        if (!entity().valid())
            return;

        const Quat rot = entity().transform().global_rotation();
        const Vec3 right = rot.rotate(Vec3::unit_x());
        const Vec3 up = rot.rotate(Vec3::unit_z());

        // Move target
        _target = _target + right * displacement.x + up * displacement.y;
        _update_pose();
    }

    void OrbitCameraController::center_on(const Vec3& position) {
        _target = position;
        _update_pose();
    }

    void OrbitCameraController::fly_move(const Vec3& local_displacement) {
        // Translate camera along its local axes. Does not change rotation.
        if (!entity().valid())
            return;

        const Quat rot = entity().transform().global_rotation();

        Vec3 pos = entity().transform().global_position();
        pos += rot.rotate(local_displacement);

        entity().transform().relocate(Pose3{rot, pos});
        _sync_from_transform();
    }

    void OrbitCameraController::fly_forward(double delta) {
        // Move along forward direction. If horizon_lock, project onto XY plane.
        if (!entity().valid())
            return;

        const Quat rot = entity().transform().global_rotation();
        Vec3 forward = rot.rotate(Vec3::unit_y());

        if (horizon_lock) {
            forward.z = 0.0;
            double len = forward.norm();
            if (len < 1e-6)
                return;
            forward = forward / len;
        }

        Vec3 pos = entity().transform().global_position();
        pos = pos + forward * delta;

        entity().transform().relocate(Pose3{rot, pos});
        _sync_from_transform();
    }

    void OrbitCameraController::fly_rotate(double yaw, double pitch, double roll) {
        // Rotate camera in place. Yaw around world Z, pitch around local X, roll around local Y.
        if (!entity().valid())
            return;

        Vec3 eye = entity().transform().global_position();
        const Quat rot = entity().transform().global_rotation();
        const Vec3 axis_right = rot.rotate(Vec3::unit_x());
        const Vec3 axis_forward = rot.rotate(Vec3::unit_y());

        // Build incremental rotation quaternions
        Quat yaw_q = Quat::from_axis_angle(Vec3{0, 0, 1}, yaw * M_PI / 180.0);
        Quat pitch_q = Quat::from_axis_angle(axis_right, pitch * M_PI / 180.0);
        Quat roll_q = Quat::from_axis_angle(axis_forward, roll * M_PI / 180.0);

        // Compose: roll * pitch * yaw * current
        Quat new_rot = roll_q * pitch_q * yaw_q * rot;

        // If horizon_lock, reconstruct rotation from forward direction via looking_at
        // This removes any accumulated roll, keeping the horizon level
        if (horizon_lock) {
            const Vec3 new_forward = new_rot.rotate(Vec3::unit_y());
            Pose3 level_pose = Pose3::looking_at(eye, eye + new_forward);
            new_rot = level_pose.ang;
        }

        entity().transform().relocate(Pose3{new_rot, eye});
        _sync_from_transform();
    }

    OrbitCameraController::ViewportState& OrbitCameraController::_get_viewport_state(uint64_t viewport_id) {
        return _viewport_states[viewport_id];
    }

    // === Input handlers ===
    // Events are C struct pointers (tc_mouse_button_event*, etc.)

    void OrbitCameraController::on_pointer(tc_pointer_event* e) {
        if (_prevent_moving || !e || !_event_targets_this_camera(e->viewport)) {
            return;
        }
        if (e->device != TC_POINTER_DEVICE_TOUCH && e->device != TC_POINTER_DEVICE_PEN) {
            return;
        }

        ViewportState& state = _get_viewport_state(viewport_key(e->viewport));
        if (e->phase == TC_POINTER_DOWN) {
            state.touch_points[e->pointer_id] = {e->x, e->y};
            state.pan_gesture.reset();
            return;
        }
        if (e->phase == TC_POINTER_CANCEL) {
            state.touch_points.erase(e->pointer_id);
            state.pan_gesture.reset();
            return;
        }

        auto point = state.touch_points.find(e->pointer_id);
        if (point == state.touch_points.end()) {
            return;
        }

        if (e->phase == TC_POINTER_MOVE) {
            if (state.touch_points.size() == 1) {
                point->second = {e->x, e->y};
                state.pan_gesture.reset();
                orbit(-e->dx * _orbit_speed, e->dy * _orbit_speed);
                return;
            }

            if (state.touch_points.size() == 2) {
                auto first = state.touch_points.begin();
                auto second = std::next(first);
                const Vec2 old_center = (first->second + second->second) * 0.5;
                const double old_dx = first->second.x - second->second.x;
                const double old_dy = first->second.y - second->second.y;
                const double old_span = std::hypot(old_dx, old_dy);

                point->second = {e->x, e->y};

                first = state.touch_points.begin();
                second = std::next(first);
                const Vec2 new_center = (first->second + second->second) * 0.5;
                const double new_dx = first->second.x - second->second.x;
                const double new_dy = first->second.y - second->second.y;
                const double new_span = std::hypot(new_dx, new_dy);

                if (!state.pan_gesture) {
                    state.pan_gesture = _begin_pan_gesture(e->viewport, old_center);
                }
                if (state.pan_gesture) {
                    const std::optional<Vec3> next_target = state.pan_gesture->target_at(new_center);
                    if (next_target) {
                        _target = *next_target;
                        _update_pose();
                    } else {
                        tc_log_error("[OrbitCameraController] Failed to update touch pan gesture");
                    }
                }
                zoom((old_span - new_span) * _touch_zoom_speed);
                state.pan_gesture = _begin_pan_gesture(e->viewport, new_center);
                return;
            }

            point->second = {e->x, e->y};
            return;
        }

        if (e->phase == TC_POINTER_UP) {
            state.touch_points.erase(point);
            state.pan_gesture.reset();
        }
    }

    void OrbitCameraController::on_mouse_button(tc_mouse_button_event* e) {
        if (!e || !_event_targets_this_camera(e->viewport)) {
            return;
        }

        // Get viewport pointer as key for per-viewport state
        uint64_t vp_key = viewport_key(e->viewport);
        ViewportState& state = _get_viewport_state(vp_key);

        if (e->button == orbit_mouse_button) {
            state.orbit_active = (e->action == static_cast<int>(Action::PRESS));
        } else if (e->button == pan_mouse_button) {
            state.pan_active = (e->action == static_cast<int>(Action::PRESS));
            state.pan_gesture.reset();
            if (state.pan_active) {
                state.pan_gesture = _begin_pan_gesture(e->viewport, Vec2{e->x, e->y});
                state.pan_active = state.pan_gesture.has_value();
            }
        }

        if (e->action == static_cast<int>(Action::PRESS)) {
            state.last_position = {e->x, e->y};
            state.has_last = true;
        }

        // Reset last position on release
        if (e->action == static_cast<int>(Action::RELEASE)) {
            state.has_last = false;
            state.pan_gesture.reset();
        }
    }

    void OrbitCameraController::on_mouse_move(tc_mouse_move_event* e) {
        if (_prevent_moving)
            return;
        if (!e || !_event_targets_this_camera(e->viewport))
            return;

        uint64_t vp_key = viewport_key(e->viewport);
        ViewportState& state = _get_viewport_state(vp_key);

        if (!state.has_last) {
            state.last_position = {e->x, e->y};
            state.has_last = true;
            return;
        }

        state.last_position = {e->x, e->y};

        if (state.orbit_active) {
            // Orbit: negative dx because moving mouse right should rotate left
            orbit(-e->dx * _orbit_speed, e->dy * _orbit_speed);
        } else if (state.pan_active) {
            if (!state.pan_gesture) {
                state.pan_gesture = _begin_pan_gesture(e->viewport, Vec2{e->x - e->dx, e->y - e->dy});
            }
            if (state.pan_gesture) {
                const std::optional<Vec3> next_target = state.pan_gesture->target_at(Vec2{e->x, e->y});
                if (next_target) {
                    _target = *next_target;
                    _update_pose();
                } else {
                    tc_log_error("[OrbitCameraController] Failed to update mouse pan gesture");
                }
            }
        }
    }

    void OrbitCameraController::on_scroll(tc_scroll_event* e) {
        if (_prevent_moving)
            return;
        if (!e || !_event_targets_this_camera(e->viewport))
            return;

        // Scroll up (positive yoffset) = zoom in (negative delta)
        zoom(-e->yoffset * _zoom_speed);
    }

} // namespace termin
