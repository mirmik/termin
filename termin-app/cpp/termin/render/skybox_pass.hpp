// skybox_pass.hpp - tgfx2-native skybox rendering.
//
// Stage 5.I: driven entirely by the tgfx2 material UBO path. The shader
// text is a @program .shader string parsed at ensure_resources time, the
// parser auto-generates the std140 MaterialParams layout from @property
// entries, and values (camera matrices + colors + variant selector) are
// packed each frame and bound via bind_material_ubo. No hand-coded layout,
// no gradient/solid shader split — a single fragment shader branches on
// the u_skybox_type @property.
#pragma once

#include "termin/render/frame_pass.hpp"
#include "termin/render/shader_parser.hpp"
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
    tgfx2::ShaderHandle fs_;
    tgfx2::BufferHandle cube_vbo_;
    tgfx2::BufferHandle cube_ibo_;
    tgfx2::BufferHandle params_ubo_;

    // Parsed from SKYBOX_SHADER_TEXT at ensure_resources time — layout
    // drives std140_pack and the UBO block_size. No hand-coded duplicate.
    MaterialUboLayout skybox_layout_;

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
