#pragma once

#if defined(__ANDROID__)

#include "tc_inspect_cpp.hpp"
#include "termin/render/frame_pass.hpp"
#include "termin/render_passes/export.h"

namespace termin {

// Native placeholder for targets that do not run Python-authored frame passes.
// Desktop builds leave the UIWidgetPass registry name to the Python pass.
class TERMIN_RENDER_PASSES_API UIWidgetPass : public CxxFramePass {
public:
    static void register_type();
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

#endif // defined(__ANDROID__)
