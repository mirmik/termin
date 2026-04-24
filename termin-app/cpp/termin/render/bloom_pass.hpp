// bloom_pass.hpp - HDR bloom post-processing pass
//
// Uses progressive downsampling/upsampling for wide, high-quality bloom.
// Based on the approach used in Unreal Engine and Unity.
#pragma once

#include "termin/render/frame_pass.hpp"
#include "tgfx2/handles.hpp"
#include "tc_inspect_cpp.hpp"

#include <vector>
#include <memory>

namespace tgfx { class IRenderDevice; }

namespace termin {

// BloomPass - HDR bloom with mip-chain downsampling/upsampling.
// Draws through tgfx::RenderContext2 end-to-end (four sub-passes:
// bright, downsample chain, upsample chain, composite). Legacy tgfx1
// dual-path removed in Stage 8.1.
class BloomPass : public CxxFramePass {
public:
    std::string input_res = "color";
    std::string output_res = "color";
    float threshold = 1.0f;
    float soft_threshold = 0.5f;
    float intensity = 1.0f;
    int mip_levels = 5;

private:
    // tgfx2 resources — persistent across frames, rebuilt on resize.
    tgfx::IRenderDevice* device2_ = nullptr;
    std::vector<tgfx::TextureHandle> mip_textures_;
    tgfx::ShaderHandle bright_fs2_;
    tgfx::ShaderHandle downsample_fs2_;
    tgfx::ShaderHandle upsample_fs2_;
    tgfx::ShaderHandle composite_fs2_;
    tgfx::BufferHandle bright_ubo_;
    tgfx::BufferHandle downsample_ubo_;
    tgfx::BufferHandle upsample_ubo_;
    tgfx::BufferHandle composite_ubo_;

    int last_tgfx2_width_ = 0;
    int last_tgfx2_height_ = 0;
    int last_tgfx2_mip_levels_ = 0;

public:
    INSPECT_FIELD(BloomPass, input_res, "Input", "string")
    INSPECT_FIELD(BloomPass, output_res, "Output", "string")
    INSPECT_FIELD_RANGE(BloomPass, threshold, "Threshold", "float", 0.0f, 10.0f)
    INSPECT_FIELD_RANGE(BloomPass, soft_threshold, "Soft Knee", "float", 0.0f, 1.0f)
    INSPECT_FIELD_RANGE(BloomPass, intensity, "Intensity", "float", 0.0f, 5.0f)
    INSPECT_FIELD_RANGE(BloomPass, mip_levels, "Mip Levels", "int", 1, 8)

    BloomPass(
        const std::string& input = "color",
        const std::string& output = "color",
        float threshold = 1.0f,
        float soft_threshold = 0.5f,
        float intensity = 1.0f,
        int mip_levels = 5
    );

    std::set<const char*> compute_reads() const override;
    std::set<const char*> compute_writes() const override;

    std::vector<std::pair<std::string, std::string>> get_inplace_aliases() const override {
        return {};
    }

    void execute(ExecuteContext& ctx) override;
    void destroy() override;

private:
    void ensure_tgfx2_shaders();
    void ensure_tgfx2_mip_textures(int width, int height);
    void destroy_tgfx2_mip_textures();
};

} // namespace termin
