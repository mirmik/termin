#include "termin/editor/camera_frustum_debug_gizmo.hpp"

#include <termin/geom/mat44.hpp>

#include <cmath>

namespace termin {

namespace {

constexpr double kSingularEpsilon = 1.0e-10;
constexpr double kPerspectiveEpsilon = 1.0e-10;

Mat44 mat44_from_array(const double* data)
{
    Mat44 result;
    for (int i = 0; i < 16; ++i) {
        result.data[i] = data[i];
    }
    return result;
}

double determinant4(const Mat44& matrix)
{
    const double* m = matrix.data;
    double inv0 = m[5] * m[10] * m[15] - m[5] * m[11] * m[14]
        - m[9] * m[6] * m[15] + m[9] * m[7] * m[14]
        + m[13] * m[6] * m[11] - m[13] * m[7] * m[10];
    double inv4 = -m[4] * m[10] * m[15] + m[4] * m[11] * m[14]
        + m[8] * m[6] * m[15] - m[8] * m[7] * m[14]
        - m[12] * m[6] * m[11] + m[12] * m[7] * m[10];
    double inv8 = m[4] * m[9] * m[15] - m[4] * m[11] * m[13]
        - m[8] * m[5] * m[15] + m[8] * m[7] * m[13]
        + m[12] * m[5] * m[11] - m[12] * m[7] * m[9];
    double inv12 = -m[4] * m[9] * m[14] + m[4] * m[10] * m[13]
        + m[8] * m[5] * m[14] - m[8] * m[6] * m[13]
        - m[12] * m[5] * m[10] + m[12] * m[6] * m[9];
    return m[0] * inv0 + m[1] * inv4 + m[2] * inv8 + m[3] * inv12;
}

bool unproject_clip_point(
    const Mat44& inverse_projection_view,
    double x,
    double y,
    double z,
    Vec3& out
)
{
    double wx = inverse_projection_view(0, 0) * x
        + inverse_projection_view(1, 0) * y
        + inverse_projection_view(2, 0) * z
        + inverse_projection_view(3, 0);
    double wy = inverse_projection_view(0, 1) * x
        + inverse_projection_view(1, 1) * y
        + inverse_projection_view(2, 1) * z
        + inverse_projection_view(3, 1);
    double wz = inverse_projection_view(0, 2) * x
        + inverse_projection_view(1, 2) * y
        + inverse_projection_view(2, 2) * z
        + inverse_projection_view(3, 2);
    double ww = inverse_projection_view(0, 3) * x
        + inverse_projection_view(1, 3) * y
        + inverse_projection_view(2, 3) * z
        + inverse_projection_view(3, 3);
    if (std::abs(ww) <= kPerspectiveEpsilon) {
        return false;
    }
    out = Vec3{wx / ww, wy / ww, wz / ww};
    return std::isfinite(out.x) && std::isfinite(out.y) && std::isfinite(out.z);
}

void set_error(std::string* error, const char* message)
{
    if (error) {
        *error = message;
    }
}

} // namespace

bool compute_camera_frustum_corners(
    const tc_camera_data& camera,
    CameraFrustumCorners& out,
    std::string* error
)
{
    Mat44 view = mat44_from_array(camera.view);
    Mat44 projection = mat44_from_array(camera.projection);
    Mat44 projection_view = projection * view;
    if (std::abs(determinant4(projection_view)) <= kSingularEpsilon) {
        set_error(error, "projection-view matrix is singular");
        return false;
    }

    Mat44 inverse_projection_view = projection_view.inverse();
    const std::array<std::array<double, 3>, 8> ndc = {{
        {{-1.0, -1.0, 0.0}},
        {{ 1.0, -1.0, 0.0}},
        {{-1.0,  1.0, 0.0}},
        {{ 1.0,  1.0, 0.0}},
        {{-1.0, -1.0, 1.0}},
        {{ 1.0, -1.0, 1.0}},
        {{-1.0,  1.0, 1.0}},
        {{ 1.0,  1.0, 1.0}},
    }};

    for (size_t i = 0; i < ndc.size(); ++i) {
        if (!unproject_clip_point(inverse_projection_view, ndc[i][0], ndc[i][1], ndc[i][2], out.points[i])) {
            set_error(error, "unprojected frustum corner is invalid");
            return false;
        }
    }

    if (error) {
        error->clear();
    }
    return true;
}

} // namespace termin
