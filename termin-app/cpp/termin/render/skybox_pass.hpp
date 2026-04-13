// skybox_pass.hpp - tgfx2-native skybox rendering.
//
// Stage 4 of the tgfx2 migration. The skybox is the first full-stack
// material-style pass going through RenderContext2 + bind_material_ubo:
// a hand-written MaterialUboLayout carries per-frame camera matrices plus
// skybox colors, packed via std140_pack and bound via the ResourceSet API
// added in Stage 1.
#pragma once

#include "termin/render/frame_pass.hpp"
#include "tgfx2/handles.hpp"
#include "tc_inspect_cpp.hpp"

#include <string>

namespace tgfx2 { class IRenderDevice; }

namespace termin {

class SkyBoxPass : public CxxFramePass {
public:
    std::string input_res = "empty";
    std::string output_res = "color";

private:
    // tgfx2 resources, all created lazily on first execute when the device
    // becomes reachable through ExecuteContext::ctx2. Destroyed in destroy().
    tgfx2::IRenderDevice* device2_ = nullptr;
    tgfx2::ShaderHandle vs_;
    tgfx2::ShaderHandle fs_gradient_;
    tgfx2::ShaderHandle fs_solid_;
    tgfx2::BufferHandle cube_vbo_;
    tgfx2::BufferHandle cube_ibo_;
    tgfx2::BufferHandle params_ubo_;

public:
    INSPECT_FIELD(SkyBoxPass, input_res, "Input", "string")
    INSPECT_FIELD(SkyBoxPass, output_res, "Output", "string")

    SkyBoxPass(
        const std::string& input = "empty",
        const std::string& output = "color",
        const std::string& pass_name = "Skybox"
    );

    std::set<const char*> compute_reads() const override;
    std::set<const char*> compute_writes() const override;

    std::vector<std::pair<std::string, std::string>> get_inplace_aliases() const override {
        return {{input_res, output_res}};
    }

    std::vector<ResourceSpec> get_resource_specs() const override;

    void execute(ExecuteContext& ctx) override;
    void destroy() override;

private:
    void ensure_resources(ExecuteContext& ctx);
};

} // namespace termin
