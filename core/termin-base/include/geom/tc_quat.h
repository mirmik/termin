// tc_quat.h - Quaternion operations
#ifndef TC_QUAT_H
#define TC_QUAT_H

#include "geom/tc_quat_detail.h"
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

TC_C_STATIC_INLINE bool tc_quat_try_from_axis_angle(tc_vec3 axis, double angle, double epsilon, tc_quat* out_quat) {
    if (out_quat == NULL) {
        return false;
    }
    const double axis_components[3] = {axis.x, axis.y, axis.z};
    double result[4];
    if (!tc_detail_try_quat_from_axis_angle_f64_components(axis_components, angle, epsilon, result)) {
        return false;
    }
    *out_quat = TC_QUAT(result[0], result[1], result[2], result[3]);
    return true;
}

TC_C_STATIC_INLINE tc_quat tc_quat_from_axis_angle(tc_vec3 axis, double angle) {
    tc_quat result;
    return tc_quat_try_from_axis_angle(axis, angle, 1.0e-12, &result) ? result : TC_QUAT(NAN, NAN, NAN, NAN);
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
    if (out_normalized == NULL) {
        return false;
    }
    const double input[4] = {q.x, q.y, q.z, q.w};
    double output[4];
    if (!tc_detail_try_normalize_f64_components(input, 4, epsilon, output)) {
        return false;
    }
    *out_normalized = TC_QUAT(output[0], output[1], output[2], output[3]);
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
    if (out_inverse == NULL) {
        return false;
    }
    const double input[4] = {q.x, q.y, q.z, q.w};
    double result[4];
    if (!tc_detail_try_inverse_quat_f64_components(input, epsilon, result)) {
        return false;
    }
    *out_inverse = TC_QUAT(result[0], result[1], result[2], result[3]);
    return true;
}

TC_C_STATIC_INLINE tc_quat tc_quat_inverse(tc_quat q) {
    tc_quat result;
    return tc_quat_try_inverse(q, 1.0e-12, &result) ? result : tc_quat_non_finite();
}

// ============================================================================
// Fast rotation by a finite unit quaternion. tc_quat is a raw xyzw value, so
// callers with uncertain input must use the checked functions below.
// ============================================================================

TC_C_STATIC_INLINE tc_vec3 tc_quat_rotate(tc_quat q, tc_vec3 v) {
    // Unit-quaternion form of q * v * q^-1.
    tc_vec3 u = TC_VEC3(q.x, q.y, q.z);
    double s = q.w;

    tc_vec3 uv = tc_vec3_cross(u, v);
    tc_vec3 uuv = tc_vec3_cross(u, uv);

    return tc_vec3_add(v, tc_vec3_add(tc_vec3_scale(uv, 2.0 * s), tc_vec3_scale(uuv, 2.0)));
}

TC_C_STATIC_INLINE tc_vec3 tc_quat_inverse_rotate(tc_quat q, tc_vec3 v) {
    return tc_quat_rotate(tc_quat_conjugate(q), v);
}

TC_C_STATIC_INLINE bool tc_quat_try_rotate(tc_quat q, tc_vec3 v, double epsilon, tc_vec3* out_rotated) {
    if (out_rotated == NULL) {
        return false;
    }
    tc_quat unit;
    if (!tc_quat_try_normalized(q, epsilon, &unit)) {
        return false;
    }
    const double quat[4] = {unit.x, unit.y, unit.z, unit.w};
    const double vector[3] = {v.x, v.y, v.z};
    double result[3];
    if (!tc_detail_try_rotate_unit_quat_f64_components(quat, vector, false, result)) {
        return false;
    }
    *out_rotated = TC_VEC3(result[0], result[1], result[2]);
    return true;
}

TC_C_STATIC_INLINE bool tc_quat_try_inverse_rotate(tc_quat q, tc_vec3 v, double epsilon, tc_vec3* out_rotated) {
    if (out_rotated == NULL) {
        return false;
    }
    tc_quat unit;
    if (!tc_quat_try_normalized(q, epsilon, &unit)) {
        return false;
    }
    const double quat[4] = {unit.x, unit.y, unit.z, unit.w};
    const double vector[3] = {v.x, v.y, v.z};
    double result[3];
    if (!tc_detail_try_rotate_unit_quat_f64_components(quat, vector, true, result)) {
        return false;
    }
    *out_rotated = TC_VEC3(result[0], result[1], result[2]);
    return true;
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
    if (!isfinite(t) || !tc_quat_try_normalized(a, 1.0e-12, &from) || !tc_quat_try_normalized(b, 1.0e-12, &to)) {
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

// Fast row-major 3x3 conversion. q must be finite and unit.
TC_C_STATIC_INLINE void tc_quat_to_matrix3_row_major(tc_quat q, double* out_row_major_9) {
    const double quat[4] = {q.x, q.y, q.z, q.w};
    tc_detail_unit_quat_to_matrix3_row_major_f64(quat, out_row_major_9);
}

TC_C_STATIC_INLINE bool tc_quat_try_to_matrix3_row_major(tc_quat q, double epsilon, double* out_row_major_9) {
    if (out_row_major_9 == NULL) {
        return false;
    }
    tc_quat unit;
    if (!tc_quat_try_normalized(q, epsilon, &unit)) {
        return false;
    }
    double result[9];
    tc_quat_to_matrix3_row_major(unit, result);
    for (int i = 0; i < 9; ++i) {
        if (!isfinite(result[i])) {
            return false;
        }
    }
    for (int i = 0; i < 9; ++i) {
        out_row_major_9[i] = result[i];
    }
    return true;
}

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
