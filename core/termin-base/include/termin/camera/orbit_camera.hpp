#pragma once

#include <optional>

#include <tcbase/tcbase_api.h>
#include <termin/geom/aabb.hpp>
#include <termin/geom/mat44.hpp>
#include <termin/geom/ray3.hpp>
#include <termin/geom/rect2.hpp>
#include <termin/geom/vec2.hpp>
#include <termin/geom/vec3.hpp>

namespace termin {

    struct OrbitCameraAngles {
        double azimuth = 0.0;
        double elevation = 0.0;
    };

    TCBASE_API Vec3 orbit_camera_eye(const Vec3& target, double distance, double azimuth, double elevation);
    TCBASE_API std::optional<OrbitCameraAngles> orbit_camera_angles(const Vec3& eye, const Vec3& target);
    TCBASE_API void orbit_camera_rotate(double& azimuth,
                                        double& elevation,
                                        double delta_azimuth,
                                        double delta_elevation,
                                        double min_elevation,
                                        double max_elevation);

    /**
     * Immutable snapshot of an orbital-camera pan gesture.
     *
     * The gesture grabs the point under the initial screen position on the
     * plane through the orbit target whose normal is the eye-to-target line.
     * target_at() returns the translated target which keeps that world point
     * under the current screen position.  The initial view/projection snapshot
     * is deliberately retained for the whole drag, avoiding accumulated drift.
     */
    class TCBASE_API OrbitCameraPan {
    public:
        static std::optional<OrbitCameraPan> begin(const Mat44& view,
                                                   const Mat44& projection,
                                                   const Vec3& eye,
                                                   const Vec3& target,
                                                   const Vec2& screen_position,
                                                   const Rect2& viewport);

        std::optional<Vec3> target_at(const Vec2& screen_position) const;
        const Vec3& grabbed_point() const;

    private:
        std::optional<Vec3> unproject(double ndc_x, double ndc_y, double ndc_z) const;
        std::optional<Vec3> point_on_plane(const Vec2& screen_position) const;

        Mat44 inverse_projection_view_{};
        Vec3 initial_target_{};
        Vec3 plane_point_{};
        Vec3 plane_normal_{};
        Vec3 grabbed_point_{};
        Rect2 viewport_{};
    };

    struct OrbitCameraRay {
        Vec3 origin;
        Vec3 direction;
    };

    class TCBASE_API OrbitCamera {
    public:
        Vec3 target{0.0, 0.0, 0.0};
        double distance = 5.0;
        double azimuth;
        double elevation;
        double fov_y;
        double near_clip = 0.01;
        double far_clip = 1000.0;
        double fitted_radius = 1.0;

        double min_distance = 0.01;
        double max_distance = 10000.0;
        double min_elevation;
        double max_elevation;

        OrbitCamera();

        Vec3 eye() const;
        void compute_eye(double out[3]) const;

        Mat44 view_matrix() const;
        Mat44 projection_matrix(double aspect) const;
        Mat44 mvp(double aspect) const;

        void view_matrix(double out16[16]) const;
        void projection_matrix(double aspect, double out16[16]) const;
        void mvp(double aspect, double out16[16]) const;

        void orbit(double d_azimuth, double d_elevation);
        void zoom(double factor);
        std::optional<OrbitCameraPan> begin_pan(const Vec2& screen_position, const Rect2& viewport) const;
        bool pan(const OrbitCameraPan& gesture, const Vec2& screen_position);
        bool pan(const Vec2& from, const Vec2& to, const Rect2& viewport);
        void fit_bounds(const AABB& bounds);

        OrbitCameraRay screen_ray(const Vec2& screen_position, const Rect2& viewport) const;
        std::optional<Vec3> world_point_on_z_plane(const Vec2& screen_position,
                                                   const Rect2& viewport,
                                                   double z = 0.0) const;

    private:
        void update_clip_planes();
    };

} // namespace termin
