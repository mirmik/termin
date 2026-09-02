#include <termin/lighting/environment_lighting.hpp>
#include <termin/lighting/shadow.hpp>
#include <termin/render/color_pass.hpp>
#include <termin/render/present_pass.hpp>
#include <termin/render/resolve_pass.hpp>
#include <termin/render/skybox_pass.hpp>
#include <termin/render/standard_gbuffer_pass.hpp>
#include <termin/render/tonemap_pass.hpp>
#include <termin/render_passes/bootstrap.hpp>

namespace termin {

    void register_builtin_render_passes() {
        (void)register_shadow_map_array_resource_type();
        (void)register_environment_lighting_resource_type();
        ColorPass::register_type();
        EnvironmentLightingPass::register_type();
        PresentToScreenPass::register_type();
        BlitPass::register_type();
        ResolvePass::register_type();
        SkyBoxPass::register_type();
        StandardGBufferPass::register_type();
        TonemapPass::register_type();
    }

} // namespace termin
