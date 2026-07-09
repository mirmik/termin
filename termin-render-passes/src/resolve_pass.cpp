#include <termin/render/resolve_pass.hpp>

#include "termin/render/execute_context.hpp"
#include "tgfx2/render_context.hpp"

#include <tcbase/tc_log.hpp>

namespace termin {

ResolvePass::ResolvePass(
    const std::string& input,
    const std::string& output
)
    : input_res(input)
    , output_res(output)
{
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

void ResolvePass::destroy() {}

TC_REGISTER_FRAME_PASS(ResolvePass);

} // namespace termin
