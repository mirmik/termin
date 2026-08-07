#include <termin/render/debug_geometry_pass.hpp>

#include "termin/camera/camera_component.hpp"
#include "tgfx2/i_render_device.hpp"
#include "tgfx2/render_context.hpp"
#include <tcbase/tc_log.hpp>
#include <termin/render/execute_context.hpp>
#include <termin/render/scene_render_services.hpp>

extern "C" {
#include "core/tc_debug_geometry.h"
#include "render/tc_render_category_flags.h"
}

namespace termin {

    DebugGeometryPass::DebugGeometryPass(const std::string& input,
                                         const std::string& output,
                                         const std::string& pass_name)
        : input_res(input),
          output_res(output) {
        set_pass_name(pass_name);
    }

    std::set<const char*> DebugGeometryPass::compute_reads() const {
        return {input_res.c_str()};
    }

    std::set<const char*> DebugGeometryPass::compute_writes() const {
        return {output_res.c_str()};
    }

    std::vector<std::pair<std::string, std::string>> DebugGeometryPass::get_inplace_aliases() const {
        return {{input_res, output_res}};
    }

    void DebugGeometryPass::execute(ExecuteContext& ctx) {
        const SceneRenderServices* services = require_scene_render_services(ctx, "DebugGeometryPass");
        if (!services)
            return;
        if (!ctx.ctx2) {
            tc::Log::error("[DebugGeometryPass] ctx2 is null");
            return;
        }
        const RenderCamera* primary_view = ctx.view.primary_view();
        if (!primary_view) {
            tc::Log::error("[DebugGeometryPass] primary render view is missing");
            return;
        }
        if ((services->render_category_mask & TC_RENDER_CATEGORY_DEBUG_GEOMETRY) == 0)
            return;

        const size_t primitive_count = tc_scene_debug_geometry_primitive_count(services->scene.handle());
        if (primitive_count == 0)
            return;

        auto color_it = ctx.tex2_writes.find(output_res);
        if (color_it == ctx.tex2_writes.end() || !color_it->second)
            return;
        tgfx::TextureHandle color = color_it->second;
        tgfx::TextureHandle depth;
        auto depth_it = ctx.tex2_depth_writes.find(output_res);
        if (depth_it != ctx.tex2_depth_writes.end())
            depth = depth_it->second;

        renderer_.begin();
        for (size_t index = 0; index < primitive_count; ++index) {
            const tc_debug_geometry_primitive* primitive =
                tc_scene_debug_geometry_primitive_at(services->scene.handle(), index);
            if (!primitive)
                continue;
            const Color4 primitive_color = {
                primitive->color[0],
                primitive->color[1],
                primitive->color[2],
                primitive->color[3],
            };
            if (primitive->kind == TC_DEBUG_GEOMETRY_LINE) {
                renderer_.line(
                    Vec3(primitive->data.line.start[0], primitive->data.line.start[1], primitive->data.line.start[2]),
                    Vec3(primitive->data.line.end[0], primitive->data.line.end[1], primitive->data.line.end[2]),
                    primitive_color,
                    primitive->depth_test);
            } else if (primitive->kind == TC_DEBUG_GEOMETRY_WIRE_SPHERE) {
                renderer_.sphere_wireframe(Vec3(primitive->data.sphere.center[0],
                                                primitive->data.sphere.center[1],
                                                primitive->data.sphere.center[2]),
                                           primitive->data.sphere.radius,
                                           primitive_color,
                                           primitive->segments,
                                           primitive->depth_test);
            } else if (primitive->kind == TC_DEBUG_GEOMETRY_WIRE_BOX) {
                const auto vec3 = [](const float value[3]) {
                    return Vec3(value[0], value[1], value[2]);
                };
                const Vec3 center = vec3(primitive->data.box.center);
                const Vec3 x = vec3(primitive->data.box.half_axis_x);
                const Vec3 y = vec3(primitive->data.box.half_axis_y);
                const Vec3 z = vec3(primitive->data.box.half_axis_z);
                const Vec3 corners[8] = {
                    center - x - y - z,
                    center + x - y - z,
                    center + x + y - z,
                    center - x + y - z,
                    center - x - y + z,
                    center + x - y + z,
                    center + x + y + z,
                    center - x + y + z,
                };
                constexpr int edges[12][2] = {
                    {0, 1},
                    {1, 2},
                    {2, 3},
                    {3, 0},
                    {4, 5},
                    {5, 6},
                    {6, 7},
                    {7, 4},
                    {0, 4},
                    {1, 5},
                    {2, 6},
                    {3, 7},
                };
                for (const auto& edge : edges) {
                    renderer_.line(corners[edge[0]], corners[edge[1]], primitive_color, primitive->depth_test);
                }
            } else if (primitive->kind == TC_DEBUG_GEOMETRY_WIRE_CAPSULE) {
                renderer_.capsule_wireframe(Vec3(primitive->data.capsule.start[0],
                                                 primitive->data.capsule.start[1],
                                                 primitive->data.capsule.start[2]),
                                            Vec3(primitive->data.capsule.end[0],
                                                 primitive->data.capsule.end[1],
                                                 primitive->data.capsule.end[2]),
                                            primitive->data.capsule.radius,
                                            primitive_color,
                                            primitive->segments,
                                            primitive->depth_test);
            }
        }

        const auto target_desc = ctx.ctx2->device().texture_desc(color);
        ctx.ctx2->begin_pass(color, depth, nullptr, 1.0f, false);
        ctx.ctx2->set_viewport(0, 0, static_cast<int>(target_desc.width), static_cast<int>(target_desc.height));
        const Mat44 view = primary_view->get_view_matrix();
        const Mat44 projection = primary_view->get_projection_matrix();
        renderer_.flush_depth(ctx.ctx2, view, projection, true);
        renderer_.flush(ctx.ctx2, view, projection, false, true);
        ctx.ctx2->end_pass();
    }

    void DebugGeometryPass::register_type() {
        auto descriptor =
            FramePassTypeDescriptorBuilder::native<DebugGeometryPass>("DebugGeometryPass", "termin-render-passes");
        auto& inspect = descriptor.inspect();
        _register_inspect_input_res(inspect);
        _register_inspect_output_res(inspect);
        _register_inspect_metadata_graph(inspect);
        (void)descriptor.commit();
    }

} // namespace termin
