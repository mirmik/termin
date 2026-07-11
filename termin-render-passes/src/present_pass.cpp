#include <termin/render/present_pass.hpp>
#include "termin/render/execute_context.hpp"
#include "tgfx2/render_context.hpp"
#include <tcbase/tc_log.hpp>

namespace termin {

PresentToScreenPass::PresentToScreenPass(
    const std::string& input,
    const std::string& output
) : input_res(input), output_res(output) {
    pass_name_set("PresentToScreen");
    link_to_type_registry("PresentToScreenPass");
}

std::set<const char*> PresentToScreenPass::compute_reads() const {
    return {input_res.c_str()};
}

std::set<const char*> PresentToScreenPass::compute_writes() const {
    return {output_res.c_str()};
}

void PresentToScreenPass::execute(ExecuteContext& ctx) {
    if (!ctx.ctx2) {
        tc::Log::error("[PresentToScreenPass] ctx.ctx2 is null");
        return;
    }

    auto in_it = ctx.tex2_reads.find(input_res);
    if (in_it == ctx.tex2_reads.end() || !in_it->second) {
        tc::Log::warn("[PresentToScreenPass] missing tgfx2 input '%s'",
                      input_res.c_str());
        return;
    }
    auto out_it = ctx.tex2_writes.find(output_res);
    if (out_it == ctx.tex2_writes.end() || !out_it->second) {
        tc::Log::warn("[PresentToScreenPass] missing tgfx2 output '%s'",
                      output_res.c_str());
        return;
    }

    ctx.ctx2->blit(in_it->second, out_it->second);
}

TC_DEFINE_FRAME_PASS_FACTORY(PresentToScreenPass);

void PresentToScreenPass::register_type() {
    register_frame_pass_PresentToScreenPass();
    _register_inspect_input_res();
    _register_inspect_output_res();
    _register_inspect_metadata_graph();
}

BlitPass::BlitPass(
    const std::string& input,
    const std::string& output,
    const std::string& pass_name
) : input_res(input), output_res(output) {
    pass_name_set(pass_name);
    link_to_type_registry("BlitPass");
}

std::set<const char*> BlitPass::compute_reads() const {
    std::set<const char*> reads;
    if (!input_res.empty()) {
        reads.insert(input_res.c_str());
    }
    if (!output_res_target.empty()) {
        reads.insert(output_res_target.c_str());
    }
    return reads;
}

std::set<const char*> BlitPass::compute_writes() const {
    return {output_res.c_str()};
}

std::vector<std::pair<std::string, std::string>> BlitPass::get_inplace_aliases() const {
    if (output_res_target.empty()) {
        return {};
    }
    return {{output_res_target, output_res}};
}

void BlitPass::execute(ExecuteContext& ctx) {
    if (!ctx.ctx2) {
        tc::Log::error("[BlitPass] ctx.ctx2 is null");
        return;
    }

    auto in_it = ctx.tex2_reads.find(input_res);
    if (in_it == ctx.tex2_reads.end() || !in_it->second) {
        tc::Log::warn("[BlitPass] missing tgfx2 input '%s'", input_res.c_str());
        return;
    }
    auto out_it = ctx.tex2_writes.find(output_res);
    if (out_it == ctx.tex2_writes.end() || !out_it->second) {
        tc::Log::warn("[BlitPass] missing tgfx2 output '%s'", output_res.c_str());
        return;
    }

    ctx.ctx2->blit(in_it->second, out_it->second);
}

TC_DEFINE_FRAME_PASS_FACTORY(BlitPass);

void BlitPass::register_type() {
    register_frame_pass_BlitPass();
    _register_inspect_input_res();
    _register_inspect_output_res();
    _register_inspect_output_res_target();
    _register_inspect_metadata_graph();
}

} // namespace termin
