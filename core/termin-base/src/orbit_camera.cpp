#include "termin/camera/orbit_camera.hpp"

#include <algorithm>
#include <cmath>
#include <limits>

#include <tcbase/tc_log.h>

namespace termin {
    namespace {
        constexpr double kPi = 3.14159265358979323846;
        constexpr double kDegToRad = kPi / 180.0;
        constexpr double kEpsilon = 1.0e-12;
        // Mat44::look_at normalizes its eye-to-target direction at 1e-10.
        constexpr double kMinFittedRadius = 1.0e-8;

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
        return Mat44::look_at(eye(), target, Vec3::unit_z());
    }

    Mat44 OrbitCamera::projection_matrix(double aspect) const {
        if (projection_type == CameraProjection::Orthographic) {
            return Mat44::orthographic(-ortho_size * aspect, ortho_size * aspect,
                                      -ortho_size, ortho_size, near_clip, far_clip);
        }
        return Mat44::perspective(fov_y, aspect, near_clip, far_clip);
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
        if (!std::isfinite(factor) || factor <= 0.0) {
            tc_log_error("[termin-base] OrbitCamera zoom factor must be finite and positive");
            return;
        }
        if (projection_type == CameraProjection::Orthographic) {
            const double next_size = ortho_size * factor;
            if (!std::isfinite(next_size) || next_size <= 0.0) {
                tc_log_error("[termin-base] OrbitCamera orthographic zoom size must remain finite and positive");
                return;
            }
            ortho_size = next_size;
            return;
        }
        distance = std::clamp(distance * factor, min_distance, max_distance);
        update_clip_planes();
    }

    void OrbitCamera::set_isometric() {
        projection_type = CameraProjection::Orthographic;
        azimuth = kPi * 0.25;
        elevation = std::asin(1.0 / std::sqrt(3.0));
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

    void OrbitCamera::fit_bounds(const AABB& bounds, double aspect) {
        if (!bounds.is_valid() || !std::isfinite(aspect) || aspect <= 0.0 ||
            !std::isfinite(fov_y) || fov_y <= 0.0 || fov_y >= kPi) {
            tc_log_error("[termin-base] OrbitCamera fit requires finite bounds, positive aspect and valid FOV");
            return;
        }
        target = bounds.center();
        const double size = bounds.size().norm();
        // A single point has no intrinsic scale. Give it a usable frame, and
        // keep the eye offset representable when the target is far from zero.
        const double coordinate_scale = std::max({std::abs(target.x), std::abs(target.y), std::abs(target.z)});
        const double precision_radius = coordinate_scale * std::numeric_limits<double>::epsilon() * 16.0;
        fitted_radius = std::max({size > 0.0 ? size * 0.5 : 1.0, kMinFittedRadius, precision_radius});
        min_distance = std::max(fitted_radius * 0.001, std::min(0.01, fitted_radius * 0.01));
        // Fit the enclosing sphere to both dimensions. The same radius also
        // keeps the entire bounds inside the depth range in either projection.
        if (projection_type == CameraProjection::Orthographic) {
            ortho_size = 1.05 * fitted_radius / std::min(aspect, 1.0);
            distance = std::max(fitted_radius * 2.5, min_distance);
        } else {
            const double half_fov = std::min(fov_y * 0.5, std::atan(std::tan(fov_y * 0.5) * aspect));
            distance = std::max(1.05 * fitted_radius / std::sin(half_fov), min_distance);
        }
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
        const double radius = std::max(fitted_radius, kMinFittedRadius);
        const double margin = radius * 2.5;
        const double min_near = std::min(0.01, radius * 0.01);
        near_clip = std::max(min_near, distance - margin);
        far_clip = std::max(near_clip + std::min(1.0, radius), distance + margin);
    }
} // namespace termin
