// resolve_pass.hpp - MSAA resolve pass
#pragma once

#include "termin/render/frame_pass.hpp"
#include "termin/render_passes/export.h"
#include "tc_inspect_cpp.hpp"

#include <string>
#include <utility>

namespace termin {

// ResolvePass resolves an MSAA color resource into a single-sample color
// resource through the backend transfer/resolve path. The strategy field is
// kept for serialized graph compatibility; average is the only supported mode.
class TERMIN_RENDER_PASSES_API ResolvePass : public CxxFramePass {
public:
    std::string input_res = "color";
    std::string output_res = "resolved";
    std::string output_res_target;
    std::string strategy = "average";

public:
    INSPECT_FIELD(ResolvePass, input_res, "Input Resource", "string")
    INSPECT_FIELD(ResolvePass, output_res, "Output Resource", "string")
    INSPECT_FIELD(ResolvePass, output_res_target, "Output Target", "string")
    INSPECT_FIELD_CHOICES(ResolvePass, strategy, "Strategy", "string",
        std::pair<const char*, const char*>{"average", "Average"})
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
};

} // namespace termin
