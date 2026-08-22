// tc_vec2f.h - Allocation-free 2D float vector operations.
#ifndef TC_VEC2F_H
#define TC_VEC2F_H

#include <math.h>
#include <stddef.h>
#include <tcbase/tc_types.h>

#ifdef __cplusplus
#define TC_VEC2F(x_, y_)                                                                                               \
    tc_vec2f {                                                                                                         \
        x_, y_                                                                                                         \
    }
#else
#define TC_VEC2F(x_, y_)                                                                                               \
    (tc_vec2f) {                                                                                                       \
        x_, y_                                                                                                         \
    }
#endif

#ifdef __cplusplus
extern "C" {
#endif

TC_C_STATIC_INLINE tc_vec2f tc_vec2f_new(float x, float y) {
    return TC_VEC2F(x, y);
}

TC_C_STATIC_INLINE tc_vec2f tc_vec2f_zero(void) {
    return TC_VEC2F(0.0f, 0.0f);
}

TC_C_STATIC_INLINE tc_vec2f tc_vec2f_unit_x(void) {
    return TC_VEC2F(1.0f, 0.0f);
}

TC_C_STATIC_INLINE tc_vec2f tc_vec2f_unit_y(void) {
    return TC_VEC2F(0.0f, 1.0f);
}

TC_C_STATIC_INLINE tc_vec2 tc_vec2f_to_double(tc_vec2f v) {
    tc_vec2 result = {(double)v.x, (double)v.y};
    return result;
}

TC_C_STATIC_INLINE tc_vec2f tc_vec2f_add(tc_vec2f a, tc_vec2f b) {
    return TC_VEC2F(a.x + b.x, a.y + b.y);
}

TC_C_STATIC_INLINE tc_vec2f tc_vec2f_sub(tc_vec2f a, tc_vec2f b) {
    return TC_VEC2F(a.x - b.x, a.y - b.y);
}

TC_C_STATIC_INLINE tc_vec2f tc_vec2f_mul(tc_vec2f a, tc_vec2f b) {
    return TC_VEC2F(a.x * b.x, a.y * b.y);
}

TC_C_STATIC_INLINE tc_vec2f tc_vec2f_div(tc_vec2f a, tc_vec2f b) {
    return TC_VEC2F(a.x / b.x, a.y / b.y);
}

TC_C_STATIC_INLINE tc_vec2f tc_vec2f_scale(tc_vec2f v, float scale) {
    return TC_VEC2F(v.x * scale, v.y * scale);
}

TC_C_STATIC_INLINE tc_vec2f tc_vec2f_neg(tc_vec2f v) {
    return TC_VEC2F(-v.x, -v.y);
}

TC_C_STATIC_INLINE tc_vec2f tc_vec2f_min(tc_vec2f a, tc_vec2f b) {
    return TC_VEC2F(fminf(a.x, b.x), fminf(a.y, b.y));
}

TC_C_STATIC_INLINE tc_vec2f tc_vec2f_max(tc_vec2f a, tc_vec2f b) {
    return TC_VEC2F(fmaxf(a.x, b.x), fmaxf(a.y, b.y));
}

TC_C_STATIC_INLINE tc_vec2f tc_vec2f_clamp(tc_vec2f v, tc_vec2f minimum, tc_vec2f maximum) {
    return TC_VEC2F(fminf(fmaxf(v.x, minimum.x), maximum.x), fminf(fmaxf(v.y, minimum.y), maximum.y));
}

TC_C_STATIC_INLINE tc_vec2f tc_vec2f_abs(tc_vec2f v) {
    return TC_VEC2F(fabsf(v.x), fabsf(v.y));
}

TC_C_STATIC_INLINE float tc_vec2f_min_component(tc_vec2f v) {
    return fminf(v.x, v.y);
}

TC_C_STATIC_INLINE float tc_vec2f_max_component(tc_vec2f v) {
    return fmaxf(v.x, v.y);
}

TC_C_STATIC_INLINE float tc_vec2f_dot(tc_vec2f a, tc_vec2f b) {
    return a.x * b.x + a.y * b.y;
}

TC_C_STATIC_INLINE float tc_vec2f_cross(tc_vec2f a, tc_vec2f b) {
    return a.x * b.y - a.y * b.x;
}

TC_C_STATIC_INLINE float tc_vec2f_length_sq(tc_vec2f v) {
    return tc_vec2f_dot(v, v);
}

TC_C_STATIC_INLINE float tc_vec2f_length(tc_vec2f v) {
    return sqrtf(tc_vec2f_length_sq(v));
}

TC_C_STATIC_INLINE bool tc_vec2f_is_finite(tc_vec2f v) {
    return isfinite(v.x) && isfinite(v.y);
}

TC_C_STATIC_INLINE bool tc_vec2f_try_normalized(tc_vec2f v, float epsilon, tc_vec2f* out_normalized) {
    float length = hypotf(v.x, v.y);
    if (out_normalized == NULL || !tc_vec2f_is_finite(v) || !isfinite(length) || !isfinite(epsilon) ||
        epsilon < 0.0f || length <= epsilon) {
        return false;
    }
    // Component-wise division avoids a subnormal reciprocal that FTZ/DAZ modes
    // may flush to zero for large finite vectors.
    tc_vec2f normalized = TC_VEC2F(v.x / length, v.y / length);
    if (!tc_vec2f_is_finite(normalized)) {
        return false;
    }
    *out_normalized = normalized;
    return true;
}

TC_C_STATIC_INLINE tc_vec2f tc_vec2f_normalized_or(tc_vec2f v, tc_vec2f fallback, float epsilon) {
    tc_vec2f result;
    return tc_vec2f_try_normalized(v, epsilon, &result) ? result : fallback;
}

#ifdef __cplusplus
}
#endif

#endif // TC_VEC2F_H
