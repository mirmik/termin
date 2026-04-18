#pragma once

#include "termin/render/frame_pass.hpp"
#include "termin/render/execute_context.hpp"
#include "tgfx2/handles.hpp"

namespace tgfx { class IRenderDevice; }

namespace termin {

/**
 * GroundGridPass - Renders an infinite ground grid on the z=0 plane.
 *
 * Draws a fullscreen quad with a procedural shader that ray-intersects
 * the z=0 plane and generates grid lines with two LOD levels (1m and 10m).
 * Includes colored axis highlights (X=red, Y=green) and distance fade-out.
 * Writes gl_FragDepth for correct depth integration with scene geometry.
 *
 * Goes through tgfx::RenderContext2 end-to-end.
 */
class GroundGridPass : public CxxFramePass {
public:
    std::string input_res = "color";
    std::string output_res = "color";

private:
    // Cached tgfx2 resources. Parameters don't fit the 128-byte
    // push-constant guarantee (3 mat4 + 2 float = 200 bytes padded to
    // 208), so everything lives in a std140 UBO at binding 0.
    tgfx::IRenderDevice* _device = nullptr;
    tgfx::ShaderHandle _vs;
    tgfx::ShaderHandle _fs;
    tgfx::BufferHandle _params_ubo;

public:
    GroundGridPass(
        const std::string& input_res = "color",
        const std::string& output_res = "color",
        const std::string& pass_name = "GroundGrid"
    );
    virtual ~GroundGridPass();

    void execute(ExecuteContext& ctx) override;
    std::set<const char*> compute_reads() const override;
    std::set<const char*> compute_writes() const override;
    std::vector<std::pair<std::string, std::string>> get_inplace_aliases() const override;

private:
    void _ensure_resources(tgfx::IRenderDevice* device);
};

} // namespace termin
