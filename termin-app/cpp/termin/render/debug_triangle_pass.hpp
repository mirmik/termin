// debug_triangle_pass.hpp - Built-in pass that draws a diagnostic triangle.
#pragma once

#include "termin/render/frame_pass.hpp"
#include "tc_inspect_cpp.hpp"

extern "C" {
#include <tgfx/resources/tc_shader_registry.h>
}

namespace tgfx { class IRenderDevice; }

namespace termin {

class DebugTrianglePass : public CxxFramePass {
public:
    std::string output_res = "OUTPUT";

private:
    tgfx::IRenderDevice* device2_ = nullptr;
    tc_shader_handle shader_handle_ = tc_shader_handle_invalid();

public:
    INSPECT_FIELD(DebugTrianglePass, output_res, "Output Resource", "string")

    explicit DebugTrianglePass(
        const std::string& output = "OUTPUT",
        const std::string& pass_name = "DebugTriangle"
    );

    std::set<const char*> compute_reads() const override;
    std::set<const char*> compute_writes() const override;

    std::vector<std::pair<std::string, std::string>> get_inplace_aliases() const override {
        return {};
    }

    void execute(ExecuteContext& ctx) override;
    void destroy() override;
};

} // namespace termin
