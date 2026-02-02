// grayscale_pass.hpp - Simple grayscale post-processing pass
#pragma once

#include "termin/render/frame_pass.hpp"
#include "termin/render/tc_shader_handle.hpp"
#include "tc_inspect_cpp.hpp"

namespace termin {

// GrayscalePass - converts image to grayscale with adjustable strength
class GrayscalePass : public CxxFramePass {
public:
    std::string input_res = "color";
    std::string output_res = "color";
    float strength = 1.0f;

private:
    TcShader shader_;

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
};

} // namespace termin
