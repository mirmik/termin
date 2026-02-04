// tc_vec3.h - 3D Vector operations
#ifndef TC_VEC3_H
#define TC_VEC3_H

#include "tc_types.h"
#include <math.h>

// C/C++ compatible struct initialization
#ifdef __cplusplus
    #define TC_VEC3(x, y, z) tc_vec3{x, y, z}
#else
    #define TC_VEC3(x, y, z) (tc_vec3){x, y, z}
#endif

#ifdef __cplusplus
extern "C" {
#endif

// ============================================================================
// Constructors
// ============================================================================

static inline tc_vec3 tc_vec3_new(double x, double y, double z) {
    return TC_VEC3(x, y, z);
}

static inline tc_vec3 tc_vec3_zero(void) {
    return TC_VEC3(0, 0, 0);
}

static inline tc_vec3 tc_vec3_one(void) {
    return TC_VEC3(1, 1, 1);
}

static inline tc_vec3 tc_vec3_unit_x(void) { return TC_VEC3(1, 0, 0); }
static inline tc_vec3 tc_vec3_unit_y(void) { return TC_VEC3(0, 1, 0); }
static inline tc_vec3 tc_vec3_unit_z(void) { return TC_VEC3(0, 0, 1); }

// ============================================================================
// Arithmetic
// ============================================================================

static inline tc_vec3 tc_vec3_add(tc_vec3 a, tc_vec3 b) {
    return TC_VEC3(a.x + b.x, a.y + b.y, a.z + b.z);
}

static inline tc_vec3 tc_vec3_sub(tc_vec3 a, tc_vec3 b) {
    return TC_VEC3(a.x - b.x, a.y - b.y, a.z - b.z);
}

static inline tc_vec3 tc_vec3_mul(tc_vec3 a, tc_vec3 b) {
    return TC_VEC3(a.x * b.x, a.y * b.y, a.z * b.z);
}

static inline tc_vec3 tc_vec3_div(tc_vec3 a, tc_vec3 b) {
    return TC_VEC3(a.x / b.x, a.y / b.y, a.z / b.z);
}

static inline tc_vec3 tc_vec3_scale(tc_vec3 v, double s) {
    return TC_VEC3(v.x * s, v.y * s, v.z * s);
}

static inline tc_vec3 tc_vec3_neg(tc_vec3 v) {
    return TC_VEC3(-v.x, -v.y, -v.z);
}

// ============================================================================
// Products
// ============================================================================

static inline double tc_vec3_dot(tc_vec3 a, tc_vec3 b) {
    return a.x * b.x + a.y * b.y + a.z * b.z;
}

static inline tc_vec3 tc_vec3_cross(tc_vec3 a, tc_vec3 b) {
    return TC_VEC3(
        a.y * b.z - a.z * b.y,
        a.z * b.x - a.x * b.z,
        a.x * b.y - a.y * b.x
    );
}

// ============================================================================
// Length / Normalization
// ============================================================================

static inline double tc_vec3_length_sq(tc_vec3 v) {
    return v.x * v.x + v.y * v.y + v.z * v.z;
}

static inline double tc_vec3_length(tc_vec3 v) {
    return sqrt(tc_vec3_length_sq(v));
}

static inline tc_vec3 tc_vec3_normalize(tc_vec3 v) {
    double len = tc_vec3_length(v);
    if (len < 1e-12) return tc_vec3_zero();
    return tc_vec3_scale(v, 1.0 / len);
}

static inline double tc_vec3_distance(tc_vec3 a, tc_vec3 b) {
    return tc_vec3_length(tc_vec3_sub(a, b));
}

// ============================================================================
// Interpolation
// ============================================================================

static inline tc_vec3 tc_vec3_lerp(tc_vec3 a, tc_vec3 b, double t) {
    return TC_VEC3(
        a.x + (b.x - a.x) * t,
        a.y + (b.y - a.y) * t,
        a.z + (b.z - a.z) * t
    );
}

// ============================================================================
// Comparison
// ============================================================================

static inline bool tc_vec3_eq(tc_vec3 a, tc_vec3 b) {
    return a.x == b.x && a.y == b.y && a.z == b.z;
}

static inline bool tc_vec3_near(tc_vec3 a, tc_vec3 b, double eps) {
    return fabs(a.x - b.x) < eps && fabs(a.y - b.y) < eps && fabs(a.z - b.z) < eps;
}

#ifdef __cplusplus
}
#endif

#endif // TC_VEC3_H
