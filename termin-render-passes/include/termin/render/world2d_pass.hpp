#pragma once

#include <set>
#include <string>
#include <utility>
#include <vector>

#include <tc_inspect_cpp.hpp>
#include <termin/render/frame_pass.hpp>
#include <termin/render_passes/export.h>
#include <tgfx/resources/tc_shader_registry.h>
#include <tgfx2/handles.hpp>

namespace tgfx {
class IRenderDevice;
}

namespace termin {

class TERMIN_RENDER_PASSES_API World2DPass : public CxxFramePass {
public:
    std::string input_res = "color";
    std::string output_res = "color_world2d";

private:
    tgfx::IRenderDevice* device_ = nullptr;
    tc_shader_handle shader_handle_ = tc_shader_handle_invalid();
    tgfx::SamplerHandle linear_sampler_{};
    tgfx::SamplerHandle nearest_sampler_{};

    void ensure_resources(tgfx::IRenderDevice& device);
    void release_resources();

public:
    static void register_type();

    INSPECT_FIELD(World2DPass, input_res, "Input Resource", "string")
    INSPECT_FIELD(World2DPass, output_res, "Output Resource", "string")
    INSPECT_TYPE_METADATA(World2DPass, graph, make_pass_graph_metadata(
        {{"input_res", "fbo"}},
        {{"output_res", "fbo"}},
        {{"input_res", "output_res"}}
    ))

    World2DPass(
        const std::string& input = "color",
        const std::string& output = "color_world2d");
    ~World2DPass() override;

    std::set<const char*> compute_reads() const override;
    std::set<const char*> compute_writes() const override;
    std::vector<std::pair<std::string, std::string>> get_inplace_aliases() const override;
    void execute(ExecuteContext& ctx) override;
    void destroy() override;
};

} // namespace termin
