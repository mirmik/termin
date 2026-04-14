#pragma once

#include "termin/render/frame_pass.hpp"
#include "termin/render/execute_context.hpp"
#include <tgfx/tgfx_shader_handle.hpp>

namespace termin {

/**
 * GroundGridPass - Renders an infinite ground grid on the z=0 plane.
 *
 * Draws a fullscreen quad with a procedural shader that ray-intersects
 * the z=0 plane and generates grid lines with two LOD levels (1m and 10m).
 * Includes colored axis highlights (X=red, Y=green) and distance fade-out.
 * Writes gl_FragDepth for correct depth integration with scene geometry.
 *
 * Goes through tgfx2::RenderContext2 end-to-end.
 */
class GroundGridPass : public CxxFramePass {
public:
    std::string input_res = "color";
    std::string output_res = "color";

    GroundGridPass(
        const std::string& input_res = "color",
        const std::string& output_res = "color",
        const std::string& pass_name = "GroundGrid"
    );
    virtual ~GroundGridPass() = default;

    void execute(ExecuteContext& ctx) override;
    std::set<const char*> compute_reads() const override;
    std::set<const char*> compute_writes() const override;
    std::vector<std::pair<std::string, std::string>> get_inplace_aliases() const override;

private:
    // TcShader kept as the compile source — tc_shader_ensure_tgfx2
    // bridges it to a tgfx2::ShaderHandle pair on first execute. We do
    // not call TcShader::use / set_uniform_* directly any more.
    TcShader _shader;
    void _ensure_shader();
};

} // namespace termin
