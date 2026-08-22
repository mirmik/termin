// Internal full-range scalar interpolation shared by the C and C++ vector APIs.
#ifndef TC_LERP_DETAIL_H
#define TC_LERP_DETAIL_H

#ifdef __cplusplus
extern "C" {
#endif

static inline double tc_detail_lerp_f64_component(double a, double b, double t) {
    if (t == 0.0) {
        return a;
    }
    if (t == 1.0) {
        return b;
    }
    // b - a can overflow for opposite-signed endpoints even though every
    // interpolation result is representable. Weighted endpoints avoid that
    // intermediate; same-signed endpoints keep the more accurate delta form.
    if ((a <= 0.0 && b >= 0.0) || (a >= 0.0 && b <= 0.0)) {
        return (1.0 - t) * a + t * b;
    }
    return a + (b - a) * t;
}

#ifdef __cplusplus
}
#endif

#endif // TC_LERP_DETAIL_H
