#include <termin/render/resolve_pass.hpp>

#include "termin/render/execute_context.hpp"
#include "tgfx2/i_render_device.hpp"
#include "tgfx2/pixel_format_utils.hpp"
#include "tgfx2/render_context.hpp"

#include <tcbase/tc_log.hpp>

namespace termin {

    namespace {

        bool query_color_resolve_contract(ExecuteContext& ctx,
                                          const std::string& input_resource,
                                          const std::string& output_resource,
                                          uint32_t view_count,
                                          tc_raster_resolve_contract& out_contract) {
            out_contract = {};
            out_contract.struct_size = sizeof(out_contract);
            out_contract.source_resource = input_resource.c_str();
            out_contract.target_resource = output_resource.c_str();
            out_contract.view_count = view_count;
            out_contract.fusion_eligible = ctx.debug_internal_capture_requests.empty();

            if (!ctx.ctx2 || input_resource.empty() || output_resource.empty()) {
                return false;
            }
            const auto input = ctx.tex2_reads.find(input_resource);
            const auto output = ctx.tex2_writes.find(output_resource);
            if (input == ctx.tex2_reads.end() || !input->second || output == ctx.tex2_writes.end() ||
                !output->second || input->second == output->second) {
                return false;
            }

            const tgfx::TextureDesc source_desc = ctx.ctx2->device().texture_desc(input->second);
            const tgfx::TextureDesc target_desc = ctx.ctx2->device().texture_desc(output->second);
            if (source_desc.sample_count <= 1 || target_desc.sample_count != 1 ||
                source_desc.width != target_desc.width || source_desc.height != target_desc.height ||
                source_desc.format != target_desc.format || source_desc.array_layers != target_desc.array_layers ||
                source_desc.array_layers != view_count || tgfx::is_depth_format(source_desc.format)) {
                return false;
            }
            return true;
        }

    } // namespace

    ResolvePass::ResolvePass(const std::string& input, const std::string& output)
        : input_res(input),
          output_res(output) {
        pass_name_set("Resolve");
        link_to_type_registry("ResolvePass");
    }

    std::set<const char*> ResolvePass::compute_reads() const {
        std::set<const char*> reads;
        if (!input_res.empty()) {
            reads.insert(input_res.c_str());
        }
        if (!output_res_target.empty()) {
            reads.insert(output_res_target.c_str());
        }
        return reads;
    }

    std::set<const char*> ResolvePass::compute_writes() const {
        return {output_res.c_str()};
    }

    std::vector<std::pair<std::string, std::string>> ResolvePass::get_inplace_aliases() const {
        if (output_res_target.empty()) {
            return {};
        }
        return {{output_res_target, output_res}};
    }

    void ResolvePass::execute(ExecuteContext& ctx) {
        if (!ctx.ctx2) {
            tc::Log::error("[ResolvePass] ctx.ctx2 is null - ResolvePass is tgfx2-only");
            return;
        }

        auto in_it = ctx.tex2_reads.find(input_res);
        if (in_it == ctx.tex2_reads.end() || !in_it->second) {
            tc::Log::warn("[ResolvePass] missing tgfx2 input '%s'", input_res.c_str());
            return;
        }

        auto out_it = ctx.tex2_writes.find(output_res);
        if (out_it == ctx.tex2_writes.end() || !out_it->second) {
            tc::Log::warn("[ResolvePass] missing tgfx2 output '%s'", output_res.c_str());
            return;
        }

        tgfx::TextureHandle input_tex = in_it->second;
        tgfx::TextureHandle output_tex = out_it->second;
        ctx.ctx2->blit(input_tex, output_tex);
    }

    bool ResolvePass::get_raster_resolve_contract(ExecuteContext& ctx,
                                                  tc_raster_resolve_contract& out_contract) const {
        return query_color_resolve_contract(ctx, input_res, output_res, 1u, out_contract);
    }

    void ResolvePass::destroy() {}

    void ResolvePass::register_type() {
        auto descriptor = FramePassTypeDescriptorBuilder::native<ResolvePass>("ResolvePass", "termin-render-passes");
        auto& inspect = descriptor.inspect();
        _register_inspect_input_res(inspect);
        _register_inspect_output_res(inspect);
        _register_inspect_output_res_target(inspect);
        _register_inspect_metadata_graph(inspect);
        (void)descriptor.commit();
    }

    MultiviewResolvePass::MultiviewResolvePass(const std::string& input, const std::string& output)
        : input_res(input),
          output_res(output) {
        pass_name_set("MultiviewResolve");
        link_to_type_registry("MultiviewResolvePass");
    }

    std::set<const char*> MultiviewResolvePass::compute_reads() const {
        std::set<const char*> reads;
        if (!input_res.empty())
            reads.insert(input_res.c_str());
        if (!output_res_target.empty())
            reads.insert(output_res_target.c_str());
        return reads;
    }

    std::set<const char*> MultiviewResolvePass::compute_writes() const {
        return {output_res.c_str()};
    }

    std::vector<std::pair<std::string, std::string>> MultiviewResolvePass::get_inplace_aliases() const {
        return output_res_target.empty()
                   ? std::vector<std::pair<std::string, std::string>>{}
                   : std::vector<std::pair<std::string, std::string>>{{output_res_target, output_res}};
    }

    void MultiviewResolvePass::execute(ExecuteContext& ctx) {
        if (!ctx.ctx2) {
            tc::Log::error("[MultiviewResolvePass] ctx.ctx2 is null");
            return;
        }
        auto input = ctx.tex2_reads.find(input_res);
        auto output = ctx.tex2_writes.find(output_res);
        if (input == ctx.tex2_reads.end() || !input->second || output == ctx.tex2_writes.end() || !output->second) {
            tc::Log::error("[MultiviewResolvePass] missing layered input or output");
            return;
        }
        const tgfx::TextureDesc in_desc = ctx.ctx2->device().texture_desc(input->second);
        const tgfx::TextureDesc out_desc = ctx.ctx2->device().texture_desc(output->second);
        if (in_desc.array_layers != 2 || out_desc.array_layers != 2 || in_desc.sample_count <= 1 ||
            out_desc.sample_count != 1) {
            tc::Log::error("[MultiviewResolvePass] expected 2-layer MSAA input and 2-layer single-sample output");
            return;
        }
        ctx.ctx2->blit(input->second, output->second);
    }

    bool MultiviewResolvePass::get_raster_resolve_contract(ExecuteContext& ctx,
                                                           tc_raster_resolve_contract& out_contract) const {
        return query_color_resolve_contract(ctx, input_res, output_res, 2u, out_contract);
    }

    void MultiviewResolvePass::register_type() {
        auto descriptor = FramePassTypeDescriptorBuilder::native<MultiviewResolvePass>("MultiviewResolvePass",
                                                                                       "termin-render-passes");
        auto& inspect = descriptor.inspect();
        _register_inspect_input_res(inspect);
        _register_inspect_output_res(inspect);
        _register_inspect_output_res_target(inspect);
        _register_inspect_metadata_graph(inspect);
        (void)descriptor.commit();
    }

} // namespace termin
