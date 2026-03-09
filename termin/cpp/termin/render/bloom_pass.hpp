// bloom_pass.hpp - HDR bloom post-processing pass
//
// Uses progressive downsampling/upsampling for wide, high-quality bloom.
// Based on the approach used in Unreal Engine and Unity.
#pragma once

#include "termin/render/frame_pass.hpp"
#include "termin/render/tc_shader_handle.hpp"
#include "tc_inspect_cpp.hpp"

#include <vector>
#include <memory>

namespace termin {

// BloomPass - HDR bloom with mip-chain downsampling/upsampling
class BloomPass : public CxxFramePass {
public:
    std::string input_res = "color";
    std::string output_res = "color";
    float threshold = 1.0f;
    float soft_threshold = 0.5f;
    float intensity = 1.0f;
    int mip_levels = 5;

private:
    // Internal mip chain FBOs
    std::vector<FramebufferHandlePtr> mip_fbos_;

    // Lazy-loaded shaders
    TcShader bright_shader_;
    TcShader downsample_shader_;
    TcShader upsample_shader_;
    TcShader composite_shader_;

    // Last known size for FBO recreation
    int last_width_ = 0;
    int last_height_ = 0;
    int last_mip_levels_ = 0;

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
    void ensure_shaders();
    void ensure_mip_fbos(GraphicsBackend* graphics, int width, int height);
};

} // namespace termin
