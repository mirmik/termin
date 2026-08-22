/// @file tc_vec4.h
/// @brief C API for the canonical double-precision four-component vector.

#ifndef TC_VEC4_H
#define TC_VEC4_H

#include <geom/tc_checked_normalization.h>
#include <geom/tc_lerp_detail.h>
#include <math.h>
#include <stddef.h>
#include <tcbase/tc_types.h>

#ifdef __cplusplus
#define TC_VEC4(x, y, z, w)                                                                                           \
    tc_vec4 {                                                                                                         \
        x, y, z, w                                                                                                    \
    }
#else
#define TC_VEC4(x, y, z, w)                                                                                           \
    (tc_vec4) {                                                                                                       \
        x, y, z, w                                                                                                    \
    }
#endif

#ifdef __cplusplus
extern "C" {
#endif

TC_C_STATIC_INLINE tc_vec4 tc_vec4_new(double x, double y, double z, double w) {
    return TC_VEC4(x, y, z, w);
}

TC_C_STATIC_INLINE tc_vec4 tc_vec4_zero(void) {
    return TC_VEC4(0.0, 0.0, 0.0, 0.0);
}

TC_C_STATIC_INLINE tc_vec4 tc_vec4_one(void) {
    return TC_VEC4(1.0, 1.0, 1.0, 1.0);
}

TC_C_STATIC_INLINE tc_vec4 tc_vec4_unit_x(void) {
    return TC_VEC4(1.0, 0.0, 0.0, 0.0);
}

TC_C_STATIC_INLINE tc_vec4 tc_vec4_unit_y(void) {
    return TC_VEC4(0.0, 1.0, 0.0, 0.0);
}

TC_C_STATIC_INLINE tc_vec4 tc_vec4_unit_z(void) {
    return TC_VEC4(0.0, 0.0, 1.0, 0.0);
}

TC_C_STATIC_INLINE tc_vec4 tc_vec4_unit_w(void) {
    return TC_VEC4(0.0, 0.0, 0.0, 1.0);
}

TC_C_STATIC_INLINE tc_vec4 tc_vec4_add(tc_vec4 a, tc_vec4 b) {
    return TC_VEC4(a.x + b.x, a.y + b.y, a.z + b.z, a.w + b.w);
}

TC_C_STATIC_INLINE tc_vec4 tc_vec4_sub(tc_vec4 a, tc_vec4 b) {
    return TC_VEC4(a.x - b.x, a.y - b.y, a.z - b.z, a.w - b.w);
}

TC_C_STATIC_INLINE tc_vec4 tc_vec4_mul(tc_vec4 a, tc_vec4 b) {
    return TC_VEC4(a.x * b.x, a.y * b.y, a.z * b.z, a.w * b.w);
}

TC_C_STATIC_INLINE tc_vec4 tc_vec4_div(tc_vec4 a, tc_vec4 b) {
    return TC_VEC4(a.x / b.x, a.y / b.y, a.z / b.z, a.w / b.w);
}

TC_C_STATIC_INLINE tc_vec4 tc_vec4_scale(tc_vec4 value, double scalar) {
    return TC_VEC4(value.x * scalar, value.y * scalar, value.z * scalar, value.w * scalar);
}

TC_C_STATIC_INLINE tc_vec4 tc_vec4_neg(tc_vec4 value) {
    return TC_VEC4(-value.x, -value.y, -value.z, -value.w);
}

TC_C_STATIC_INLINE double tc_vec4_dot(tc_vec4 a, tc_vec4 b) {
    return a.x * b.x + a.y * b.y + a.z * b.z + a.w * b.w;
}

TC_C_STATIC_INLINE double tc_vec4_length_sq(tc_vec4 value) {
    return tc_vec4_dot(value, value);
}

TC_C_STATIC_INLINE double tc_vec4_length(tc_vec4 value) {
    return hypot(hypot(value.x, value.y), hypot(value.z, value.w));
}

TC_C_STATIC_INLINE bool tc_vec4_is_finite(tc_vec4 value) {
    return isfinite(value.x) && isfinite(value.y) && isfinite(value.z) && isfinite(value.w);
}

TC_C_STATIC_INLINE bool tc_vec4_try_normalized(tc_vec4 value, double epsilon, tc_vec4* out_normalized) {
    if (out_normalized == NULL) {
        return false;
    }
    const double input[4] = {value.x, value.y, value.z, value.w};
    double output[4];
    if (!tc_detail_try_normalize_f64_components(input, 4, epsilon, output)) {
        return false;
    }
    *out_normalized = TC_VEC4(output[0], output[1], output[2], output[3]);
    return true;
}

TC_C_STATIC_INLINE tc_vec4 tc_vec4_normalized_or(tc_vec4 value, tc_vec4 fallback, double epsilon) {
    tc_vec4 result;
    return tc_vec4_try_normalized(value, epsilon, &result) ? result : fallback;
}

/// Component-wise interpolation. Finite endpoints remain representable across
/// the full double range for t in [0, 1].
TC_C_STATIC_INLINE tc_vec4 tc_vec4_lerp(tc_vec4 a, tc_vec4 b, double t) {
    return TC_VEC4(tc_detail_lerp_f64_component(a.x, b.x, t),
                   tc_detail_lerp_f64_component(a.y, b.y, t),
                   tc_detail_lerp_f64_component(a.z, b.z, t),
                   tc_detail_lerp_f64_component(a.w, b.w, t));
}

TC_C_STATIC_INLINE bool tc_vec4_eq(tc_vec4 a, tc_vec4 b) {
    return a.x == b.x && a.y == b.y && a.z == b.z && a.w == b.w;
}

TC_C_STATIC_INLINE bool tc_vec4_near(tc_vec4 a, tc_vec4 b, double epsilon) {
    return fabs(a.x - b.x) < epsilon && fabs(a.y - b.y) < epsilon && fabs(a.z - b.z) < epsilon &&
           fabs(a.w - b.w) < epsilon;
}

#ifdef __cplusplus
}
#endif

#endif // TC_VEC4_H
