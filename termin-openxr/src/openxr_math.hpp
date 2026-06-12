#pragma once

#if defined(TERMIN_OPENXR_HAS_HEADERS) && defined(__ANDROID__)

#include <array>
#include <vector>

#include <openxr/openxr.h>

#include <termin/geom/mat44.hpp>
#include <termin/geom/vec3.hpp>

namespace termin::openxr {

XrVector3f rotate_xr_vector(const XrQuaternionf& q, const XrVector3f& v);
termin::Vec3 xr_direction_to_scene_direction(const XrVector3f& p);

std::array<float, 16> make_identity_matrix();
std::array<float, 16> make_xr_projection_matrix_vulkan(const XrFovf& fov, float near_z, float far_z);
termin::Mat44 make_engine_projection_from_xr_fov(const XrFovf& fov, float near_z, float far_z);
std::array<float, 16> multiply_matrix(
    const std::array<float, 16>& a,
    const std::array<float, 16>& b
);
std::array<float, 16> make_view_matrix_from_xr_pose(const XrPosef& pose);
termin::Mat44 mat44_from_float_array(const std::array<float, 16>& src);
termin::Mat44 make_scene_to_xr_matrix();
termin::Mat44 make_xr_to_scene_matrix();
termin::Vec3 xr_position_to_scene_position(const XrVector3f& p);

} // namespace termin::openxr

#endif // defined(TERMIN_OPENXR_HAS_HEADERS) && defined(__ANDROID__)
