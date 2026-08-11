#include <termin/lighting/shadow.hpp>
#include <termin/lighting/environment_lighting.hpp>
#include <termin/render/bloom_pass.hpp>
#include <termin/render/color_pass.hpp>
#include <termin/render/debug_geometry_pass.hpp>
#include <termin/render/debug_triangle_pass.hpp>
#include <termin/render/grayscale_pass.hpp>
#include <termin/render/ground_grid_pass.hpp>
#include <termin/render/id_pass.hpp>
#include <termin/render/present_pass.hpp>
#include <termin/render/resolve_pass.hpp>
#include <termin/render/shadow_pass.hpp>
#include <termin/render/skybox_pass.hpp>
#include <termin/render/standard_gbuffer_pass.hpp>
#include <termin/render/tonemap_pass.hpp>
#include <termin/render/ui_widget_pass.hpp>
#include <termin/render/world2d_pass.hpp>
#include <termin/render_passes/bootstrap.hpp>

namespace termin {

    void register_builtin_render_passes() {
        (void)register_shadow_map_array_resource_type();
        (void)register_environment_lighting_resource_type();
        BloomPass::register_type();
        ColorPass::register_type();
        MultiviewColorPass::register_type();
        DebugTrianglePass::register_type();
        DebugGeometryPass::register_type();
        EnvironmentLightingPass::register_type();
        GrayscalePass::register_type();
        GroundGridPass::register_type();
        IdPass::register_type();
        PresentToScreenPass::register_type();
        BlitPass::register_type();
        ResolvePass::register_type();
        MultiviewResolvePass::register_type();
        ShadowPass::register_type();
        SkyBoxPass::register_type();
        StandardGBufferPass::register_type();
        TonemapPass::register_type();
        MultiviewTonemapPass::register_type();
        World2DPass::register_type();
        UIWidgetPass::register_type();
    }

} // namespace termin
