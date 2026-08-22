#include <geom/tc_vec3f.h>

#include "guard_c.h"

#include <float.h>
#include <math.h>

static int equal_vec3f(tc_vec3f lhs, tc_vec3f rhs) {
    return lhs.x == rhs.x && lhs.y == rhs.y && lhs.z == rhs.z;
}

static void check_failure_is_transactional(tc_vec3f lhs, tc_vec3f rhs) {
    const tc_vec3f sentinel = TC_VEC3F(9.0f, 8.0f, 7.0f);
    tc_vec3f output = sentinel;
    GUARD_C_CHECK(!tc_vec3f_try_cwise_product(lhs, rhs, &output));
    GUARD_C_CHECK(equal_vec3f(output, sentinel));
}

GUARD_C_TEST(test_cwise_product_success_and_zero_components) {
    tc_vec3f product = tc_vec3f_zero();
    GUARD_C_CHECK(tc_vec3f_try_cwise_product(
        TC_VEC3F(2.0f, -3.0f, 4.0f), TC_VEC3F(5.0f, -0.5f, 0.25f), &product));
    GUARD_C_CHECK(equal_vec3f(product, TC_VEC3F(10.0f, 1.5f, 1.0f)));

    GUARD_C_CHECK(tc_vec3f_try_cwise_product(
        TC_VEC3F(0.0f, -0.0f, 5.0f), TC_VEC3F(FLT_MAX, -2.0f, 0.0f), &product));
    GUARD_C_CHECK(product.x == 0.0f && product.y == 0.0f && product.z == 0.0f);
    return 0;
}

GUARD_C_TEST(test_cwise_product_rejects_non_finite_inputs_transactionally) {
    check_failure_is_transactional(TC_VEC3F(NAN, 1.0f, 1.0f), tc_vec3f_one());
    check_failure_is_transactional(tc_vec3f_one(), TC_VEC3F(1.0f, INFINITY, 1.0f));
    return 0;
}

GUARD_C_TEST(test_cwise_product_rejects_overflow_transactionally) {
    check_failure_is_transactional(TC_VEC3F(FLT_MAX, 1.0f, 1.0f), TC_VEC3F(2.0f, 1.0f, 1.0f));
    return 0;
}

GUARD_C_TEST(test_cwise_product_rejects_nonzero_to_zero_underflow_transactionally) {
    check_failure_is_transactional(TC_VEC3F(FLT_MIN, 1.0f, 1.0f), TC_VEC3F(FLT_MIN, 1.0f, 1.0f));
    return 0;
}

GUARD_C_TEST(test_cwise_product_rejects_null_output) {
    GUARD_C_CHECK(!tc_vec3f_try_cwise_product(tc_vec3f_one(), tc_vec3f_one(), NULL));
    return 0;
}

int main(int argc, char** argv) {
    GUARD_C_BEGIN_ARGS(argc, argv);
    GUARD_C_RUN(test_cwise_product_success_and_zero_components);
    GUARD_C_RUN(test_cwise_product_rejects_non_finite_inputs_transactionally);
    GUARD_C_RUN(test_cwise_product_rejects_overflow_transactionally);
    GUARD_C_RUN(test_cwise_product_rejects_nonzero_to_zero_underflow_transactionally);
    GUARD_C_RUN(test_cwise_product_rejects_null_output);
    return GUARD_C_END();
}
