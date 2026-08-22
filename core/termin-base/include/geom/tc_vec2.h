// tc_vec2.h - 2D vector operations
#ifndef TC_VEC2_H
#define TC_VEC2_H

#include <math.h>
#include <stddef.h>
#include <tcbase/tc_types.h>

#ifdef __cplusplus
#define TC_VEC2(x, y)                                                                                                  \
    tc_vec2 {                                                                                                          \
        x, y                                                                                                           \
    }
#else
#define TC_VEC2(x, y)                                                                                                  \
    (tc_vec2) {                                                                                                        \
        x, y                                                                                                           \
    }
#endif

#ifdef __cplusplus
extern "C" {
#endif

TC_C_STATIC_INLINE tc_vec2 tc_vec2_new(double x, double y) {
    return TC_VEC2(x, y);
}

TC_C_STATIC_INLINE tc_vec2 tc_vec2_zero(void) {
    return TC_VEC2(0.0, 0.0);
}

TC_C_STATIC_INLINE tc_vec2 tc_vec2_unit_x(void) {
    return TC_VEC2(1.0, 0.0);
}

TC_C_STATIC_INLINE tc_vec2 tc_vec2_unit_y(void) {
    return TC_VEC2(0.0, 1.0);
}

TC_C_STATIC_INLINE tc_vec2f tc_vec2_to_float(tc_vec2 v) {
    tc_vec2f result = {(float)v.x, (float)v.y};
    return result;
}

TC_C_STATIC_INLINE tc_vec2 tc_vec2_add(tc_vec2 a, tc_vec2 b) {
    return TC_VEC2(a.x + b.x, a.y + b.y);
}

TC_C_STATIC_INLINE tc_vec2 tc_vec2_sub(tc_vec2 a, tc_vec2 b) {
    return TC_VEC2(a.x - b.x, a.y - b.y);
}

TC_C_STATIC_INLINE tc_vec2 tc_vec2_mul(tc_vec2 a, tc_vec2 b) {
    return TC_VEC2(a.x * b.x, a.y * b.y);
}

TC_C_STATIC_INLINE tc_vec2 tc_vec2_div(tc_vec2 a, tc_vec2 b) {
    return TC_VEC2(a.x / b.x, a.y / b.y);
}

TC_C_STATIC_INLINE tc_vec2 tc_vec2_scale(tc_vec2 v, double s) {
    return TC_VEC2(v.x * s, v.y * s);
}

TC_C_STATIC_INLINE tc_vec2 tc_vec2_neg(tc_vec2 v) {
    return TC_VEC2(-v.x, -v.y);
}

TC_C_STATIC_INLINE tc_vec2 tc_vec2_min(tc_vec2 a, tc_vec2 b) {
    return TC_VEC2(fmin(a.x, b.x), fmin(a.y, b.y));
}

TC_C_STATIC_INLINE tc_vec2 tc_vec2_max(tc_vec2 a, tc_vec2 b) {
    return TC_VEC2(fmax(a.x, b.x), fmax(a.y, b.y));
}

TC_C_STATIC_INLINE tc_vec2 tc_vec2_clamp(tc_vec2 v, tc_vec2 minimum, tc_vec2 maximum) {
    return TC_VEC2(fmin(fmax(v.x, minimum.x), maximum.x), fmin(fmax(v.y, minimum.y), maximum.y));
}

TC_C_STATIC_INLINE tc_vec2 tc_vec2_abs(tc_vec2 v) {
    return TC_VEC2(fabs(v.x), fabs(v.y));
}

TC_C_STATIC_INLINE double tc_vec2_min_component(tc_vec2 v) {
    return fmin(v.x, v.y);
}

TC_C_STATIC_INLINE double tc_vec2_max_component(tc_vec2 v) {
    return fmax(v.x, v.y);
}

TC_C_STATIC_INLINE double tc_vec2_dot(tc_vec2 a, tc_vec2 b) {
    return a.x * b.x + a.y * b.y;
}

TC_C_STATIC_INLINE double tc_vec2_cross(tc_vec2 a, tc_vec2 b) {
    return a.x * b.y - a.y * b.x;
}

TC_C_STATIC_INLINE double tc_vec2_length_sq(tc_vec2 v) {
    return v.x * v.x + v.y * v.y;
}

TC_C_STATIC_INLINE double tc_vec2_length(tc_vec2 v) {
    return sqrt(tc_vec2_length_sq(v));
}

TC_C_STATIC_INLINE bool tc_vec2_is_finite(tc_vec2 v) {
    return isfinite(v.x) && isfinite(v.y);
}

TC_C_STATIC_INLINE bool tc_vec2_try_normalized(tc_vec2 v, double epsilon, tc_vec2* out_normalized) {
    double length = hypot(v.x, v.y);
    if (out_normalized == NULL || !tc_vec2_is_finite(v) || !isfinite(length) || !isfinite(epsilon) || epsilon < 0.0 ||
        length <= epsilon) {
        return false;
    }
    // Component-wise division avoids a subnormal reciprocal that FTZ/DAZ modes
    // may flush to zero for large finite vectors.
    tc_vec2 normalized = TC_VEC2(v.x / length, v.y / length);
    if (!tc_vec2_is_finite(normalized)) {
        return false;
    }
    *out_normalized = normalized;
    return true;
}

TC_C_STATIC_INLINE tc_vec2 tc_vec2_normalized_or(tc_vec2 v, tc_vec2 fallback, double epsilon) {
    tc_vec2 result;
    return tc_vec2_try_normalized(v, epsilon, &result) ? result : fallback;
}

TC_C_STATIC_INLINE tc_vec2 tc_vec2_lerp(tc_vec2 a, tc_vec2 b, double t) {
    return TC_VEC2(a.x + (b.x - a.x) * t, a.y + (b.y - a.y) * t);
}

#ifdef __cplusplus
}
#endif

#endif // TC_VEC2_H
