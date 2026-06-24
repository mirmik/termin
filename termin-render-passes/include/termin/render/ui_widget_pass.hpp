#pragma once

#include "tc_inspect_cpp.hpp"
#include "termin/render/frame_pass.hpp"
#include "termin/render_passes/export.h"

namespace termin {

// Native desktop placeholder for widget UI composition.
// The player runtime cannot depend on Python-authored frame passes, but the
// default pipeline still needs the same resource edge.
class TERMIN_RENDER_PASSES_API UIWidgetPass : public CxxFramePass {
public:
    std::string input_res = "color";
    std::string output_res = "color+widgets";
    bool include_internal_entities = false;

    INSPECT_FIELD(UIWidgetPass, input_res, "Input Resource", "string")
    INSPECT_FIELD(UIWidgetPass, output_res, "Output Resource", "string")
    INSPECT_FIELD(UIWidgetPass, include_internal_entities, "Include Internal Entities", "bool")
    INSPECT_TYPE_METADATA(UIWidgetPass, graph, make_pass_graph_metadata(
        {{"input_res", "fbo"}},
        {{"output_res", "fbo"}},
        {{"input_res", "output_res"}}
    ))

    UIWidgetPass(
        const std::string& input = "color",
        const std::string& output = "color+widgets"
    );

    std::set<const char*> compute_reads() const override;
    std::set<const char*> compute_writes() const override;
    std::vector<std::pair<std::string, std::string>> get_inplace_aliases() const override;

    void execute(ExecuteContext& ctx) override;
};

} // namespace termin
