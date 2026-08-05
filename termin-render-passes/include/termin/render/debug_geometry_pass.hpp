#pragma once

#include "termin/render/frame_pass.hpp"
#include "termin/render_passes/export.h"
#include <tgfx2/immediate_renderer.hpp>

namespace termin {

class TERMIN_RENDER_PASSES_API DebugGeometryPass : public CxxFramePass {
private:
    ImmediateRenderer renderer_;

public:
    std::string input_res = "color";
    std::string output_res = "color";

    INSPECT_FIELD(DebugGeometryPass, input_res, "Input Resource", "string")
    INSPECT_FIELD(DebugGeometryPass, output_res, "Output Resource", "string")
    INSPECT_TYPE_METADATA(DebugGeometryPass, graph, make_pass_graph_metadata(
        {{"input_res", "fbo"}},
        {{"output_res", "fbo"}},
        {{"input_res", "output_res"}}
    ))

    static void register_type();

    DebugGeometryPass(
        const std::string& input_res = "color",
        const std::string& output_res = "color",
        const std::string& pass_name = "DebugGeometry"
    );

    void execute(ExecuteContext& ctx) override;
    std::set<const char*> compute_reads() const override;
    std::set<const char*> compute_writes() const override;
    std::vector<std::pair<std::string, std::string>> get_inplace_aliases() const override;
};

} // namespace termin
