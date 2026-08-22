#include "termin/camera/screen_ray.hpp"

#include <cmath>

#include <termin/geom/affine3.hpp>

namespace termin {
    namespace {
        bool fail(ScreenRayError reason, ScreenRayError* error) noexcept {
            if (error != nullptr) {
                *error = reason;
            }
            return false;
        }

        bool validate_screen_inputs(const Vec2& screen_point,
                                    const Rect2& viewport,
                                    double epsilon,
                                    ScreenRayError* error) noexcept {
            if (!std::isfinite(epsilon) || epsilon < 0.0) {
                return fail(ScreenRayError::InvalidTolerance, error);
            }
            if (!screen_point.is_finite()) {
                return fail(ScreenRayError::InvalidScreenPoint, error);
            }
            if (!viewport.is_finite() || viewport.width <= 0.0 || viewport.height <= 0.0) {
                return fail(ScreenRayError::InvalidViewport, error);
            }
            return true;
        }

        bool compute_ndc(const Vec2& screen_point,
                         const Rect2& viewport,
                         double& ndc_x,
                         double& ndc_y,
                         ScreenRayError* error) noexcept {
            ndc_x = ((screen_point.x - viewport.x) / viewport.width) * 2.0 - 1.0;
            ndc_y = ((screen_point.y - viewport.y) / viewport.height) * 2.0 - 1.0;
            return (std::isfinite(ndc_x) && std::isfinite(ndc_y)) ? true
                                                                  : fail(ScreenRayError::InvalidUnprojection, error);
        }

        bool homogeneous_point(const Vec4& value, Vec3& out) noexcept {
            if (!value.is_finite() || value.w == 0.0) {
                return false;
            }
            const Vec3 result{value.x / value.w, value.y / value.w, value.z / value.w};
            if (!result.is_finite()) {
                return false;
            }
            out = result;
            return true;
        }

        bool finish_ray(
            const Vec3& origin, const Vec3& raw_direction, Ray3& out, ScreenRayError* error, double epsilon) noexcept {
            Vec3 direction;
            if (!raw_direction.try_normalized(direction, epsilon)) {
                return fail(ScreenRayError::DegenerateDirection, error);
            }

            const Ray3 result{origin, direction};
            out = result;
            if (error != nullptr) {
                *error = ScreenRayError::None;
            }
            return true;
        }

        bool load_checked_split_transform(const Mat44& projection,
                                          const Mat44& view,
                                          double epsilon,
                                          Mat44& inverse_projection,
                                          Affine3d& view_affine,
                                          ScreenRayError* error) noexcept {
            if (!projection.is_finite() || !view.is_finite()) {
                return fail(ScreenRayError::NonFiniteProjectionView, error);
            }
            if (!projection.try_inverse(inverse_projection, epsilon)) {
                return fail(ScreenRayError::SingularProjectionView, error);
            }
            // A camera view is affine by contract. Require its homogeneous row
            // exactly so tiny projective terms are never silently discarded.
            if (!Affine3d::try_from_matrix4(view.data, view_affine, 0.0)) {
                return fail(ScreenRayError::NonAffineView, error);
            }
            return true;
        }

        void succeed(ScreenRayError* error) noexcept {
            if (error != nullptr) {
                *error = ScreenRayError::None;
            }
        }
    } // namespace

    const char* screen_ray_error_message(ScreenRayError error) noexcept {
        switch (error) {
        case ScreenRayError::None:
            return "no error";
        case ScreenRayError::InvalidTolerance:
            return "screen projection tolerance must be finite and non-negative";
        case ScreenRayError::InvalidScreenPoint:
            return "screen point must be finite";
        case ScreenRayError::InvalidClipDepth:
            return "TerminClip depth must be finite and in [0, 1]";
        case ScreenRayError::InvalidWorldPoint:
            return "world point must be finite";
        case ScreenRayError::InvalidViewport:
            return "viewport must be finite and have positive width and height";
        case ScreenRayError::MissingViewTransform:
            return "view transform is unavailable";
        case ScreenRayError::NonFiniteProjectionView:
            return "projection/view transform must be finite";
        case ScreenRayError::NonAffineView:
            return "view matrix must be affine";
        case ScreenRayError::SingularProjectionView:
            return "projection/view transform has no reliable inverse";
        case ScreenRayError::InvalidUnprojection:
            return "clip points cannot be unprojected to finite world points";
        case ScreenRayError::InvalidProjection:
            return "world point cannot be projected to finite screen coordinates";
        case ScreenRayError::DegenerateDirection:
            return "unprojected near and far points do not define a reliable direction";
        }
        return "unknown screen-ray error";
    }

    bool try_unproject_screen_point(const Mat44& projection,
                                    const Mat44& view,
                                    const Vec2& screen_point,
                                    double termin_clip_depth,
                                    const Rect2& viewport,
                                    Vec3& out,
                                    ScreenRayError* error,
                                    double epsilon) noexcept {
        if (!validate_screen_inputs(screen_point, viewport, epsilon, error)) {
            return false;
        }
        if (!std::isfinite(termin_clip_depth) || termin_clip_depth < 0.0 || termin_clip_depth > 1.0) {
            return fail(ScreenRayError::InvalidClipDepth, error);
        }

        Mat44 inverse_projection;
        Affine3d view_affine;
        if (!load_checked_split_transform(projection, view, epsilon, inverse_projection, view_affine, error)) {
            return false;
        }

        double ndc_x = 0.0;
        double ndc_y = 0.0;
        if (!compute_ndc(screen_point, viewport, ndc_x, ndc_y, error)) {
            return false;
        }

        Vec3 view_point;
        if (!homogeneous_point(inverse_projection.transform_homogeneous({ndc_x, ndc_y, termin_clip_depth, 1.0}),
                               view_point)) {
            return fail(ScreenRayError::InvalidUnprojection, error);
        }

        // Apply the inverse view as an origin plus a translation-free vector.
        // This avoids combining a small camera-local point with the large view
        // translation before the inverse basis has been applied.
        Vec3 world_origin;
        Vec3 world_offset;
        if (!view_affine.try_inverse_transform_point(Vec3::zero(), world_origin, epsilon) ||
            !view_affine.try_inverse_transform_vector(view_point, world_offset, epsilon)) {
            return fail(ScreenRayError::SingularProjectionView, error);
        }
        const Vec3 result = world_origin + world_offset;
        if (!result.is_finite()) {
            return fail(ScreenRayError::InvalidUnprojection, error);
        }

        out = result;
        succeed(error);
        return true;
    }

    bool try_project_world_point(const Mat44& projection,
                                 const Mat44& view,
                                 const Vec3& world_point,
                                 const Rect2& viewport,
                                 ProjectedScreenPoint& out,
                                 ScreenRayError* error,
                                 double epsilon) noexcept {
        if (!std::isfinite(epsilon) || epsilon < 0.0) {
            return fail(ScreenRayError::InvalidTolerance, error);
        }
        if (!world_point.is_finite()) {
            return fail(ScreenRayError::InvalidWorldPoint, error);
        }
        if (!viewport.is_finite() || viewport.width <= 0.0 || viewport.height <= 0.0) {
            return fail(ScreenRayError::InvalidViewport, error);
        }

        Mat44 inverse_projection;
        Affine3d view_affine;
        if (!load_checked_split_transform(projection, view, epsilon, inverse_projection, view_affine, error)) {
            return false;
        }

        // Center the world point at the view-space origin before applying the
        // view basis. For large worlds this retains the local difference that
        // would otherwise be lost while adding the stored view translation.
        Vec3 world_view_origin;
        if (!view_affine.try_inverse_transform_point(Vec3::zero(), world_view_origin, epsilon)) {
            return fail(ScreenRayError::SingularProjectionView, error);
        }
        const Vec3 view_point = view_affine.transform_vector(world_point - world_view_origin);
        if (!view_point.is_finite()) {
            return fail(ScreenRayError::InvalidProjection, error);
        }

        const Vec4 clip = projection.transform_homogeneous({view_point.x, view_point.y, view_point.z, 1.0});
        if (!clip.is_finite() || clip.w == 0.0) {
            return fail(ScreenRayError::InvalidProjection, error);
        }
        const Vec3 ndc{clip.x / clip.w, clip.y / clip.w, clip.z / clip.w};
        if (!ndc.is_finite()) {
            return fail(ScreenRayError::InvalidProjection, error);
        }

        ProjectedScreenPoint result;
        result.screen = {
            viewport.x + (ndc.x + 1.0) * 0.5 * viewport.width,
            viewport.y + (ndc.y + 1.0) * 0.5 * viewport.height,
        };
        result.depth = ndc.z;
        result.view_point = view_point;
        if (!result.screen.is_finite() || !std::isfinite(result.depth)) {
            return fail(ScreenRayError::InvalidProjection, error);
        }

        out = result;
        succeed(error);
        return true;
    }

    bool try_unproject_screen_ray(const Mat44& projection_view,
                                  const Vec2& screen_point,
                                  const Rect2& viewport,
                                  Ray3& out,
                                  ScreenRayError* error,
                                  double epsilon) noexcept {
        if (!validate_screen_inputs(screen_point, viewport, epsilon, error)) {
            return false;
        }
        if (!projection_view.is_finite()) {
            return fail(ScreenRayError::NonFiniteProjectionView, error);
        }

        Mat44 inverse_projection_view;
        if (!projection_view.try_inverse(inverse_projection_view, epsilon)) {
            return fail(ScreenRayError::SingularProjectionView, error);
        }

        double ndc_x = 0.0;
        double ndc_y = 0.0;
        if (!compute_ndc(screen_point, viewport, ndc_x, ndc_y, error)) {
            return false;
        }

        Vec3 near_point;
        Vec3 far_point;
        // A tiny but non-zero W is still a mathematically defined projective
        // point. World-space validity is checked after the exact divide.
        if (!homogeneous_point(inverse_projection_view.transform_homogeneous({ndc_x, ndc_y, 0.0, 1.0}), near_point) ||
            !homogeneous_point(inverse_projection_view.transform_homogeneous({ndc_x, ndc_y, 1.0, 1.0}), far_point)) {
            return fail(ScreenRayError::InvalidUnprojection, error);
        }

        return finish_ray(near_point, far_point - near_point, out, error, epsilon);
    }

    bool try_unproject_screen_ray(const Mat44& projection,
                                  const Mat44& view,
                                  const Vec2& screen_point,
                                  const Rect2& viewport,
                                  Ray3& out,
                                  ScreenRayError* error,
                                  double epsilon) noexcept {
        if (!validate_screen_inputs(screen_point, viewport, epsilon, error)) {
            return false;
        }
        if (!projection.is_finite() || !view.is_finite()) {
            return fail(ScreenRayError::NonFiniteProjectionView, error);
        }

        Mat44 inverse_projection;
        Affine3d view_affine;
        if (!load_checked_split_transform(projection, view, epsilon, inverse_projection, view_affine, error)) {
            return false;
        }

        double ndc_x = 0.0;
        double ndc_y = 0.0;
        if (!compute_ndc(screen_point, viewport, ndc_x, ndc_y, error)) {
            return false;
        }

        Vec3 near_camera;
        Vec3 far_camera;
        if (!homogeneous_point(inverse_projection.transform_homogeneous({ndc_x, ndc_y, 0.0, 1.0}), near_camera) ||
            !homogeneous_point(inverse_projection.transform_homogeneous({ndc_x, ndc_y, 1.0, 1.0}), far_camera)) {
            return fail(ScreenRayError::InvalidUnprojection, error);
        }

        Vec3 world_origin;
        Vec3 world_direction;
        if (!view_affine.try_inverse_transform_point(near_camera, world_origin, epsilon) ||
            !view_affine.try_inverse_transform_vector(far_camera - near_camera, world_direction, epsilon)) {
            return fail(ScreenRayError::SingularProjectionView, error);
        }

        return finish_ray(world_origin, world_direction, out, error, epsilon);
    }

} // namespace termin
