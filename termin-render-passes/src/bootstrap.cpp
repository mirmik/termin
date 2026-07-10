#include <termin/render_passes/bootstrap.hpp>
#include <termin/render/bloom_pass.hpp>
#include <termin/render/collider_gizmo_pass.hpp>
#include <termin/render/color_pass.hpp>
#include <termin/render/debug_triangle_pass.hpp>
#include <termin/render/grayscale_pass.hpp>
#include <termin/render/ground_grid_pass.hpp>
#include <termin/render/id_pass.hpp>
#include <termin/render/present_pass.hpp>
#include <termin/render/resolve_pass.hpp>
#include <termin/render/shadow_pass.hpp>
#include <termin/render/skybox_pass.hpp>
#include <termin/render/tonemap_pass.hpp>
#include <termin/render/ui_widget_pass.hpp>

namespace termin {

void register_builtin_render_passes() {
    BloomPass::register_type();
    ColliderGizmoPass::register_type();
    ColorPass::register_type();
    DebugTrianglePass::register_type();
    GrayscalePass::register_type();
    GroundGridPass::register_type();
    IdPass::register_type();
    PresentToScreenPass::register_type();
    BlitPass::register_type();
    ResolvePass::register_type();
    ShadowPass::register_type();
    SkyBoxPass::register_type();
    TonemapPass::register_type();
#if defined(__ANDROID__)
    UIWidgetPass::register_type();
#endif
}

} // namespace termin
