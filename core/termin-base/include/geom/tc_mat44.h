// tc_mat44.h - C helpers for the ABI-friendly column-major 4x4 matrix type
#ifndef TC_MAT44_H
#define TC_MAT44_H

#include <math.h>
#include <stddef.h>
#include <tcbase/tc_types.h>

#ifdef __cplusplus
extern "C" {
#endif

TC_C_STATIC_INLINE tc_mat44 tc_mat44_zero(void) {
    const tc_mat44 result = {{0.0}};
    return result;
}

TC_C_STATIC_INLINE tc_mat44 tc_mat44_identity(void) {
    tc_mat44 result = tc_mat44_zero();
    result.m[0] = 1.0;
    result.m[5] = 1.0;
    result.m[10] = 1.0;
    result.m[15] = 1.0;
    return result;
}

TC_C_STATIC_INLINE bool tc_mat44_is_finite(tc_mat44 matrix) {
    for (size_t index = 0; index < 16; ++index) {
        if (!isfinite(matrix.m[index])) {
            return false;
        }
    }
    return true;
}

#ifdef __cplusplus
}
#endif

#endif // TC_MAT44_H
