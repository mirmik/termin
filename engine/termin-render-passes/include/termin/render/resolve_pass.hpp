// resolve_pass.hpp - MSAA resolve pass
#pragma once

#include "tc_inspect_cpp.hpp"
#include "termin/render/frame_pass.hpp"
#include "termin/render_passes/export.h"

#include <string>
#include <utility>

namespace termin {

    // ResolvePass resolves an MSAA color resource into a single-sample color
    // resource through the backend transfer/resolve path.
    class TERMIN_RENDER_PASSES_API ResolvePass : public CxxFramePass {
    public:
        std::string input_res = "color";
        std::string output_res = "resolved";
        std::string output_res_target;
        static void register_type();

    public:
        INSPECT_FIELD(ResolvePass, input_res, "Input Resource", "string")
        INSPECT_FIELD(ResolvePass, output_res, "Output Resource", "string")
        INSPECT_FIELD(ResolvePass, output_res_target, "Output Target", "string")
        INSPECT_TYPE_METADATA(ResolvePass,
                              graph,
                              make_pass_graph_metadata({{"input_res", "fbo"}, {"output_res_target", "fbo"}},
                                                       {{"output_res", "fbo"}},
                                                       {{"output_res_target", "output_res"}}))

        ResolvePass(const std::string& input = "color", const std::string& output = "resolved");

        std::set<const char*> compute_reads() const override;
        std::set<const char*> compute_writes() const override;

        std::vector<std::pair<std::string, std::string>> get_inplace_aliases() const override;

        void execute(ExecuteContext& ctx) override;
        bool get_raster_resolve_contract(ExecuteContext& ctx,
                                         tc_raster_resolve_contract& out_contract) const override;
        void destroy() override;
    };

    class TERMIN_RENDER_PASSES_API MultiviewResolvePass final : public CxxFramePass {
    public:
        std::string input_res = "color";
        std::string output_res = "resolved";
        std::string output_res_target;

        static void register_type();
        INSPECT_FIELD(MultiviewResolvePass, input_res, "Input Resource", "string")
        INSPECT_FIELD(MultiviewResolvePass, output_res, "Output Resource", "string")
        INSPECT_FIELD(MultiviewResolvePass, output_res_target, "Output Target", "string")
        INSPECT_TYPE_METADATA(MultiviewResolvePass,
                              graph,
                              make_pass_graph_metadata({{"input_res", "multiview_fbo"},
                                                        {"output_res_target", "multiview_fbo"}},
                                                       {{"output_res", "multiview_fbo"}},
                                                       {{"output_res_target", "output_res"}}))

        MultiviewResolvePass(const std::string& input = "color", const std::string& output = "resolved");

        std::set<const char*> compute_reads() const override;
        std::set<const char*> compute_writes() const override;
        std::vector<std::pair<std::string, std::string>> get_inplace_aliases() const override;
        void execute(ExecuteContext& ctx) override;
        bool get_raster_resolve_contract(ExecuteContext& ctx,
                                         tc_raster_resolve_contract& out_contract) const override;
    };

} // namespace termin
