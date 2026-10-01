// Internal C++ definition fragment included by geom_types.h after tc_vec3.
struct tc_quat {
    // Raw packed xyzw coefficients. rotate/inverse_rotate/to_matrix are finite
    // unit-quaternion fast paths; use their try_ counterparts for uncertain
    // runtime input.
    double x = 0.0;
    double y = 0.0;
    double z = 0.0;
    double w = 1.0;

    constexpr tc_quat() noexcept = default;
    constexpr tc_quat(double x, double y, double z, double w) noexcept
        : x(x),
          y(y),
          z(z),
          w(w) {}

    static constexpr tc_quat identity() noexcept {
        return {0, 0, 0, 1};
    }

    tc_quat operator*(const tc_quat& q) const noexcept {
        return {w * q.x + x * q.w + y * q.z - z * q.y,
                w * q.y - x * q.z + y * q.w + z * q.x,
                w * q.z + x * q.y - y * q.x + z * q.w,
                w * q.w - x * q.x - y * q.y - z * q.z};
    }

    tc_quat conjugate() const noexcept {
        return {-x, -y, -z, w};
    }

    double dot(const tc_quat& other) const noexcept {
        return x * other.x + y * other.y + z * other.z + w * other.w;
    }

    double norm_squared() const noexcept {
        return dot(*this);
    }

    double norm() const noexcept {
        const double squared = norm_squared();
        // A positive subnormal sum may already have lost a material fraction
        // of its terms. Use hypot for that range as well as complete under/overflow.
        if (std::isnormal(squared)) {
            return std::sqrt(squared);
        }
        return std::hypot(std::hypot(x, y), std::hypot(z, w));
    }

    bool is_finite() const noexcept {
        return std::isfinite(x) && std::isfinite(y) && std::isfinite(z) && std::isfinite(w);
    }

    bool try_normalized(tc_quat& out, double epsilon = 1.0e-12) const noexcept {
        const double input[4] = {x, y, z, w};
        double output[4];
        if (!tc_detail_try_normalize_f64_components(input, 4, epsilon, output)) {
            return false;
        }
        out = {output[0], output[1], output[2], output[3]};
        return true;
    }

    tc_quat normalized_or(const tc_quat& fallback, double epsilon = 1.0e-12) const noexcept {
        tc_quat result;
        return try_normalized(result, epsilon) ? result : fallback;
    }

    tc_quat normalized(double epsilon = 1.0e-12) const noexcept {
        tc_quat result;
        if (try_normalized(result, epsilon)) {
            return result;
        }
        const double nan = std::numeric_limits<double>::quiet_NaN();
        return {nan, nan, nan, nan};
    }

    bool try_inverse(tc_quat& out, double epsilon = 1.0e-12) const noexcept {
        const double input[4] = {x, y, z, w};
        double result[4];
        if (!tc_detail_try_inverse_quat_f64_components(input, epsilon, result)) {
            return false;
        }
        out = {result[0], result[1], result[2], result[3]};
        return true;
    }

    tc_quat inverse(double epsilon = 1.0e-12) const noexcept {
        tc_quat result;
        if (try_inverse(result, epsilon)) {
            return result;
        }
        const double nan = std::numeric_limits<double>::quiet_NaN();
        return {nan, nan, nan, nan};
    }

    // Fast path: both the quaternion and vector must be finite and the
    // quaternion must have unit norm. Use try_rotate for uncertain input.
    tc_vec3 rotate(const tc_vec3& v) const noexcept {
        double tx = 2.0 * (y * v.z - z * v.y);
        double ty = 2.0 * (z * v.x - x * v.z);
        double tz = 2.0 * (x * v.y - y * v.x);

        return {v.x + w * tx + y * tz - z * ty, v.y + w * ty + z * tx - x * tz, v.z + w * tz + x * ty - y * tx};
    }

    // Fast path with the same finite unit-quaternion precondition as rotate.
    tc_vec3 inverse_rotate(const tc_vec3& v) const noexcept {
        return conjugate().rotate(v);
    }

    bool try_rotate(const tc_vec3& v, tc_vec3& out, double epsilon = 1.0e-12) const noexcept {
        tc_quat unit;
        if (!try_normalized(unit, epsilon)) {
            return false;
        }
        const double quat[4] = {unit.x, unit.y, unit.z, unit.w};
        const double vector[3] = {v.x, v.y, v.z};
        double result[3];
        if (!tc_detail_try_rotate_unit_quat_f64_components(quat, vector, false, result)) {
            return false;
        }
        out = {result[0], result[1], result[2]};
        return true;
    }

    bool try_inverse_rotate(const tc_vec3& v, tc_vec3& out, double epsilon = 1.0e-12) const noexcept {
        tc_quat unit;
        if (!try_normalized(unit, epsilon)) {
            return false;
        }
        const double quat[4] = {unit.x, unit.y, unit.z, unit.w};
        const double vector[3] = {v.x, v.y, v.z};
        double result[3];
        if (!tc_detail_try_rotate_unit_quat_f64_components(quat, vector, true, result)) {
            return false;
        }
        out = {result[0], result[1], result[2]};
        return true;
    }

    static bool
    try_from_axis_angle(const tc_vec3& axis, double angle, tc_quat& out, double epsilon = 1.0e-12) noexcept {
        const double axis_components[3] = {axis.x, axis.y, axis.z};
        double result[4];
        if (!tc_detail_try_quat_from_axis_angle_f64_components(axis_components, angle, epsilon, result)) {
            return false;
        }
        out = {result[0], result[1], result[2], result[3]};
        return true;
    }

    static tc_quat from_axis_angle(const tc_vec3& axis, double angle) {
        tc_quat result;
        if (try_from_axis_angle(axis, angle, result)) {
            return result;
        }
        const double nan = std::numeric_limits<double>::quiet_NaN();
        return {nan, nan, nan, nan};
    }

    static tc_quat look_rotation(const tc_vec3& forward, const tc_vec3& up = tc_vec3::unit_z()) {
        tc_vec3 f = forward.normalized();
        tc_vec3 r = f.cross(up).normalized();
        tc_vec3 u = r.cross(f);

        double m[9] = {r.x, f.x, u.x, r.y, f.y, u.y, r.z, f.z, u.z};
        return from_rotation_matrix(m);
    }

    static bool
    try_slerp(const tc_quat& a, const tc_quat& b, double t, tc_quat& out, double epsilon = 1.0e-12) noexcept {
        if (!std::isfinite(t) || !std::isfinite(epsilon) || epsilon < 0.0) {
            return false;
        }

        tc_quat from;
        tc_quat to;
        if (!a.try_normalized(from, epsilon) || !b.try_normalized(to, epsilon)) {
            return false;
        }

        double normalized_dot = from.dot(to);
        if (!std::isfinite(normalized_dot)) {
            return false;
        }
        if (normalized_dot < 0.0) {
            to = {-to.x, -to.y, -to.z, -to.w};
            normalized_dot = -normalized_dot;
        }
        if (normalized_dot > 1.0) {
            normalized_dot = 1.0;
        }

        tc_quat interpolated;
        if (normalized_dot > 0.9995) {
            interpolated = {from.x + t * (to.x - from.x),
                            from.y + t * (to.y - from.y),
                            from.z + t * (to.z - from.z),
                            from.w + t * (to.w - from.w)};
        } else {
            const double theta = std::acos(normalized_dot);
            const double sin_theta = std::sin(theta);
            const double from_angle = (1.0 - t) * theta;
            const double to_angle = t * theta;
            if (!std::isfinite(theta) || !std::isfinite(sin_theta) || sin_theta == 0.0 || !std::isfinite(from_angle) ||
                !std::isfinite(to_angle)) {
                return false;
            }
            const double from_weight = std::sin(from_angle) / sin_theta;
            const double to_weight = std::sin(to_angle) / sin_theta;
            interpolated = {from_weight * from.x + to_weight * to.x,
                            from_weight * from.y + to_weight * to.y,
                            from_weight * from.z + to_weight * to.z,
                            from_weight * from.w + to_weight * to.w};
        }

        tc_quat result;
        if (!interpolated.try_normalized(result, epsilon)) {
            return false;
        }
        out = result;
        return true;
    }

    static tc_quat slerp(const tc_quat& a, const tc_quat& b, double t, double epsilon = 1.0e-12) noexcept {
        tc_quat result;
        if (try_slerp(a, b, t, result, epsilon)) {
            return result;
        }
        const double nan = std::numeric_limits<double>::quiet_NaN();
        return {nan, nan, nan, nan};
    }

    static bool try_from_euler(const tc_vec3& euler_xyz, tc_quat& out) noexcept {
        if (!euler_xyz.is_finite()) {
            return false;
        }

        const double cx = std::cos(euler_xyz.x * 0.5);
        const double sx = std::sin(euler_xyz.x * 0.5);
        const double cy = std::cos(euler_xyz.y * 0.5);
        const double sy = std::sin(euler_xyz.y * 0.5);
        const double cz = std::cos(euler_xyz.z * 0.5);
        const double sz = std::sin(euler_xyz.z * 0.5);
        const tc_quat raw{sx * cy * cz - cx * sy * sz,
                          cx * sy * cz + sx * cy * sz,
                          cx * cy * sz - sx * sy * cz,
                          cx * cy * cz + sx * sy * sz};
        tc_quat result;
        if (!raw.try_normalized(result, 0.0)) {
            return false;
        }
        out = result;
        return true;
    }

    static tc_quat from_euler(const tc_vec3& euler_xyz) noexcept {
        tc_quat result;
        if (try_from_euler(euler_xyz, result)) {
            return result;
        }
        const double nan = std::numeric_limits<double>::quiet_NaN();
        return {nan, nan, nan, nan};
    }

    bool try_to_euler(tc_vec3& out, double epsilon = 1.0e-12) const noexcept {
        tc_quat q;
        if (!try_normalized(q, epsilon)) {
            return false;
        }

        double sin_pitch = 2.0 * (q.w * q.y - q.z * q.x);
        if (sin_pitch > 1.0) {
            sin_pitch = 1.0;
        } else if (sin_pitch < -1.0) {
            sin_pitch = -1.0;
        }

        tc_vec3 result;
        if (std::abs(sin_pitch) >= 1.0 - 1.0e-12) {
            // XYZ gimbal policy: choose roll = 0 and retain the uniquely
            // observable combined Z rotation in yaw.
            result.x = 0.0;
            result.y = std::copysign(0.5 * 3.14159265358979323846, sin_pitch);
            result.z = std::atan2(2.0 * (q.w * q.z - q.x * q.y), 1.0 - 2.0 * (q.x * q.x + q.z * q.z));
        } else {
            result.x = std::atan2(2.0 * (q.w * q.x + q.y * q.z), 1.0 - 2.0 * (q.x * q.x + q.y * q.y));
            result.y = std::asin(sin_pitch);
            result.z = std::atan2(2.0 * (q.w * q.z + q.x * q.y), 1.0 - 2.0 * (q.y * q.y + q.z * q.z));
        }
        if (!result.is_finite()) {
            return false;
        }
        out = result;
        return true;
    }

    tc_vec3 to_euler(double epsilon = 1.0e-12) const noexcept {
        tc_vec3 result;
        if (try_to_euler(result, epsilon)) {
            return result;
        }
        const double nan = std::numeric_limits<double>::quiet_NaN();
        return {nan, nan, nan};
    }

    // Checked row-major 3x3 proper rotation; failure preserves out.
    static bool try_from_rotation_matrix(const double* row_major_9,
                                         tc_quat& out,
                                         double epsilon = 1.0e-8) noexcept {
        double result[4];
        if (!tc_detail_try_quat_from_rotation_matrix_row_major_f64(row_major_9, epsilon, result)) {
            return false;
        }
        out = {result[0], result[1], result[2], result[3]};
        return true;
    }

    // Unchecked legacy conversion: m must point to a finite row-major proper
    // rotation matrix. Use try_from_rotation_matrix for uncertain input.
    static tc_quat from_rotation_matrix(const double* m) {
        double trace = m[0] + m[4] + m[8];
        double x, y, z, w;

        if (trace > 0) {
            double s = 0.5 / std::sqrt(trace + 1.0);
            w = 0.25 / s;
            x = (m[7] - m[5]) * s;
            y = (m[2] - m[6]) * s;
            z = (m[3] - m[1]) * s;
        } else if (m[0] > m[4] && m[0] > m[8]) {
            double s = 2.0 * std::sqrt(1.0 + m[0] - m[4] - m[8]);
            w = (m[7] - m[5]) / s;
            x = 0.25 * s;
            y = (m[1] + m[3]) / s;
            z = (m[2] + m[6]) / s;
        } else if (m[4] > m[8]) {
            double s = 2.0 * std::sqrt(1.0 + m[4] - m[0] - m[8]);
            w = (m[2] - m[6]) / s;
            x = (m[1] + m[3]) / s;
            y = 0.25 * s;
            z = (m[5] + m[7]) / s;
        } else {
            double s = 2.0 * std::sqrt(1.0 + m[8] - m[0] - m[4]);
            w = (m[3] - m[1]) / s;
            x = (m[2] + m[6]) / s;
            y = (m[5] + m[7]) / s;
            z = 0.25 * s;
        }

        return tc_quat{x, y, z, w}.normalized();
    }

    bool try_to_matrix(double* out_row_major_9, double epsilon = 1.0e-12) const noexcept {
        if (out_row_major_9 == nullptr) {
            return false;
        }
        tc_quat unit;
        if (!try_normalized(unit, epsilon)) {
            return false;
        }
        double result[9];
        unit.to_matrix(result);
        for (double coefficient : result) {
            if (!std::isfinite(coefficient)) {
                return false;
            }
        }
        for (int i = 0; i < 9; ++i) {
            out_row_major_9[i] = result[i];
        }
        return true;
    }

    // Fast row-major 3x3 conversion. The quaternion must be finite and unit;
    // use try_to_matrix for uncertain input.
    void to_matrix(double* m) const noexcept {
        const double quat[4] = {x, y, z, w};
        tc_detail_unit_quat_to_matrix3_row_major_f64(quat, m);
    }
};
