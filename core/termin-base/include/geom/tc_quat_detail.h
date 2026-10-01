// Internal component helpers shared by the C and C++ quaternion frontends.
#ifndef TC_QUAT_DETAIL_H
#define TC_QUAT_DETAIL_H

#include <math.h>
#include <stdbool.h>
#include <stddef.h>

#include <geom/tc_checked_normalization.h>

#ifdef __cplusplus
extern "C" {
#endif

// Apply a finite unit quaternion to a finite vector after scaling the vector
// by its largest component. This avoids overflow in the cross-product
// intermediates; the output is transactional when scale restoration itself is
// not representable. Quaternion normalization is the caller's job.
static inline bool tc_detail_try_rotate_unit_quat_f64_components(const double* quat_xyzw,
                                                                 const double* vector_xyz,
                                                                 bool inverse,
                                                                 double* out_xyz) {
    if (quat_xyzw == NULL || vector_xyz == NULL || out_xyz == NULL) {
        return false;
    }
    for (int i = 0; i < 4; ++i) {
        if (!isfinite(quat_xyzw[i])) {
            return false;
        }
    }

    double scale = 0.0;
    for (int i = 0; i < 3; ++i) {
        if (!isfinite(vector_xyz[i])) {
            return false;
        }
        scale = fmax(scale, fabs(vector_xyz[i]));
    }
    if (scale == 0.0) {
        out_xyz[0] = vector_xyz[0];
        out_xyz[1] = vector_xyz[1];
        out_xyz[2] = vector_xyz[2];
        return true;
    }

    const double qx = inverse ? -quat_xyzw[0] : quat_xyzw[0];
    const double qy = inverse ? -quat_xyzw[1] : quat_xyzw[1];
    const double qz = inverse ? -quat_xyzw[2] : quat_xyzw[2];
    const double qw = quat_xyzw[3];
    const double vx = vector_xyz[0] / scale;
    const double vy = vector_xyz[1] / scale;
    const double vz = vector_xyz[2] / scale;

    const double tx = 2.0 * (qy * vz - qz * vy);
    const double ty = 2.0 * (qz * vx - qx * vz);
    const double tz = 2.0 * (qx * vy - qy * vx);
    const double rotated[3] = {
        vx + qw * tx + qy * tz - qz * ty,
        vy + qw * ty + qz * tx - qx * tz,
        vz + qw * tz + qx * ty - qy * tx,
    };

    double result[3];
    for (int i = 0; i < 3; ++i) {
        result[i] = rotated[i] * scale;
        if (!isfinite(result[i])) {
            return false;
        }
    }
    out_xyz[0] = result[0];
    out_xyz[1] = result[1];
    out_xyz[2] = result[2];
    return true;
}

static inline bool
tc_detail_try_inverse_quat_f64_components(const double* quat_xyzw, double epsilon, double* out_xyzw) {
    if (quat_xyzw == NULL || out_xyzw == NULL || !isfinite(epsilon) || epsilon < 0.0) {
        return false;
    }

    double scale = 0.0;
    for (int i = 0; i < 4; ++i) {
        if (!isfinite(quat_xyzw[i])) {
            return false;
        }
        scale = fmax(scale, fabs(quat_xyzw[i]));
    }
    if (scale == 0.0) {
        return false;
    }

    const double sx = quat_xyzw[0] / scale;
    const double sy = quat_xyzw[1] / scale;
    const double sz = quat_xyzw[2] / scale;
    const double sw = quat_xyzw[3] / scale;
    const double scaled_squared = sx * sx + sy * sy + sz * sz + sw * sw;
    const double scaled_length = sqrt(scaled_squared);
    if (!isfinite(scaled_length) || scaled_length == 0.0 || scale <= epsilon / scaled_length) {
        return false;
    }

    // conj(q) / |q|^2 == conj(q / scale) / |q / scale|^2 / scale.
    const double result[4] = {
        -sx / scaled_squared / scale,
        -sy / scaled_squared / scale,
        -sz / scaled_squared / scale,
        sw / scaled_squared / scale,
    };
    for (int i = 0; i < 4; ++i) {
        if (!isfinite(result[i])) {
            return false;
        }
    }
    for (int i = 0; i < 4; ++i) {
        out_xyzw[i] = result[i];
    }
    return true;
}

static inline bool tc_detail_try_quat_from_axis_angle_f64_components(const double* axis_xyz,
                                                                     double angle,
                                                                     double epsilon,
                                                                     double* out_xyzw) {
    if (axis_xyz == NULL || out_xyzw == NULL || !isfinite(angle)) {
        return false;
    }
    double unit_axis[3];
    if (!tc_detail_try_normalize_f64_components(axis_xyz, 3, epsilon, unit_axis)) {
        return false;
    }

    const double half = angle * 0.5;
    const double sine = sin(half);
    const double result[4] = {
        unit_axis[0] * sine,
        unit_axis[1] * sine,
        unit_axis[2] * sine,
        cos(half),
    };
    for (int i = 0; i < 4; ++i) {
        if (!isfinite(result[i])) {
            return false;
        }
    }
    for (int i = 0; i < 4; ++i) {
        out_xyzw[i] = result[i];
    }
    return true;
}

// Accept only a finite proper rotation, with an absolute tolerance on every
// row/column Gram coefficient and determinant. Failure never changes output.
static inline bool tc_detail_try_quat_from_rotation_matrix_row_major_f64(const double* m,
                                                                        double epsilon,
                                                                        double* out_xyzw) {
    if (m == NULL || out_xyzw == NULL || !isfinite(epsilon) || epsilon < 0.0 || epsilon >= 1.0) {
        return false;
    }
    for (int i = 0; i < 9; ++i) {
        if (!isfinite(m[i])) {
            return false;
        }
    }
    for (int i = 0; i < 3; ++i) {
        for (int j = i; j < 3; ++j) {
            double rows = 0.0;
            double columns = 0.0;
            for (int k = 0; k < 3; ++k) {
                rows += m[i * 3 + k] * m[j * 3 + k];
                columns += m[k * 3 + i] * m[k * 3 + j];
            }
            const double expected = i == j ? 1.0 : 0.0;
            if (!isfinite(rows) || !isfinite(columns) || fabs(rows - expected) > epsilon ||
                fabs(columns - expected) > epsilon) {
                return false;
            }
        }
    }
    const double determinant = m[0] * (m[4] * m[8] - m[5] * m[7]) -
                               m[1] * (m[3] * m[8] - m[5] * m[6]) +
                               m[2] * (m[3] * m[7] - m[4] * m[6]);
    if (!isfinite(determinant) || determinant <= 0.0 || fabs(determinant - 1.0) > epsilon) {
        return false;
    }

    double raw[4];
    const double trace = m[0] + m[4] + m[8];
    if (trace > 0.0) {
        const double s = 2.0 * sqrt(trace + 1.0);
        raw[0] = (m[7] - m[5]) / s;
        raw[1] = (m[2] - m[6]) / s;
        raw[2] = (m[3] - m[1]) / s;
        raw[3] = 0.25 * s;
    } else if (m[0] > m[4] && m[0] > m[8]) {
        const double s = 2.0 * sqrt(1.0 + m[0] - m[4] - m[8]);
        raw[0] = 0.25 * s;
        raw[1] = (m[1] + m[3]) / s;
        raw[2] = (m[2] + m[6]) / s;
        raw[3] = (m[7] - m[5]) / s;
    } else if (m[4] > m[8]) {
        const double s = 2.0 * sqrt(1.0 + m[4] - m[0] - m[8]);
        raw[0] = (m[1] + m[3]) / s;
        raw[1] = 0.25 * s;
        raw[2] = (m[5] + m[7]) / s;
        raw[3] = (m[2] - m[6]) / s;
    } else {
        const double s = 2.0 * sqrt(1.0 + m[8] - m[0] - m[4]);
        raw[0] = (m[2] + m[6]) / s;
        raw[1] = (m[5] + m[7]) / s;
        raw[2] = 0.25 * s;
        raw[3] = (m[3] - m[1]) / s;
    }
    double result[4];
    if (!tc_detail_try_normalize_f64_components(raw, 4, 0.0, result)) {
        return false;
    }
    // q and -q represent the same rotation. Prefer positive w, then the first
    // nonzero x/y/z component for exact half turns.
    const int sign_order[4] = {3, 0, 1, 2};
    double sign = 1.0;
    for (int i = 0; i < 4; ++i) {
        if (result[sign_order[i]] != 0.0) {
            sign = result[sign_order[i]] < 0.0 ? -1.0 : 1.0;
            break;
        }
    }
    for (int i = 0; i < 4; ++i) {
        out_xyzw[i] = result[i] == 0.0 ? 0.0 : sign * result[i];
    }
    return true;
}

static inline void tc_detail_unit_quat_to_matrix3_row_major_f64(const double* quat_xyzw, double* out_row_major_9) {
    const double x = quat_xyzw[0];
    const double y = quat_xyzw[1];
    const double z = quat_xyzw[2];
    const double w = quat_xyzw[3];
    const double xx = x * x, yy = y * y, zz = z * z;
    const double xy = x * y, xz = x * z, yz = y * z;
    const double wx = w * x, wy = w * y, wz = w * z;

    out_row_major_9[0] = 1.0 - 2.0 * (yy + zz);
    out_row_major_9[1] = 2.0 * (xy - wz);
    out_row_major_9[2] = 2.0 * (xz + wy);
    out_row_major_9[3] = 2.0 * (xy + wz);
    out_row_major_9[4] = 1.0 - 2.0 * (xx + zz);
    out_row_major_9[5] = 2.0 * (yz - wx);
    out_row_major_9[6] = 2.0 * (xz - wy);
    out_row_major_9[7] = 2.0 * (yz + wx);
    out_row_major_9[8] = 1.0 - 2.0 * (xx + yy);
}

#ifdef __cplusplus
}
#endif

#endif // TC_QUAT_DETAIL_H
