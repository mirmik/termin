#include <termin/render/ui_widget_pass.hpp>

#include "termin/render/execute_context.hpp"
#include "tgfx2/render_context.hpp"

#include <tcbase/tc_log.hpp>

namespace termin {

UIWidgetPass::UIWidgetPass(
    const std::string& input,
    const std::string& output
) : input_res(input), output_res(output) {
    pass_name_set("UIWidgets");
    link_to_type_registry("UIWidgetPass");
}

std::set<const char*> UIWidgetPass::compute_reads() const {
    return {input_res.c_str()};
}

std::set<const char*> UIWidgetPass::compute_writes() const {
    return {output_res.c_str()};
}

std::vector<std::pair<std::string, std::string>> UIWidgetPass::get_inplace_aliases() const {
    return {{input_res, output_res}};
}

void UIWidgetPass::execute(ExecuteContext& ctx) {
    if (!ctx.ctx2) {
        tc::Log::error("[UIWidgetPass] ctx.ctx2 is null");
        return;
    }

    auto in_it = ctx.tex2_reads.find(input_res);
    auto out_it = ctx.tex2_writes.find(output_res);
    if (in_it == ctx.tex2_reads.end() || !in_it->second ||
        out_it == ctx.tex2_writes.end() || !out_it->second) {
        tc::Log::warn(
            "[UIWidgetPass] missing tgfx2 resources input='%s' output='%s'",
            input_res.c_str(),
            output_res.c_str()
        );
        return;
    }

    ctx.ctx2->blit(in_it->second, out_it->second);
}

TC_REGISTER_FRAME_PASS(UIWidgetPass);

} // namespace termin
