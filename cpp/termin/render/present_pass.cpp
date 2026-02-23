#include "present_pass.hpp"
#include "termin/render/execute_context.hpp"
#include "tgfx/graphics_backend.hpp"
#include "tc_log.hpp"

namespace termin {

PresentToScreenPass::PresentToScreenPass(
    const std::string& input,
    const std::string& output
) : input_res(input), output_res(output) {
    pass_name_set("PresentToScreen");
    link_to_type_registry("PresentToScreenPass");
}

std::set<const char*> PresentToScreenPass::compute_reads() const {
    return {input_res.c_str()};
}

std::set<const char*> PresentToScreenPass::compute_writes() const {
    return {output_res.c_str()};
}

void PresentToScreenPass::execute(ExecuteContext& ctx) {
    auto* fb_in = ctx.reads_fbos.find(input_res) != ctx.reads_fbos.end()
        ? dynamic_cast<FramebufferHandle*>(ctx.reads_fbos[input_res])
        : nullptr;
    auto* fb_out = ctx.writes_fbos.find(output_res) != ctx.writes_fbos.end()
        ? dynamic_cast<FramebufferHandle*>(ctx.writes_fbos[output_res])
        : nullptr;

    if (!fb_in || !fb_out) {
        tc::Log::warn("[PresentToScreenPass] Missing FBO: input=%p output=%p",
            (void*)fb_in, (void*)fb_out);
        return;
    }

    int src_w = fb_in->get_width();
    int src_h = fb_in->get_height();

    // Blit from input to output
    ctx.graphics->blit_framebuffer(
        fb_in,
        fb_out,
        0, 0, src_w, src_h,
        ctx.rect.x, ctx.rect.y, ctx.rect.x + ctx.rect.width, ctx.rect.y + ctx.rect.height,
        true,   // blit color
        false   // don't blit depth
    );
}

TC_REGISTER_FRAME_PASS(PresentToScreenPass);

} // namespace termin
