// tc_vec3f.h - Allocation-free 3D float vector operations.
#ifndef TC_VEC3F_H
#define TC_VEC3F_H

#include <geom/tc_checked_normalization.h>
#include <math.h>
#include <stddef.h>
#include <tcbase/tc_types.h>

#ifdef __cplusplus
#define TC_VEC3F(x_, y_, z_)                                                                                           \
    tc_vec3f {                                                                                                         \
        x_, y_, z_                                                                                                     \
    }
#else
#define TC_VEC3F(x_, y_, z_)                                                                                           \
    (tc_vec3f) {                                                                                                       \
        x_, y_, z_                                                                                                     \
    }
#endif

#ifdef __cplusplus
extern "C" {
#endif

TC_C_STATIC_INLINE tc_vec3f tc_vec3f_new(float x, float y, float z) {
    return TC_VEC3F(x, y, z);
}

TC_C_STATIC_INLINE tc_vec3f tc_vec3f_zero(void) {
    return TC_VEC3F(0.0f, 0.0f, 0.0f);
}

TC_C_STATIC_INLINE tc_vec3f tc_vec3f_one(void) {
    return TC_VEC3F(1.0f, 1.0f, 1.0f);
}

TC_C_STATIC_INLINE tc_vec3f tc_vec3f_unit_x(void) {
    return TC_VEC3F(1.0f, 0.0f, 0.0f);
}

TC_C_STATIC_INLINE tc_vec3f tc_vec3f_unit_y(void) {
    return TC_VEC3F(0.0f, 1.0f, 0.0f);
}

TC_C_STATIC_INLINE tc_vec3f tc_vec3f_unit_z(void) {
    return TC_VEC3F(0.0f, 0.0f, 1.0f);
}

TC_C_STATIC_INLINE tc_vec3 tc_vec3f_to_double(tc_vec3f v) {
    tc_vec3 result = {(double)v.x, (double)v.y, (double)v.z};
    return result;
}

TC_C_STATIC_INLINE tc_vec3f tc_vec3f_add(tc_vec3f a, tc_vec3f b) {
    return TC_VEC3F(a.x + b.x, a.y + b.y, a.z + b.z);
}

TC_C_STATIC_INLINE tc_vec3f tc_vec3f_sub(tc_vec3f a, tc_vec3f b) {
    return TC_VEC3F(a.x - b.x, a.y - b.y, a.z - b.z);
}

TC_C_STATIC_INLINE tc_vec3f tc_vec3f_mul(tc_vec3f a, tc_vec3f b) {
    return TC_VEC3F(a.x * b.x, a.y * b.y, a.z * b.z);
}

TC_C_STATIC_INLINE tc_vec3f tc_vec3f_div(tc_vec3f a, tc_vec3f b) {
    return TC_VEC3F(a.x / b.x, a.y / b.y, a.z / b.z);
}

TC_C_STATIC_INLINE tc_vec3f tc_vec3f_scale(tc_vec3f v, float scale) {
    return TC_VEC3F(v.x * scale, v.y * scale, v.z * scale);
}

TC_C_STATIC_INLINE tc_vec3f tc_vec3f_neg(tc_vec3f v) {
    return TC_VEC3F(-v.x, -v.y, -v.z);
}

TC_C_STATIC_INLINE tc_vec3f tc_vec3f_min(tc_vec3f a, tc_vec3f b) {
    return TC_VEC3F(fminf(a.x, b.x), fminf(a.y, b.y), fminf(a.z, b.z));
}

TC_C_STATIC_INLINE tc_vec3f tc_vec3f_max(tc_vec3f a, tc_vec3f b) {
    return TC_VEC3F(fmaxf(a.x, b.x), fmaxf(a.y, b.y), fmaxf(a.z, b.z));
}

TC_C_STATIC_INLINE tc_vec3f tc_vec3f_clamp(tc_vec3f v, tc_vec3f minimum, tc_vec3f maximum) {
    return TC_VEC3F(fminf(fmaxf(v.x, minimum.x), maximum.x),
                    fminf(fmaxf(v.y, minimum.y), maximum.y),
                    fminf(fmaxf(v.z, minimum.z), maximum.z));
}

TC_C_STATIC_INLINE tc_vec3f tc_vec3f_abs(tc_vec3f v) {
    return TC_VEC3F(fabsf(v.x), fabsf(v.y), fabsf(v.z));
}

TC_C_STATIC_INLINE float tc_vec3f_min_component(tc_vec3f v) {
    return fminf(v.x, fminf(v.y, v.z));
}

TC_C_STATIC_INLINE float tc_vec3f_max_component(tc_vec3f v) {
    return fmaxf(v.x, fmaxf(v.y, v.z));
}

TC_C_STATIC_INLINE float tc_vec3f_dot(tc_vec3f a, tc_vec3f b) {
    return a.x * b.x + a.y * b.y + a.z * b.z;
}

TC_C_STATIC_INLINE tc_vec3f tc_vec3f_cross(tc_vec3f a, tc_vec3f b) {
    return TC_VEC3F(a.y * b.z - a.z * b.y, a.z * b.x - a.x * b.z, a.x * b.y - a.y * b.x);
}

TC_C_STATIC_INLINE float tc_vec3f_length_sq(tc_vec3f v) {
    return tc_vec3f_dot(v, v);
}

TC_C_STATIC_INLINE float tc_vec3f_length(tc_vec3f v) {
    return sqrtf(tc_vec3f_length_sq(v));
}

TC_C_STATIC_INLINE bool tc_vec3f_is_finite(tc_vec3f v) {
    return isfinite(v.x) && isfinite(v.y) && isfinite(v.z);
}

// Computes a finite component-wise product without losing a non-zero
// component entirely to underflow. On failure, out_product is unchanged.
TC_C_STATIC_INLINE bool tc_vec3f_try_cwise_product(tc_vec3f lhs, tc_vec3f rhs, tc_vec3f* out_product) {
    if (out_product == NULL || !tc_vec3f_is_finite(lhs) || !tc_vec3f_is_finite(rhs)) {
        return false;
    }

    tc_vec3f product = tc_vec3f_mul(lhs, rhs);
    if (!tc_vec3f_is_finite(product) || (lhs.x != 0.0f && rhs.x != 0.0f && product.x == 0.0f) ||
        (lhs.y != 0.0f && rhs.y != 0.0f && product.y == 0.0f) ||
        (lhs.z != 0.0f && rhs.z != 0.0f && product.z == 0.0f)) {
        return false;
    }

    *out_product = product;
    return true;
}

TC_C_STATIC_INLINE bool tc_vec3f_try_normalized(tc_vec3f v, float epsilon, tc_vec3f* out_normalized) {
    if (out_normalized == NULL) {
        return false;
    }
    const float input[3] = {v.x, v.y, v.z};
    float output[3];
    if (!tc_detail_try_normalize_f32_components(input, 3, epsilon, output)) {
        return false;
    }
    *out_normalized = TC_VEC3F(output[0], output[1], output[2]);
    return true;
}

TC_C_STATIC_INLINE tc_vec3f tc_vec3f_normalized_or(tc_vec3f v, tc_vec3f fallback, float epsilon) {
    tc_vec3f result;
    return tc_vec3f_try_normalized(v, epsilon, &result) ? result : fallback;
}

#ifdef __cplusplus
}
#endif

#endif // TC_VEC3F_H
