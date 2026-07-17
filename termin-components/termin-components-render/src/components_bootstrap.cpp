#include <termin/render/components_bootstrap.hpp>

#include <termin/camera/camera_component.hpp>
#include <termin/camera/orbit_camera_controller.hpp>
#include <termin/lighting/light_component.hpp>
#include <termin/render/line_renderer.hpp>
#include <termin/render/material_pass.hpp>
#include <termin/render/depth_pass.hpp>
#include <termin/render/normal_pass.hpp>
#include <termin/render/mesh_renderer.hpp>
#include <termin/render/skinned_mesh_renderer.hpp>
#include <termin/render/world_text_component.hpp>
#include <termin/xr/xr_origin_component.hpp>
#include <termin/xr/xr_thumbstick_locomotion_component.hpp>

namespace termin {

void register_builtin_render_component_types() {
    CameraComponent::register_type();
    OrbitCameraController::register_type();
    LightComponent::register_type();
    MeshRenderer::register_type();
    SkinnedMeshRenderer::register_type();
    LineRenderer::register_type();
    WorldTextComponent::register_type();
    XrOriginComponent::register_type();
    XrThumbstickLocomotionComponent::register_type();
}

void register_builtin_render_component_pass_types() {
    GeometryPassBase::register_type();
    MaterialPass::register_type();
    DepthPass::register_type();
    DepthOnlyPass::register_type();
    DepthToColorPass::register_type();
    ColorToDepthPass::register_type();
    NormalPass::register_type();
}

} // namespace termin
