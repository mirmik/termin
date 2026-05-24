// resolve_pass.hpp - MSAA resolve pass
#pragma once

#include "termin/render/frame_pass.hpp"
#include "tgfx2/handles.hpp"
#include "tc_inspect_cpp.hpp"

extern "C" {
#include <tgfx/resources/tc_shader_registry.h>
}

#include <string>
#include <unordered_map>
#include <utility>

namespace tgfx { class IRenderDevice; }

namespace termin {

// ResolvePass resolves an MSAA color resource into a single-sample color
// resource. Average uses the backend transfer/resolve path; min/max use a
// shader resolve for depth-like masks where averaging changes meaning.
class ResolvePass : public CxxFramePass {
public:
    std::string input_res = "color";
    std::string output_res = "resolved";
    std::string output_res_target;
    std::string strategy = "average";

private:
    tgfx::IRenderDevice* device2_ = nullptr;
    std::unordered_map<std::string, tc_shader_handle> shader_handles_;

public:
    INSPECT_FIELD(ResolvePass, input_res, "Input Resource", "string")
    INSPECT_FIELD(ResolvePass, output_res, "Output Resource", "string")
    INSPECT_FIELD(ResolvePass, output_res_target, "Output Target", "string")
    INSPECT_FIELD_CHOICES(ResolvePass, strategy, "Strategy", "string",
        std::pair<const char*, const char*>{"average", "Average"},
        std::pair<const char*, const char*>{"min", "Min"},
        std::pair<const char*, const char*>{"max", "Max"})
    INSPECT_TYPE_METADATA(ResolvePass, graph, make_pass_graph_metadata(
        {{"input_res", "fbo"}, {"output_res_target", "fbo"}},
        {{"output_res", "fbo"}},
        {{"output_res_target", "output_res"}}
    ))

    ResolvePass(
        const std::string& input = "color",
        const std::string& output = "resolved",
        const std::string& strategy = "average"
    );

    std::set<const char*> compute_reads() const override;
    std::set<const char*> compute_writes() const override;

    std::vector<std::pair<std::string, std::string>> get_inplace_aliases() const override;

    void execute(ExecuteContext& ctx) override;
    void destroy() override;

private:
    tgfx::ShaderHandle shader_for(tgfx::IRenderDevice& device, const std::string& mode, int samples);
};

} // namespace termin
