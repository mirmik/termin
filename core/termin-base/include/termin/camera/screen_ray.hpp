#pragma once

#include <tcbase/tcbase_api.h>
#include <termin/geom/mat44.hpp>
#include <termin/geom/ray3.hpp>
#include <termin/geom/rect2.hpp>
#include <termin/geom/vec2.hpp>
#include <termin/geom/vec3.hpp>

namespace termin {

    /** Failure reported by checked screen/world projection producers and adapters. */
    enum class ScreenRayError {
        None,
        InvalidTolerance,
        InvalidScreenPoint,
        InvalidClipDepth,
        InvalidWorldPoint,
        InvalidViewport,
        MissingViewTransform,
        NonFiniteProjectionView,
        NonAffineView,
        SingularProjectionView,
        InvalidUnprojection,
        InvalidProjection,
        DegenerateDirection,
    };

    /** Stable human-readable description for a screen-ray failure. */
    TCBASE_API const char* screen_ray_error_message(ScreenRayError error) noexcept;

    /**
     * Semantic result of projecting a world point into a viewport.
     *
     * screen uses the same top-left/Y-down coordinate system as the input to
     * try_unproject_screen_point. depth is the canonical TerminClip Z value.
     * view_point is retained so camera owners do not need
     * to repeat an unchecked world-to-view transform merely to obtain view
     * depth or other camera-local diagnostics.
     */
    struct ProjectedScreenPoint {
        Vec2 screen{};
        double depth = 0.0;
        Vec3 view_point{};
    };

    /**
     * Unproject one top-left/Y-down screen point at a TerminClip depth.
     *
     * TerminClip depth must be finite and in [0, 1]. Projection and affine
     * view are supplied separately so homogeneous division occurs in camera
     * space before the large world-space translation is applied. On failure,
     * out is left unchanged.
     */
    TCBASE_API bool try_unproject_screen_point(const Mat44& projection,
                                               const Mat44& view,
                                               const Vec2& screen_point,
                                               double termin_clip_depth,
                                               const Rect2& viewport,
                                               Vec3& out,
                                               ScreenRayError* error = nullptr,
                                               double epsilon = 1.0e-12) noexcept;

    /**
     * Project a world point through separate affine view and projection matrices.
     *
     * The result uses TerminClip and top-left/Y-down viewport coordinates.
     * Points outside the viewport or clip-depth interval remain projectable;
     * only invalid inputs, unreliable transforms and an invalid homogeneous
     * divide fail. On failure, out is left unchanged.
     */
    TCBASE_API bool try_project_world_point(const Mat44& projection,
                                            const Mat44& view,
                                            const Vec3& world_point,
                                            const Rect2& viewport,
                                            ProjectedScreenPoint& out,
                                            ScreenRayError* error = nullptr,
                                            double epsilon = 1.0e-12) noexcept;

    /**
     * Unproject a framebuffer point through a double-precision projection-view matrix.
     *
     * Termin clip space uses a top-left screen origin and Z in [0, 1]. The
     * returned ray starts on the Z=0 clip plane and points toward the Z=1 clip
     * plane. Homogeneous division rejects exact zero W; epsilon is used for the
     * matrix-inverse reliability check and for rejecting a negligible ray
     * direction.
     *
     * On failure, out is left unchanged. When error is non-null it receives
     * ScreenRayError::None on success or the concrete failure reason.
     */
    TCBASE_API bool try_unproject_screen_ray(const Mat44& projection_view,
                                             const Vec2& screen_point,
                                             const Rect2& viewport,
                                             Ray3& out,
                                             ScreenRayError* error = nullptr,
                                             double epsilon = 1.0e-12) noexcept;

    /**
     * Unproject through separately supplied projection and view matrices.
     *
     * Prefer this overload when both matrices are available. It inverts the
     * projective matrix generically, treats the view as an affine transform,
     * and transforms the direction without its world translation. This
     * preserves a reliable checked path when a large world-space translation
     * makes the composed projection-view matrix poorly conditioned in storage
     * precision.
     *
     * The validation, clip-space convention and unchanged-out contract match
     * the projection-view overload above.
     */
    TCBASE_API bool try_unproject_screen_ray(const Mat44& projection,
                                             const Mat44& view,
                                             const Vec2& screen_point,
                                             const Rect2& viewport,
                                             Ray3& out,
                                             ScreenRayError* error = nullptr,
                                             double epsilon = 1.0e-12) noexcept;

} // namespace termin
