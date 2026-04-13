// grayscale_pass.hpp - Simple grayscale post-processing pass
#pragma once

#include "termin/render/frame_pass.hpp"
#include <tgfx/tgfx_shader_handle.hpp>
#include "tgfx2/handles.hpp"
#include "tc_inspect_cpp.hpp"

namespace tgfx2 { class IRenderDevice; }

namespace termin {

// GrayscalePass - converts image to grayscale with adjustable strength.
//
// Dual-path during the tgfx2 migration:
//   - If ExecuteContext::ctx2 is non-null, the pass draws through
//     tgfx2::RenderContext2 end-to-end: built-in FSQ, std140 UBO for
//     parameters bound via bind_uniform_buffer, input texture bound via
//     bind_sampled_texture. No raw GL calls.
//   - Otherwise the legacy tgfx path is used (GraphicsBackend + TcShader).
class GrayscalePass : public CxxFramePass {
public:
    std::string input_res = "color";
    std::string output_res = "color";
    float strength = 1.0f;

private:
    // Legacy tgfx shader (used on the legacy path).
    TcShader shader_;

    // tgfx2 resources (used on the ctx2 path). Created lazily on first
    // execute. Destroyed in destroy() via device2_ if that pointer was
    // captured — otherwise leaked until device shutdown.
    tgfx2::IRenderDevice* device2_ = nullptr;
    tgfx2::ShaderHandle fs2_;
    tgfx2::BufferHandle params_ubo_;
    float uploaded_strength_ = -1.0f;

public:
    INSPECT_FIELD(GrayscalePass, input_res, "Input", "string")
    INSPECT_FIELD(GrayscalePass, output_res, "Output", "string")
    INSPECT_FIELD_RANGE(GrayscalePass, strength, "Strength", "float", 0.0f, 1.0f)

    GrayscalePass(
        const std::string& input = "color",
        const std::string& output = "color",
        float strength = 1.0f
    );

    std::set<const char*> compute_reads() const override;
    std::set<const char*> compute_writes() const override;

    std::vector<std::pair<std::string, std::string>> get_inplace_aliases() const override {
        return {};
    }

    void execute(ExecuteContext& ctx) override;
    void destroy() override;

private:
    void ensure_shader();
    void execute_legacy(ExecuteContext& ctx);
    void execute_tgfx2(ExecuteContext& ctx);
};

} // namespace termin
