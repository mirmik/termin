#include <geom/tc_quat.h>

#include "guard_c.h"

#include <float.h>
#include <math.h>
#include <stddef.h>
#include <string.h>

static int near(double lhs, double rhs, double epsilon) {
    return fabs(lhs - rhs) <= epsilon;
}

static int equal_quat(tc_quat lhs, tc_quat rhs) {
    return lhs.x == rhs.x && lhs.y == rhs.y && lhs.z == rhs.z && lhs.w == rhs.w;
}

static int equal_vec3(tc_vec3 lhs, tc_vec3 rhs) {
    return lhs.x == rhs.x && lhs.y == rhs.y && lhs.z == rhs.z;
}

static int near_quat(tc_quat lhs, tc_quat rhs, double epsilon) {
    return near(lhs.x, rhs.x, epsilon) && near(lhs.y, rhs.y, epsilon) && near(lhs.z, rhs.z, epsilon) &&
           near(lhs.w, rhs.w, epsilon);
}

static int same_rotation(tc_quat lhs, tc_quat rhs, double epsilon) {
    tc_quat lhs_unit;
    tc_quat rhs_unit;
    if (!tc_quat_try_normalized(lhs, 0.0, &lhs_unit) || !tc_quat_try_normalized(rhs, 0.0, &rhs_unit)) {
        return 0;
    }
    return fabs(fabs(tc_quat_dot(lhs_unit, rhs_unit)) - 1.0) <= epsilon;
}

static void check_normalize_failure(tc_quat value, double epsilon) {
    const tc_quat sentinel = TC_QUAT(9.0, 8.0, 7.0, 6.0);
    tc_quat out = sentinel;
    GUARD_C_CHECK(!tc_quat_try_normalized(value, epsilon, &out));
    GUARD_C_CHECK(equal_quat(out, sentinel));
}

static void check_inverse_failure(tc_quat value, double epsilon) {
    const tc_quat sentinel = TC_QUAT(9.0, 8.0, 7.0, 6.0);
    tc_quat out = sentinel;
    GUARD_C_CHECK(!tc_quat_try_inverse(value, epsilon, &out));
    GUARD_C_CHECK(equal_quat(out, sentinel));
}

static void check_slerp_failure(tc_quat a, tc_quat b, double t, double epsilon) {
    const tc_quat sentinel = TC_QUAT(9.0, 8.0, 7.0, 6.0);
    tc_quat out = sentinel;
    GUARD_C_CHECK(!tc_quat_try_slerp(a, b, t, epsilon, &out));
    GUARD_C_CHECK(equal_quat(out, sentinel));
}

static void check_rotate_failure(tc_quat q, tc_vec3 value, double epsilon) {
    const tc_vec3 sentinel = TC_VEC3(9.0, 8.0, 7.0);
    tc_vec3 out = sentinel;
    GUARD_C_CHECK(!tc_quat_try_rotate(q, value, epsilon, &out));
    GUARD_C_CHECK(equal_vec3(out, sentinel));
    GUARD_C_CHECK(!tc_quat_try_inverse_rotate(q, value, epsilon, &out));
    GUARD_C_CHECK(equal_vec3(out, sentinel));
}

static void check_matrix_failure(tc_quat q, double epsilon) {
    double out[9] = {9.0, 8.0, 7.0, 6.0, 5.0, 4.0, 3.0, 2.0, 1.0};
    const double sentinel[9] = {9.0, 8.0, 7.0, 6.0, 5.0, 4.0, 3.0, 2.0, 1.0};
    GUARD_C_CHECK(!tc_quat_try_to_matrix3_row_major(q, epsilon, out));
    for (int i = 0; i < 9; ++i) {
        GUARD_C_CHECK(out[i] == sentinel[i]);
    }
}

GUARD_C_TEST(test_quat_abi_and_raw_products) {
    GUARD_C_CHECK(sizeof(tc_quat) == sizeof(double) * 4);
    GUARD_C_CHECK(offsetof(tc_quat, x) == sizeof(double) * 0);
    GUARD_C_CHECK(offsetof(tc_quat, y) == sizeof(double) * 1);
    GUARD_C_CHECK(offsetof(tc_quat, z) == sizeof(double) * 2);
    GUARD_C_CHECK(offsetof(tc_quat, w) == sizeof(double) * 3);

    const tc_quat a = TC_QUAT(1.0, 2.0, 3.0, 4.0);
    const tc_quat b = TC_QUAT(-2.0, 0.5, 1.5, -1.0);
    GUARD_C_CHECK(tc_quat_dot(a, b) == -0.5);
    GUARD_C_CHECK(tc_quat_norm_squared(a) == 30.0);
    GUARD_C_CHECK(tc_quat_length_sq(a) == tc_quat_norm_squared(a));
    GUARD_C_CHECK(near(tc_quat_norm(a), sqrt(30.0), 1.0e-15));
    GUARD_C_CHECK(tc_quat_length(a) == tc_quat_norm(a));
    GUARD_C_CHECK(tc_quat_is_finite(a));
    GUARD_C_CHECK(!tc_quat_is_finite(TC_QUAT(NAN, 0.0, 0.0, 1.0)));

    GUARD_C_CHECK(isfinite(tc_quat_norm(TC_QUAT(DBL_MAX, 0.0, 0.0, 0.0))));
    GUARD_C_CHECK(isinf(tc_quat_norm_squared(TC_QUAT(DBL_MAX, 0.0, 0.0, 0.0))));
    return 0;
}

GUARD_C_TEST(test_checked_normalization_is_stable_and_transactional) {
    tc_quat normalized = tc_quat_identity();
    GUARD_C_CHECK(tc_quat_try_normalized(TC_QUAT(0.0, 0.0, 0.0, 7.0), 1.0e-12, &normalized));
    GUARD_C_CHECK(equal_quat(normalized, tc_quat_identity()));
    GUARD_C_CHECK(tc_quat_try_normalized(TC_QUAT(DBL_MAX, 0.0, 0.0, 0.0), 0.0, &normalized));
    GUARD_C_CHECK(equal_quat(normalized, TC_QUAT(1.0, 0.0, 0.0, 0.0)));

    const tc_quat partial_underflow = TC_QUAT(2.0e-162, 2.0e-162, 0.0, 0.0);
    GUARD_C_CHECK(tc_quat_try_normalized(partial_underflow, 0.0, &normalized));
    GUARD_C_CHECK(near(tc_quat_norm(normalized), 1.0, 1.0e-15));

    const double smallest_subnormal = nextafter(0.0, 1.0);
    GUARD_C_CHECK(tc_quat_try_normalized(TC_QUAT(smallest_subnormal, 0.0, 0.0, 0.0), 0.0, &normalized));
    GUARD_C_CHECK(equal_quat(normalized, TC_QUAT(1.0, 0.0, 0.0, 0.0)));

    const tc_quat fallback = TC_QUAT(4.0, 3.0, 2.0, 1.0);
    GUARD_C_CHECK(equal_quat(tc_quat_normalized_or(TC_QUAT(0.0, 0.0, 0.0, 0.0), fallback, 0.0), fallback));

    check_normalize_failure(TC_QUAT(0.0, 0.0, 0.0, 0.0), 0.0);
    check_normalize_failure(TC_QUAT(NAN, 0.0, 0.0, 1.0), 0.0);
    check_normalize_failure(TC_QUAT(INFINITY, 0.0, 0.0, 1.0), 0.0);
    check_normalize_failure(tc_quat_identity(), -1.0);
    check_normalize_failure(tc_quat_identity(), NAN);
    check_normalize_failure(tc_quat_identity(), INFINITY);
    check_normalize_failure(tc_quat_identity(), 1.0);
    GUARD_C_CHECK(!tc_quat_try_normalized(tc_quat_identity(), 0.0, NULL));

    const tc_quat invalid = tc_quat_normalize(TC_QUAT(0.0, 0.0, 0.0, 0.0));
    GUARD_C_CHECK(!tc_quat_is_finite(invalid));
    return 0;
}

GUARD_C_TEST(test_checked_inverse_is_true_for_non_unit_quaternions) {
    const tc_quat value = TC_QUAT(1.0, -2.0, 3.0, 4.0);
    tc_quat inverse = tc_quat_identity();
    GUARD_C_CHECK(tc_quat_try_inverse(value, 1.0e-12, &inverse));
    GUARD_C_CHECK(near_quat(tc_quat_mul(value, inverse), tc_quat_identity(), 1.0e-15));
    GUARD_C_CHECK(near_quat(tc_quat_mul(inverse, value), tc_quat_identity(), 1.0e-15));

    GUARD_C_CHECK(tc_quat_try_inverse(TC_QUAT(0.0, 0.0, 0.0, 2.0), 0.0, &inverse));
    GUARD_C_CHECK(equal_quat(inverse, TC_QUAT(0.0, 0.0, 0.0, 0.5)));

    const tc_quat largest_finite = TC_QUAT(DBL_MAX, 0.0, 0.0, 0.0);
    GUARD_C_CHECK(tc_quat_try_inverse(largest_finite, 0.0, &inverse));
    GUARD_C_CHECK(inverse.x < 0.0 && isfinite(inverse.x));
    GUARD_C_CHECK(near_quat(tc_quat_mul(largest_finite, inverse), tc_quat_identity(), 1.0e-15));

    const tc_quat partial_underflow = TC_QUAT(2.0e-162, 2.0e-162, 0.0, 0.0);
    GUARD_C_CHECK(tc_quat_try_inverse(partial_underflow, 0.0, &inverse));
    GUARD_C_CHECK(near_quat(tc_quat_mul(partial_underflow, inverse), tc_quat_identity(), 1.0e-15));

    check_inverse_failure(TC_QUAT(nextafter(0.0, 1.0), 0.0, 0.0, 0.0), 0.0);

    check_inverse_failure(TC_QUAT(0.0, 0.0, 0.0, 0.0), 0.0);
    check_inverse_failure(TC_QUAT(NAN, 0.0, 0.0, 1.0), 0.0);
    check_inverse_failure(TC_QUAT(0.0, INFINITY, 0.0, 1.0), 0.0);
    check_inverse_failure(tc_quat_identity(), -1.0);
    check_inverse_failure(tc_quat_identity(), NAN);
    check_inverse_failure(tc_quat_identity(), 1.0);
    GUARD_C_CHECK(!tc_quat_try_inverse(tc_quat_identity(), 0.0, NULL));
    GUARD_C_CHECK(!tc_quat_is_finite(tc_quat_inverse(TC_QUAT(0.0, 0.0, 0.0, 0.0))));
    return 0;
}

GUARD_C_TEST(test_checked_full_range_rotate_inverse_rotate_and_matrix_agree) {
    const tc_quat multi_max = TC_QUAT(DBL_MAX, DBL_MAX, DBL_MAX, DBL_MAX);
    tc_quat normalized = tc_quat_identity();
    GUARD_C_CHECK(tc_quat_try_normalized(multi_max, 0.0, &normalized));
    GUARD_C_CHECK(equal_quat(normalized, TC_QUAT(0.5, 0.5, 0.5, 0.5)));
    GUARD_C_CHECK(isinf(tc_quat_norm(multi_max)));
    GUARD_C_CHECK(isinf(tc_quat_norm_squared(multi_max)));

    tc_quat inverse = tc_quat_identity();
    GUARD_C_CHECK(tc_quat_try_inverse(multi_max, 0.0, &inverse));
    GUARD_C_CHECK(inverse.x < 0.0 && inverse.y < 0.0 && inverse.z < 0.0 && inverse.w > 0.0);
    GUARD_C_CHECK(tc_quat_is_finite(inverse));
    GUARD_C_CHECK(near_quat(tc_quat_mul(multi_max, inverse), tc_quat_identity(), 2.0e-15));

    const tc_quat quarter_turn = tc_quat_from_axis_angle(TC_VEC3(0.0, 0.0, 7.0), M_PI * 0.5);
    const tc_quat scaled =
        TC_QUAT(quarter_turn.x * 9.0, quarter_turn.y * 9.0, quarter_turn.z * 9.0, quarter_turn.w * 9.0);
    const tc_vec3 vector = TC_VEC3(2.0, -3.0, 4.0);
    tc_vec3 rotated = TC_VEC3(9.0, 8.0, 7.0);
    tc_vec3 recovered = TC_VEC3(6.0, 5.0, 4.0);
    GUARD_C_CHECK(tc_quat_try_rotate(scaled, vector, 1.0e-12, &rotated));
    GUARD_C_CHECK(near(rotated.x, 3.0, 1.0e-14));
    GUARD_C_CHECK(near(rotated.y, 2.0, 1.0e-14));
    GUARD_C_CHECK(near(rotated.z, 4.0, 1.0e-14));
    GUARD_C_CHECK(tc_quat_try_inverse_rotate(scaled, rotated, 1.0e-12, &recovered));
    GUARD_C_CHECK(near(recovered.x, vector.x, 1.0e-14));
    GUARD_C_CHECK(near(recovered.y, vector.y, 1.0e-14));
    GUARD_C_CHECK(near(recovered.z, vector.z, 1.0e-14));

    double matrix[9];
    GUARD_C_CHECK(tc_quat_try_to_matrix3_row_major(scaled, 1.0e-12, matrix));
    const tc_vec3 matrix_rotated = TC_VEC3(matrix[0] * vector.x + matrix[1] * vector.y + matrix[2] * vector.z,
                                           matrix[3] * vector.x + matrix[4] * vector.y + matrix[5] * vector.z,
                                           matrix[6] * vector.x + matrix[7] * vector.y + matrix[8] * vector.z);
    GUARD_C_CHECK(near(matrix_rotated.x, rotated.x, 1.0e-14));
    GUARD_C_CHECK(near(matrix_rotated.y, rotated.y, 1.0e-14));
    GUARD_C_CHECK(near(matrix_rotated.z, rotated.z, 1.0e-14));

    GUARD_C_CHECK(tc_quat_try_rotate(multi_max, vector, 0.0, &rotated));
    GUARD_C_CHECK(tc_quat_try_to_matrix3_row_major(multi_max, 0.0, matrix));
    GUARD_C_CHECK(near(matrix[0] * vector.x + matrix[1] * vector.y + matrix[2] * vector.z, rotated.x, 1.0e-14));
    GUARD_C_CHECK(near(matrix[3] * vector.x + matrix[4] * vector.y + matrix[5] * vector.z, rotated.y, 1.0e-14));
    GUARD_C_CHECK(near(matrix[6] * vector.x + matrix[7] * vector.y + matrix[8] * vector.z, rotated.z, 1.0e-14));

    const tc_quat half_turn_z = TC_QUAT(0.0, 0.0, 1.0, 0.0);
    const tc_vec3 largest_vector = TC_VEC3(DBL_MAX, 0.0, 0.0);
    GUARD_C_CHECK(tc_quat_try_rotate(half_turn_z, largest_vector, 0.0, &rotated));
    GUARD_C_CHECK(rotated.x == -DBL_MAX);
    GUARD_C_CHECK(rotated.y == 0.0);
    GUARD_C_CHECK(rotated.z == 0.0);
    GUARD_C_CHECK(tc_quat_try_inverse_rotate(half_turn_z, largest_vector, 0.0, &recovered));
    GUARD_C_CHECK(recovered.x == -DBL_MAX);
    GUARD_C_CHECK(recovered.y == 0.0);
    GUARD_C_CHECK(recovered.z == 0.0);
    GUARD_C_CHECK(tc_quat_try_to_matrix3_row_major(half_turn_z, 0.0, matrix));
    GUARD_C_CHECK(matrix[0] * largest_vector.x == rotated.x);
    return 0;
}

GUARD_C_TEST(test_checked_rotate_and_matrix_fail_transactionally) {
    const tc_vec3 vector = TC_VEC3(1.0, 2.0, 3.0);
    check_rotate_failure(TC_QUAT(0.0, 0.0, 0.0, 0.0), vector, 0.0);
    check_rotate_failure(TC_QUAT(NAN, 0.0, 0.0, 1.0), vector, 0.0);
    check_rotate_failure(TC_QUAT(0.0, INFINITY, 0.0, 1.0), vector, 0.0);
    check_rotate_failure(tc_quat_identity(), TC_VEC3(NAN, 0.0, 0.0), 0.0);
    check_rotate_failure(tc_quat_identity(), vector, -1.0);
    check_rotate_failure(tc_quat_identity(), vector, NAN);
    check_rotate_failure(tc_quat_identity(), vector, 1.0);
    check_rotate_failure(tc_quat_from_axis_angle(tc_vec3_unit_z(), M_PI * 0.25), TC_VEC3(DBL_MAX, DBL_MAX, 0.0), 0.0);
    GUARD_C_CHECK(!tc_quat_try_rotate(tc_quat_identity(), vector, 0.0, NULL));
    GUARD_C_CHECK(!tc_quat_try_inverse_rotate(tc_quat_identity(), vector, 0.0, NULL));

    check_matrix_failure(TC_QUAT(0.0, 0.0, 0.0, 0.0), 0.0);
    check_matrix_failure(TC_QUAT(NAN, 0.0, 0.0, 1.0), 0.0);
    check_matrix_failure(TC_QUAT(0.0, 0.0, INFINITY, 1.0), 0.0);
    check_matrix_failure(tc_quat_identity(), -1.0);
    check_matrix_failure(tc_quat_identity(), NAN);
    check_matrix_failure(tc_quat_identity(), 1.0);
    GUARD_C_CHECK(!tc_quat_try_to_matrix3_row_major(tc_quat_identity(), 0.0, NULL));
    return 0;
}

GUARD_C_TEST(test_axis_angle_is_checked_normalized_and_transactional) {
    tc_quat result = TC_QUAT(9.0, 8.0, 7.0, 6.0);
    GUARD_C_CHECK(tc_quat_try_from_axis_angle(TC_VEC3(0.0, 0.0, 7.0), M_PI * 0.5, 1.0e-12, &result));
    GUARD_C_CHECK(same_rotation(result, TC_QUAT(0.0, 0.0, sin(M_PI * 0.25), cos(M_PI * 0.25)), 1.0e-15));
    GUARD_C_CHECK(tc_quat_try_from_axis_angle(TC_VEC3(DBL_MAX, DBL_MAX, 0.0), 0.73, 0.0, &result));
    GUARD_C_CHECK(near(tc_quat_norm(result), 1.0, 1.0e-15));

    const tc_quat sentinel = TC_QUAT(9.0, 8.0, 7.0, 6.0);
    result = sentinel;
    GUARD_C_CHECK(!tc_quat_try_from_axis_angle(tc_vec3_zero(), 0.5, 0.0, &result));
    GUARD_C_CHECK(equal_quat(result, sentinel));
    GUARD_C_CHECK(!tc_quat_try_from_axis_angle(TC_VEC3(NAN, 0.0, 0.0), 0.5, 0.0, &result));
    GUARD_C_CHECK(!tc_quat_try_from_axis_angle(TC_VEC3(0.0, INFINITY, 0.0), 0.5, 0.0, &result));
    GUARD_C_CHECK(!tc_quat_try_from_axis_angle(tc_vec3_unit_x(), NAN, 0.0, &result));
    GUARD_C_CHECK(!tc_quat_try_from_axis_angle(tc_vec3_unit_x(), INFINITY, 0.0, &result));
    GUARD_C_CHECK(!tc_quat_try_from_axis_angle(tc_vec3_unit_x(), 0.5, -1.0, &result));
    GUARD_C_CHECK(!tc_quat_try_from_axis_angle(tc_vec3_unit_x(), 0.5, NAN, &result));
    GUARD_C_CHECK(!tc_quat_try_from_axis_angle(tc_vec3_unit_x(), 0.5, 0.0, NULL));
    GUARD_C_CHECK(equal_quat(result, sentinel));
    GUARD_C_CHECK(!tc_quat_is_finite(tc_quat_from_axis_angle(tc_vec3_zero(), 0.5)));
    return 0;
}

GUARD_C_TEST(test_checked_slerp_normalizes_and_uses_shortest_path) {
    const tc_quat identity_scaled = TC_QUAT(0.0, 0.0, 0.0, 2.0);
    const tc_quat quarter_turn_scaled = TC_QUAT(0.0, 0.0, 3.0 * sin(M_PI / 4.0), 3.0 * cos(M_PI / 4.0));
    tc_quat result = TC_QUAT(9.0, 8.0, 7.0, 6.0);

    GUARD_C_CHECK(tc_quat_try_slerp(identity_scaled, quarter_turn_scaled, 0.5, 1.0e-12, &result));
    GUARD_C_CHECK(same_rotation(result, tc_quat_from_axis_angle(tc_vec3_unit_z(), M_PI / 4.0), 1.0e-14));
    GUARD_C_CHECK(near(tc_quat_norm(result), 1.0, 1.0e-15));

    const tc_quat negative_identity = TC_QUAT(0.0, 0.0, 0.0, -5.0);
    GUARD_C_CHECK(tc_quat_try_slerp(identity_scaled, negative_identity, 0.37, 1.0e-12, &result));
    GUARD_C_CHECK(same_rotation(result, tc_quat_identity(), 1.0e-15));

    const tc_quat near_identity = tc_quat_from_axis_angle(tc_vec3_unit_x(), 1.0e-5);
    GUARD_C_CHECK(tc_quat_try_slerp(tc_quat_identity(), near_identity, 0.25, 1.0e-12, &result));
    GUARD_C_CHECK(same_rotation(result, tc_quat_from_axis_angle(tc_vec3_unit_x(), 2.5e-6), 1.0e-13));

    GUARD_C_CHECK(tc_quat_try_slerp(tc_quat_identity(), quarter_turn_scaled, 1.5, 1.0e-12, &result));
    GUARD_C_CHECK(same_rotation(result, tc_quat_from_axis_angle(tc_vec3_unit_z(), 3.0 * M_PI / 4.0), 1.0e-14));
    GUARD_C_CHECK(tc_quat_try_slerp(tc_quat_identity(), quarter_turn_scaled, -0.5, 1.0e-12, &result));
    GUARD_C_CHECK(same_rotation(result, tc_quat_from_axis_angle(tc_vec3_unit_z(), -M_PI / 4.0), 1.0e-14));
    return 0;
}

GUARD_C_TEST(test_checked_slerp_rejects_invalid_values_transactionally) {
    const tc_quat zero = TC_QUAT(0.0, 0.0, 0.0, 0.0);
    check_slerp_failure(zero, tc_quat_identity(), 0.5, 0.0);
    check_slerp_failure(tc_quat_identity(), TC_QUAT(NAN, 0.0, 0.0, 1.0), 0.5, 0.0);
    check_slerp_failure(tc_quat_identity(), TC_QUAT(0.0, INFINITY, 0.0, 1.0), 0.5, 0.0);
    check_slerp_failure(tc_quat_identity(), tc_quat_identity(), NAN, 0.0);
    check_slerp_failure(tc_quat_identity(), tc_quat_identity(), INFINITY, 0.0);
    check_slerp_failure(tc_quat_identity(), tc_quat_identity(), 0.5, -1.0);
    check_slerp_failure(tc_quat_identity(), tc_quat_identity(), 0.5, NAN);
    check_slerp_failure(tc_quat_identity(), tc_quat_identity(), 0.5, 1.0);
    GUARD_C_CHECK(!tc_quat_try_slerp(tc_quat_identity(), tc_quat_identity(), 0.5, 0.0, NULL));
    GUARD_C_CHECK(!tc_quat_is_finite(tc_quat_slerp(zero, tc_quat_identity(), 0.5)));
    return 0;
}

GUARD_C_TEST(test_euler_xyz_composition_round_trip_and_gimbal_policy) {
    const tc_vec3 euler = TC_VEC3(0.37, -0.42, 0.81);
    tc_quat from_euler = TC_QUAT(9.0, 8.0, 7.0, 6.0);
    GUARD_C_CHECK(tc_quat_try_from_euler(euler, &from_euler));
    const tc_quat composed = tc_quat_mul(tc_quat_from_axis_angle(tc_vec3_unit_z(), euler.z),
                                         tc_quat_mul(tc_quat_from_axis_angle(tc_vec3_unit_y(), euler.y),
                                                     tc_quat_from_axis_angle(tc_vec3_unit_x(), euler.x)));
    GUARD_C_CHECK(same_rotation(from_euler, composed, 1.0e-14));

    tc_vec3 recovered = TC_VEC3(9.0, 8.0, 7.0);
    GUARD_C_CHECK(tc_quat_try_to_euler(
        TC_QUAT(from_euler.x * 7.0, from_euler.y * 7.0, from_euler.z * 7.0, from_euler.w * 7.0), 1.0e-12, &recovered));
    GUARD_C_CHECK(near(recovered.x, euler.x, 1.0e-14));
    GUARD_C_CHECK(near(recovered.y, euler.y, 1.0e-14));
    GUARD_C_CHECK(near(recovered.z, euler.z, 1.0e-14));

    const tc_vec3 locked = TC_VEC3(0.4, M_PI * 0.5, -0.7);
    const tc_quat locked_quat = tc_quat_from_euler(locked);
    GUARD_C_CHECK(tc_quat_try_to_euler(locked_quat, 1.0e-12, &recovered));
    GUARD_C_CHECK(recovered.x == 0.0);
    GUARD_C_CHECK(near(recovered.y, M_PI * 0.5, 1.0e-15));
    GUARD_C_CHECK(same_rotation(tc_quat_from_euler(recovered), locked_quat, 1.0e-14));

    const tc_vec3 negative_locked = TC_VEC3(0.4, -M_PI * 0.5, -0.7);
    const tc_quat negative_locked_quat = tc_quat_from_euler(negative_locked);
    GUARD_C_CHECK(tc_quat_try_to_euler(negative_locked_quat, 1.0e-12, &recovered));
    GUARD_C_CHECK(recovered.x == 0.0);
    GUARD_C_CHECK(near(recovered.y, -M_PI * 0.5, 1.0e-15));
    GUARD_C_CHECK(same_rotation(tc_quat_from_euler(recovered), negative_locked_quat, 1.0e-14));
    return 0;
}

GUARD_C_TEST(test_euler_checked_failures_are_transactional) {
    const tc_quat quat_sentinel = TC_QUAT(9.0, 8.0, 7.0, 6.0);
    tc_quat quat_out = quat_sentinel;
    GUARD_C_CHECK(!tc_quat_try_from_euler(TC_VEC3(NAN, 0.0, 0.0), &quat_out));
    GUARD_C_CHECK(equal_quat(quat_out, quat_sentinel));
    GUARD_C_CHECK(!tc_quat_try_from_euler(TC_VEC3(0.0, INFINITY, 0.0), &quat_out));
    GUARD_C_CHECK(equal_quat(quat_out, quat_sentinel));
    GUARD_C_CHECK(!tc_quat_try_from_euler(tc_vec3_zero(), NULL));
    GUARD_C_CHECK(!tc_quat_is_finite(tc_quat_from_euler(TC_VEC3(0.0, NAN, 0.0))));

    const tc_vec3 vec_sentinel = TC_VEC3(9.0, 8.0, 7.0);
    tc_vec3 vec_out = vec_sentinel;
    GUARD_C_CHECK(!tc_quat_try_to_euler(TC_QUAT(0.0, 0.0, 0.0, 0.0), 0.0, &vec_out));
    GUARD_C_CHECK(equal_vec3(vec_out, vec_sentinel));
    GUARD_C_CHECK(!tc_quat_try_to_euler(TC_QUAT(NAN, 0.0, 0.0, 1.0), 0.0, &vec_out));
    GUARD_C_CHECK(equal_vec3(vec_out, vec_sentinel));
    GUARD_C_CHECK(!tc_quat_try_to_euler(tc_quat_identity(), -1.0, &vec_out));
    GUARD_C_CHECK(!tc_quat_try_to_euler(tc_quat_identity(), NAN, &vec_out));
    GUARD_C_CHECK(!tc_quat_try_to_euler(tc_quat_identity(), 0.0, NULL));
    GUARD_C_CHECK(!tc_vec3_is_finite(tc_quat_to_euler(TC_QUAT(0.0, 0.0, 0.0, 0.0))));
    GUARD_C_CHECK(equal_vec3(vec_out, vec_sentinel));
    return 0;
}

GUARD_C_TEST(test_rotation_matrix_conversion_covers_branches_and_row_major_orientation) {
    const tc_quat rotations[] = {
        TC_QUAT(0.0, 0.0, 0.0, 1.0),
        TC_QUAT(-1.0, 0.0, 0.0, 0.0),
        TC_QUAT(0.0, -1.0, 0.0, 0.0),
        TC_QUAT(0.0, 0.0, -1.0, 0.0),
        tc_quat_from_euler(TC_VEC3(0.4, -0.7, 1.1)),
        tc_quat_from_euler(TC_VEC3(-2.6, 0.3, -2.1)),
    };
    for (size_t i = 0; i < sizeof(rotations) / sizeof(rotations[0]); ++i) {
        double matrix[9], restored[9];
        tc_quat_to_matrix3_row_major(rotations[i], matrix);
        tc_quat out = TC_QUAT(9.0, 8.0, 7.0, 6.0);
        GUARD_C_REQUIRE(tc_quat_try_from_rotation_matrix(matrix, 1.0e-8, &out));
        GUARD_C_CHECK(near(tc_quat_norm(out), 1.0, 1.0e-15));
        GUARD_C_CHECK(same_rotation(out, rotations[i], 1.0e-15));
        GUARD_C_CHECK(out.w >= 0.0);
        if (i >= 1 && i <= 3) {
            GUARD_C_CHECK(near_quat(out, TC_QUAT(-rotations[i].x, -rotations[i].y,
                                               -rotations[i].z, -rotations[i].w), 0.0));
        }
        const double components[4] = {out.x, out.y, out.z, out.w};
        for (int j = 0; j < 4; ++j) {
            GUARD_C_CHECK(components[j] != 0.0 || !signbit(components[j]));
        }
        tc_quat_to_matrix3_row_major(out, restored);
        for (int j = 0; j < 9; ++j) {
            GUARD_C_CHECK(near(restored[j], matrix[j], 1.0e-14));
        }
    }
    const double z_quarter_turn[9] = {0.0, -1.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 1.0};
    tc_quat out;
    GUARD_C_REQUIRE(tc_quat_try_from_rotation_matrix(z_quarter_turn, 0.0, &out));
    const tc_vec3 rotated = tc_quat_rotate(out, TC_VEC3(1.0, 0.0, 0.0));
    GUARD_C_CHECK(near(rotated.x, 0.0, 1.0e-15));
    GUARD_C_CHECK(near(rotated.y, 1.0, 1.0e-15));
    GUARD_C_CHECK(near(rotated.z, 0.0, 1.0e-15));
    return 0;
}

GUARD_C_TEST(test_rotation_matrix_rejections_preserve_output_and_input) {
    const double invalid[][9] = {
        {-1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0}, /* reflection */
        {0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0},
        {1.0, 0.2, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0}, /* shear */
        {2.0, 0.0, 0.0, 0.0, 2.0, 0.0, 0.0, 0.0, 2.0},
        {NAN, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0},
        {1.0, 0.0, 0.0, 0.0, INFINITY, 0.0, 0.0, 0.0, 1.0},
        {DBL_MAX, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0},
    };
    const tc_quat sentinel = TC_QUAT(9.0, 8.0, 7.0, 6.0);
    for (size_t i = 0; i < sizeof(invalid) / sizeof(invalid[0]); ++i) {
        double matrix[9], original[9];
        memcpy(matrix, invalid[i], sizeof(matrix));
        memcpy(original, matrix, sizeof(matrix));
        tc_quat out = sentinel;
        GUARD_C_CHECK(!tc_quat_try_from_rotation_matrix(matrix, 1.0e-8, &out));
        GUARD_C_CHECK(equal_quat(out, sentinel));
        GUARD_C_CHECK(memcmp(matrix, original, sizeof(matrix)) == 0);
    }
    const double identity[9] = {1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0};
    const double bad_epsilon[] = {-1.0, 1.0, NAN, INFINITY};
    tc_quat out = sentinel;
    for (size_t i = 0; i < sizeof(bad_epsilon) / sizeof(bad_epsilon[0]); ++i) {
        GUARD_C_CHECK(!tc_quat_try_from_rotation_matrix(identity, bad_epsilon[i], &out));
        GUARD_C_CHECK(equal_quat(out, sentinel));
    }
    GUARD_C_CHECK(!tc_quat_try_from_rotation_matrix(NULL, 1.0e-8, &out));
    GUARD_C_CHECK(equal_quat(out, sentinel));
    GUARD_C_CHECK(!tc_quat_try_from_rotation_matrix(identity, 1.0e-8, NULL));
    double noisy_identity[9] = {1.0 + 1.0e-7, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0};
    GUARD_C_CHECK(!tc_quat_try_from_rotation_matrix(noisy_identity, 1.0e-8, &out));
    GUARD_C_CHECK(equal_quat(out, sentinel));
    GUARD_C_REQUIRE(tc_quat_try_from_rotation_matrix(noisy_identity, 1.0e-6, &out));
    GUARD_C_CHECK(near_quat(out, tc_quat_identity(), 0.0));
    return 0;
}

int main(int argc, char** argv) {
    GUARD_C_BEGIN_ARGS(argc, argv);
    GUARD_C_RUN(test_quat_abi_and_raw_products);
    GUARD_C_RUN(test_checked_normalization_is_stable_and_transactional);
    GUARD_C_RUN(test_checked_inverse_is_true_for_non_unit_quaternions);
    GUARD_C_RUN(test_checked_full_range_rotate_inverse_rotate_and_matrix_agree);
    GUARD_C_RUN(test_checked_rotate_and_matrix_fail_transactionally);
    GUARD_C_RUN(test_axis_angle_is_checked_normalized_and_transactional);
    GUARD_C_RUN(test_checked_slerp_normalizes_and_uses_shortest_path);
    GUARD_C_RUN(test_checked_slerp_rejects_invalid_values_transactionally);
    GUARD_C_RUN(test_euler_xyz_composition_round_trip_and_gimbal_policy);
    GUARD_C_RUN(test_euler_checked_failures_are_transactional);
    GUARD_C_RUN(test_rotation_matrix_conversion_covers_branches_and_row_major_orientation);
    GUARD_C_RUN(test_rotation_matrix_rejections_preserve_output_and_input);
    return GUARD_C_END();
}
