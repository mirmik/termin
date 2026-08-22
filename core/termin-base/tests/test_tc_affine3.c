#include <geom/tc_aabb.h>
#include <geom/tc_affine3.h>
#include <geom/tc_quat.h>

#include "guard_c.h"

#include <float.h>
#include <math.h>
#include <stddef.h>

static int near(double a, double b, double epsilon) {
    return fabs(a - b) <= epsilon;
}

static int near_vec3(tc_vec3 a, tc_vec3 b, double epsilon) {
    return near(a.x, b.x, epsilon) && near(a.y, b.y, epsilon) && near(a.z, b.z, epsilon);
}

static int near_identity_basis(tc_basis3d basis, double epsilon) {
    return near_vec3(basis.x, TC_VEC3(1.0, 0.0, 0.0), epsilon) && near_vec3(basis.y, TC_VEC3(0.0, 1.0, 0.0), epsilon) &&
           near_vec3(basis.z, TC_VEC3(0.0, 0.0, 1.0), epsilon);
}

int main(void) {
    GUARD_C_CHECK(sizeof(tc_basis3d) == sizeof(double) * 9);
    GUARD_C_CHECK(offsetof(tc_basis3d, x) == sizeof(double) * 0);
    GUARD_C_CHECK(offsetof(tc_basis3d, y) == sizeof(double) * 3);
    GUARD_C_CHECK(offsetof(tc_basis3d, z) == sizeof(double) * 6);
    GUARD_C_CHECK(sizeof(tc_affine3d) == sizeof(double) * 12);
    GUARD_C_CHECK(offsetof(tc_affine3d, basis) == sizeof(double) * 0);
    GUARD_C_CHECK(offsetof(tc_affine3d, translation) == sizeof(double) * 9);
    GUARD_C_CHECK(sizeof(tc_aabbf) == sizeof(float) * 6);

    tc_vec3f checked_normalized = TC_VEC3F(9.0f, 8.0f, 7.0f);
    GUARD_C_CHECK(!tc_vec3f_try_normalized(tc_vec3f_zero(), 1.0e-6f, &checked_normalized));
    GUARD_C_CHECK(checked_normalized.x == 9.0f && checked_normalized.y == 8.0f && checked_normalized.z == 7.0f);
    GUARD_C_CHECK(tc_vec3f_try_normalized(TC_VEC3F(0.0f, 3.0f, 4.0f), 1.0e-6f, &checked_normalized));
    GUARD_C_CHECK(tc_vec3f_try_normalized(TC_VEC3F(FLT_MAX, 0.0f, 0.0f), 0.0f, &checked_normalized));
    GUARD_C_CHECK(checked_normalized.x == 1.0f && checked_normalized.y == 0.0f && checked_normalized.z == 0.0f);
    GUARD_C_CHECK(tc_vec3f_try_normalized(TC_VEC3F(FLT_MAX, FLT_MAX, FLT_MAX), 0.0f, &checked_normalized));
    GUARD_C_CHECK(fabsf(tc_vec3f_dot(checked_normalized, checked_normalized) - 1.0f) < 2.0e-6f);

    tc_vec3 checked_normalized_double = TC_VEC3(9.0, 8.0, 7.0);
    GUARD_C_CHECK(tc_vec3_try_normalized(TC_VEC3(DBL_MAX, 0.0, 0.0), 0.0, &checked_normalized_double));
    GUARD_C_CHECK(checked_normalized_double.x == 1.0 && checked_normalized_double.y == 0.0 &&
                  checked_normalized_double.z == 0.0);
    GUARD_C_CHECK(tc_vec3_try_normalized(TC_VEC3(DBL_MAX, DBL_MAX, DBL_MAX), 0.0, &checked_normalized_double));
    GUARD_C_CHECK(fabs(tc_vec3_dot(checked_normalized_double, checked_normalized_double) - 1.0) < 2.0e-15);

    tc_aabbf float_bounds = tc_aabbf_zero();
    GUARD_C_CHECK(tc_aabbf_is_valid(float_bounds));
    tc_aabbf_extend(&float_bounds, TC_VEC3F(-2.0f, 3.0f, -4.0f));
    tc_aabbf_extend(&float_bounds, TC_VEC3F(5.0f, 6.0f, 7.0f));
    GUARD_C_CHECK(float_bounds.min_point.x == -2.0f);
    GUARD_C_CHECK(float_bounds.max_point.z == 7.0f);
    GUARD_C_CHECK(tc_aabbf_contains(float_bounds, TC_VEC3F(0.0f, 1.0f, 2.0f)));

    tc_quat child_rotation = tc_quat_from_axis_angle(tc_vec3_unit_z(), 0.63);
    tc_affine3d parent = tc_affine3d_mul(tc_affine3d_translation(5.0, -3.0, 2.0), tc_affine3d_scaling(2.0, 0.5, 1.25));
    tc_affine3d child = tc_affine3d_trs(TC_VEC3(-1.0, 4.0, 0.75), child_rotation, TC_VEC3(0.8, 1.4, 2.0));
    tc_vec3 point = TC_VEC3(3.0, -2.0, 1.5);
    tc_vec3 sequential = tc_affine3d_transform_point(parent, tc_affine3d_transform_point(child, point));
    tc_affine3d composed_affine = tc_affine3d_mul(parent, child);
    tc_vec3 composed = tc_affine3d_transform_point(composed_affine, point);
    GUARD_C_CHECK(near_vec3(sequential, composed, 1.0e-12));

    // Non-uniform parent scale and rotated child produce non-orthogonal
    // columns. Exact affine composition must retain that shear.
    double xy_dot = tc_vec3_dot(composed_affine.basis.x, composed_affine.basis.y);
    GUARD_C_CHECK(fabs(xy_dot) > 1.0e-3);

    tc_affine3d reflection =
        tc_affine3d_mul(tc_affine3d_translation(7.0, -5.0, 3.0),
                        tc_affine3d_mul(tc_affine3d_rotation(tc_quat_from_euler(TC_VEC3(0.2, -0.4, 0.7))),
                                        tc_affine3d_scaling(-2.0, 0.75, 1.5)));
    tc_affine3d inverse = tc_affine3d_identity();
    GUARD_C_CHECK(tc_affine3d_try_inverse(reflection, 1.0e-12, &inverse));
    tc_vec3 round_trip = tc_affine3d_transform_point(inverse, tc_affine3d_transform_point(reflection, point));
    GUARD_C_CHECK(near_vec3(round_trip, point, 1.0e-11));

    tc_affine3d unchanged = tc_affine3d_translation(9.0, 11.0, 13.0);
    GUARD_C_CHECK(!tc_affine3d_try_inverse(tc_affine3d_scaling(0.0, 2.0, 3.0), 1.0e-12, &unchanged));
    GUARD_C_CHECK(unchanged.translation.x == 9.0);
    GUARD_C_CHECK(unchanged.translation.y == 11.0);
    GUARD_C_CHECK(unchanged.translation.z == 13.0);
    GUARD_C_CHECK(!tc_affine3d_try_inverse(tc_affine3d_identity(), 1.0e-12, NULL));

    tc_basis3d scale_inverse = tc_basis3d_identity();
    tc_basis3d uniformly_small = tc_basis3d_scaling(1.0e-6, 1.0e-6, 1.0e-6);
    GUARD_C_CHECK(tc_basis3d_try_inverse(uniformly_small, 1.0e-12, &scale_inverse));
    GUARD_C_CHECK(near_identity_basis(tc_basis3d_mul(uniformly_small, scale_inverse), 1.0e-12));
    tc_basis3d uniformly_large = tc_basis3d_scaling(1.0e6, 1.0e6, 1.0e6);
    GUARD_C_CHECK(tc_basis3d_try_inverse(uniformly_large, 1.0e-12, &scale_inverse));
    GUARD_C_CHECK(near_identity_basis(tc_basis3d_mul(scale_inverse, uniformly_large), 1.0e-12));

    tc_basis3d inverse_sentinel =
        tc_basis3d_new(TC_VEC3(9.0, 8.0, 7.0), TC_VEC3(6.0, 5.0, 4.0), TC_VEC3(3.0, 2.0, 1.0));
    tc_basis3d expected_inverse_sentinel = inverse_sentinel;
    tc_basis3d mixed_axes = tc_basis3d_from_quat(tc_quat_from_axis_angle(tc_vec3_unit_z(), 0.7853981633974483));
    tc_basis3d unreliable =
        tc_basis3d_mul(mixed_axes, tc_basis3d_mul(tc_basis3d_scaling(1.0e-16, 1.0e16, 1.0), mixed_axes));
    GUARD_C_CHECK(!tc_basis3d_try_inverse(unreliable, 1.0e-12, &inverse_sentinel));
    GUARD_C_CHECK(near_vec3(inverse_sentinel.x, expected_inverse_sentinel.x, 0.0));
    GUARD_C_CHECK(near_vec3(inverse_sentinel.y, expected_inverse_sentinel.y, 0.0));
    GUARD_C_CHECK(near_vec3(inverse_sentinel.z, expected_inverse_sentinel.z, 0.0));

    tc_basis3d non_finite_basis = tc_basis3d_identity();
    non_finite_basis.x.x = NAN;
    GUARD_C_CHECK(!tc_basis3d_try_inverse(non_finite_basis, 1.0e-12, &inverse_sentinel));
    GUARD_C_CHECK(!tc_basis3d_try_inverse(tc_basis3d_identity(), -1.0, &inverse_sentinel));
    GUARD_C_CHECK(!tc_basis3d_try_inverse(tc_basis3d_identity(), NAN, &inverse_sentinel));
    GUARD_C_CHECK(near_vec3(inverse_sentinel.x, expected_inverse_sentinel.x, 0.0));

    tc_basis3d oriented_nonuniform =
        tc_basis3d_mul(tc_basis3d_from_quat(tc_quat_from_axis_angle(tc_vec3_normalize(TC_VEC3(1.0, 2.0, -0.5)), 0.71)),
                       tc_basis3d_scaling(2.0, 3.0, 4.0));
    tc_vec3 local_tangent0 = TC_VEC3(1.0, 2.0, -0.5);
    tc_vec3 local_tangent1 = TC_VEC3(-0.3, 0.4, 1.2);
    tc_vec3 local_normal = tc_vec3_cross(local_tangent0, local_tangent1);
    tc_vec3 transformed_normal = TC_VEC3(99.0, 98.0, 97.0);
    GUARD_C_CHECK(tc_basis3d_try_transform_normal(oriented_nonuniform, local_normal, 1.0e-12, &transformed_normal));
    GUARD_C_CHECK(fabs(tc_vec3_dot(transformed_normal,
                                   tc_basis3d_transform_vector(oriented_nonuniform, local_tangent0))) < 1.0e-12);
    GUARD_C_CHECK(fabs(tc_vec3_dot(transformed_normal,
                                   tc_basis3d_transform_vector(oriented_nonuniform, local_tangent1))) < 1.0e-12);

    tc_vec3 raw_normal = TC_VEC3(99.0, 98.0, 97.0);
    GUARD_C_CHECK(tc_basis3d_try_transform_normal(
        tc_basis3d_scaling(2.0, 3.0, 4.0), TC_VEC3(0.0, 0.0, 2.0), 1.0e-12, &raw_normal));
    GUARD_C_CHECK(near_vec3(raw_normal, TC_VEC3(0.0, 0.0, 0.5), 1.0e-12));

    tc_affine3d normal_affine = tc_affine3d_new(oriented_nonuniform, TC_VEC3(1.0e12, -2.0e12, 3.0e12));
    tc_vec3 affine_normal = TC_VEC3(99.0, 98.0, 97.0);
    GUARD_C_CHECK(tc_affine3d_try_transform_normal(normal_affine, local_normal, 1.0e-12, &affine_normal));
    GUARD_C_CHECK(near_vec3(affine_normal, transformed_normal, 1.0e-12));

    tc_vec3 normal_sentinel = TC_VEC3(99.0, 98.0, 97.0);
    GUARD_C_CHECK(!tc_basis3d_try_transform_normal(
        tc_basis3d_scaling(1.0, 0.0, 1.0), tc_vec3_unit_z(), 1.0e-12, &normal_sentinel));
    GUARD_C_CHECK(
        !tc_basis3d_try_transform_normal(tc_basis3d_identity(), TC_VEC3(NAN, 0.0, 0.0), 1.0e-12, &normal_sentinel));
    GUARD_C_CHECK(!tc_basis3d_try_transform_normal(tc_basis3d_identity(), tc_vec3_unit_z(), -1.0, &normal_sentinel));
    normal_affine.translation.x = INFINITY;
    GUARD_C_CHECK(!tc_affine3d_try_transform_normal(normal_affine, tc_vec3_unit_z(), 1.0e-12, &normal_sentinel));
    GUARD_C_CHECK(near_vec3(normal_sentinel, TC_VEC3(99.0, 98.0, 97.0), 0.0));

    tc_affine3d large_frame = tc_affine3d_mul(
        tc_affine3d_translation(1.0e12, -2.0e12, 3.0e12),
        tc_affine3d_rotation(tc_quat_from_axis_angle(tc_vec3_normalize(TC_VEC3(1.0, -2.0, 3.0)), 0.73)));
    tc_vec3 large_local_point = TC_VEC3(0.25, -0.5, 1.75);
    tc_vec3 large_world_point = tc_affine3d_transform_point(large_frame, large_local_point);
    tc_vec3 recovered_point = TC_VEC3(9.0, 8.0, 7.0);
    GUARD_C_CHECK(tc_affine3d_try_inverse_transform_point(large_frame, large_world_point, 1.0e-12, &recovered_point));
    GUARD_C_CHECK(near_vec3(recovered_point, large_local_point, 5.0e-4));

    tc_vec3 local_vector = TC_VEC3(-0.5, 0.75, 0.125);
    tc_vec3 world_vector = tc_affine3d_transform_vector(large_frame, local_vector);
    tc_vec3 recovered_vector = TC_VEC3(6.0, 5.0, 4.0);
    GUARD_C_CHECK(tc_affine3d_try_inverse_transform_vector(large_frame, world_vector, 1.0e-12, &recovered_vector));
    GUARD_C_CHECK(near_vec3(recovered_vector, local_vector, 1.0e-12));

    recovered_point = TC_VEC3(9.0, 8.0, 7.0);
    GUARD_C_CHECK(!tc_affine3d_try_inverse_transform_point(
        tc_affine3d_scaling(1.0, 0.0, 1.0), large_world_point, 1.0e-12, &recovered_point));
    GUARD_C_CHECK(recovered_point.x == 9.0 && recovered_point.y == 8.0 && recovered_point.z == 7.0);

    double matrix[16];
    tc_affine3d_to_matrix4(composed_affine, matrix);
    GUARD_C_CHECK(matrix[3] == 0.0);
    GUARD_C_CHECK(matrix[7] == 0.0);
    GUARD_C_CHECK(matrix[11] == 0.0);
    GUARD_C_CHECK(matrix[15] == 1.0);

    tc_affine3d matrix_round_trip = tc_affine3d_identity();
    GUARD_C_CHECK(tc_affine3d_try_from_matrix4(matrix, 1.0e-12, &matrix_round_trip));
    GUARD_C_CHECK(near_vec3(tc_affine3d_transform_point(matrix_round_trip, point), composed, 1.0e-12));

    matrix[3] = 0.25;
    GUARD_C_CHECK(!tc_affine3d_try_from_matrix4(matrix, 1.0e-12, &matrix_round_trip));

    matrix[3] = 0.0;
    matrix_round_trip = tc_affine3d_translation(9.0, 11.0, 13.0);
    GUARD_C_CHECK(!tc_affine3d_try_from_matrix4(matrix, -1.0, &matrix_round_trip));
    GUARD_C_CHECK(!tc_affine3d_try_from_matrix4(matrix, NAN, &matrix_round_trip));
    GUARD_C_CHECK(near_identity_basis(matrix_round_trip.basis, 0.0));
    GUARD_C_CHECK(near_vec3(matrix_round_trip.translation, TC_VEC3(9.0, 11.0, 13.0), 0.0));

    return 0;
}
