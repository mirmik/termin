#include <termin/render/world2d_quad_geometry.hpp>

#include <algorithm>

namespace termin {
    std::array<Vec3, 4> world2d_quad_corners(const World2DQuadRect& local_rect, const Mat44& model) {
        // On the XZ plane, this winding has normal -Y.
        return {
            model.transform_point({local_rect.min_x, 0.0, local_rect.min_z}),
            model.transform_point({local_rect.min_x, 0.0, local_rect.max_z}),
            model.transform_point({local_rect.max_x, 0.0, local_rect.max_z}),
            model.transform_point({local_rect.max_x, 0.0, local_rect.min_z}),
        };
    }

    AABB world2d_quad_bounds(const World2DQuadRect& local_rect, const Mat44& model) {
        const auto corners = world2d_quad_corners(local_rect, model);
        return AABB::from_points(corners.data(), corners.size());
    }

    bool ray_intersects_world2d_quad(const Ray3& ray,
                                     const World2DQuadRect& local_rect,
                                     const Mat44& model,
                                     double* out_ray_parameter) {
        const auto corners = world2d_quad_corners(local_rect, model);
        RayTriangleHit first;
        RayTriangleHit second;
        const bool hit_first = try_intersect_ray_triangle(ray, corners[0], corners[1], corners[2], first);
        const bool hit_second = try_intersect_ray_triangle(ray, corners[0], corners[2], corners[3], second);
        if (!hit_first && !hit_second) {
            return false;
        }
        if (out_ray_parameter) {
            *out_ray_parameter = hit_first && hit_second ? std::min(first.ray_parameter, second.ray_parameter)
                                                         : (hit_first ? first.ray_parameter : second.ray_parameter);
        }
        return true;
    }

} // namespace termin
