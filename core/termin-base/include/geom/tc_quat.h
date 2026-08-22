// tc_quat.h - Quaternion operations
#ifndef TC_QUAT_H
#define TC_QUAT_H

#include "geom/tc_vec3.h"
#include <math.h>
#include <tcbase/tc_types.h>

// C/C++ compatible struct initialization
#ifdef __cplusplus
#define TC_QUAT(x, y, z, w)                                                                                            \
    tc_quat {                                                                                                          \
        x, y, z, w                                                                                                     \
    }
#else
#define TC_QUAT(x, y, z, w)                                                                                            \
    (tc_quat) {                                                                                                        \
        x, y, z, w                                                                                                     \
    }
#endif

#ifdef __cplusplus
extern "C" {
#endif

#ifndef M_PI
#define M_PI 3.14159265358979323846
#endif

// ============================================================================
// Constructors
// ============================================================================

TC_C_STATIC_INLINE tc_quat tc_quat_new(double x, double y, double z, double w) {
    return TC_QUAT(x, y, z, w);
}

TC_C_STATIC_INLINE tc_quat tc_quat_identity(void) {
    return TC_QUAT(0, 0, 0, 1);
}

// From axis-angle (axis should be normalized)
TC_C_STATIC_INLINE tc_quat tc_quat_from_axis_angle(tc_vec3 axis, double angle) {
    double half = angle * 0.5;
    double s = sin(half);
    return TC_QUAT(axis.x * s, axis.y * s, axis.z * s, cos(half));
}

// ============================================================================
// Operations
// ============================================================================

TC_C_STATIC_INLINE tc_quat tc_quat_mul(tc_quat a, tc_quat b) {
    return TC_QUAT(a.w * b.x + a.x * b.w + a.y * b.z - a.z * b.y,
                   a.w * b.y - a.x * b.z + a.y * b.w + a.z * b.x,
                   a.w * b.z + a.x * b.y - a.y * b.x + a.z * b.w,
                   a.w * b.w - a.x * b.x - a.y * b.y - a.z * b.z);
}

TC_C_STATIC_INLINE tc_quat tc_quat_conjugate(tc_quat q) {
    return TC_QUAT(-q.x, -q.y, -q.z, q.w);
}

TC_C_STATIC_INLINE double tc_quat_dot(tc_quat a, tc_quat b) {
    return a.x * b.x + a.y * b.y + a.z * b.z + a.w * b.w;
}

TC_C_STATIC_INLINE double tc_quat_norm_squared(tc_quat q) {
    return tc_quat_dot(q, q);
}

TC_C_STATIC_INLINE double tc_quat_length_sq(tc_quat q) {
    return tc_quat_norm_squared(q);
}

TC_C_STATIC_INLINE double tc_quat_norm(tc_quat q) {
    double squared = tc_quat_norm_squared(q);
    // A positive subnormal sum may already have lost a material fraction of
    // its terms. Use hypot for that range as well as complete under/overflow.
    if (isnormal(squared)) {
        return sqrt(squared);
    }
    return hypot(hypot(q.x, q.y), hypot(q.z, q.w));
}

TC_C_STATIC_INLINE double tc_quat_length(tc_quat q) {
    return tc_quat_norm(q);
}

TC_C_STATIC_INLINE bool tc_quat_is_finite(tc_quat q) {
    return isfinite(q.x) && isfinite(q.y) && isfinite(q.z) && isfinite(q.w);
}

TC_C_STATIC_INLINE tc_quat tc_quat_non_finite(void) {
    return TC_QUAT(NAN, NAN, NAN, NAN);
}

TC_C_STATIC_INLINE bool tc_quat_try_normalized(tc_quat q, double epsilon, tc_quat* out_normalized) {
    double length = tc_quat_norm(q);
    if (out_normalized == NULL || !tc_quat_is_finite(q) || !isfinite(length) || !isfinite(epsilon) || epsilon < 0.0 ||
        length <= epsilon) {
        return false;
    }

    tc_quat result = TC_QUAT(q.x / length, q.y / length, q.z / length, q.w / length);
    if (!tc_quat_is_finite(result)) {
        return false;
    }
    *out_normalized = result;
    return true;
}

TC_C_STATIC_INLINE tc_quat tc_quat_normalized_or(tc_quat q, tc_quat fallback, double epsilon) {
    tc_quat result;
    return tc_quat_try_normalized(q, epsilon, &result) ? result : fallback;
}

TC_C_STATIC_INLINE tc_quat tc_quat_normalize(tc_quat q) {
    tc_quat result;
    return tc_quat_try_normalized(q, 1.0e-12, &result) ? result : tc_quat_non_finite();
}

TC_C_STATIC_INLINE bool tc_quat_try_inverse(tc_quat q, double epsilon, tc_quat* out_inverse) {
    double length = tc_quat_norm(q);
    if (out_inverse == NULL || !tc_quat_is_finite(q) || !isfinite(length) || !isfinite(epsilon) || epsilon < 0.0 ||
        length <= epsilon) {
        return false;
    }

    // Avoid forming norm_squared, which may overflow for an otherwise valid
    // finite quaternion.
    tc_quat result =
        TC_QUAT(-q.x / length / length, -q.y / length / length, -q.z / length / length, q.w / length / length);
    if (!tc_quat_is_finite(result)) {
        return false;
    }
    *out_inverse = result;
    return true;
}

TC_C_STATIC_INLINE tc_quat tc_quat_inverse(tc_quat q) {
    tc_quat result;
    return tc_quat_try_inverse(q, 1.0e-12, &result) ? result : tc_quat_non_finite();
}

// ============================================================================
// Rotate vector by a finite unit quaternion. tc_quat is a raw xyzw value, so
// callers with uncertain input must normalize it explicitly first.
// ============================================================================

TC_C_STATIC_INLINE tc_vec3 tc_quat_rotate(tc_quat q, tc_vec3 v) {
    // Unit-quaternion form of q * v * q^-1.
    tc_vec3 u = TC_VEC3(q.x, q.y, q.z);
    double s = q.w;

    tc_vec3 uv = tc_vec3_cross(u, v);
    tc_vec3 uuv = tc_vec3_cross(u, uv);

    return tc_vec3_add(v, tc_vec3_add(tc_vec3_scale(uv, 2.0 * s), tc_vec3_scale(uuv, 2.0)));
}

// ============================================================================
// Interpolation
// ============================================================================

TC_C_STATIC_INLINE tc_quat tc_quat_lerp(tc_quat a, tc_quat b, double t) {
    // Simple linear interpolation (not normalized)
    return TC_QUAT(a.x + (b.x - a.x) * t, a.y + (b.y - a.y) * t, a.z + (b.z - a.z) * t, a.w + (b.w - a.w) * t);
}

TC_C_STATIC_INLINE tc_quat tc_quat_nlerp(tc_quat a, tc_quat b, double t) {
    tc_quat from;
    tc_quat to;
    tc_quat result;
    if (!isfinite(t) || !tc_quat_try_normalized(a, 1.0e-12, &from) ||
        !tc_quat_try_normalized(b, 1.0e-12, &to)) {
        return tc_quat_non_finite();
    }
    double dot = tc_quat_dot(from, to);
    if (dot < 0) {
        to = TC_QUAT(-to.x, -to.y, -to.z, -to.w);
    }
    return tc_quat_try_normalized(tc_quat_lerp(from, to, t), 1.0e-12, &result) ? result : tc_quat_non_finite();
}

TC_C_STATIC_INLINE bool tc_quat_try_slerp(tc_quat a, tc_quat b, double t, double epsilon, tc_quat* out_slerp) {
    if (out_slerp == NULL || !isfinite(t) || !isfinite(epsilon) || epsilon < 0.0) {
        return false;
    }

    tc_quat from;
    tc_quat to;
    if (!tc_quat_try_normalized(a, epsilon, &from) || !tc_quat_try_normalized(b, epsilon, &to)) {
        return false;
    }

    double dot = tc_quat_dot(from, to);
    if (!isfinite(dot)) {
        return false;
    }

    if (dot < 0) {
        to = TC_QUAT(-to.x, -to.y, -to.z, -to.w);
        dot = -dot;
    }
    if (dot > 1.0) {
        dot = 1.0;
    }

    tc_quat interpolated;
    if (dot > 0.9995) {
        interpolated = tc_quat_lerp(from, to, t);
    } else {
        double theta = acos(dot);
        double sin_theta = sin(theta);
        double from_angle = (1.0 - t) * theta;
        double to_angle = t * theta;
        if (!isfinite(theta) || !isfinite(sin_theta) || sin_theta == 0.0 || !isfinite(from_angle) ||
            !isfinite(to_angle)) {
            return false;
        }
        double from_weight = sin(from_angle) / sin_theta;
        double to_weight = sin(to_angle) / sin_theta;
        interpolated = TC_QUAT(from_weight * from.x + to_weight * to.x,
                               from_weight * from.y + to_weight * to.y,
                               from_weight * from.z + to_weight * to.z,
                               from_weight * from.w + to_weight * to.w);
    }

    tc_quat result;
    if (!tc_quat_try_normalized(interpolated, epsilon, &result)) {
        return false;
    }
    *out_slerp = result;
    return true;
}

TC_C_STATIC_INLINE tc_quat tc_quat_slerp(tc_quat a, tc_quat b, double t) {
    tc_quat result;
    return tc_quat_try_slerp(a, b, t, 1.0e-12, &result) ? result : tc_quat_non_finite();
}

// ============================================================================
// Conversion
// ============================================================================

// Euler angles are an XYZ vector in radians. Composition matches
// qz(yaw) * qy(pitch) * qx(roll).
TC_C_STATIC_INLINE bool tc_quat_try_from_euler(tc_vec3 euler_xyz, tc_quat* out_quat) {
    if (out_quat == NULL || !tc_vec3_is_finite(euler_xyz)) {
        return false;
    }

    double cx = cos(euler_xyz.x * 0.5), sx = sin(euler_xyz.x * 0.5);
    double cy = cos(euler_xyz.y * 0.5), sy = sin(euler_xyz.y * 0.5);
    double cz = cos(euler_xyz.z * 0.5), sz = sin(euler_xyz.z * 0.5);
    tc_quat raw = TC_QUAT(sx * cy * cz - cx * sy * sz,
                          cx * sy * cz + sx * cy * sz,
                          cx * cy * sz - sx * sy * cz,
                          cx * cy * cz + sx * sy * sz);
    tc_quat result;
    if (!tc_quat_try_normalized(raw, 0.0, &result)) {
        return false;
    }
    *out_quat = result;
    return true;
}

TC_C_STATIC_INLINE tc_quat tc_quat_from_euler(tc_vec3 euler_xyz) {
    tc_quat result;
    return tc_quat_try_from_euler(euler_xyz, &result) ? result : tc_quat_non_finite();
}

TC_C_STATIC_INLINE bool tc_quat_try_to_euler(tc_quat value, double epsilon, tc_vec3* out_euler_xyz) {
    if (out_euler_xyz == NULL) {
        return false;
    }

    tc_quat q;
    if (!tc_quat_try_normalized(value, epsilon, &q)) {
        return false;
    }

    double sin_pitch = 2.0 * (q.w * q.y - q.z * q.x);
    if (sin_pitch > 1.0) {
        sin_pitch = 1.0;
    } else if (sin_pitch < -1.0) {
        sin_pitch = -1.0;
    }

    tc_vec3 result;
    if (fabs(sin_pitch) >= 1.0 - 1.0e-12) {
        // At gimbal lock choose roll = 0 and retain the observable combined
        // Z rotation in yaw.
        result = TC_VEC3(0.0,
                         copysign(M_PI * 0.5, sin_pitch),
                         atan2(2.0 * (q.w * q.z - q.x * q.y), 1.0 - 2.0 * (q.x * q.x + q.z * q.z)));
    } else {
        result = TC_VEC3(atan2(2.0 * (q.w * q.x + q.y * q.z), 1.0 - 2.0 * (q.x * q.x + q.y * q.y)),
                         asin(sin_pitch),
                         atan2(2.0 * (q.w * q.z + q.x * q.y), 1.0 - 2.0 * (q.y * q.y + q.z * q.z)));
    }
    if (!tc_vec3_is_finite(result)) {
        return false;
    }
    *out_euler_xyz = result;
    return true;
}

TC_C_STATIC_INLINE tc_vec3 tc_quat_to_euler(tc_quat q) {
    tc_vec3 result;
    return tc_quat_try_to_euler(q, 1.0e-12, &result) ? result : TC_VEC3(NAN, NAN, NAN);
}

#ifdef __cplusplus
}
#endif

#endif // TC_QUAT_H
