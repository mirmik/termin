#include "termin/camera/orbit_camera.hpp"

#include <algorithm>
#include <cmath>
#include <cstring>

namespace termin {
    namespace {
        constexpr double kPi = 3.14159265358979323846;
        constexpr double kDegToRad = kPi / 180.0;
        constexpr double kEpsilon = 1.0e-12;

        bool finite(const Vec3& value) {
            return std::isfinite(value.x) && std::isfinite(value.y) && std::isfinite(value.z);
        }

        bool finite(const Mat44& value) {
            return std::all_of(std::begin(value.data), std::end(value.data), [](double item) {
                return std::isfinite(item);
            });
        }

        void copy_mat(const Mat44& source, double out[16]) {
            std::memcpy(out, source.data, sizeof(source.data));
        }

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

        std::optional<Vec3> transform_clip_point(const Mat44& matrix, double x, double y, double z) {
            const double tx = matrix(0, 0) * x + matrix(1, 0) * y + matrix(2, 0) * z + matrix(3, 0);
            const double ty = matrix(0, 1) * x + matrix(1, 1) * y + matrix(2, 1) * z + matrix(3, 1);
            const double tz = matrix(0, 2) * x + matrix(1, 2) * y + matrix(2, 2) * z + matrix(3, 2);
            const double tw = matrix(0, 3) * x + matrix(1, 3) * y + matrix(2, 3) * z + matrix(3, 3);
            if (!std::isfinite(tw) || std::abs(tw) <= kEpsilon) {
                return std::nullopt;
            }
            const Vec3 point{tx / tw, ty / tw, tz / tw};
            return finite(point) ? std::optional<Vec3>(point) : std::nullopt;
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
        if (!std::isfinite(viewport.x) || !std::isfinite(viewport.y) || !std::isfinite(viewport.width) ||
            !std::isfinite(viewport.height) || viewport.width <= 0.0 || viewport.height <= 0.0 || !finite(eye) ||
            !finite(target)) {
            return std::nullopt;
        }
        const Mat44 projection_view = projection * view;
        const double determinant = projection_view.determinant();
        if (!finite(projection_view) || !std::isfinite(determinant) || determinant == 0.0) {
            return std::nullopt;
        }
        const Vec3 eye_to_target = target - eye;
        if (eye_to_target.norm() <= kEpsilon) {
            return std::nullopt;
        }

        OrbitCameraPan result;
        result.inverse_projection_view_ = projection_view.inverse();
        if (!finite(result.inverse_projection_view_)) {
            return std::nullopt;
        }
        result.initial_target_ = target;
        result.plane_point_ = target;
        result.plane_normal_ = eye_to_target.normalized();
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
        const Vec3 target = initial_target_ + grabbed_point_ - *current;
        return finite(target) ? std::optional<Vec3>(target) : std::nullopt;
    }

    const Vec3& OrbitCameraPan::grabbed_point() const {
        return grabbed_point_;
    }

    std::optional<Vec3> OrbitCameraPan::unproject(double ndc_x, double ndc_y, double ndc_z) const {
        return transform_clip_point(inverse_projection_view_, ndc_x, ndc_y, ndc_z);
    }

    std::optional<Vec3> OrbitCameraPan::point_on_plane(const Vec2& screen_position) const {
        if (!std::isfinite(screen_position.x) || !std::isfinite(screen_position.y)) {
            return std::nullopt;
        }
        const double ndc_x = ((screen_position.x - viewport_.x) / viewport_.width) * 2.0 - 1.0;
        const double ndc_y = ((screen_position.y - viewport_.y) / viewport_.height) * 2.0 - 1.0;
        const std::optional<Vec3> near_point = unproject(ndc_x, ndc_y, 0.0);
        const std::optional<Vec3> far_point = unproject(ndc_x, ndc_y, 1.0);
        if (!near_point || !far_point) {
            return std::nullopt;
        }
        const Vec3 ray = *far_point - *near_point;
        const double denominator = ray.dot(plane_normal_);
        if (!std::isfinite(denominator) || std::abs(denominator) <= kEpsilon) {
            return std::nullopt;
        }
        const double distance = (plane_point_ - *near_point).dot(plane_normal_) / denominator;
        const Vec3 point = *near_point + ray * distance;
        return finite(point) ? std::optional<Vec3>(point) : std::nullopt;
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
        copy_mat(view_matrix(), out);
    }

    void OrbitCamera::projection_matrix(double aspect, double out[16]) const {
        copy_mat(projection_matrix(aspect), out);
    }

    void OrbitCamera::mvp(double aspect, double out[16]) const {
        copy_mat(mvp(aspect), out);
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

    OrbitCameraRay OrbitCamera::screen_ray(const Vec2& screen_position, const Rect2& viewport) const {
        const double safe_width = std::max(viewport.width, 1.0);
        const double safe_height = std::max(viewport.height, 1.0);
        const double aspect = std::max(safe_width / safe_height, 0.001);
        const double ndc_x = (screen_position.x - viewport.x) / safe_width * 2.0 - 1.0;
        const double ndc_y = (screen_position.y - viewport.y) / safe_height * 2.0 - 1.0;
        const Mat44 inverse_projection_view = mvp(aspect).inverse();
        const std::optional<Vec3> near_point = transform_clip_point(inverse_projection_view, ndc_x, ndc_y, 0.0);
        const std::optional<Vec3> far_point = transform_clip_point(inverse_projection_view, ndc_x, ndc_y, 1.0);
        if (!near_point || !far_point) {
            return {};
        }
        return {*near_point, (*far_point - *near_point).normalized()};
    }

    std::optional<Vec3> OrbitCamera::world_point_on_z_plane(const Vec2& screen_position,
                                                            const Rect2& viewport,
                                                            double z) const {
        const OrbitCameraRay ray = screen_ray(screen_position, viewport);
        if (std::abs(ray.direction.z) < kEpsilon) {
            return std::nullopt;
        }
        const double distance_along_ray = (z - ray.origin.z) / ray.direction.z;
        if (distance_along_ray < 0.0) {
            return std::nullopt;
        }
        return ray.origin + ray.direction * distance_along_ray;
    }

    void OrbitCamera::update_clip_planes() {
        const double radius = std::max(fitted_radius, 1.0);
        const double margin = radius * 2.5;
        near_clip = std::max(0.01, distance - margin);
        far_clip = std::max(near_clip + 1.0, distance + margin);
    }
} // namespace termin
