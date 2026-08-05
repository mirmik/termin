#include <termin/render/debug_geometry_pass.hpp>

#include "termin/camera/camera_component.hpp"
#include "tgfx2/i_render_device.hpp"
#include "tgfx2/render_context.hpp"
#include <termin/render/execute_context.hpp>

extern "C" {
#include "core/tc_debug_geometry.h"
#include "render/tc_render_category_flags.h"
}

namespace termin {

DebugGeometryPass::DebugGeometryPass(
    const std::string& input,
    const std::string& output,
    const std::string& pass_name
) : input_res(input), output_res(output) {
    set_pass_name(pass_name);
}

std::set<const char*> DebugGeometryPass::compute_reads() const {
    return {input_res.c_str()};
}

std::set<const char*> DebugGeometryPass::compute_writes() const {
    return {output_res.c_str()};
}

std::vector<std::pair<std::string, std::string>>
DebugGeometryPass::get_inplace_aliases() const {
    return {{input_res, output_res}};
}

void DebugGeometryPass::execute(ExecuteContext& ctx) {
    if (!ctx.scene.valid() || !ctx.ctx2 || !ctx.camera) return;
    if ((ctx.render_category_mask & TC_RENDER_CATEGORY_DEBUG_GEOMETRY) == 0) return;

    const size_t primitive_count =
        tc_scene_debug_geometry_primitive_count(ctx.scene.handle());
    if (primitive_count == 0) return;

    auto color_it = ctx.tex2_writes.find(output_res);
    if (color_it == ctx.tex2_writes.end() || !color_it->second) return;
    tgfx::TextureHandle color = color_it->second;
    tgfx::TextureHandle depth;
    auto depth_it = ctx.tex2_depth_writes.find(output_res);
    if (depth_it != ctx.tex2_depth_writes.end()) depth = depth_it->second;

    renderer_.begin();
    for (size_t index = 0; index < primitive_count; ++index) {
        const tc_debug_geometry_primitive* primitive =
            tc_scene_debug_geometry_primitive_at(ctx.scene.handle(), index);
        if (!primitive) continue;
        const Color4 primitive_color = {
            primitive->color[0], primitive->color[1],
            primitive->color[2], primitive->color[3],
        };
        if (primitive->kind == TC_DEBUG_GEOMETRY_LINE) {
            renderer_.line(
                Vec3(
                    primitive->data.line.start[0],
                    primitive->data.line.start[1],
                    primitive->data.line.start[2]),
                Vec3(
                    primitive->data.line.end[0],
                    primitive->data.line.end[1],
                    primitive->data.line.end[2]),
                primitive_color,
                primitive->depth_test);
        } else if (primitive->kind == TC_DEBUG_GEOMETRY_WIRE_SPHERE) {
            renderer_.sphere_wireframe(
                Vec3(
                    primitive->data.sphere.center[0],
                    primitive->data.sphere.center[1],
                    primitive->data.sphere.center[2]),
                primitive->data.sphere.radius,
                primitive_color,
                primitive->segments,
                primitive->depth_test);
        }
    }

    const auto target_desc = ctx.ctx2->device().texture_desc(color);
    ctx.ctx2->begin_pass(color, depth, nullptr, 1.0f, false);
    ctx.ctx2->set_viewport(
        0, 0,
        static_cast<int>(target_desc.width),
        static_cast<int>(target_desc.height));
    const Mat44 view = ctx.camera->get_view_matrix();
    const Mat44 projection = ctx.camera->get_projection_matrix();
    renderer_.flush_depth(ctx.ctx2, view, projection, true);
    renderer_.flush(ctx.ctx2, view, projection, false, true);
    ctx.ctx2->end_pass();
}

void DebugGeometryPass::register_type() {
    auto descriptor = FramePassTypeDescriptorBuilder::native<DebugGeometryPass>(
        "DebugGeometryPass", "termin-render-passes");
    auto& inspect = descriptor.inspect();
    _register_inspect_input_res(inspect);
    _register_inspect_output_res(inspect);
    _register_inspect_metadata_graph(inspect);
    (void)descriptor.commit();
}

} // namespace termin
