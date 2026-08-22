// Internal helpers for checked normalization of small fixed-size vectors.
#ifndef TC_CHECKED_NORMALIZATION_H
#define TC_CHECKED_NORMALIZATION_H

#include <math.h>
#include <stdbool.h>
#include <stddef.h>

#ifdef __cplusplus
extern "C" {
#endif

// The public length/norm functions intentionally retain their ordinary
// sqrt(sum-of-squares) overflow semantics. Checked normalization uses a
// separate scale-by-max path because the unit direction can remain
// representable when the magnitude itself does not.
static inline bool
tc_detail_try_normalize_f64_components(const double* input, size_t count, double epsilon, double* output) {
    if (input == NULL || output == NULL || count == 0 || count > 4 || !isfinite(epsilon) || epsilon < 0.0) {
        return false;
    }

    double scale = 0.0;
    for (size_t i = 0; i < count; ++i) {
        if (!isfinite(input[i])) {
            return false;
        }
        scale = fmax(scale, fabs(input[i]));
    }
    if (scale == 0.0) {
        return false;
    }

    double scaled[4];
    double scaled_squared = 0.0;
    for (size_t i = 0; i < count; ++i) {
        scaled[i] = input[i] / scale;
        scaled_squared += scaled[i] * scaled[i];
    }

    const double scaled_length = sqrt(scaled_squared);
    if (!isfinite(scaled_length) || scaled_length == 0.0 || scale <= epsilon / scaled_length) {
        return false;
    }

    double normalized[4];
    for (size_t i = 0; i < count; ++i) {
        normalized[i] = scaled[i] / scaled_length;
        if (!isfinite(normalized[i])) {
            return false;
        }
    }
    for (size_t i = 0; i < count; ++i) {
        output[i] = normalized[i];
    }
    return true;
}

static inline bool
tc_detail_try_normalize_f32_components(const float* input, size_t count, float epsilon, float* output) {
    if (input == NULL || output == NULL || count == 0 || count > 4 || !isfinite(epsilon) || epsilon < 0.0f) {
        return false;
    }

    float scale = 0.0f;
    for (size_t i = 0; i < count; ++i) {
        if (!isfinite(input[i])) {
            return false;
        }
        scale = fmaxf(scale, fabsf(input[i]));
    }
    if (scale == 0.0f) {
        return false;
    }

    float scaled[4];
    float scaled_squared = 0.0f;
    for (size_t i = 0; i < count; ++i) {
        scaled[i] = input[i] / scale;
        scaled_squared += scaled[i] * scaled[i];
    }

    const float scaled_length = sqrtf(scaled_squared);
    if (!isfinite(scaled_length) || scaled_length == 0.0f || scale <= epsilon / scaled_length) {
        return false;
    }

    float normalized[4];
    for (size_t i = 0; i < count; ++i) {
        normalized[i] = scaled[i] / scaled_length;
        if (!isfinite(normalized[i])) {
            return false;
        }
    }
    for (size_t i = 0; i < count; ++i) {
        output[i] = normalized[i];
    }
    return true;
}

#ifdef __cplusplus
}
#endif

#endif // TC_CHECKED_NORMALIZATION_H
