#include "openxr_math.hpp"

#if defined(TERMIN_OPENXR_HAS_HEADERS) && defined(__ANDROID__)

#include <cmath>

namespace termin::openxr {

XrVector3f rotate_xr_vector(const XrQuaternionf& q, const XrVector3f& v) {
    const float tx = 2.0f * (q.y * v.z - q.z * v.y);
    const float ty = 2.0f * (q.z * v.x - q.x * v.z);
    const float tz = 2.0f * (q.x * v.y - q.y * v.x);

    return XrVector3f{
        v.x + q.w * tx + q.y * tz - q.z * ty,
        v.y + q.w * ty + q.z * tx - q.x * tz,
        v.z + q.w * tz + q.x * ty - q.y * tx
    };
}

termin::Vec3 xr_direction_to_scene_direction(const XrVector3f& p) {
    return termin::Vec3{
        static_cast<double>(p.x),
        static_cast<double>(-p.z),
        static_cast<double>(p.y)
    };
}

std::array<float, 16> make_identity_matrix() {
    return {
        1.0f, 0.0f, 0.0f, 0.0f,
        0.0f, 1.0f, 0.0f, 0.0f,
        0.0f, 0.0f, 1.0f, 0.0f,
        0.0f, 0.0f, 0.0f, 1.0f,
    };
}

std::array<float, 16> make_xr_projection_matrix_vulkan(const XrFovf& fov, float near_z, float far_z) {
    const float tan_left = std::tan(fov.angleLeft);
    const float tan_right = std::tan(fov.angleRight);
    const float tan_down = std::tan(fov.angleDown);
    const float tan_up = std::tan(fov.angleUp);
    const float tan_width = tan_right - tan_left;
    const float tan_height = tan_down - tan_up;

    std::array<float, 16> m{};
    m[0] = 2.0f / tan_width;
    m[5] = 2.0f / tan_height;
    m[8] = (tan_right + tan_left) / tan_width;
    m[9] = (tan_up + tan_down) / tan_height;
    m[10] = far_z / (near_z - far_z);
    m[11] = -1.0f;
    m[14] = (far_z * near_z) / (near_z - far_z);
    return m;
}

termin::Mat44 make_engine_projection_from_xr_fov(const XrFovf& fov, float near_z, float far_z) {
    constexpr double kPi = 3.14159265358979323846;
    const double tan_left = std::tan(static_cast<double>(fov.angleLeft));
    const double tan_right = std::tan(static_cast<double>(fov.angleRight));
    const double tan_down = std::tan(static_cast<double>(fov.angleDown));
    const double tan_up = std::tan(static_cast<double>(fov.angleUp));
    const double tan_width = tan_right - tan_left;
    const double tan_height = tan_up - tan_down;

    termin::Mat44 m = termin::Mat44::zero();
    if (std::abs(tan_width) < 1e-9 || std::abs(tan_height) < 1e-9 || far_z <= near_z) {
        return termin::Mat44::perspective(90.0 * kPi / 180.0, 1.0, near_z, far_z);
    }

    // Engine camera space is X-right, Y-forward, Z-up. OpenXR FOV angles
    // describe the same physical eye frustum in X-right, Y-up, -Z-forward.
    // Convert only the projection coefficients; keep the resulting matrix in
    // engine semantics so shaders may safely use view_pos.y as linear depth.
    m(0, 0) = 2.0 / tan_width;
    m(1, 0) = -(tan_right + tan_left) / tan_width;
    m(2, 1) = -2.0 / tan_height;
    m(1, 1) = (tan_up + tan_down) / tan_height;
    m(1, 2) = far_z / (far_z - near_z);
    m(3, 2) = -(far_z * near_z) / (far_z - near_z);
    m(1, 3) = 1.0;
    return m;
}

std::array<float, 16> multiply_matrix(
    const std::array<float, 16>& a,
    const std::array<float, 16>& b
) {
    std::array<float, 16> out{};
    for (int col = 0; col < 4; ++col) {
        for (int row = 0; row < 4; ++row) {
            out[col * 4 + row] =
                a[0 * 4 + row] * b[col * 4 + 0] +
                a[1 * 4 + row] * b[col * 4 + 1] +
                a[2 * 4 + row] * b[col * 4 + 2] +
                a[3 * 4 + row] * b[col * 4 + 3];
        }
    }
    return out;
}

std::array<float, 16> make_view_matrix_from_xr_pose(const XrPosef& pose) {
    const XrQuaternionf& q = pose.orientation;
    const float x2 = q.x + q.x;
    const float y2 = q.y + q.y;
    const float z2 = q.z + q.z;
    const float xx = q.x * x2;
    const float xy = q.x * y2;
    const float xz = q.x * z2;
    const float yy = q.y * y2;
    const float yz = q.y * z2;
    const float zz = q.z * z2;
    const float wx = q.w * x2;
    const float wy = q.w * y2;
    const float wz = q.w * z2;

    const float r00 = 1.0f - (yy + zz);
    const float r01 = xy - wz;
    const float r02 = xz + wy;
    const float r10 = xy + wz;
    const float r11 = 1.0f - (xx + zz);
    const float r12 = yz - wx;
    const float r20 = xz - wy;
    const float r21 = yz + wx;
    const float r22 = 1.0f - (xx + yy);

    const XrVector3f& p = pose.position;
    const float tx = -(r00 * p.x + r10 * p.y + r20 * p.z);
    const float ty = -(r01 * p.x + r11 * p.y + r21 * p.z);
    const float tz = -(r02 * p.x + r12 * p.y + r22 * p.z);

    return {
        r00, r01, r02, 0.0f,
        r10, r11, r12, 0.0f,
        r20, r21, r22, 0.0f,
        tx,  ty,  tz,  1.0f,
    };
}

termin::Mat44 mat44_from_float_array(const std::array<float, 16>& src) {
    termin::Mat44 out = termin::Mat44::identity();
    for (size_t i = 0; i < src.size(); ++i) {
        out.data[i] = static_cast<double>(src[i]);
    }
    return out;
}

termin::Mat44 make_scene_to_xr_matrix() {
    termin::Mat44 m = termin::Mat44::identity();
    m.data[0] = 1.0;
    m.data[1] = 0.0;
    m.data[2] = 0.0;
    m.data[4] = 0.0;
    m.data[5] = 0.0;
    m.data[6] = -1.0;
    m.data[8] = 0.0;
    m.data[9] = 1.0;
    m.data[10] = 0.0;
    return m;
}

termin::Mat44 make_xr_to_scene_matrix() {
    termin::Mat44 m = termin::Mat44::identity();
    m.data[0] = 1.0;
    m.data[1] = 0.0;
    m.data[2] = 0.0;
    m.data[4] = 0.0;
    m.data[5] = 0.0;
    m.data[6] = 1.0;
    m.data[8] = 0.0;
    m.data[9] = -1.0;
    m.data[10] = 0.0;
    return m;
}

termin::Vec3 xr_position_to_scene_position(const XrVector3f& p) {
    return termin::Vec3{
        static_cast<double>(p.x),
        static_cast<double>(-p.z),
        static_cast<double>(p.y)
    };
}

} // namespace termin::openxr

#endif // defined(TERMIN_OPENXR_HAS_HEADERS) && defined(__ANDROID__)
