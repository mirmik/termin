#include <termin/lighting/shadow.hpp>
#include <termin/render/color_pass.hpp>
#include <termin/render/present_pass.hpp>
#include <termin/render/resolve_pass.hpp>
#include <termin/render_passes/bootstrap.hpp>

namespace termin {

    void register_builtin_render_passes() {
        (void)register_shadow_map_array_resource_type();
        ColorPass::register_type();
        PresentToScreenPass::register_type();
        BlitPass::register_type();
        ResolvePass::register_type();
    }

} // namespace termin
