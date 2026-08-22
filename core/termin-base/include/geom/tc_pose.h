// tc_pose.h - Pose types (ang + lin + optional scale)
#ifndef TC_POSE_H
#define TC_POSE_H

#include "geom/tc_quat.h"
#include "geom/tc_vec3.h"
#include <tcbase/tc_types.h>

// C/C++ compatible struct initialization
// Layout: ang first, then lin (matches C++ Pose3/GeneralPose3)
#ifdef __cplusplus
#define TC_POSE3(rot, pos)                                                                                             \
    tc_pose3 {                                                                                                         \
        rot, pos                                                                                                       \
    }
#define TC_GPOSE(rot, pos, scl)                                                                                        \
    tc_general_pose3 {                                                                                                 \
        rot, pos, scl                                                                                                  \
    }
#else
#define TC_POSE3(rot, pos)                                                                                             \
    (tc_pose3) {                                                                                                       \
        rot, pos                                                                                                       \
    }
#define TC_GPOSE(rot, pos, scl)                                                                                        \
    (tc_general_pose3) {                                                                                               \
        rot, pos, scl                                                                                                  \
    }
#endif

#ifdef __cplusplus
extern "C" {
#endif

// ============================================================================
// Pose3 (ang + lin, no scale)
// ============================================================================
// Pose values store raw quaternion coefficients for ABI compatibility. All
// transform, composition, inverse and matrix fast paths below require ang to
// be finite and unit; validate and normalize at the owning input boundary.

TC_C_STATIC_INLINE tc_pose3 tc_pose3_identity(void) {
    return TC_POSE3(tc_quat_identity(), tc_vec3_zero());
}

TC_C_STATIC_INLINE tc_pose3 tc_pose3_new(tc_quat rot, tc_vec3 pos) {
    return TC_POSE3(rot, pos);
}

TC_C_STATIC_INLINE tc_pose3 tc_pose3_from_position(tc_vec3 pos) {
    return TC_POSE3(tc_quat_identity(), pos);
}

TC_C_STATIC_INLINE tc_pose3 tc_pose3_from_rotation(tc_quat rot) {
    return TC_POSE3(rot, tc_vec3_zero());
}

// Composition: parent * child
TC_C_STATIC_INLINE tc_pose3 tc_pose3_mul(tc_pose3 parent, tc_pose3 child) {
    return TC_POSE3(tc_quat_mul(parent.ang, child.ang), tc_vec3_add(parent.lin, tc_quat_rotate(parent.ang, child.lin)));
}

TC_C_STATIC_INLINE tc_pose3 tc_pose3_inverse(tc_pose3 p) {
    tc_quat inv_rot = tc_quat_inverse(p.ang);
    return TC_POSE3(inv_rot, tc_quat_rotate(inv_rot, tc_vec3_neg(p.lin)));
}

TC_C_STATIC_INLINE tc_vec3 tc_pose3_transform_point(tc_pose3 p, tc_vec3 point) {
    return tc_vec3_add(p.lin, tc_quat_rotate(p.ang, point));
}

TC_C_STATIC_INLINE tc_vec3 tc_pose3_transform_vector(tc_pose3 p, tc_vec3 vec) {
    return tc_quat_rotate(p.ang, vec);
}

// ============================================================================
// GeneralPose3 (ang + lin + scale)
// ============================================================================

TC_C_STATIC_INLINE tc_general_pose3 tc_gpose_identity(void) {
    return TC_GPOSE(tc_quat_identity(), tc_vec3_zero(), tc_vec3_one());
}

TC_C_STATIC_INLINE tc_general_pose3 tc_gpose_new(tc_quat rot, tc_vec3 pos, tc_vec3 scale) {
    return TC_GPOSE(rot, pos, scale);
}

TC_C_STATIC_INLINE tc_general_pose3 tc_gpose_from_pose(tc_pose3 p) {
    return TC_GPOSE(p.ang, p.lin, tc_vec3_one());
}

TC_C_STATIC_INLINE tc_pose3 tc_gpose_to_pose(tc_general_pose3 gp) {
    return TC_POSE3(gp.ang, gp.lin);
}

// Projected TRS composition. The exact affine product can contain shear.
TC_C_STATIC_INLINE tc_general_pose3 tc_gpose_compose_trs_projected(tc_general_pose3 parent, tc_general_pose3 child) {
    tc_vec3 scaled_child = tc_vec3_mul(parent.scale, child.lin);
    tc_vec3 rotated_child = tc_quat_rotate(parent.ang, scaled_child);

    return TC_GPOSE(tc_quat_mul(parent.ang, child.ang),
                    tc_vec3_add(parent.lin, rotated_child),
                    tc_vec3_mul(parent.scale, child.scale));
}

// Projected TRS inverse. The exact affine inverse can contain shear.
TC_C_STATIC_INLINE tc_general_pose3 tc_gpose_inverse_trs_projected(tc_general_pose3 p) {
    tc_quat inv_rot = tc_quat_inverse(p.ang);
    tc_vec3 inv_scale = TC_VEC3(1.0 / p.scale.x, 1.0 / p.scale.y, 1.0 / p.scale.z);
    tc_vec3 neg_pos = tc_vec3_neg(p.lin);
    tc_vec3 rotated = tc_quat_rotate(inv_rot, neg_pos);
    tc_vec3 scaled = tc_vec3_mul(inv_scale, rotated);

    return TC_GPOSE(inv_rot, scaled, inv_scale);
}

TC_C_STATIC_INLINE tc_vec3 tc_gpose_transform_point(tc_general_pose3 p, tc_vec3 point) {
    tc_vec3 scaled = tc_vec3_mul(p.scale, point);
    tc_vec3 rotated = tc_quat_rotate(p.ang, scaled);
    return tc_vec3_add(p.lin, rotated);
}

TC_C_STATIC_INLINE tc_vec3 tc_gpose_transform_vector(tc_general_pose3 p, tc_vec3 vec) {
    tc_vec3 scaled = tc_vec3_mul(p.scale, vec);
    return tc_quat_rotate(p.ang, scaled);
}

// ============================================================================
// Matrix conversion
// ============================================================================

// Fill 4x4 column-major matrix from Pose3 (no scale)
TC_C_STATIC_INLINE void tc_pose3_to_matrix(tc_pose3 p, double* out) {
    double rotation[9];
    tc_quat_to_matrix3_row_major(p.ang, rotation);

    // Column 0
    out[0] = rotation[0];
    out[1] = rotation[3];
    out[2] = rotation[6];
    out[3] = 0.0;

    // Column 1
    out[4] = rotation[1];
    out[5] = rotation[4];
    out[6] = rotation[7];
    out[7] = 0.0;

    // Column 2
    out[8] = rotation[2];
    out[9] = rotation[5];
    out[10] = rotation[8];
    out[11] = 0.0;

    // Column 3 (translation)
    out[12] = p.lin.x;
    out[13] = p.lin.y;
    out[14] = p.lin.z;
    out[15] = 1.0;
}

// Fill 4x4 column-major matrix from GeneralPose3
TC_C_STATIC_INLINE void tc_gpose_to_mat44(tc_general_pose3 p, tc_mat44* out) {
    double rotation[9];
    tc_quat_to_matrix3_row_major(p.ang, rotation);

    double sx = p.scale.x, sy = p.scale.y, sz = p.scale.z;

    // Column 0
    out->m[0] = sx * rotation[0];
    out->m[1] = sx * rotation[3];
    out->m[2] = sx * rotation[6];
    out->m[3] = 0.0;

    // Column 1
    out->m[4] = sy * rotation[1];
    out->m[5] = sy * rotation[4];
    out->m[6] = sy * rotation[7];
    out->m[7] = 0.0;

    // Column 2
    out->m[8] = sz * rotation[2];
    out->m[9] = sz * rotation[5];
    out->m[10] = sz * rotation[8];
    out->m[11] = 0.0;

    // Column 3 (translation)
    out->m[12] = p.lin.x;
    out->m[13] = p.lin.y;
    out->m[14] = p.lin.z;
    out->m[15] = 1.0;
}

// Interpolation
TC_C_STATIC_INLINE tc_general_pose3 tc_gpose_lerp(tc_general_pose3 a, tc_general_pose3 b, double t) {
    return TC_GPOSE(tc_quat_slerp(a.ang, b.ang, t), tc_vec3_lerp(a.lin, b.lin, t), tc_vec3_lerp(a.scale, b.scale, t));
}

#ifdef __cplusplus
}
#endif

#endif // TC_POSE_H
