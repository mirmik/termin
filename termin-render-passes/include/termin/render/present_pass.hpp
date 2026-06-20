#pragma once

#include "termin/render/frame_pass.hpp"
#include "termin/render_passes/export.h"
#include "tc_inspect_cpp.hpp"

namespace termin {

// PresentToScreenPass - copies input FBO to output FBO via blit.
// Does NOT use inplace aliases, so breaks inplace chains.
// Use this to copy rendered content to OUTPUT/DISPLAY.
class TERMIN_RENDER_PASSES_API PresentToScreenPass : public CxxFramePass {
public:
    std::string input_res = "color";
    std::string output_res = "OUTPUT";

    INSPECT_FIELD(PresentToScreenPass, input_res, "Input Resource", "string")
    INSPECT_FIELD(PresentToScreenPass, output_res, "Output Resource", "string")
    INSPECT_TYPE_METADATA(PresentToScreenPass, graph, make_pass_graph_metadata(
        {{"input_res", "fbo"}},
        {},
        {}
    ))

    PresentToScreenPass(
        const std::string& input = "color",
        const std::string& output = "OUTPUT"
    );

    std::set<const char*> compute_reads() const override;
    std::set<const char*> compute_writes() const override;

    // No inplace aliases - this breaks the chain
    std::vector<std::pair<std::string, std::string>> get_inplace_aliases() const override {
        return {};
    }

    void execute(ExecuteContext& ctx) override;
};

// BlitPass - copies one FBO into another graph-selected FBO target.
// This is the native equivalent of the old Python BlitPass so serialized
// pipelines can run in C++-only runtimes such as OpenXR/Android.
class TERMIN_RENDER_PASSES_API BlitPass : public CxxFramePass {
public:
    std::string input_res = "color";
    std::string output_res = "blit";
    std::string output_res_target;

    INSPECT_FIELD(BlitPass, input_res, "Input Resource", "string")
    INSPECT_FIELD(BlitPass, output_res, "Output Resource", "string")
    INSPECT_FIELD(BlitPass, output_res_target, "Output Target", "string")
    INSPECT_TYPE_METADATA(BlitPass, graph, make_pass_graph_metadata(
        {{"input_res", "fbo"}, {"output_res_target", "fbo"}},
        {{"output_res", "fbo"}},
        {{"output_res_target", "output_res"}}
    ))

    BlitPass(
        const std::string& input = "color",
        const std::string& output = "blit",
        const std::string& pass_name = "Blit"
    );

    std::set<const char*> compute_reads() const override;
    std::set<const char*> compute_writes() const override;

    std::vector<std::pair<std::string, std::string>> get_inplace_aliases() const override;

    void execute(ExecuteContext& ctx) override;
};

} // namespace termin
