#include <termin/render/annotation_pass.hpp>

#include <cmath>
#include <cstring>
#include <tcbase/tc_log.hpp>
#include <termin/render/execute_context.hpp>
#include <termin_visual_scene/annotation_geometry3d.hpp>
#include <tgfx2/i_render_device.hpp>
#include <tgfx2/render_context.hpp>

namespace termin {
    namespace {
        struct AnnotationBatch {
            ImmediateRenderer& renderer;
            Mat44 view_projection;
            float pixels_per_dip;
        };

        bool collect(const tc_visual_draw_submission3d* submission, void* user) {
            const auto& packet = submission->packet;
            if (!packet.protocol || std::strcmp(packet.protocol, TC_VISUAL_ANNOTATION_PROTOCOL_3D) != 0)
                return true; // Other scene protocols belong to their own passes.
            if (!packet.payload || packet.payload_size != sizeof(tc_visual_annotation_packet3d))
                return false;
            const auto& annotations = *static_cast<const tc_visual_annotation_packet3d*>(packet.payload);
            if (annotations.count && !annotations.commands)
                return false;
            auto& batch = *static_cast<AnnotationBatch*>(user);
            visual::append_annotation_triangles(batch.renderer.tri_vertices,
                                                annotations,
                                                submission->world_from_local,
                                                batch.view_projection,
                                                submission->view->viewport_width,
                                                submission->view->viewport_height,
                                                batch.pixels_per_dip);
            return true;
        }
    } // namespace

    AnnotationPass::AnnotationPass(const std::string& input, const std::string& output)
        : input_res(input),
          output_res(output) {
        pass_name_set("Annotations");
        link_to_type_registry("AnnotationPass");
    }

    bool AnnotationPass::set_scene(uint32_t index, uint32_t generation, float pixels_per_dip) {
        const tc_visual_scene3d_handle scene{index, generation};
        if (!tc_visual_scene3d_is_valid(scene) || !std::isfinite(pixels_per_dip) || pixels_per_dip <= 0) {
            tc::Log::error("[AnnotationPass] invalid visual scene or DIP scale");
            return false;
        }
        scene_ = scene;
        pixels_per_dip_ = pixels_per_dip;
        return true;
    }

    std::set<const char*> AnnotationPass::compute_reads() const {
        return {input_res.c_str()};
    }
    std::set<const char*> AnnotationPass::compute_writes() const {
        return {output_res.c_str()};
    }
    std::vector<std::pair<std::string, std::string>> AnnotationPass::get_inplace_aliases() const {
        return {{input_res, output_res}};
    }

    void AnnotationPass::execute(ExecuteContext& ctx) {
        if (tc_visual_scene3d_handle_is_invalid(scene_))
            return;
        const auto* camera = ctx.view.primary_view();
        const auto color = ctx.tex2_writes.find(output_res);
        if (!ctx.ctx2 || !camera || color == ctx.tex2_writes.end() || !color->second) {
            tc::Log::error("[AnnotationPass] missing render context, camera or target '%s'", output_res.c_str());
            return;
        }
        const auto desc = ctx.ctx2->device().texture_desc(color->second);
        const tc_visual_view3d view{camera->view.to_tc_mat44(),
                                    camera->projection.to_tc_mat44(),
                                    camera->position,
                                    desc.width,
                                    desc.height,
                                    nullptr};
        AnnotationBatch batch{renderer_, camera->projection * camera->view, pixels_per_dip_};
        renderer_.begin();
        tc_visual_draw_sink3d sink{[](const tc_visual_view3d*, void*) { return true; },
                                   collect,
                                   [](void*) { return true; },
                                   [](void* user) { static_cast<AnnotationBatch*>(user)->renderer.begin(); },
                                   &batch};
        if (!tc_visual_scene3d_paint(scene_, &view, &sink)) {
            tc::Log::error("[AnnotationPass] failed to collect VisualScene3D annotations");
            return;
        }
        if (renderer_.tri_vertices.empty())
            return;
        ctx.ctx2->begin_pass(color->second, {}, nullptr, 1.0f, false);
        ctx.ctx2->set_viewport(0, 0, desc.width, desc.height);
        ctx.ctx2->set_polygon_mode(tgfx::PolygonMode::Fill);
        renderer_.flush(ctx.ctx2, Mat44::identity(), Mat44::identity(), false, true);
        ctx.ctx2->end_pass();
    }

    void AnnotationPass::register_type() {
        auto descriptor =
            FramePassTypeDescriptorBuilder::native<AnnotationPass>("AnnotationPass", "termin-render-passes");
        _register_inspect_input_res(descriptor.inspect());
        _register_inspect_output_res(descriptor.inspect());
        _register_inspect_metadata_graph(descriptor.inspect());
        (void)descriptor.commit();
    }
} // namespace termin
