#include <termin/render/execute_context.hpp>
#include <termin/render/output_transform_pass.hpp>

#include "tgfx2/builtin_shader_sources.hpp"
#include "tgfx2/enums.hpp"
#include "tgfx2/i_render_device.hpp"
#include "tgfx2/render_context.hpp"
#include "tgfx2/tc_shader_bridge.hpp"

extern "C" {
#include <tgfx/resources/tc_shader.h>
}

#include <tcbase/tc_log.hpp>

namespace termin {

    constexpr const char* OUTPUT_TRANSFORM_ENGINE_SHADER_UUID = "termin-engine-output-transform";

    OutputTransformPass::OutputTransformPass(const std::string& input, const std::string& output)
        : input_res(input), output_res(output) {
        pass_name_set("OutputTransform");
        link_to_type_registry("OutputTransformPass");
    }

    std::set<const char*> OutputTransformPass::compute_reads() const {
        return input_res.empty() ? std::set<const char*>{} : std::set<const char*>{input_res.c_str()};
    }

    std::set<const char*> OutputTransformPass::compute_writes() const {
        return output_res.empty() ? std::set<const char*>{} : std::set<const char*>{output_res.c_str()};
    }

    void OutputTransformPass::execute(ExecuteContext& ctx) {
        if (!ctx.ctx2) {
            tc::Log::error("[OutputTransformPass] ctx.ctx2 is null — pass is tgfx2-only");
            return;
        }

        auto in_it = ctx.tex2_reads.find(input_res);
        if (in_it == ctx.tex2_reads.end() || !in_it->second) {
            tc::Log::error("[OutputTransformPass] Missing input texture '%s'", input_res.c_str());
            return;
        }
        auto out_it = ctx.tex2_writes.find(output_res);
        if (out_it == ctx.tex2_writes.end() || !out_it->second) {
            tc::Log::error("[OutputTransformPass] Missing output texture '%s'", output_res.c_str());
            return;
        }

        const tgfx::TextureHandle input = in_it->second;
        const tgfx::TextureHandle output = out_it->second;
        const auto output_desc = ctx.ctx2->device().texture_desc(output);
        if (output_desc.width == 0 || output_desc.height == 0) {
            tc::Log::error("[OutputTransformPass] Output texture '%s' has zero extent", output_res.c_str());
            return;
        }

        device2_ = &ctx.ctx2->device();
        if (tc_shader_handle_is_invalid(shader_handle_)) {
            shader_handle_ = tgfx::register_builtin_shader_from_catalog(OUTPUT_TRANSFORM_ENGINE_SHADER_UUID);
            if (tc_shader_handle_is_invalid(shader_handle_)) {
                tc::Log::error("[OutputTransformPass] Failed to register built-in shader");
                return;
            }
        }

        tgfx::ShaderHandle fragment_shader;
        tc_shader* raw = tc_shader_get(shader_handle_);
        if (!raw || !tc_shader_ensure_tgfx2(raw, device2_, nullptr, &fragment_shader)) {
            tc::Log::error("[OutputTransformPass] tc_shader_ensure_tgfx2 failed");
            return;
        }

        ctx.ctx2->begin_pass(output);
        ctx.ctx2->set_viewport(0,
                               0,
                               static_cast<int>(output_desc.width),
                               static_cast<int>(output_desc.height));
        ctx.ctx2->set_depth_test(false);
        ctx.ctx2->set_depth_write(false);
        ctx.ctx2->set_blend(false);
        ctx.ctx2->set_cull(tgfx::CullMode::None);
        ctx.ctx2->bind_shader(ctx.ctx2->fsq_vertex_shader(), fragment_shader);

        tgfx::VertexLayoutDesc fsq_layout;
        fsq_layout.stride = 4 * sizeof(float);
        fsq_layout.attribute_count = 2;
        fsq_layout.attributes[0] = {0, tgfx::VertexFormat::Float2, 0, tgfx::intern_vertex_semantic("position")};
        fsq_layout.attributes[1] = {
            1, tgfx::VertexFormat::Float2, 2 * sizeof(float), tgfx::intern_vertex_semantic("uv")};
        ctx.ctx2->set_vertex_layout(fsq_layout);

        ctx.ctx2->use_shader_resource_layout(raw);
        ctx.ctx2->bind_texture("u_input", input);
        ctx.ctx2->draw_fullscreen_quad();
        ctx.ctx2->end_pass();
    }

    void OutputTransformPass::destroy() {
        device2_ = nullptr;
    }

    void OutputTransformPass::register_type() {
        auto descriptor =
            FramePassTypeDescriptorBuilder::native<OutputTransformPass>("OutputTransformPass", "termin-render-passes");
        auto& inspect = descriptor.inspect();
        _register_inspect_input_res(inspect);
        _register_inspect_output_res(inspect);
        _register_inspect_metadata_graph(inspect);
        (void)descriptor.commit();
    }

} // namespace termin
