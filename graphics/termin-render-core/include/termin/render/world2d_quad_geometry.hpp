#pragma once

#include <array>

#include <termin/geom/aabb.hpp>
#include <termin/geom/mat44.hpp>
#include <termin/geom/ray3.hpp>
#include <termin/render/render_export.hpp>

namespace termin {

    struct World2DQuadRect {
        double min_x = 0.0;
        double min_z = 0.0;
        double max_x = 0.0;
        double max_z = 0.0;
    };

    // Counter-clockwise when seen from the canonical camera on -Y looking +Y.
    RENDER_CORE_API std::array<Vec3, 4> world2d_quad_corners(const World2DQuadRect& local_rect, const Mat44& model);

    // Returns an exact planar AABB. No arbitrary thickness is introduced.
    RENDER_CORE_API AABB world2d_quad_bounds(const World2DQuadRect& local_rect, const Mat44& model);

    // Exact ray/quad test. The returned ray parameter t locates the hit at
    // ray.point_at(t). Hits at the ray origin are accepted.
    // Negative/non-uniform scale is handled by transforming all four corners.
    // Any failure leaves out_ray_parameter unchanged.
    RENDER_CORE_API bool ray_intersects_world2d_quad(const Ray3& ray,
                                                     const World2DQuadRect& local_rect,
                                                     const Mat44& model,
                                                     double* out_ray_parameter = nullptr);

} // namespace termin
