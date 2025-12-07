#pragma once

#include "vec3.hpp"
#include <cmath>

namespace termin {
namespace geom {

struct Quat {
    double x, y, z, w;  // (x, y, z, w) format

    Quat() : x(0), y(0), z(0), w(1) {}
    Quat(double x, double y, double z, double w) : x(x), y(y), z(z), w(w) {}

    static Quat identity() { return {0, 0, 0, 1}; }

    // Quaternion multiplication
    Quat operator*(const Quat& q) const {
        return {
            w * q.x + x * q.w + y * q.z - z * q.y,
            w * q.y - x * q.z + y * q.w + z * q.x,
            w * q.z + x * q.y - y * q.x + z * q.w,
            w * q.w - x * q.x - y * q.y - z * q.z
        };
    }

    Quat conjugate() const { return {-x, -y, -z, w}; }
    Quat inverse() const { return conjugate(); }  // Assumes unit quaternion

    double norm() const { return std::sqrt(x * x + y * y + z * z + w * w); }

    Quat normalized() const {
        double n = norm();
        return n > 1e-10 ? Quat{x / n, y / n, z / n, w / n} : identity();
    }

    // Rotate vector by quaternion (optimized formula)
    Vec3 rotate(const Vec3& v) const {
        // t = 2 * cross(q.xyz, v)
        double tx = 2.0 * (y * v.z - z * v.y);
        double ty = 2.0 * (z * v.x - x * v.z);
        double tz = 2.0 * (x * v.y - y * v.x);

        // result = v + w * t + cross(q.xyz, t)
        return {
            v.x + w * tx + y * tz - z * ty,
            v.y + w * ty + z * tx - x * tz,
            v.z + w * tz + x * ty - y * tx
        };
    }

    // Inverse rotate
    Vec3 inverse_rotate(const Vec3& v) const {
        return conjugate().rotate(v);
    }

    // Create from axis-angle
    static Quat from_axis_angle(const Vec3& axis, double angle) {
        double half = angle * 0.5;
        double s = std::sin(half);
        Vec3 n = axis.normalized();
        return {n.x * s, n.y * s, n.z * s, std::cos(half)};
    }

    // To 3x3 rotation matrix (row-major)
    void to_matrix(double* m) const {
        double xx = x * x, yy = y * y, zz = z * z;
        double xy = x * y, xz = x * z, yz = y * z;
        double wx = w * x, wy = w * y, wz = w * z;

        m[0] = 1 - 2 * (yy + zz);  m[1] = 2 * (xy - wz);      m[2] = 2 * (xz + wy);
        m[3] = 2 * (xy + wz);      m[4] = 1 - 2 * (xx + zz);  m[5] = 2 * (yz - wx);
        m[6] = 2 * (xz - wy);      m[7] = 2 * (yz + wx);      m[8] = 1 - 2 * (xx + yy);
    }
};

// Spherical linear interpolation
inline Quat slerp(const Quat& q1, Quat q2, double t) {
    double dot = q1.x * q2.x + q1.y * q2.y + q1.z * q2.z + q1.w * q2.w;

    if (dot < 0) {
        q2 = {-q2.x, -q2.y, -q2.z, -q2.w};
        dot = -dot;
    }

    if (dot > 0.9995) {
        // Linear interpolation for close quaternions
        Quat result = {
            q1.x + t * (q2.x - q1.x),
            q1.y + t * (q2.y - q1.y),
            q1.z + t * (q2.z - q1.z),
            q1.w + t * (q2.w - q1.w)
        };
        return result.normalized();
    }

    double theta_0 = std::acos(dot);
    double theta = theta_0 * t;
    double sin_theta = std::sin(theta);
    double sin_theta_0 = std::sin(theta_0);

    double s1 = std::cos(theta) - dot * sin_theta / sin_theta_0;
    double s2 = sin_theta / sin_theta_0;

    return {
        s1 * q1.x + s2 * q2.x,
        s1 * q1.y + s2 * q2.y,
        s1 * q1.z + s2 * q2.z,
        s1 * q1.w + s2 * q2.w
    };
}

} // namespace geom
} // namespace termin
