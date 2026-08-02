#include <termin/render_passes/bootstrap.hpp>
#include <termin/render/color_pass.hpp>
#include <termin/render/present_pass.hpp>
#include <termin/render/resolve_pass.hpp>

namespace termin {

void register_builtin_render_passes() {
    ColorPass::register_type();
    PresentToScreenPass::register_type();
    BlitPass::register_type();
    ResolvePass::register_type();
}

} // namespace termin
