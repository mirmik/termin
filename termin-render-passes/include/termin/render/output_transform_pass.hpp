#pragma once

#include "tc_inspect_cpp.hpp"
#include "termin/render/frame_pass.hpp"
#include "termin/render_passes/export.h"
#include "tgfx2/handles.hpp"
extern "C" {
#include <tgfx/resources/tc_shader_registry.h>
}

namespace tgfx {
    class IRenderDevice;
}

namespace termin {

    // Final display transform. The input is linear display-referred color;
    // the output is encoded with the sRGB OETF for an UNORM display target.
    class TERMIN_RENDER_PASSES_API OutputTransformPass final : public CxxFramePass {
    public:
        std::string input_res = "color";
        std::string output_res = "OUTPUT";

    private:
        tgfx::IRenderDevice* device2_ = nullptr;
        tc_shader_handle shader_handle_ = tc_shader_handle_invalid();

    public:
        static void register_type();

        INSPECT_FIELD(OutputTransformPass, input_res, "Input Resource", "string")
        INSPECT_FIELD(OutputTransformPass, output_res, "Output Resource", "string")
        INSPECT_TYPE_METADATA(OutputTransformPass,
                              graph,
                              make_pass_graph_metadata({{"input_res", "fbo"}}, {}, {}))

        OutputTransformPass(const std::string& input = "color", const std::string& output = "OUTPUT");

        std::set<const char*> compute_reads() const override;
        std::set<const char*> compute_writes() const override;
        std::vector<std::pair<std::string, std::string>> get_inplace_aliases() const override {
            return {};
        }

        void execute(ExecuteContext& ctx) override;
        void destroy() override;
    };

} // namespace termin
