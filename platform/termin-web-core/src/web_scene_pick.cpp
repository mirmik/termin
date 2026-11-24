#include "web_scene_pick.hpp"

#include <algorithm>
#include <cmath>
#include <stdexcept>

#include <core/tc_entity_pool.h>
#include <render/tc_render_target.h>
#include <render/tc_viewport.h>
#include <termin/camera/screen_ray.hpp>
#include <termin/geom/ray3.hpp>
#include <termin/render/camera_capability.hpp>
#include <termin/render/render_scene_item_collector.hpp>
#include <tgfx/resources/tc_mesh_registry.h>

namespace termin::web {
    namespace {
        bool crosses_bounds(const Ray3& ray, const tc_aabb& bounds, double end) {
            double start = 0.0;
            for (int axis = 0; axis < 3; ++axis) {
                const double origin = ray.origin[axis], direction = ray.direction[axis];
                if (direction == 0.0) {
                    if (origin < bounds.min_point[axis] || origin > bounds.max_point[axis])
                        return false;
                    continue;
                }
                const double a = (bounds.min_point[axis] - origin) / direction;
                const double b = (bounds.max_point[axis] - origin) / direction;
                start = std::max(start, std::min(a, b));
                end = std::min(end, std::max(a, b));
                if (start > end)
                    return false;
            }
            return true;
        }

        bool intersect_section(const tc_render_item& item, const Ray3& world_segment, double& nearest) {
            if (item.kind != TC_RENDER_ITEM_KIND_MESH || !(item.flags & TC_RENDER_ITEM_FLAG_CONSERVATIVE_MESH_BOUNDS))
                return false;
            tc_mesh* mesh = tc_mesh_get(item.payload.mesh.mesh_handle);
            const size_t section = item.payload.mesh.submesh_index;
            const tc_submesh* submesh = mesh ? tc_mesh_get_submesh(mesh, section) : nullptr;
            // Bounds are computed only after validating first_index/index_count,
            // signed base vertex offsets, CPU storage, and all vertex positions.
            tc_aabb bounds;
            if (!submesh || submesh->draw_mode != TC_DRAW_TRIANGLES ||
                !tc_mesh_get_submesh_bounds(mesh, section, &bounds))
                return false;

            Mat44 inverse;
            if (!Mat44f(item.model_matrix).to_double().try_inverse(inverse))
                return false;
            // Keeping the transformed direction unnormalized preserves the same
            // segment parameter across differently scaled objects.
            Ray3 ray;
            ray.origin = inverse.transform_point(world_segment.origin);
            ray.direction = inverse.transform_direction(world_segment.direction);
            if (!crosses_bounds(ray, bounds, nearest))
                return false;

            bool found = false;
            const size_t end = static_cast<size_t>(submesh->first_index) + submesh->index_count;
            for (size_t i = submesh->first_index; end - i >= 3; i += 3) {
                tc_vec3f vertices[3];
                for (size_t j = 0; j < 3; ++j) {
                    const int64_t vertex = static_cast<int64_t>(mesh->indices[i + j]) + submesh->vertex_offset;
                    if (!tc_mesh_get_position3f(mesh, static_cast<uint32_t>(vertex), &vertices[j]))
                        return false;
                }
                RayTriangleHit hit;
                if (try_intersect_ray_triangle(
                        ray, vertices[0].to_double(), vertices[1].to_double(), vertices[2].to_double(), hit) &&
                    hit.ray_parameter <= nearest) {
                    nearest = hit.ray_parameter;
                    found = true;
                }
            }
            return found;
        }
    } // namespace

    const char* pick_mesh_entity(tc_display_handle display, float x, float y) {
        if (!std::isfinite(x) || !std::isfinite(y))
            throw std::invalid_argument("pick coordinates must be finite");
        int display_width, display_height;
        tc_display_get_size(display, &display_width, &display_height);
        if (x < 0 || x >= display_width || y < 0 || y >= display_height)
            return "";
        const tc_viewport_handle viewport = tc_display_viewport_at_screen(display, x, y);
        if (!tc_viewport_handle_valid(viewport))
            return "";
        const auto target = tc_viewport_get_render_target(viewport);
        if (!tc_render_target_handle_valid(target) || !tc_render_target_get_enabled(target))
            return "";
        const int width = tc_render_target_get_width(target), height = tc_render_target_get_height(target);
        RenderCameraSnapshot camera;
        if (width <= 0 || height <= 0 ||
            !resolve_render_camera(tc_viewport_get_camera(viewport), double(width) / height, camera))
            throw std::runtime_error("could not resolve the viewport camera");

        int px, py, pw, ph;
        tc_viewport_get_pixel_rect(viewport, &px, &py, &pw, &ph);
        const Rect2 rect{double(px), double(display_height - py - ph), double(pw), double(ph)};
        Vec3 near_point, far_point;
        if (!try_unproject_screen_point(camera.camera.projection, camera.camera.view, {x, y}, 0, rect, near_point) ||
            !try_unproject_screen_point(camera.camera.projection, camera.camera.view, {x, y}, 1, rect, far_point))
            throw std::runtime_error("could not unproject the pointer into the scene");

        RenderSceneItemCollectRequest request;
        request.scene = tc_viewport_get_scene(viewport);
        request.layer_mask = camera.layer_mask & tc_render_target_get_layer_mask(target);
        request.render_category_mask = camera.render_category_mask;
        request.camera = &camera.camera;
        request.debug_pass_name = "Web mesh picking";
        RenderSceneItemCollector collector;
        if (!collector.collect(request))
            throw std::runtime_error("could not collect the scene's render items");

        Ray3 segment;
        segment.origin = near_point;
        segment.direction = far_point - near_point;
        double nearest = 1.0;
        const char* uuid = "";
        for (const tc_render_item& item : collector.items()) {
            const tc_component* source = render_scene_item_component(item);
            if (source && tc_entity_pickable(source->owner) && intersect_section(item, segment, nearest))
                uuid = tc_entity_uuid(source->owner);
        }
        return uuid;
    }
} // namespace termin::web
