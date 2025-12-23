#pragma once

#include "termin/geom/mat44.hpp"
#include "termin/geom/vec3.hpp"
#include "termin/geom/quat.hpp"

#define _USE_MATH_DEFINES
#include <cmath>

#ifndef M_PI
#define M_PI 3.14159265358979323846
#endif

namespace termin {

/**
 * Camera projection type.
 */
enum class CameraProjection {
    Perspective,
    Orthographic
};

/**
 * Camera data structure.
 *
 * Stores projection parameters and computes projection/view matrices.
 * Coordinate convention: Y-forward, Z-up.
 *
 * For view matrix computation, the camera's world pose (position + rotation)
 * must be provided externally (from Entity/Transform system).
 */
struct Camera {
    CameraProjection projection_type = CameraProjection::Perspective;

    // Common parameters
    double near = 0.1;
    double far = 100.0;

    // Perspective parameters
    double fov_y = 1.0472;  // 60 degrees in radians
    double aspect = 1.0;

    // Orthographic parameters
    double ortho_left = -1.0;
    double ortho_right = 1.0;
    double ortho_bottom = -1.0;
    double ortho_top = 1.0;

    Camera() = default;

    /**
     * Create perspective camera.
     *
     * @param fov_y_rad  Vertical field of view in radians
     * @param aspect     Aspect ratio (width / height)
     * @param near       Near clipping plane
     * @param far        Far clipping plane
     */
    static Camera perspective(double fov_y_rad, double aspect, double near = 0.1, double far = 100.0) {
        Camera cam;
        cam.projection_type = CameraProjection::Perspective;
        cam.fov_y = fov_y_rad;
        cam.aspect = aspect;
        cam.near = near;
        cam.far = far;
        return cam;
    }

    /**
     * Create perspective camera with FOV in degrees.
     */
    static Camera perspective_deg(double fov_y_deg, double aspect, double near = 0.1, double far = 100.0) {
        return perspective(fov_y_deg * M_PI / 180.0, aspect, near, far);
    }

    /**
     * Create orthographic camera.
     */
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

    /**
     * Get projection matrix based on camera type.
     *
     * Uses Y-forward, Z-up convention.
     */
    Mat44 projection_matrix() const {
        if (projection_type == CameraProjection::Perspective) {
            return Mat44::perspective(fov_y, aspect, near, far);
        } else {
            return Mat44::orthographic(ortho_left, ortho_right, ortho_bottom, ortho_top, near, far);
        }
    }

    /**
     * Compute view matrix from camera world pose.
     *
     * The view matrix is the inverse of the camera's model matrix.
     *
     * @param position  Camera world position
     * @param rotation  Camera world rotation (quaternion)
     * @return View matrix
     */
    static Mat44 view_matrix(const Vec3& position, const Quat& rotation) {
        // View matrix = inverse of model matrix
        // For rigid transform: inv(T * R) = inv(R) * inv(T) = R^T * (-R^T * t)

        Quat inv_rot = rotation.conjugate();
        Vec3 inv_pos = inv_rot.rotate(-position);

        return Mat44::compose(inv_pos, inv_rot, Vec3{1, 1, 1});
    }

    /**
     * Compute view matrix using look-at.
     *
     * @param eye     Camera position
     * @param target  Point to look at
     * @param up      Up direction (default: +Z)
     */
    static Mat44 view_matrix_look_at(const Vec3& eye, const Vec3& target,
                                      const Vec3& up = Vec3::unit_z()) {
        return Mat44::look_at(eye, target, up);
    }

    /**
     * Set aspect ratio (for perspective camera).
     */
    void set_aspect(double new_aspect) {
        aspect = new_aspect;
    }

    /**
     * Set FOV in radians (for perspective camera).
     */
    void set_fov(double fov_rad) {
        fov_y = fov_rad;
    }

    /**
     * Set FOV in degrees (for perspective camera).
     */
    void set_fov_deg(double fov_deg) {
        fov_y = fov_deg * M_PI / 180.0;
    }

    /**
     * Get FOV in degrees.
     */
    double get_fov_deg() const {
        return fov_y * 180.0 / M_PI;
    }
};

} // namespace termin
