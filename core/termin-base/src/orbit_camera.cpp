#include "termin/camera/orbit_camera.hpp"

#include <algorithm>
#include <cmath>

#include <tcbase/tc_log.h>

namespace termin {
    namespace {
        constexpr double kPi = 3.14159265358979323846;
        constexpr double kDegToRad = kPi / 180.0;
        constexpr double kEpsilon = 1.0e-12;

        Mat44 look_at_negative_z(const Vec3& eye, const Vec3& target, const Vec3& up) {
            const Vec3 forward = (target - eye).normalized();
            const Vec3 right = forward.cross(up).normalized();
            const Vec3 camera_up = right.cross(forward);
            Mat44 matrix = Mat44::identity();
            matrix(0, 0) = right.x;
            matrix(1, 0) = right.y;
            matrix(2, 0) = right.z;
            matrix(0, 1) = camera_up.x;
            matrix(1, 1) = camera_up.y;
            matrix(2, 1) = camera_up.z;
            matrix(0, 2) = -forward.x;
            matrix(1, 2) = -forward.y;
            matrix(2, 2) = -forward.z;
            matrix(3, 0) = -right.dot(eye);
            matrix(3, 1) = -camera_up.dot(eye);
            matrix(3, 2) = forward.dot(eye);
            return matrix;
        }

        Mat44 perspective_negative_z(double fov_y, double aspect, double near_clip, double far_clip) {
            Mat44 matrix;
            const double scale = 1.0 / std::tan(fov_y * 0.5);
            const double depth = far_clip - near_clip;
            matrix(0, 0) = scale / aspect;
            matrix(1, 1) = -scale;
            matrix(2, 2) = -far_clip / depth;
            matrix(3, 2) = -(far_clip * near_clip) / depth;
            matrix(2, 3) = -1.0;
            return matrix;
        }

    } // namespace

    Vec3 orbit_camera_eye(const Vec3& target, double distance, double azimuth, double elevation) {
        const double cos_elevation = std::cos(elevation);
        return {target.x + distance * cos_elevation * std::sin(azimuth),
                target.y - distance * cos_elevation * std::cos(azimuth),
                target.z + distance * std::sin(elevation)};
    }

    std::optional<OrbitCameraAngles> orbit_camera_angles(const Vec3& eye, const Vec3& target) {
        const Vec3 offset = eye - target;
        const double distance = offset.norm();
        if (!std::isfinite(distance) || distance <= kEpsilon) {
            return std::nullopt;
        }
        const Vec3 direction = offset / distance;
        return OrbitCameraAngles{std::atan2(direction.x, -direction.y),
                                 std::asin(std::clamp(direction.z, -1.0, 1.0))};
    }

    void orbit_camera_rotate(double& azimuth,
                             double& elevation,
                             double delta_azimuth,
                             double delta_elevation,
                             double min_elevation,
                             double max_elevation) {
        azimuth += delta_azimuth;
        elevation = std::clamp(elevation + delta_elevation, min_elevation, max_elevation);
    }

    std::optional<OrbitCameraPan> OrbitCameraPan::begin(const Mat44& view,
                                                        const Mat44& projection,
                                                        const Vec3& eye,
                                                        const Vec3& target,
                                                        const Vec2& screen_position,
                                                        const Rect2& viewport) {
        if (!viewport.is_finite() || viewport.width <= 0.0 || viewport.height <= 0.0 || !eye.is_finite() ||
            !target.is_finite()) {
            return std::nullopt;
        }
        if (!projection.is_finite() || !view.is_finite()) {
            return std::nullopt;
        }
        const Vec3 eye_to_target = target - eye;
        Vec3 plane_normal;
        if (!eye_to_target.try_normalized(plane_normal, kEpsilon)) {
            return std::nullopt;
        }

        OrbitCameraPan result;
        result.projection_ = projection;
        result.view_ = view;
        result.initial_target_ = target;
        result.plane_point_ = target;
        result.plane_normal_ = plane_normal;
        result.viewport_ = viewport;
        const std::optional<Vec3> grabbed = result.point_on_plane(screen_position);
        if (!grabbed) {
            return std::nullopt;
        }
        result.grabbed_point_ = *grabbed;
        return result;
    }

    std::optional<Vec3> OrbitCameraPan::target_at(const Vec2& screen_position) const {
        const std::optional<Vec3> current = point_on_plane(screen_position);
        if (!current) {
            return std::nullopt;
        }
        // Form the cursor delta before adding the large-world target. Left-to-
        // right `(target + grabbed) - current` would discard local precision
        // in the intermediate value when all three points are far from origin.
        const Vec3 target = initial_target_ + (grabbed_point_ - *current);
        return target.is_finite() ? std::optional<Vec3>(target) : std::nullopt;
    }

    const Vec3& OrbitCameraPan::grabbed_point() const {
        return grabbed_point_;
    }

    std::optional<Ray3> OrbitCameraPan::ray_at(const Vec2& screen_position) const {
        Ray3 ray;
        return try_unproject_screen_ray(projection_, view_, screen_position, viewport_, ray, nullptr, kEpsilon)
                   ? std::optional<Ray3>(ray)
                   : std::nullopt;
    }

    std::optional<Vec3> OrbitCameraPan::point_on_plane(const Vec2& screen_position) const {
        const std::optional<Ray3> ray = ray_at(screen_position);
        if (!ray) {
            return std::nullopt;
        }
        Vec3 point;
        if (!try_intersect_ray_plane(*ray, plane_point_, plane_normal_, point, false, kEpsilon)) {
            return std::nullopt;
        }
        return point;
    }

    OrbitCamera::OrbitCamera()
        : azimuth(45.0 * kDegToRad),
          elevation(30.0 * kDegToRad),
          fov_y(45.0 * kDegToRad),
          min_elevation(-89.0 * kDegToRad),
          max_elevation(89.0 * kDegToRad) {}

    Vec3 OrbitCamera::eye() const {
        return orbit_camera_eye(target, distance, azimuth, elevation);
    }

    void OrbitCamera::compute_eye(double out[3]) const {
        const Vec3 value = eye();
        out[0] = value.x;
        out[1] = value.y;
        out[2] = value.z;
    }

    Mat44 OrbitCamera::view_matrix() const {
        return look_at_negative_z(eye(), target, Vec3::unit_z());
    }

    Mat44 OrbitCamera::projection_matrix(double aspect) const {
        return perspective_negative_z(fov_y, aspect, near_clip, far_clip);
    }

    Mat44 OrbitCamera::mvp(double aspect) const {
        return projection_matrix(aspect) * view_matrix();
    }

    void OrbitCamera::view_matrix(double out[16]) const {
        view_matrix().copy_column_major_to(out);
    }

    void OrbitCamera::projection_matrix(double aspect, double out[16]) const {
        projection_matrix(aspect).copy_column_major_to(out);
    }

    void OrbitCamera::mvp(double aspect, double out[16]) const {
        mvp(aspect).copy_column_major_to(out);
    }

    void OrbitCamera::orbit(double delta_azimuth, double delta_elevation) {
        orbit_camera_rotate(azimuth, elevation, delta_azimuth, delta_elevation, min_elevation, max_elevation);
    }

    void OrbitCamera::zoom(double factor) {
        distance = std::clamp(distance * factor, min_distance, max_distance);
        update_clip_planes();
    }

    std::optional<OrbitCameraPan> OrbitCamera::begin_pan(const Vec2& screen_position, const Rect2& viewport) const {
        if (viewport.width <= 0.0 || viewport.height <= 0.0) {
            return std::nullopt;
        }
        return OrbitCameraPan::begin(view_matrix(),
                                     projection_matrix(viewport.width / viewport.height),
                                     eye(),
                                     target,
                                     screen_position,
                                     viewport);
    }

    bool OrbitCamera::pan(const OrbitCameraPan& gesture, const Vec2& screen_position) {
        const std::optional<Vec3> next_target = gesture.target_at(screen_position);
        if (!next_target) {
            return false;
        }
        target = *next_target;
        return true;
    }

    bool OrbitCamera::pan(const Vec2& from, const Vec2& to, const Rect2& viewport) {
        const std::optional<OrbitCameraPan> gesture = begin_pan(from, viewport);
        return gesture && pan(*gesture, to);
    }

    void OrbitCamera::fit_bounds(const AABB& bounds) {
        target = bounds.center();
        const double size = bounds.size().norm();
        fitted_radius = std::max(size * 0.5, 1.0);
        distance = std::max(size * 1.2, min_distance);
        min_distance = std::max(fitted_radius * 0.001, 0.01);
        max_distance = std::max(max_distance, distance + fitted_radius * 20.0);
        update_clip_planes();
    }

    std::optional<Ray3>
    OrbitCamera::try_screen_ray(const Vec2& screen_position, const Rect2& viewport, ScreenRayError* error) const {
        ScreenRayError local_error = ScreenRayError::None;
        ScreenRayError* const result_error = error != nullptr ? error : &local_error;

        if (!screen_position.is_finite()) {
            *result_error = ScreenRayError::InvalidScreenPoint;
            tc_log_error("[termin-base] OrbitCamera screen ray failed: %s", screen_ray_error_message(*result_error));
            return std::nullopt;
        }
        if (!viewport.is_finite() || viewport.width <= 0.0 || viewport.height <= 0.0) {
            *result_error = ScreenRayError::InvalidViewport;
            tc_log_error("[termin-base] OrbitCamera screen ray failed: %s", screen_ray_error_message(*result_error));
            return std::nullopt;
        }

        Ray3 ray;
        const double aspect = viewport.width / viewport.height;
        if (!try_unproject_screen_ray(
                projection_matrix(aspect), view_matrix(), screen_position, viewport, ray, result_error, kEpsilon)) {
            tc_log_error("[termin-base] OrbitCamera screen ray failed: %s", screen_ray_error_message(*result_error));
            return std::nullopt;
        }
        return ray;
    }

    std::optional<ProjectedScreenPoint>
    OrbitCamera::try_project_world_point(const Vec3& world_point, const Rect2& viewport, ScreenRayError* error) const {
        ScreenRayError local_error = ScreenRayError::None;
        ScreenRayError* const result_error = error != nullptr ? error : &local_error;
        if (!viewport.is_finite() || viewport.width <= 0.0 || viewport.height <= 0.0) {
            *result_error = ScreenRayError::InvalidViewport;
            tc_log_error("[termin-base] OrbitCamera world projection failed: %s",
                         screen_ray_error_message(*result_error));
            return std::nullopt;
        }

        ProjectedScreenPoint projected;
        const double aspect = viewport.width / viewport.height;
        if (!termin::try_project_world_point(
                projection_matrix(aspect), view_matrix(), world_point, viewport, projected, result_error, kEpsilon)) {
            tc_log_error("[termin-base] OrbitCamera world projection failed: %s",
                         screen_ray_error_message(*result_error));
            return std::nullopt;
        }
        return projected;
    }

    std::optional<Vec3> OrbitCamera::world_point_on_z_plane(const Vec2& screen_position,
                                                            const Rect2& viewport,
                                                            double z) const {
        if (!std::isfinite(z)) {
            tc_log_error("[termin-base] OrbitCamera z-plane projection failed: plane coordinate must be finite");
            return std::nullopt;
        }
        const std::optional<Ray3> ray = try_screen_ray(screen_position, viewport);
        if (!ray) {
            return std::nullopt;
        }
        Vec3 point;
        if (!try_intersect_ray_plane(*ray, {0.0, 0.0, z}, Vec3::unit_z(), point, true, kEpsilon)) {
            return std::nullopt;
        }
        return point;
    }

    void OrbitCamera::update_clip_planes() {
        const double radius = std::max(fitted_radius, 1.0);
        const double margin = radius * 2.5;
        near_clip = std::max(0.01, distance - margin);
        far_clip = std::max(near_clip + 1.0, distance + margin);
    }
} // namespace termin
