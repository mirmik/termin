#include <termin/render/resolve_pass.hpp>

#include "termin/render/execute_context.hpp"
#include "tgfx2/render_context.hpp"

#include <cctype>
#include <tcbase/tc_log.hpp>

namespace termin {
namespace {

std::string normalize_strategy(const std::string& value) {
    std::string mode;
    mode.reserve(value.size());
    for (char c : value) {
        if (!std::isspace(static_cast<unsigned char>(c))) {
            mode.push_back(static_cast<char>(std::tolower(static_cast<unsigned char>(c))));
        }
    }
    return mode.empty() ? "average" : mode;
}

} // namespace

ResolvePass::ResolvePass(
    const std::string& input,
    const std::string& output,
    const std::string& strategy_value
)
    : input_res(input)
    , output_res(output)
    , strategy(strategy_value)
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
    const std::string mode = normalize_strategy(strategy);
    if (mode != "average") {
        tc::Log::warn("[ResolvePass] strategy '%s' is deprecated; using average resolve in pass '%s'",
                      strategy.c_str(), get_pass_name().c_str());
    }
    ctx.ctx2->blit(input_tex, output_tex);
}

void ResolvePass::destroy() {}

TC_REGISTER_FRAME_PASS(ResolvePass);

} // namespace termin
