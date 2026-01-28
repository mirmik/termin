#pragma once

#include "termin/render/frame_pass.hpp"

namespace termin {

// PresentToScreenPass - copies input FBO to output FBO via blit.
// Does NOT use inplace aliases, so breaks inplace chains.
// Use this to copy rendered content to OUTPUT/DISPLAY.
class PresentToScreenPass : public CxxFramePass {
public:
    std::string input_res = "color";
    std::string output_res = "OUTPUT";

    PresentToScreenPass(
        const std::string& input = "color",
        const std::string& output = "OUTPUT"
    );

    std::set<const char*> compute_reads() const override;
    std::set<const char*> compute_writes() const override;

    // No inplace aliases - this breaks the chain
    std::vector<std::pair<std::string, std::string>> get_inplace_aliases() const override {
        return {};
    }

    void execute(ExecuteContext& ctx) override;
};

} // namespace termin
