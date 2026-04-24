#include "present_pass.hpp"
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

TC_REGISTER_FRAME_PASS(PresentToScreenPass);

} // namespace termin
