#pragma once

#include "vec3.hpp"
#include "quat.hpp"

namespace termin {

struct Pose3 {
    Quat ang;  // Rotation (quaternion)
    Vec3 lin;  // Translation

    Pose3() : ang(Quat::identity()), lin(Vec3::zero()) {}
    Pose3(const Quat& ang, const Vec3& lin) : ang(ang), lin(lin) {}

    static Pose3 identity() { return {}; }

    // SE(3) composition: this * other
    Pose3 operator*(const Pose3& other) const {
        return {
            ang * other.ang,
            lin + ang.rotate(other.lin)
        };
    }

    // Inverse pose
    Pose3 inverse() const {
        Quat inv_ang = ang.inverse();
        return {inv_ang, inv_ang.rotate(-lin)};
    }

    // Transform point: R * p + t
    Vec3 transform_point(const Vec3& p) const {
        return ang.rotate(p) + lin;
    }

    // Transform vector (rotation only)
    Vec3 transform_vector(const Vec3& v) const {
        return ang.rotate(v);
    }

    // Rotate point (alias for transform_vector)
    Vec3 rotate_point(const Vec3& p) const {
        return ang.rotate(p);
    }

    // Inverse transform point: R^T * (p - t)
    Vec3 inverse_transform_point(const Vec3& p) const {
        return ang.inverse_rotate(p - lin);
    }

    // Inverse transform vector
    Vec3 inverse_transform_vector(const Vec3& v) const {
        return ang.inverse_rotate(v);
    }

    // Normalize quaternion
    Pose3 normalized() const {
        return {ang.normalized(), lin};
    }

    // With new translation
    Pose3 with_translation(const Vec3& new_lin) const {
        return {ang, new_lin};
    }

    // With new rotation
    Pose3 with_rotation(const Quat& new_ang) const {
        return {new_ang, lin};
    }

    // Get 3x3 rotation matrix
    void rotation_matrix(double* m) const {
        ang.to_matrix(m);
    }

    // Factory methods
    static Pose3 translation(double x, double y, double z) {
        return {Quat::identity(), {x, y, z}};
    }

    static Pose3 translation(const Vec3& t) {
        return {Quat::identity(), t};
    }

    static Pose3 rotation(const Vec3& axis, double angle) {
        return {Quat::from_axis_angle(axis, angle), Vec3::zero()};
    }

    static Pose3 rotate_x(double angle) {
        return rotation(Vec3::unit_x(), angle);
    }

    static Pose3 rotate_y(double angle) {
        return rotation(Vec3::unit_y(), angle);
    }

    static Pose3 rotate_z(double angle) {
        return rotation(Vec3::unit_z(), angle);
    }
};

// Linear interpolation
inline Pose3 lerp(const Pose3& p1, const Pose3& p2, double t) {
    return {
        slerp(p1.ang, p2.ang, t),
        p1.lin + (p2.lin - p1.lin) * t
    };
}

} // namespace termin
