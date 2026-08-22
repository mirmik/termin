#include <geom/tc_vec4.h>

#include "guard_c.h"

#include <float.h>
#include <math.h>

static int equal_vec4(tc_vec4 lhs, tc_vec4 rhs) {
    return lhs.x == rhs.x && lhs.y == rhs.y && lhs.z == rhs.z && lhs.w == rhs.w;
}

GUARD_C_TEST(test_vec4_arithmetic_and_finite_check) {
    const tc_vec4 lhs = TC_VEC4(1.0, 2.0, 3.0, 4.0);
    const tc_vec4 rhs = TC_VEC4(5.0, 6.0, 7.0, 8.0);
    GUARD_C_CHECK(equal_vec4(tc_vec4_add(lhs, rhs), TC_VEC4(6.0, 8.0, 10.0, 12.0)));
    GUARD_C_CHECK(equal_vec4(tc_vec4_scale(lhs, 2.0), TC_VEC4(2.0, 4.0, 6.0, 8.0)));
    GUARD_C_CHECK(tc_vec4_dot(lhs, rhs) == 70.0);
    GUARD_C_CHECK(tc_vec4_is_finite(lhs));
    GUARD_C_CHECK(!tc_vec4_is_finite(TC_VEC4(0.0, 0.0, INFINITY, 0.0)));
    return 0;
}

GUARD_C_TEST(test_vec4_checked_normalization_is_full_range_and_transactional) {
    tc_vec4 output = TC_VEC4(9.0, 8.0, 7.0, 6.0);
    GUARD_C_CHECK(tc_vec4_try_normalized(TC_VEC4(DBL_MAX, DBL_MAX, DBL_MAX, DBL_MAX), 0.0, &output));
    GUARD_C_CHECK(equal_vec4(output, TC_VEC4(0.5, 0.5, 0.5, 0.5)));

    const tc_vec4 sentinel = TC_VEC4(9.0, 8.0, 7.0, 6.0);
    output = sentinel;
    GUARD_C_CHECK(!tc_vec4_try_normalized(tc_vec4_zero(), 1.0e-12, &output));
    GUARD_C_CHECK(equal_vec4(output, sentinel));
    return 0;
}

GUARD_C_TEST(test_vec4_lerp_handles_opposite_full_range_endpoints) {
    const tc_vec4 lhs = TC_VEC4(-DBL_MAX, DBL_MAX, -DBL_MAX, DBL_MAX);
    const tc_vec4 rhs = TC_VEC4(DBL_MAX, -DBL_MAX, DBL_MAX, -DBL_MAX);
    GUARD_C_CHECK(equal_vec4(tc_vec4_lerp(lhs, rhs, 0.0), lhs));
    GUARD_C_CHECK(equal_vec4(tc_vec4_lerp(lhs, rhs, 1.0), rhs));
    const tc_vec4 midpoint = tc_vec4_lerp(lhs, rhs, 0.5);
    GUARD_C_CHECK(tc_vec4_is_finite(midpoint));
    GUARD_C_CHECK(equal_vec4(midpoint, tc_vec4_zero()));
    return 0;
}

int main(int argc, char** argv) {
    GUARD_C_BEGIN_ARGS(argc, argv);
    GUARD_C_RUN(test_vec4_arithmetic_and_finite_check);
    GUARD_C_RUN(test_vec4_checked_normalization_is_full_range_and_transactional);
    GUARD_C_RUN(test_vec4_lerp_handles_opposite_full_range_endpoints);
    return GUARD_C_END();
}
