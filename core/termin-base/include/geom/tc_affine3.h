// tc_affine3.h - Exact packed double-precision 3D affine operations.
#ifndef TC_AFFINE3_H
#define TC_AFFINE3_H

#include <float.h>
#include <math.h>
#include <stdbool.h>
#include <stddef.h>

#include <geom/tc_vec3.h>
#include <tcbase/tc_types.h>

#ifdef __cplusplus
#define TC_BASIS3D(x_, y_, z_)                                                                                         \
    tc_basis3d {                                                                                                       \
        x_, y_, z_                                                                                                     \
    }
#define TC_AFFINE3D(basis_, translation_)                                                                              \
    tc_affine3d {                                                                                                      \
        basis_, translation_                                                                                           \
    }
#else
#define TC_BASIS3D(x_, y_, z_)                                                                                         \
    (tc_basis3d) {                                                                                                     \
        x_, y_, z_                                                                                                     \
    }
#define TC_AFFINE3D(basis_, translation_)                                                                              \
    (tc_affine3d) {                                                                                                    \
        basis_, translation_                                                                                           \
    }
#endif

#ifdef __cplusplus
extern "C" {
#endif

TC_C_STATIC_INLINE tc_basis3d tc_basis3d_new(tc_vec3 x, tc_vec3 y, tc_vec3 z) {
    return TC_BASIS3D(x, y, z);
}

TC_C_STATIC_INLINE tc_basis3d tc_basis3d_identity(void) {
    return TC_BASIS3D(TC_VEC3(1.0, 0.0, 0.0), TC_VEC3(0.0, 1.0, 0.0), TC_VEC3(0.0, 0.0, 1.0));
}

// rotation must be a unit quaternion, matching the existing Pose3 contract.
TC_C_STATIC_INLINE tc_basis3d tc_basis3d_from_quat(tc_quat rotation) {
    double xx = rotation.x * rotation.x;
    double yy = rotation.y * rotation.y;
    double zz = rotation.z * rotation.z;
    double xy = rotation.x * rotation.y;
    double xz = rotation.x * rotation.z;
    double yz = rotation.y * rotation.z;
    double wx = rotation.w * rotation.x;
    double wy = rotation.w * rotation.y;
    double wz = rotation.w * rotation.z;

    return TC_BASIS3D(TC_VEC3(1.0 - 2.0 * (yy + zz), 2.0 * (xy + wz), 2.0 * (xz - wy)),
                      TC_VEC3(2.0 * (xy - wz), 1.0 - 2.0 * (xx + zz), 2.0 * (yz + wx)),
                      TC_VEC3(2.0 * (xz + wy), 2.0 * (yz - wx), 1.0 - 2.0 * (xx + yy)));
}

TC_C_STATIC_INLINE tc_basis3d tc_basis3d_scaling(double sx, double sy, double sz) {
    return TC_BASIS3D(TC_VEC3(sx, 0.0, 0.0), TC_VEC3(0.0, sy, 0.0), TC_VEC3(0.0, 0.0, sz));
}

TC_C_STATIC_INLINE tc_vec3 tc_basis3d_transform_vector(tc_basis3d basis, tc_vec3 vector) {
    return TC_VEC3(basis.x.x * vector.x + basis.y.x * vector.y + basis.z.x * vector.z,
                   basis.x.y * vector.x + basis.y.y * vector.y + basis.z.y * vector.z,
                   basis.x.z * vector.x + basis.y.z * vector.y + basis.z.z * vector.z);
}

// parent * child applies child first, then parent.
TC_C_STATIC_INLINE tc_basis3d tc_basis3d_mul(tc_basis3d parent, tc_basis3d child) {
    return TC_BASIS3D(tc_basis3d_transform_vector(parent, child.x),
                      tc_basis3d_transform_vector(parent, child.y),
                      tc_basis3d_transform_vector(parent, child.z));
}

TC_C_STATIC_INLINE double tc_basis3d_determinant(tc_basis3d basis) {
    return basis.x.x * (basis.y.y * basis.z.z - basis.y.z * basis.z.y) -
           basis.y.x * (basis.x.y * basis.z.z - basis.x.z * basis.z.y) +
           basis.z.x * (basis.x.y * basis.y.z - basis.x.z * basis.y.y);
}

TC_C_STATIC_INLINE bool tc_basis3d_is_finite(tc_basis3d basis) {
    return isfinite(basis.x.x) && isfinite(basis.x.y) && isfinite(basis.x.z) && isfinite(basis.y.x) &&
           isfinite(basis.y.y) && isfinite(basis.y.z) && isfinite(basis.z.x) && isfinite(basis.z.y) &&
           isfinite(basis.z.z);
}

TC_C_STATIC_INLINE bool tc_basis3d_inverse_products_are_reliable(tc_basis3d basis, tc_basis3d inverse, double epsilon) {
    double tolerance = fmax(epsilon, sqrt(DBL_EPSILON));
    tc_basis3d left = tc_basis3d_mul(basis, inverse);
    tc_basis3d right = tc_basis3d_mul(inverse, basis);
    if (!tc_basis3d_is_finite(left) || !tc_basis3d_is_finite(right)) {
        return false;
    }

    return fabs(left.x.x - 1.0) <= tolerance && fabs(left.x.y) <= tolerance && fabs(left.x.z) <= tolerance &&
           fabs(left.y.x) <= tolerance && fabs(left.y.y - 1.0) <= tolerance && fabs(left.y.z) <= tolerance &&
           fabs(left.z.x) <= tolerance && fabs(left.z.y) <= tolerance && fabs(left.z.z - 1.0) <= tolerance &&
           fabs(right.x.x - 1.0) <= tolerance && fabs(right.x.y) <= tolerance && fabs(right.x.z) <= tolerance &&
           fabs(right.y.x) <= tolerance && fabs(right.y.y - 1.0) <= tolerance && fabs(right.y.z) <= tolerance &&
           fabs(right.z.x) <= tolerance && fabs(right.z.y) <= tolerance && fabs(right.z.z - 1.0) <= tolerance;
}

TC_C_STATIC_INLINE bool tc_basis3d_try_inverse(tc_basis3d basis, double epsilon, tc_basis3d* out_inverse) {
    if (out_inverse == NULL || !tc_basis3d_is_finite(basis) || !isfinite(epsilon) || epsilon < 0.0) {
        return false;
    }

    // Two-sided equilibration makes the rank test independent of the world
    // unit. In particular, a well-conditioned uniform scale has the same
    // pivots whether its coefficients are 1e-6, 1, or 1e6.
    double input[3][3] = {
        {basis.x.x, basis.y.x, basis.z.x},
        {basis.x.y, basis.y.y, basis.z.y},
        {basis.x.z, basis.y.z, basis.z.z},
    };
    double column_scale[3] = {0.0, 0.0, 0.0};
    for (int column = 0; column < 3; ++column) {
        for (int row = 0; row < 3; ++row) {
            column_scale[column] = fmax(column_scale[column], fabs(input[row][column]));
        }
        if (column_scale[column] == 0.0 || !isfinite(column_scale[column])) {
            return false;
        }
    }

    double row_scale[3] = {0.0, 0.0, 0.0};
    for (int row = 0; row < 3; ++row) {
        for (int column = 0; column < 3; ++column) {
            row_scale[row] = fmax(row_scale[row], fabs(input[row][column] / column_scale[column]));
        }
        if (row_scale[row] == 0.0 || !isfinite(row_scale[row])) {
            return false;
        }
    }

    double augmented[3][6] = {{0.0}};
    for (int row = 0; row < 3; ++row) {
        for (int column = 0; column < 3; ++column) {
            augmented[row][column] = input[row][column] / column_scale[column] / row_scale[row];
            augmented[row][column + 3] = row == column ? 1.0 : 0.0;
        }
    }

    double pivot_threshold = fmax(epsilon, DBL_EPSILON);
    for (int pivot_column = 0; pivot_column < 3; ++pivot_column) {
        int pivot_row = pivot_column;
        double pivot_abs = fabs(augmented[pivot_row][pivot_column]);
        for (int row = pivot_column + 1; row < 3; ++row) {
            double candidate_abs = fabs(augmented[row][pivot_column]);
            if (candidate_abs > pivot_abs) {
                pivot_abs = candidate_abs;
                pivot_row = row;
            }
        }
        if (!isfinite(pivot_abs) || pivot_abs <= pivot_threshold) {
            return false;
        }
        if (pivot_row != pivot_column) {
            for (int column = 0; column < 6; ++column) {
                double temporary = augmented[pivot_column][column];
                augmented[pivot_column][column] = augmented[pivot_row][column];
                augmented[pivot_row][column] = temporary;
            }
        }

        double pivot = augmented[pivot_column][pivot_column];
        for (int column = 0; column < 6; ++column) {
            augmented[pivot_column][column] /= pivot;
            if (!isfinite(augmented[pivot_column][column])) {
                return false;
            }
        }

        for (int row = 0; row < 3; ++row) {
            if (row == pivot_column) {
                continue;
            }
            double factor = augmented[row][pivot_column];
            for (int column = 0; column < 6; ++column) {
                augmented[row][column] -= factor * augmented[pivot_column][column];
                if (!isfinite(augmented[row][column])) {
                    return false;
                }
            }
        }
    }

    tc_basis3d candidate = TC_BASIS3D(TC_VEC3(augmented[0][3] / column_scale[0] / row_scale[0],
                                              augmented[1][3] / column_scale[1] / row_scale[0],
                                              augmented[2][3] / column_scale[2] / row_scale[0]),
                                      TC_VEC3(augmented[0][4] / column_scale[0] / row_scale[1],
                                              augmented[1][4] / column_scale[1] / row_scale[1],
                                              augmented[2][4] / column_scale[2] / row_scale[1]),
                                      TC_VEC3(augmented[0][5] / column_scale[0] / row_scale[2],
                                              augmented[1][5] / column_scale[1] / row_scale[2],
                                              augmented[2][5] / column_scale[2] / row_scale[2]));
    if (!tc_basis3d_is_finite(candidate)) {
        return false;
    }

    if (!tc_basis3d_inverse_products_are_reliable(basis, candidate, epsilon)) {
        // One right iterative-refinement step can remove the cancellation
        // residue introduced while undoing equilibration. Both products are
        // checked again before publishing the result.
        tc_basis3d product = tc_basis3d_mul(basis, candidate);
        tc_basis3d residual = TC_BASIS3D(TC_VEC3(1.0 - product.x.x, -product.x.y, -product.x.z),
                                         TC_VEC3(-product.y.x, 1.0 - product.y.y, -product.y.z),
                                         TC_VEC3(-product.z.x, -product.z.y, 1.0 - product.z.z));
        tc_basis3d correction = tc_basis3d_mul(candidate, residual);
        tc_basis3d refined = TC_BASIS3D(tc_vec3_add(candidate.x, correction.x),
                                        tc_vec3_add(candidate.y, correction.y),
                                        tc_vec3_add(candidate.z, correction.z));
        if (!tc_basis3d_is_finite(refined) || !tc_basis3d_inverse_products_are_reliable(basis, refined, epsilon)) {
            return false;
        }
        candidate = refined;
    }

    *out_inverse = candidate;
    return true;
}

// Normals are covectors: applying a basis uses its inverse transpose. The
// result intentionally remains unnormalized so callers can choose their own
// normalization and degeneracy policy.
TC_C_STATIC_INLINE bool
tc_basis3d_try_transform_normal(tc_basis3d basis, tc_vec3 normal, double epsilon, tc_vec3* out_normal) {
    if (out_normal == NULL || !tc_vec3_is_finite(normal) || !isfinite(epsilon) || epsilon < 0.0) {
        return false;
    }

    tc_basis3d inverse;
    if (!tc_basis3d_try_inverse(basis, epsilon, &inverse)) {
        return false;
    }
    tc_vec3 result =
        TC_VEC3(tc_vec3_dot(inverse.x, normal), tc_vec3_dot(inverse.y, normal), tc_vec3_dot(inverse.z, normal));
    if (!tc_vec3_is_finite(result)) {
        return false;
    }
    *out_normal = result;
    return true;
}

TC_C_STATIC_INLINE tc_affine3d tc_affine3d_new(tc_basis3d basis, tc_vec3 translation) {
    return TC_AFFINE3D(basis, translation);
}

TC_C_STATIC_INLINE tc_affine3d tc_affine3d_identity(void) {
    return TC_AFFINE3D(tc_basis3d_identity(), TC_VEC3(0.0, 0.0, 0.0));
}

TC_C_STATIC_INLINE tc_affine3d tc_affine3d_translation(double x, double y, double z) {
    return TC_AFFINE3D(tc_basis3d_identity(), TC_VEC3(x, y, z));
}

TC_C_STATIC_INLINE tc_affine3d tc_affine3d_rotation(tc_quat rotation) {
    return TC_AFFINE3D(tc_basis3d_from_quat(rotation), TC_VEC3(0.0, 0.0, 0.0));
}

TC_C_STATIC_INLINE tc_affine3d tc_affine3d_scaling(double sx, double sy, double sz) {
    return TC_AFFINE3D(tc_basis3d_scaling(sx, sy, sz), TC_VEC3(0.0, 0.0, 0.0));
}

// T * R * S for column vectors.
TC_C_STATIC_INLINE tc_affine3d tc_affine3d_trs(tc_vec3 translation, tc_quat rotation, tc_vec3 scale) {
    tc_basis3d basis = tc_basis3d_from_quat(rotation);
    basis.x = tc_vec3_scale(basis.x, scale.x);
    basis.y = tc_vec3_scale(basis.y, scale.y);
    basis.z = tc_vec3_scale(basis.z, scale.z);
    return TC_AFFINE3D(basis, translation);
}

TC_C_STATIC_INLINE tc_affine3d tc_affine3d_from_pose3(tc_pose3 pose) {
    return tc_affine3d_trs(pose.lin, pose.ang, TC_VEC3(1.0, 1.0, 1.0));
}

TC_C_STATIC_INLINE tc_affine3d tc_affine3d_from_general_pose3(tc_general_pose3 pose) {
    return tc_affine3d_trs(pose.lin, pose.ang, pose.scale);
}

// parent * child applies child first, then parent.
TC_C_STATIC_INLINE tc_affine3d tc_affine3d_mul(tc_affine3d parent, tc_affine3d child) {
    return TC_AFFINE3D(tc_basis3d_mul(parent.basis, child.basis),
                       tc_vec3_add(parent.translation, tc_basis3d_transform_vector(parent.basis, child.translation)));
}

TC_C_STATIC_INLINE tc_vec3 tc_affine3d_transform_point(tc_affine3d affine, tc_vec3 point) {
    return tc_vec3_add(affine.translation, tc_basis3d_transform_vector(affine.basis, point));
}

TC_C_STATIC_INLINE tc_vec3 tc_affine3d_transform_vector(tc_affine3d affine, tc_vec3 vector) {
    return tc_basis3d_transform_vector(affine.basis, vector);
}

TC_C_STATIC_INLINE bool tc_affine3d_is_finite(tc_affine3d affine) {
    return tc_basis3d_is_finite(affine.basis) && isfinite(affine.translation.x) && isfinite(affine.translation.y) &&
           isfinite(affine.translation.z);
}

TC_C_STATIC_INLINE bool
tc_affine3d_try_transform_normal(tc_affine3d affine, tc_vec3 normal, double epsilon, tc_vec3* out_normal) {
    if (!tc_affine3d_is_finite(affine)) {
        return false;
    }
    return tc_basis3d_try_transform_normal(affine.basis, normal, epsilon, out_normal);
}

// Applies the inverse without materializing its translation. Besides avoiding
// a temporary, this centered form preserves substantially more useful
// precision for affine frames located far from the world origin.
TC_C_STATIC_INLINE bool
tc_affine3d_try_inverse_transform_point(tc_affine3d affine, tc_vec3 point, double epsilon, tc_vec3* out_point) {
    if (out_point == NULL || !tc_affine3d_is_finite(affine) || !tc_vec3_is_finite(point) || !isfinite(epsilon) ||
        epsilon < 0.0) {
        return false;
    }

    tc_basis3d inverse_basis;
    if (!tc_basis3d_try_inverse(affine.basis, epsilon, &inverse_basis)) {
        return false;
    }
    tc_vec3 centered = tc_vec3_sub(point, affine.translation);
    tc_vec3 result = tc_basis3d_transform_vector(inverse_basis, centered);
    if (!tc_vec3_is_finite(result)) {
        return false;
    }
    *out_point = result;
    return true;
}

TC_C_STATIC_INLINE bool
tc_affine3d_try_inverse_transform_vector(tc_affine3d affine, tc_vec3 vector, double epsilon, tc_vec3* out_vector) {
    if (out_vector == NULL || !tc_affine3d_is_finite(affine) || !tc_vec3_is_finite(vector) || !isfinite(epsilon) ||
        epsilon < 0.0) {
        return false;
    }

    tc_basis3d inverse_basis;
    if (!tc_basis3d_try_inverse(affine.basis, epsilon, &inverse_basis)) {
        return false;
    }
    tc_vec3 result = tc_basis3d_transform_vector(inverse_basis, vector);
    if (!tc_vec3_is_finite(result)) {
        return false;
    }
    *out_vector = result;
    return true;
}

TC_C_STATIC_INLINE double tc_affine3d_determinant(tc_affine3d affine) {
    return tc_basis3d_determinant(affine.basis);
}

TC_C_STATIC_INLINE bool tc_affine3d_try_inverse(tc_affine3d affine, double epsilon, tc_affine3d* out_inverse) {
    if (out_inverse == NULL || !tc_affine3d_is_finite(affine)) {
        return false;
    }

    tc_basis3d inverse_basis;
    if (!tc_basis3d_try_inverse(affine.basis, epsilon, &inverse_basis)) {
        return false;
    }

    tc_vec3 inverse_translation = tc_basis3d_transform_vector(inverse_basis, tc_vec3_neg(affine.translation));
    tc_affine3d candidate = TC_AFFINE3D(inverse_basis, inverse_translation);
    if (!tc_affine3d_is_finite(candidate)) {
        return false;
    }
    *out_inverse = candidate;
    return true;
}

// Expands to the public OpenGL-style column-major 4x4 convention.
TC_C_STATIC_INLINE void tc_affine3d_to_matrix4(tc_affine3d affine, double* out_column_major_16) {
    if (out_column_major_16 == NULL) {
        return;
    }

    out_column_major_16[0] = affine.basis.x.x;
    out_column_major_16[1] = affine.basis.x.y;
    out_column_major_16[2] = affine.basis.x.z;
    out_column_major_16[3] = 0.0;
    out_column_major_16[4] = affine.basis.y.x;
    out_column_major_16[5] = affine.basis.y.y;
    out_column_major_16[6] = affine.basis.y.z;
    out_column_major_16[7] = 0.0;
    out_column_major_16[8] = affine.basis.z.x;
    out_column_major_16[9] = affine.basis.z.y;
    out_column_major_16[10] = affine.basis.z.z;
    out_column_major_16[11] = 0.0;
    out_column_major_16[12] = affine.translation.x;
    out_column_major_16[13] = affine.translation.y;
    out_column_major_16[14] = affine.translation.z;
    out_column_major_16[15] = 1.0;
}

TC_C_STATIC_INLINE bool
tc_affine3d_try_from_matrix4(const double* column_major_16, double epsilon, tc_affine3d* out_affine) {
    if (column_major_16 == NULL || out_affine == NULL || !isfinite(epsilon) || epsilon < 0.0) {
        return false;
    }

    for (size_t i = 0; i < 16; ++i) {
        if (!isfinite(column_major_16[i])) {
            return false;
        }
    }

    if (fabs(column_major_16[3]) > epsilon || fabs(column_major_16[7]) > epsilon ||
        fabs(column_major_16[11]) > epsilon || fabs(column_major_16[15] - 1.0) > epsilon) {
        return false;
    }

    *out_affine = TC_AFFINE3D(TC_BASIS3D(TC_VEC3(column_major_16[0], column_major_16[1], column_major_16[2]),
                                         TC_VEC3(column_major_16[4], column_major_16[5], column_major_16[6]),
                                         TC_VEC3(column_major_16[8], column_major_16[9], column_major_16[10])),
                              TC_VEC3(column_major_16[12], column_major_16[13], column_major_16[14]));
    return true;
}

#ifdef __cplusplus
}
#endif

#endif // TC_AFFINE3_H
