#pragma once

#include <termin/geom/mat44.hpp>
#include <termin/geom/quat.hpp>
#include <termin/geom/vec3.hpp>

#define _USE_MATH_DEFINES
#include <cmath>

#ifndef M_PI
#define M_PI 3.14159265358979323846
#endif

namespace termin {

enum class CameraProjection {
    Perspective,
    Orthographic
};

struct Camera {
public:
    CameraProjection projection_type = CameraProjection::Perspective;
    double near = 0.1;
    double far = 100.0;
    double fov_y = 1.0472;
    double aspect = 1.0;
    double ortho_left = -1.0;
    double ortho_right = 1.0;
    double ortho_bottom = -1.0;
    double ortho_top = 1.0;

public:
    Camera() = default;

    static Camera perspective(double fov_y_rad, double aspect, double near = 0.1, double far = 100.0) {
        Camera cam;
        cam.projection_type = CameraProjection::Perspective;
        cam.fov_y = fov_y_rad;
        cam.aspect = aspect;
        cam.near = near;
        cam.far = far;
        return cam;
    }

    static Camera perspective_deg(double fov_y_deg, double aspect, double near = 0.1, double far = 100.0) {
        return perspective(fov_y_deg * M_PI / 180.0, aspect, near, far);
    }

    static Camera orthographic(double left, double right, double bottom, double top,
                               double near = 0.1, double far = 100.0) {
        Camera cam;
        cam.projection_type = CameraProjection::Orthographic;
        cam.ortho_left = left;
        cam.ortho_right = right;
        cam.ortho_bottom = bottom;
        cam.ortho_top = top;
        cam.near = near;
        cam.far = far;
        return cam;
    }

    Mat44 projection_matrix() const {
        if (projection_type == CameraProjection::Perspective) {
            return Mat44::perspective(fov_y, aspect, near, far);
        }
        return Mat44::orthographic(ortho_left, ortho_right, ortho_bottom, ortho_top, near, far);
    }

    static Mat44 view_matrix(const Vec3& position, const Quat& rotation) {
        Quat inv_rot = rotation.conjugate();
        Vec3 inv_pos = inv_rot.rotate(-position);
        return Mat44::compose(inv_pos, inv_rot, Vec3{1, 1, 1});
    }

    static Mat44 view_matrix_look_at(const Vec3& eye, const Vec3& target,
                                     const Vec3& up = Vec3::unit_z()) {
        return Mat44::look_at(eye, target, up);
    }

    void set_aspect(double new_aspect) {
        aspect = new_aspect;
    }

    void set_fov(double fov_rad) {
        fov_y = fov_rad;
    }

    void set_fov_deg(double fov_deg) {
        fov_y = fov_deg * M_PI / 180.0;
    }

    double get_fov_deg() const {
        return fov_y * 180.0 / M_PI;
    }
};

} // namespace termin
