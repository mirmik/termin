// tonemap_pass.hpp - HDR to LDR tonemapping post-processing pass
#pragma once

#include "termin/render/frame_pass.hpp"
#include "termin/render/tc_shader_handle.hpp"
#include "tc_inspect_cpp.hpp"

namespace termin {

// Tonemapping methods
enum class TonemapMethod : int {
    ACES = 0,
    REINHARD = 1,
    NONE = 2
};

// TonemapPass - converts HDR to displayable LDR range
class TonemapPass : public CxxFramePass {
public:
    std::string input_res = "color";
    std::string output_res = "color";
    float exposure = 1.0f;
    int method = 0;  // TonemapMethod::ACES

private:
    TcShader shader_;

public:
    INSPECT_FIELD(TonemapPass, input_res, "Input", "string")
    INSPECT_FIELD(TonemapPass, output_res, "Output", "string")
    INSPECT_FIELD_RANGE(TonemapPass, exposure, "Exposure", "float", 0.1f, 10.0f)
    INSPECT_FIELD_RANGE(TonemapPass, method, "Method", "int", 0, 2)

    TonemapPass(
        const std::string& input = "color",
        const std::string& output = "color",
        float exposure = 1.0f,
        int method = 0
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
