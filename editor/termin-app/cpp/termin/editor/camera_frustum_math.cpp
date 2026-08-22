#include "termin/editor/camera_frustum_debug_gizmo.hpp"

#include <termin/geom/mat44.hpp>

#include <cmath>

namespace termin {

    namespace {

        constexpr double kSingularEpsilon = 1.0e-10;
        constexpr double kPerspectiveEpsilon = 1.0e-10;

        void set_error(std::string* error, const char* message) {
            if (error) {
                *error = message;
            }
        }

    } // namespace

    bool compute_camera_frustum_corners(const tc_camera_data& camera, CameraFrustumCorners& out, std::string* error) {
        const Mat44 view = Mat44::from_column_major_f64(camera.view);
        const Mat44 projection = Mat44::from_column_major_f64(camera.projection);
        const Mat44 projection_view = projection * view;
        if (!projection_view.is_finite()) {
            set_error(error, "projection-view matrix is non-finite");
            return false;
        }
        const double determinant = projection_view.determinant();
        if (!std::isfinite(determinant) || std::abs(determinant) <= kSingularEpsilon) {
            set_error(error, "projection-view matrix is singular");
            return false;
        }

        Mat44 inverse_projection_view;
        if (!projection_view.try_inverse(inverse_projection_view, kSingularEpsilon)) {
            set_error(error, "projection-view matrix cannot be inverted");
            return false;
        }
        const std::array<Vec3, 8> ndc = {{
            {-1.0, -1.0, 0.0},
            {1.0, -1.0, 0.0},
            {-1.0, 1.0, 0.0},
            {1.0, 1.0, 0.0},
            {-1.0, -1.0, 1.0},
            {1.0, -1.0, 1.0},
            {-1.0, 1.0, 1.0},
            {1.0, 1.0, 1.0},
        }};

        CameraFrustumCorners result;
        for (size_t i = 0; i < ndc.size(); ++i) {
            if (!inverse_projection_view.try_transform_point(ndc[i], result.points[i], kPerspectiveEpsilon)) {
                set_error(error, "unprojected frustum corner is invalid");
                return false;
            }
        }

        out = result;
        if (error) {
            error->clear();
        }
        return true;
    }

} // namespace termin
